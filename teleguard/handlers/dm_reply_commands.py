"""DM Reply command handlers"""

import logging

from telethon import Button, events

logger = logging.getLogger(__name__)


class DMReplyCommands:
    """Handles DM reply configuration commands"""

    def __init__(self, bot, bot_manager):
        self.bot = bot
        self.bot_manager = bot_manager

    def register_handlers(self):
        """Register command handlers"""

        @self.bot.on(events.NewMessage(pattern=r"^/dm_reply$"))
        async def dm_reply_command(event):
            user_id = event.sender_id
            
            # If in group, set that group as DM reply group
            if not event.is_private:
                from ..core.mongo_database import mongodb
                
                # Check if user has accounts
                accounts = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(None)
                if not accounts:
                    await event.reply("❌ You don't have any active accounts. Add an account first in private chat with the bot.")
                    return
                
                # Check if group has topics enabled
                try:
                    chat = await event.get_chat()
                    is_forum = getattr(chat, "forum", False)
                    if not is_forum:
                        await event.reply(
                            "❌ **Topics Not Enabled**\n\n"
                            "This group doesn't have Topics enabled.\n\n"
                            "**To enable:**\n"
                            "1. Go to Group Settings\n"
                            "2. Enable 'Topics'\n"
                            "3. Try /dm_reply again"
                        )
                        return
                except Exception as e:
                    await event.reply(f"❌ Error checking group: {e}")
                    return
                
                # Show account selection
                from telethon import Button
                buttons = []
                for acc in accounts:
                    acc_name = acc.get('name', 'Unknown')
                    # Sanitize account name for display and callback
                    display_name = acc_name if acc_name and not all(ord(c) > 127 for c in acc_name) else f"Account {acc.get('phone', 'Unknown')}"
                    # Use original name for callback to match database
                    buttons.append([Button.inline(f"📱 {display_name}", f"dm_link:{acc_name}:{event.chat_id}")])
                buttons.append([Button.inline("❌ Cancel", "dm_cancel")])
                
                await event.reply(
                    f"✅ **Group Ready for DM Manager**\n\n"
                    f"📍 Group: {chat.title}\n"
                    f"🆔 ID: `{event.chat_id}`\n\n"
                    f"Select which account's DMs should be forwarded here:",
                    buttons=buttons
                )
                return
            
            # If in private chat, show setup instructions
            await event.reply(
                "⚙️ **DM Manager Setup**\n\n"
                "📋 **Steps:**\n"
                "1. Create a new group\n"
                "2. Enable Topics in group settings\n"
                "3. Add this bot to the group as admin\n"
                "4. In the group, send /dm_reply\n"
                "5. Select which account to link\n\n"
                "💡 All DMs to that account will create topics in the group."
            )
        
        # Alias for backward compatibility
        @self.bot.on(events.NewMessage(pattern=r"^/set_dm_group$"))
        async def set_dm_group_alias(event):
            await dm_reply_command(event)

        @self.bot.on(events.NewMessage(pattern=r"^/dm_status$"))
        async def dm_status_command(event):
            if not event.is_private:
                return
            user_id = event.sender_id
            admin_group_id = (
                await self.bot_manager.unified_messaging._get_user_admin_group(user_id)
            )
            if admin_group_id:
                status_text = (
                    f"📨 **Unified Messaging Status**\n\n"
                    f"✅ **Enabled**\n"
                    f"📍 Group ID: `{admin_group_id}`\n\n"
                    f"All DMs to your managed accounts automatically create topics in this group."
                )
                buttons = [
                    [Button.inline("🔄 Change Group", "dm_change_group")],
                    [Button.inline("❌ Disable", "dm_disable")],
                ]
            else:
                status_text = (
                    f"📨 **Unified Messaging Status**\n\n"
                    f"❌ **Disabled**\n\n"
                    f"Use /set_dm_group to enable automatic topic creation."
                )
                buttons = [[Button.inline("✅ Enable", "dm_enable")]]
            await event.reply(status_text, buttons=buttons)

        @self.bot.on(events.CallbackQuery(pattern=b"dm_"))
        async def handle_dm_callbacks(event):
            data = event.data.decode("utf-8")
            user_id = event.sender_id
            
            if data.startswith("dm_link:"):
                # Format: dm_link:account_name:group_id
                parts = data.split(":", 2)
                if len(parts) != 3:
                    await event.answer("❌ Invalid data", alert=True)
                    return
                
                account_name = parts[1].strip()
                # Handle empty or invisible account names
                if not account_name or account_name.isspace() or all(ord(c) > 127 for c in account_name):
                    await event.answer("❌ Invalid account name", alert=True)
                    return
                
                try:
                    group_id = int(parts[2])
                except ValueError:
                    await event.answer("❌ Invalid group ID", alert=True)
                    return
                
                from ..core.mongo_database import mongodb
                
                # Update account with DM group
                result = await mongodb.db.accounts.update_one(
                    {"user_id": user_id, "name": account_name},
                    {"$set": {"dm_reply_group_id": group_id}}
                )
                
                if result.modified_count > 0 or result.matched_count > 0:
                    await event.edit(
                        f"✅ **DM Manager Configured**\n\n"
                        f"📱 Account: {account_name}\n"
                        f"📍 Group ID: `{group_id}`\n\n"
                        f"🎯 **Active!** All DMs to {account_name} will now create topics here.\n\n"
                        f"**How to reply:**\n"
                        f"• Go to the topic for a conversation\n"
                        f"• Reply to any message in the topic\n"
                        f"• Your reply will be sent from {account_name}"
                    )
                else:
                    await event.answer("❌ Account not found", alert=True)
                return
            
            if data == "dm_cancel":
                await event.edit("❌ Setup cancelled")
                return
            
            if data.startswith("dm_set:"):
                account_name = data.split(":", 1)[1]
                self.bot_manager.pending_actions[user_id] = {
                    "action": "set_dm_group_id",
                    "account_name": account_name
                }
                await event.edit(
                    f"📨 **Set DM Group for {account_name}**\n\n"
                    "Send me your **Forum Group** ID.\n\n"
                    "**Requirements:**\n"
                    "• Group must have Topics enabled\n"
                    "• Bot must be admin with topic management permissions\n\n"
                    "**How to get group ID:**\n"
                    "1. Add @userinfobot to your forum group\n"
                    "2. Send any message\n"
                    "3. Copy the group ID (negative number)\n"
                    "4. Remove @userinfobot from group\n\n"
                    "Reply with the group ID:"
                )
            elif data == "dm_enable":
                from ..core.mongo_database import mongodb
                accounts = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(None)
                if not accounts:
                    await event.edit("❌ No active accounts found.")
                    return
                from telethon import Button
                buttons = [[Button.inline(f"📱 {acc.get('name', 'Unknown')}", f"dm_set:{acc.get('name')}")]
                          for acc in accounts]
                await event.edit(
                    "📨 **Enable DM Reply**\n\n"
                    "Select account to configure:",
                    buttons=buttons
                )
            elif data == "dm_change_group":
                from ..core.mongo_database import mongodb
                accounts = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(None)
                if not accounts:
                    await event.edit("❌ No active accounts found.")
                    return
                from telethon import Button
                buttons = [[Button.inline(f"📱 {acc.get('name', 'Unknown')}", f"dm_set:{acc.get('name')}")]
                          for acc in accounts]
                await event.edit(
                    "📨 **Change DM Reply Group**\n\n"
                    "Select account:",
                    buttons=buttons
                )
            elif data == "dm_disable":
                from ..core.mongo_database import mongodb
                accounts = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(None)
                if not accounts:
                    await event.edit("❌ No active accounts found.")
                    return
                from telethon import Button
                buttons = [[Button.inline(f"📱 {acc.get('name', 'Unknown')}", f"dm_dis:{acc.get('name')}")]
                          for acc in accounts]
                await event.edit(
                    "📨 **Disable DM Reply**\n\n"
                    "Select account:",
                    buttons=buttons
                )
            elif data.startswith("dm_dis:"):
                account_name = data.split(":", 1)[1]
                from ..core.mongo_database import mongodb
                await mongodb.db.accounts.update_one(
                    {"user_id": user_id, "name": account_name},
                    {"$unset": {"dm_reply_group_id": ""}}
                )
                await event.edit(
                    f"📨 **Unified Messaging Disabled**\n\n"
                    f"❌ Disabled for {account_name}\n\n"
                    f"Use /set_dm_group to enable it again."
                )

    async def handle_dm_group_input(self, event, user_id, group_id_text):
        """Handle DM group ID input"""
        try:
            group_id = int(group_id_text.strip())
            if group_id > 0:
                await event.reply(
                    "❌ Please provide a negative group ID (groups have negative IDs)"
                )
                return
            
            from ..core.mongo_database import mongodb
            
            # Get pending action to know which account
            pending = self.bot_manager.pending_actions.get(user_id, {})
            account_name = pending.get("account_name")
            
            if not account_name:
                await event.reply("❌ No account selected. Please use the menu to set up DM group.")
                return
            
            # Store group ID for specific account
            await mongodb.db.accounts.update_one(
                {"user_id": user_id, "name": account_name},
                {"$set": {"dm_reply_group_id": group_id}}
            )
            
            await event.reply(
                f"✅ **Unified Messaging Configured**\n\n"
                f"📍 Account: {account_name}\n"
                f"📍 Group ID: `{group_id}`\n\n"
                f"🎯 **Auto-Topic Creation Active**\n\n"
                f"All DMs to {account_name} will now automatically create **Topics** in this group.\n\n"
                f"**How it works:**\n"
                f"• Private messages to this account create topics\n"
                f"• Each conversation gets its own thread\n"
                f"• Reply in topics to respond\n\n"
                f"Use /dm_status to check status."
            )
        except ValueError:
            await event.reply("❌ Invalid group ID. Please provide a numeric group ID.")
        except Exception as e:
            logger.error(f"Error setting DM group: {e}")
            await event.reply("❌ An error occurred. Please try again.")

        @self.bot.on(events.NewMessage(pattern=r"^/debug_topics$"))
        async def debug_topics_command(event):
            """Debug command to check topic mappings"""
            if not event.is_private:
                return

            user_id = event.sender_id
            from ..core.mongo_database import mongodb

            try:
                # Get user's accounts with DM groups
                accounts = await mongodb.db.accounts.find(
                    {"user_id": user_id, "is_active": True}
                ).to_list(None)

                msg = f"📊 **DM Reply Debug Info**\n\n"
                msg += f"**Active Accounts:** {len(accounts)}\n\n"

                if accounts:
                    msg += "**Your Accounts:**\n"
                    for acc in accounts:
                        acc_name = acc.get('name', 'Unknown')
                        group_id = acc.get('dm_reply_group_id')
                        msg += f"\n📱 **{acc_name}**\n"
                        
                        if group_id:
                            msg += f"  Group ID: `{group_id}`\n"
                            
                            # Check if group is accessible and has forum enabled
                            try:
                                chat_info = await self.bot.get_entity(group_id)
                                is_forum = getattr(chat_info, "forum", False)
                                msg += f"  Forum Enabled: {'✅ Yes' if is_forum else '❌ No'}\n"
                                
                                # Get topic count for this group
                                topic_count = await mongodb.db.topic_mappings.count_documents(
                                    {"admin_group_id": group_id}
                                )
                                msg += f"  Topics Created: {topic_count}\n"
                            except Exception as e:
                                msg += f"  Status: ❌ Cannot access group ({str(e)[:50]})\n"
                        else:
                            msg += f"  Status: ❌ No DM group configured\n"
                    msg += "\n"
                else:
                    msg += "**No active accounts found.**\n\n"

                # Get all topic mappings
                all_mappings = await mongodb.db.topic_mappings.find({}).to_list(None)
                msg += f"**Total Topics in Database:** {len(all_mappings)}\n\n"

                msg += "**Setup Instructions:**\n"
                msg += "1. Use /set_dm_group to configure\n"
                msg += "2. Make sure group has Topics enabled\n"
                msg += "3. Bot must be admin with topic permissions\n"
                msg += "4. Send a test DM to your account\n"

                await event.reply(msg)

            except Exception as e:
                logger.error(f"Debug topics error: {e}", exc_info=True)
                await event.reply(f"❌ Error: {e}")

        @self.bot.on(events.NewMessage(pattern=r"^/refresh_dm_handlers$"))
        async def refresh_dm_handlers_command(event):
            """Refresh DM handlers for all accounts"""
            if not event.is_private:
                return

            user_id = event.sender_id

            try:
                await event.reply("🔄 Refreshing DM handlers...")

                if (
                    hasattr(self.bot_manager, "dm_reply_handler")
                    and self.bot_manager.dm_reply_handler
                ):
                    await self.bot_manager.dm_reply_handler.refresh_all_handlers()

                    # Count registered handlers for this user
                    user_handlers = sum(
                        1
                        for key in self.bot_manager.dm_reply_handler.handled_clients
                        if key.startswith(f"{user_id}:")
                    )

                    await event.reply(
                        f"✅ **DM Handlers Refreshed**\n\n"
                        f"Registered handlers for your accounts: {user_handlers}\n\n"
                        f"All your accounts should now receive DM notifications with topic creation."
                    )
                else:
                    await event.reply("❌ DM reply handler not available")

            except Exception as e:
                logger.error(f"Refresh handlers error: {e}")
                await event.reply(f"❌ Error: {e}")
