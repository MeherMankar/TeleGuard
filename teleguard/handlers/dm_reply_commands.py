"""DM Reply command handlers"""

import logging
from telethon import events, Button

logger = logging.getLogger(__name__)


class DMReplyCommands:
    """Handles DM reply configuration commands"""
    
    def __init__(self, bot, bot_manager):
        self.bot = bot
        self.bot_manager = bot_manager
        self.dm_reply_handler = bot_manager.dm_reply_handler
        
    def register_handlers(self):
        """Register command handlers"""
        
        @self.bot.on(events.NewMessage(pattern=r'^/set_dm_group$'))
        async def set_dm_group_command(event):
            if not event.is_private:
                return
                
            user_id = event.sender_id
            
            # Set pending action for group ID input
            self.bot_manager.pending_actions[user_id] = {
                "action": "set_dm_group_id"
            }
            
            await event.reply(
                "📨 **Set DM Reply Group**\n\n"
                "Send me your group ID where you want to receive DM notifications.\n\n"
                "**How to get group ID:**\n"
                "1. Add @userinfobot to your group\n"
                "2. Send any message\n"
                "3. Copy the group ID (negative number)\n"
                "4. Remove @userinfobot from group\n\n"
                "Reply with the group ID:"
            )
        
        @self.bot.on(events.NewMessage(pattern=r'^/dm_status$'))
        async def dm_status_command(event):
            if not event.is_private:
                return
                
            user_id = event.sender_id
            admin_group_id = await self.dm_reply_handler.get_admin_group(user_id)
            
            if admin_group_id:
                status_text = (
                    f"📨 **DM Reply Status**\n\n"
                    f"✅ **Enabled**\n"
                    f"📍 Group ID: `{admin_group_id}`\n\n"
                    f"All DMs to your managed accounts will be forwarded to this group."
                )
                buttons = [
                    [Button.inline("🔄 Change Group", "dm_change_group")],
                    [Button.inline("❌ Disable", "dm_disable")]
                ]
            else:
                status_text = (
                    f"📨 **DM Reply Status**\n\n"
                    f"❌ **Disabled**\n\n"
                    f"Use /set_dm_group to enable DM forwarding."
                )
                buttons = [
                    [Button.inline("✅ Enable", "dm_enable")]
                ]
            
            await event.reply(status_text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"dm_"))
        async def handle_dm_callbacks(event):
            data = event.data.decode('utf-8')
            user_id = event.sender_id
            
            if data == "dm_enable":
                self.bot_manager.pending_actions[user_id] = {
                    "action": "set_dm_group_id"
                }
                await event.edit(
                    "📨 **Enable DM Reply**\n\n"
                    "Send me your group ID where you want to receive DM notifications.\n\n"
                    "**How to get group ID:**\n"
                    "1. Add @userinfobot to your group\n"
                    "2. Send any message\n"
                    "3. Copy the group ID (negative number)\n"
                    "4. Remove @userinfobot from group\n\n"
                    "Reply with the group ID:"
                )
            
            elif data == "dm_change_group":
                self.bot_manager.pending_actions[user_id] = {
                    "action": "set_dm_group_id"
                }
                await event.edit(
                    "📨 **Change DM Reply Group**\n\n"
                    "Send me the new group ID:\n\n"
                    "Reply with the group ID:"
                )
            
            elif data == "dm_disable":
                await self.dm_reply_handler.set_admin_group(user_id, None)
                await event.edit(
                    "📨 **DM Reply Disabled**\n\n"
                    "❌ DM forwarding has been disabled.\n\n"
                    "Use /set_dm_group to enable it again."
                )
    
    async def handle_dm_group_input(self, event, user_id, group_id_text):
        """Handle DM group ID input"""
        try:
            group_id = int(group_id_text.strip())
            
            if group_id > 0:
                await event.reply("❌ Please provide a negative group ID (groups have negative IDs)")
                return
            
            success, message = await self.dm_reply_handler.set_admin_group(user_id, group_id)
            
            if success:
                await event.reply(
                    f"✅ **DM Reply Group Set**\n\n"
                    f"📍 Group ID: `{group_id}`\n\n"
                    f"All DMs to your managed accounts will now be forwarded to this group.\n\n"
                    f"Use /dm_status to check status."
                )
            else:
                await event.reply(f"❌ Failed to set group: {message}")
                
        except ValueError:
            await event.reply("❌ Invalid group ID. Please provide a numeric group ID.")
        except Exception as e:
            logger.error(f"Error setting DM group: {e}")
            await event.reply("❌ An error occurred. Please try again.")