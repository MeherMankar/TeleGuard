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

        @self.bot.on(events.NewMessage(pattern=r"^/enable_topics$"))
        async def enable_topics_command(event):
            logger.info(f"enable_topics command received from {event.sender_id}, is_private={event.is_private}")
            user_id = event.sender_id
            from ..core.mongo_database import mongodb
            
            # Debug: Check all accounts
            all_accounts = await mongodb.db.accounts.find({"user_id": user_id, "is_active": True}).to_list(None)
            logger.info(f"Total active accounts for user {user_id}: {len(all_accounts)}")
            for acc in all_accounts:
                logger.info(f"  Account: {acc.get('name')}, has dm_reply_group_id: {acc.get('dm_reply_group_id') is not None}")
            
            # Get accounts WITHOUT dm_reply_group_id
            accounts = await mongodb.db.accounts.find({
                "user_id": user_id,
                "is_active": True,
                "dm_reply_group_id": {"$exists": False}
            }).to_list(None)
            
            if not accounts:
                await event.reply(
                    "✅ **All Accounts Have Topics Enabled**\n\n"
                    "All your active accounts already have DM topics configured.\n\n"
                    "Use /disable_topics to disable for specific accounts."
                )
                return
            
            buttons = [[Button.inline(f"📱 {acc.get('name', 'Unknown')}", f"dm_set:{acc.get('name')}")]
                      for acc in accounts]
            buttons.append([Button.inline("❌ Cancel", "dm_cancel")])
            
            await event.reply(
                "📨 **Enable DM Topics**\n\n"
                f"Select account to enable ({len(accounts)} available):",
                buttons=buttons
            )

        @self.bot.on(events.NewMessage(pattern=r"^/disable_topics$"))
        async def disable_topics_command(event):
            logger.info(f"disable_topics command received from {event.sender_id}, is_private={event.is_private}")
            user_id = event.sender_id
            from ..core.mongo_database import mongodb
            
            # Get accounts WITH dm_reply_group_id
            accounts = await mongodb.db.accounts.find({
                "user_id": user_id,
                "is_active": True,
                "dm_reply_group_id": {"$exists": True}
            }).to_list(None)
            
            if not accounts:
                await event.reply(
                    "❌ **No Topics Enabled**\n\n"
                    "None of your accounts have DM topics enabled.\n\n"
                    "Use /enable_topics to enable for specific accounts."
                )
                return
            
            buttons = [[Button.inline(f"📱 {acc.get('name', 'Unknown')}", f"dm_dis:{acc.get('name')}")]
                      for acc in accounts]
            buttons.append([Button.inline("❌ Cancel", "dm_cancel")])
            
            await event.reply(
                "🗑️ **Disable DM Topics**\n\n"
                f"Select account to disable ({len(accounts)} enabled):",
                buttons=buttons
            )

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

                msg = "📊 **DM Reply Debug Info**\n\n"
                msg += f"**Active Accounts:** {len(accounts)}\n\n"

                if accounts:
                    msg += "**Your Accounts:**\n"
                    for acc in accounts:
                        acc_name = acc.get('name', 'Unknown')
                        group_id = acc.get('dm_reply_group_id')
                        phone = acc.get('phone', 'N/A')
                        msg += f"\n📱 **{acc_name}** ({phone})\n"
                        
                        # Check if client is loaded
                        client = self.bot_manager.user_clients.get(user_id, {}).get(acc_name)
                        if client:
                            is_connected = client.is_connected() if client else False
                            msg += f"  Client: {'✅ Loaded' if client else '❌ Not loaded'}\n"
                            msg += f"  Connected: {'✅ Yes' if is_connected else '❌ No'}\n"
                        else:
                            msg += "  Client: ❌ Not loaded\n"
                        
                        # Check if handlers are set up
                        if hasattr(self.bot_manager, 'unified_messaging'):
                            client_key = f"{user_id}:{acc_name}"
                            has_handler = client_key in self.bot_manager.unified_messaging.handled_clients
                            msg += f"  Handler: {'✅ Set up' if has_handler else '❌ Not set up'}\n"
                        
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
                            msg += "  Status: ❌ No DM group configured\n"
                    msg += "\n"
                else:
                    msg += "**No active accounts found.**\n\n"

                # Get all topic mappings
                all_mappings = await mongodb.db.topic_mappings.find({}).to_list(None)
                msg += f"**Total Topics in Database:** {len(all_mappings)}\n\n"

                msg += "**Next Steps:**\n"
                msg += "1. Make sure client is loaded and connected\n"
                msg += "2. Make sure handler is set up\n"
                msg += "3. Send a test DM to your account\n"
                msg += "4. Check logs for 📨 messages\n"

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

        @self.bot.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and (e.forward or (e.text and e.text.strip().startswith('-')))))
        async def handle_forwarded_or_id(event):
            user_id = event.sender_id
            if not hasattr(self.bot_manager, 'pending_dm_setups') or user_id not in self.bot_manager.pending_dm_setups:
                return
            account_name = self.bot_manager.pending_dm_setups[user_id]
            group_id = event.forward.chat.id if event.forward and event.forward.chat else (int(event.text.strip()) if event.text and event.text.strip().startswith('-') else None)
            if not group_id:
                return
            try:
                from ..core.mongo_database import mongodb
                chat_info = await self.bot.get_entity(group_id)
                if not getattr(chat_info, "forum", False):
                    await event.reply("❌ Not a forum group. Enable Topics in settings.")
                    return
                result = await mongodb.db.accounts.update_one({"user_id": user_id, "name": account_name}, {"$set": {"dm_reply_group_id": group_id}})
                if result.modified_count > 0 or result.matched_count > 0:
                    if hasattr(self.bot_manager, 'unified_messaging') and self.bot_manager.unified_messaging:
                        client = self.bot_manager.user_clients.get(user_id, {}).get(account_name)
                        if client and client.is_connected():
                            self.bot_manager.unified_messaging._setup_client_handlers(user_id, account_name, client)
                    await event.reply(f"✅ **DM Topics Enabled!**\n\n📱 Account: {account_name}\n📍 Group: {chat_info.title}\n🆔 ID: `{group_id}`\n\n🎯 DMs will create topics!")
                    del self.bot_manager.pending_dm_setups[user_id]
            except Exception as e:
                await event.reply(f"❌ Error: {str(e)}")

        @self.bot.on(events.CallbackQuery(pattern=b"dm_"))
        async def handle_dm_callbacks(event):
            data = event.data.decode("utf-8")
            user_id = event.sender_id
            if data.startswith("dm_reply:"):
                return
                
            safe_data = ''.join(char if ord(char) < 128 else '?' for char in data)
            logger.info(f"DM callback handler triggered: {safe_data} from user {user_id}")
            
            if data.startswith("dm_set:"):
                account_name = data.split(":", 1)[1]
                await event.edit(
                    f"📨 **Enable DM Topics for {account_name}**\n\n"
                    f"**Option 1: Forward Message (Easy)**\n"
                    f"1. Forward any message from your forum group\n"
                    f"2. I'll auto-detect and configure it\n\n"
                    f"**Option 2: Manual ID Entry**\n"
                    f"• Send the group ID directly (e.g., `-1001234567890`)\n\n"
                    f"💡 **Tip:** Make sure Topics are enabled in group settings!"
                )
                # Store pending setup
                if not hasattr(self.bot_manager, 'pending_dm_setups'):
                    self.bot_manager.pending_dm_setups = {}
                self.bot_manager.pending_dm_setups[user_id] = account_name
                return
            
            if data.startswith("dm_link:"):
                # Format: dm_link:account_name:group_id
                parts = data.split(":", 2)
                if len(parts) != 3:
                    await event.answer("❌ Invalid data", alert=True)
                    return
                
                account_name = parts[1].strip()
                # Only reject if completely empty
                if not account_name:
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
                    # Trigger handler setup for this account
                    logger.info(f"Setting up handlers for account {account_name} after DM group config")
                    if hasattr(self.bot_manager, 'unified_messaging') and self.bot_manager.unified_messaging:
                        # Get the client for this account
                        client = self.bot_manager.user_clients.get(user_id, {}).get(account_name)
                        if client and client.is_connected():
                            logger.info(f"Found connected client for {account_name}, setting up handlers")
                            self.bot_manager.unified_messaging._setup_client_handlers(user_id, account_name, client)
                        else:
                            logger.warning(f"Client for {account_name} not found or not connected")
                    
                    await event.edit(
                        f"✅ **DM Manager Configured**\n\n"
                        f"📱 Account configured\n"
                        f"📍 Group ID: `{group_id}`\n\n"
                        f"🎯 **Active!** Send a test DM to your account to create a topic.\n\n"
                        f"**How to reply:**\n"
                        f"• Go to the topic for a conversation\n"
                        f"• Reply to any message in the topic\n"
                        f"• Your reply will be sent from your account"
                    )
                else:
                    await event.answer("❌ Account not found", alert=True)
                return
            
            if data == "dm_cancel":
                await event.edit("❌ Setup cancelled")
                return
            if data.startswith("dm_dis:"):
                account_name = data.split(":", 1)[1]
                from ..core.mongo_database import mongodb
                await mongodb.db.accounts.update_one(
                    {"user_id": user_id, "name": account_name},
                    {"$unset": {"dm_reply_group_id": ""}}
                )
                # Also delete all topic mappings for this account
                account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                if account:
                    me_id = account.get("telegram_id")
                    if me_id:
                        deleted = await mongodb.db.topic_mappings.delete_many({"account_id": me_id})
                        await mongodb.db.dm_senders.delete_many({"account_id": me_id})
                        logger.info(f"Deleted {deleted.deleted_count} topics for account {account_name}")
                await event.edit(
                    f"✅ **DM Manager Disabled**\n\n"
                    f"❌ Disabled for {account_name}\n"
                    f"🗑️ All topics removed\n\n"
                    f"Use /enable_topics in a forum group to enable again."
                )

    async def handle_dm_group_input(self, event, _user_id, _group_id_text):
        """Handle DM group ID input - DEPRECATED, use /enable_topics in forum group instead"""
        await event.reply(
            "❌ **This method is deprecated**\n\n"
            "Please use the new method:\n"
            "1. Go to your forum group\n"
            "2. Use /enable_topics command\n"
            "3. Select the account\n\n"
            "This is simpler and more reliable!"
        )
