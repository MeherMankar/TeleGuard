"""Transfer Ownership Handler - Transfer accounts to another user"""
import logging
from telethon import Button, events
from ..core.mongo_database import mongodb
from bson import ObjectId

logger = logging.getLogger(__name__)

class TransferOwnershipHandler:
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.pending_transfers = {}
        self.pending_coowner = {}
    
    def register_handlers(self):
        """Register transfer ownership and co-owner commands"""
        
        @self.bot.on(events.NewMessage(pattern=r"/addcoowner"))
        async def addcoowner_command(event):
            user_id = event.sender_id
            try:
                accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
                if not accounts:
                    await event.reply("No accounts found. Add accounts first.")
                    return
                
                self.pending_coowner[user_id] = None
                await event.reply(
                    f"Add Co-Owner\n\n"
                    f"You have {len(accounts)} account(s)\n\n"
                    f"Reply with user ID or username:\n"
                    f"Examples: 123456789 or @username\n\n"
                    f"Note: Co-owner will have access to ALL current and future accounts!"
                )
            except Exception as e:
                logger.error(f"Add co-owner error: {e}")
                await event.reply(f"Error: {str(e)}")
        
        @self.bot.on(events.NewMessage(pattern=r"/transfer"))
        async def transfer_command(event):
            user_id = event.sender_id
            try:
                accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
                if not accounts:
                    await event.reply("No accounts found to transfer.")
                    return
                
                self.pending_transfers[user_id] = {"selected_accounts": [], "target_user": None}
                
                buttons = []
                for account in accounts:
                    name = account.get('name', 'Unknown')
                    phone = account.get('phone', 'Unknown')
                    buttons.append([Button.inline(f"Select {name} ({phone})", f"transfer_toggle:{account['_id']}")])
                
                buttons.append([Button.inline("Select All", "transfer_select_all")])
                buttons.append([Button.inline("Done", "transfer_done")])
                buttons.append([Button.inline("Cancel", "transfer_cancel")])
                
                await event.reply(f"Transfer Ownership\n\nYou have {len(accounts)} account(s)\nSelect accounts to transfer:", buttons=buttons)
            except Exception as e:
                logger.error(f"Transfer error: {e}")
                await event.reply(f"Error: {str(e)}")
        
        @self.bot.on(events.CallbackQuery(pattern=r"^transfer_toggle:(.+)$"))
        async def toggle_account(event):
            user_id = event.sender_id
            account_id = event.pattern_match.group(1).decode()
            
            if user_id not in self.pending_transfers:
                await event.answer("Session expired. Use /transfer again.")
                return
            
            selected = self.pending_transfers[user_id]["selected_accounts"]
            if account_id in selected:
                selected.remove(account_id)
            else:
                selected.append(account_id)
            
            await self._update_selection_menu(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^transfer_select_all$"))
        async def select_all(event):
            user_id = event.sender_id
            if user_id not in self.pending_transfers:
                await event.answer("Session expired.")
                return
            
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            self.pending_transfers[user_id]["selected_accounts"] = [str(acc['_id']) for acc in accounts]
            await self._update_selection_menu(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^transfer_done$"))
        async def done_selection(event):
            user_id = event.sender_id
            if user_id not in self.pending_transfers:
                await event.answer("Session expired.")
                return
            
            selected = self.pending_transfers[user_id]["selected_accounts"]
            if not selected:
                await event.answer("No accounts selected!", alert=True)
                return
            
            await event.edit(f"Selected: {len(selected)} account(s)\n\nReply with user ID or username:")
            await event.answer("Reply with user ID or username")
        
        @self.bot.on(events.CallbackQuery(pattern=r"^transfer_cancel$"))
        async def cancel_transfer(event):
            user_id = event.sender_id
            if user_id in self.pending_transfers:
                del self.pending_transfers[user_id]
            await event.edit("Transfer cancelled.")
        
        @self.bot.on(events.CallbackQuery(pattern=r"^coowner_cancel$"))
        async def cancel_coowner(event):
            user_id = event.sender_id
            if user_id in self.pending_coowner:
                del self.pending_coowner[user_id]
            await event.edit("Co-owner addition cancelled.")
    
    async def _update_selection_menu(self, event, user_id: int):
        """Update account selection menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            selected = self.pending_transfers[user_id]["selected_accounts"]
            
            buttons = []
            for account in accounts:
                name = account.get('name', 'Unknown')
                phone = account.get('phone', 'Unknown')
                icon = "✓" if str(account['_id']) in selected else " "
                buttons.append([Button.inline(f"[{icon}] {name} ({phone})", f"transfer_toggle:{account['_id']}")])
            
            buttons.append([Button.inline("Select All", "transfer_select_all")])
            buttons.append([Button.inline("Done", "transfer_done")])
            buttons.append([Button.inline("Cancel", "transfer_cancel")])
            
            await event.edit(f"Selected: {len(selected)}/{len(accounts)}\n\nSelect accounts:", buttons=buttons)
            await event.answer()
        except Exception as e:
            logger.error(f"Update menu error: {e}")
