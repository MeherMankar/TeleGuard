"""Group management handler"""
import logging
from telethon import events, Button
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty, Channel
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class GroupManager:
    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager
        self.user_clients = bot_manager.user_clients
    
    def register_handlers(self):
        """Register group management handlers"""
        self.bot.add_event_handler(
            self._show_group_menu,
            events.CallbackQuery(pattern=r"^group_manager$")
        )
        self.bot.add_event_handler(
            self._list_groups,
            events.CallbackQuery(pattern=r"^group_list:(.+)$")
        )
        self.bot.add_event_handler(
            self._leave_group,
            events.CallbackQuery(pattern=r"^group_leave:(.+):(.+)$")
        )
        logger.info("Group manager handlers registered")
    
    async def _show_group_menu(self, event):
        """Show group management menu"""
        user_id = event.sender_id
        
        try:
            accounts = await mongodb.db.accounts.find(
                {"user_id": user_id, "is_active": True}
            ).to_list(length=None)
            
            if not accounts:
                await event.answer("❌ No accounts found", alert=True)
                return
            
            buttons = []
            for acc in accounts:
                name = acc.get('name', acc.get('phone', 'Unknown'))
                buttons.append([Button.inline(f"📱 {name}", f"group_list:{name}")])
            
            buttons.append([Button.inline("🔙 Back", "menu:main")])
            
            await event.edit(
                "👥 **Group Manager**\n\n"
                "Select an account to manage groups:",
                buttons=buttons
            )
        except Exception as e:
            logger.error(f"Group menu error: {e}")
            await event.answer("❌ Error loading menu", alert=True)
    
    async def _list_groups(self, event):
        """List groups for account"""
        user_id = event.sender_id
        account_name = event.pattern_match.group(1).decode()
        
        try:
            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client:
                await event.answer("❌ Account not found", alert=True)
                return
            
            dialogs = await client.get_dialogs(limit=100)
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            
            if not groups:
                await event.edit(
                    f"👥 **Groups - {account_name}**\n\n"
                    "No groups found.",
                    buttons=[[Button.inline("🔙 Back", "group_manager")]]
                )
                return
            
            text = f"👥 **Groups - {account_name}**\n\n"
            buttons = []
            
            for group in groups[:20]:
                title = group.title[:30]
                buttons.append([
                    Button.inline(f"📤 {title}", f"group_leave:{account_name}:{group.id}")
                ])
            
            buttons.append([Button.inline("🔙 Back", "group_manager")])
            
            await event.edit(
                text + f"Found {len(groups)} groups. Select to leave:",
                buttons=buttons
            )
        except Exception as e:
            logger.error(f"List groups error: {e}")
            await event.answer("❌ Error loading groups", alert=True)
    
    async def _leave_group(self, event):
        """Leave a group"""
        user_id = event.sender_id
        account_name = event.pattern_match.group(1).decode()
        group_id = int(event.pattern_match.group(2).decode())
        
        try:
            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client:
                await event.answer("❌ Account not found", alert=True)
                return
            
            await client.delete_dialog(group_id)
            await event.answer("✅ Left group successfully", alert=True)
            await self._list_groups(event)
        except Exception as e:
            logger.error(f"Leave group error: {e}")
            await event.answer(f"❌ Error: {str(e)}", alert=True)
