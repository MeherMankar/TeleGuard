"""Cleanup operations module"""

import logging

from telethon import Button

from ...core.mongo_database import mongodb
from ...utils.network_helpers import format_display_name

logger = logging.getLogger(__name__)


class CleanupOperations:
    def __init__(self, menu_system):
        self.menu = menu_system
        self.bot = menu_system.bot
        self.bot_manager = menu_system.account_manager  # account_manager IS bot_manager

    async def send_bulk_cleanup_selection(self, user_id, message_id):
        """Send bulk cleanup selection for all accounts"""
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
            length=None
        )
        if not accounts:
            await self.bot.edit_message(
                user_id,
                message_id,
                "❌ No accounts found",
                buttons=[[Button.inline("🔙 Back", "cleanup:menu")]],
            )
            return

        active_accounts = [acc for acc in accounts if acc.get("is_active", False)]
        text = f"🧹 **Bulk Cleanup - All Accounts**\n\n📊 **Accounts:** {
            len(active_accounts)} active / {
            len(accounts)} total\n\n📋 **What would you like to clean?**\n\nThis will clean ALL your accounts at once.\n\n💬 **Personal chats** - Direct messages\n🤖 **Bot chats** - Bot conversations\n📢 **Telegram official** - Service chats\n🚫 **Spambot chats** - @spambot\n🚪 **Exit channels** - Leave all channels\n👥 **Exit groups** - Leave all groups\n🗑️ **Delete owned groups** - Delete your groups\n📺 **Delete owned channels** - Delete your channels\n\n⚠️ **WARNING**: This affects ALL accounts!"

        if self.bot_manager:
            self.bot_manager.pending_actions[user_id] = {
                "action": "bulk_cleanup_selection"
            }

        await self.bot.edit_message(user_id, message_id, text)
        await self.bot.send_message(
            user_id,
            "📝 **Reply with cleanup type:**\n\n**Examples:**\n• `personal,bots`\n• `channels,groups`\n• `my_messages`\n• `all`\n\n**Options:** `personal`, `bots`, `telegram`, `spambot`, `my_messages`, `channels`, `groups`, `owned_groups`, `owned_channels`, `all`",
        )

    async def execute_bulk_cleanup(self, user_id, cleanup_types):
        """Execute cleanup on all user accounts"""

        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
            length=None
        )
        if not accounts:
            await self.bot.send_message(user_id, "❌ No accounts found")
            return

        active_accounts = [acc for acc in accounts if acc.get("is_active", False)]
        if not active_accounts:
            await self.bot.send_message(user_id, "❌ No active accounts found")
            return

        # Parse cleanup settings
        cleanup_list = [t.strip().lower() for t in cleanup_types.split(",")]
        if "all" in cleanup_list:
            cleanup_list = [
                "personal",
                "bots",
                "telegram",
                "spambot",
                "channels",
                "groups",
                "owned_groups",
                "owned_channels",
            ]

        cleanup_settings = {
            "personal_chats": "personal" in cleanup_list,
            "bot_chats": "bots" in cleanup_list,
            "telegram_chat": "telegram" in cleanup_list,
            "spambot_chat": "spambot" in cleanup_list,
            "channels": "channels" in cleanup_list,
            "groups": "groups" in cleanup_list,
            "owned_groups": "owned_groups" in cleanup_list,
            "owned_channels": "owned_channels" in cleanup_list,
            "my_messages": "my_messages" in cleanup_list,
        }

        status_msg = await self.bot.send_message(
            user_id,
            f"🚀 **Bulk Cleanup Started**\n\n📊 Processing {
                len(active_accounts)} accounts...\n⏳ Please wait...",
        )

        from ...core.account_cleaner import AccountCleaner

        cleaner = AccountCleaner()

        results = []
        for i, account in enumerate(active_accounts, 1):
            account_name = account.get("name")
            display_name = format_display_name(account)

            # Get client
            client = None
            if (
                hasattr(self.bot_manager, "user_clients")
                and user_id in self.bot_manager.user_clients
            ):
                client = self.bot_manager.user_clients[user_id].get(account_name)

            if not client or not client.is_connected():
                results.append(f"❌ {display_name}: Not connected")
                continue

            try:
                await status_msg.edit(
                    f"🚀 **Bulk Cleanup**\n\n📊 Progress: {i}/{
                        len(active_accounts)}\n🧹 Cleaning: {display_name}\n⏳ Please wait..."
                )

                result = await cleaner.cleanup_account(client, cleanup_settings, None)
                results.append(f"✅ {display_name}: Completed")

                # Log cleanup
                import time

                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {
                        "$push": {
                            "audit_log": {
                                "action": "bulk_cleanup_completed",
                                "cleanup_types": cleanup_types,
                                "timestamp": int(time.time()),
                                "result": "success",
                            }
                        }
                    },
                )
            except Exception as e:
                logger.error(f"Cleanup failed for {display_name}: {e}")
                results.append(f"❌ {display_name}: {str(e)[:50]}")

        # Send final results
        result_text = (
            f"✅ **Bulk Cleanup Completed!**\n\n"
            f"📊 **Summary:**\n"
            f"• Total: {len(active_accounts)} accounts\n"
            f"• Success: {sum(1 for r in results if r.startswith('✅'))}\n"
            f"• Failed: {sum(1 for r in results if r.startswith('❌'))}\n\n"
            f"**Results:**\n" + "\n".join(results[:10])
        )

        if len(results) > 10:
            result_text += f"\n\n... and {len(results) - 10} more"

        buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
        await status_msg.edit(result_text, buttons=buttons)

    async def send_cleanup_selection(self, user_id, message_id, account_id):
        from bson import ObjectId

        account = await mongodb.db.accounts.find_one(
            {"_id": ObjectId(account_id), "user_id": user_id}
        )
        if not account:
            await self.bot.edit_message(
                user_id,
                message_id,
                "❌ Account not found",
                buttons=[[Button.inline("🔙 Back", "cleanup:menu")]],
            )
            return
        display_name = format_display_name(account)
        text = f"🧹 **Cleanup Selection - {display_name}**\n\n📋 **What would you like to clean?**\n\nSelect what to clean (you can choose multiple options):\n\n💬 **Personal chats** - Direct messages with users\n🤖 **Bot chats** - Conversations with bots\n📢 **Telegram official** - Telegram service chats\n🚫 **Spambot chats** - @spambot conversations\n🗑️ **My messages** - Delete all your sent messages from groups\n🚪 **Exit channels** - Leave all channels\n👥 **Exit groups** - Leave all groups\n🗑️ **Delete owned groups** - Delete groups you own\n📺 **Delete owned channels** - Delete channels you own\n\n⚠️ **WARNING**: These actions cannot be undone!"
        if self.bot_manager:
            self.bot_manager.pending_actions[user_id] = {
                "action": "cleanup_selection",
                "account_id": account_id,
            }
        await self.bot.edit_message(user_id, message_id, text)
        await self.bot.send_message(
            user_id,
            "📝 **Reply with your selection:**\n\nType what you want to clean, separated by commas:\n\n**Examples:**\n• `personal,bots` - Clean personal chats and bot chats\n• `channels,groups` - Exit all channels and groups\n• `my_messages` - Delete all your sent messages from groups\n• `all` - Clean everything\n\n**Available options:**\n`personal`, `bots`, `telegram`, `spambot`, `my_messages`, `channels`, `groups`, `owned_groups`, `owned_channels`, `all`",
        )

    async def execute_cleanup(self, event, user_id, account_id, cleanup_types):
        from bson import ObjectId

        logger.info(
            f"execute_cleanup called: user={user_id}, account={account_id}, types={cleanup_types}"
        )

        account = await mongodb.db.accounts.find_one(
            {"_id": ObjectId(account_id), "user_id": user_id}
        )
        if not account:
            logger.error(f"Account not found: {account_id}")
            await self.bot.send_message(user_id, "❌ Account not found")
            return

        if not self.bot_manager:
            logger.error("Bot manager not available")
            await self.bot.send_message(user_id, "❌ Service unavailable")
            return

        client = None
        if (
            hasattr(self.bot_manager, "user_clients")
            and user_id in self.bot_manager.user_clients
        ):
            account_name = account.get("name")
            client = self.bot_manager.user_clients[user_id].get(account_name)
            logger.info(
                f"Found client for account {account_name}: {client is not None}"
            )

        if not client or not client.is_connected():
            logger.error(f"Client not connected for account {account.get('name')}")
            await self.bot.send_message(
                user_id, "❌ Account not connected. Please ensure account is active."
            )
            return

        display_name = format_display_name(account)
        cleanup_list = [t.strip().lower() for t in cleanup_types.split(",")]
        if "all" in cleanup_list:
            cleanup_list = [
                "personal",
                "bots",
                "telegram",
                "spambot",
                "channels",
                "groups",
                "owned_groups",
                "owned_channels",
            ]

        cleanup_settings = {
            "personal_chats": "personal" in cleanup_list,
            "bot_chats": "bots" in cleanup_list,
            "telegram_chat": "telegram" in cleanup_list,
            "spambot_chat": "spambot" in cleanup_list,
            "channels": "channels" in cleanup_list,
            "groups": "groups" in cleanup_list,
            "owned_groups": "owned_groups" in cleanup_list,
            "owned_channels": "owned_channels" in cleanup_list,
            "my_messages": "my_messages" in cleanup_list,
        }

        logger.info(f"Cleanup settings: {cleanup_settings}")

        # Send initial status message
        status_msg = await self.bot.send_message(
            user_id,
            f"🚀 **Starting cleanup for {display_name}**\n\n⏳ Analyzing account...\n📊 Progress will be shown below",
        )

        from ...core.account_cleaner import AccountCleaner

        cleaner = AccountCleaner()
        import time

        last_update_time = time.time()

        async def progress_callback(text):
            nonlocal last_update_time
            current_time = time.time()
            if current_time - last_update_time < 2:
                return
            try:
                await status_msg.edit(f"🚀 **Cleaning {display_name}**\n\n{text}")
                last_update_time = current_time
            except Exception as e:
                logger.debug(f"Progress update error: {e}")

        logger.info("Starting cleanup_account...")
        result = await cleaner.cleanup_account(
            client, cleanup_settings, progress_callback
        )
        logger.info(f"Cleanup completed with result: {result[:100]}...")

        result_text = f"✅ **Cleanup completed!**\n\n📱 Account: {display_name}\n\n📊 **Results:**\n{result}\n\n🔒 All operations completed securely"
        buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]

        try:
            await status_msg.edit(result_text, buttons=buttons)
            logger.info("Final result message sent successfully")
        except Exception as e:
            logger.error(f"Failed to edit final message: {e}")
            try:
                await self.bot.send_message(user_id, result_text, buttons=buttons)
            except Exception as e2:
                logger.error(f"Failed to send new message: {e2}")

        # Add audit log
        try:
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {
                    "$push": {
                        "audit_log": {
                            "action": "cleanup_completed",
                            "cleanup_types": cleanup_types,
                            "timestamp": int(time.time()),
                            "result": "success",
                        }
                    }
                },
            )
        except Exception as e:
            logger.error(f"Failed to add audit entry: {e}")
