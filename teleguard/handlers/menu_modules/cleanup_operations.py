"""Cleanup operations module"""

import logging
import time

from telethon import Button

from ...core.cleanup_types import parse_cleanup_types
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

        if self.bot_manager:
            self.bot_manager.pending_actions[user_id] = {
                "action": "bulk_cleanup_selection"
            }

        text = (
            f"🧹 **Bulk Cleanup — All Accounts**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 **Accounts:** {len(active_accounts)} active / {len(accounts)} total\n\n"
            "📋 **What would you like to clean?**\n\n"
            "💬 `personal` — Direct messages\n"
            "🤖 `bots` — Bot conversations\n"
            "📢 `telegram` — Service chats\n"
            "🚫 `spambot` — @spambot\n"
            "�️ `my_messages` — Your sent messages from groups\n"
            "🚪 `channels` — Leave all channels\n"
            "👥 `groups` — Leave all groups\n"
            "🗑️ `owned_groups` — Delete your groups\n"
            "📺 `owned_channels` — Delete your channels\n"
            "🔥 `all` — Everything above\n\n"
            "⚠️ **This affects ALL accounts!**\n\n"
            "📝 **Reply with your selection** (comma-separated):\n"
            "Examples: `personal,bots` · `channels,groups` · `all`"
        )
        buttons = [[Button.inline("❌ Cancel", "cleanup:menu")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

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

        try:
            selected_types, cleanup_settings = parse_cleanup_types(cleanup_types)
        except ValueError as e:
            await self.bot.send_message(user_id, f"❌ {e}")
            return

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
                succeeded = self._cleanup_result_succeeded(result)
                result_status = "success" if succeeded else "partial_failure"
                marker = "✅" if succeeded else "⚠️"
                results.append(f"{marker} {display_name}: {result_status}")

                # Log cleanup
                try:
                    await mongodb.db.accounts.update_one(
                        {"_id": account["_id"]},
                        {
                            "$push": {
                                "audit_log": {
                                    "action": "bulk_cleanup_completed",
                                    "cleanup_types": selected_types,
                                    "timestamp": int(time.time()),
                                    "result": result_status,
                                }
                            }
                        },
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to add cleanup audit entry for {display_name}: {e}"
                    )
            except Exception as e:
                logger.error(f"Cleanup failed for {display_name}: {e}")
                results.append(f"❌ {display_name}: {str(e)[:50]}")

        # Send final results
        result_text = (
            f"✅ **Bulk Cleanup Completed!**\n\n"
            f"📊 **Summary:**\n"
            f"• Total: {len(active_accounts)} accounts\n"
            f"• Completed: {sum(1 for r in results if r.startswith('✅'))}\n"
            f"• Partial/failed: {sum(1 for r in results if not r.startswith('✅'))}\n\n"
            f"**Results:**\n" + "\n".join(results[:10])
        )

        if len(results) > 10:
            result_text += f"\n\n... and {len(results) - 10} more"

        buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
        await status_msg.edit(result_text, buttons=buttons)

    @staticmethod
    def _cleanup_result_succeeded(result):
        return (
            "📊 Cleanup Summary:" in result
            and "⚠️ Errors: 0" in result
        )

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

        if self.bot_manager:
            self.bot_manager.pending_actions[user_id] = {
                "action": "cleanup_selection",
                "account_id": account_id,
            }

        text = (
            f"🧹 **Cleanup Selection — {display_name}**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📋 **What would you like to clean?**\n\n"
            "💬 `personal` — Direct messages with users\n"
            "🤖 `bots` — Conversations with bots\n"
            "📢 `telegram` — Telegram service chats\n"
            "🚫 `spambot` — @spambot conversations\n"
            "🗑️ `my_messages` — Delete your sent messages from groups\n"
            "🚪 `channels` — Leave all channels\n"
            "👥 `groups` — Leave all groups\n"
            "🗑️ `owned_groups` — Delete groups you own\n"
            "📺 `owned_channels` — Delete channels you own\n"
            "🔥 `all` — Everything above\n\n"
            "⚠️ **These actions cannot be undone!**\n\n"
            "📝 **Reply with your selection** (comma-separated):\n"
            "Examples: `personal,bots` · `channels,groups` · `all`"
        )
        buttons = [[Button.inline("❌ Cancel", "cleanup:menu")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

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
        try:
            selected_types, cleanup_settings = parse_cleanup_types(cleanup_types)
        except ValueError as e:
            await self.bot.send_message(user_id, f"❌ {e}")
            return

        logger.info(f"Cleanup settings: {cleanup_settings}")

        # Send initial status message
        status_msg = await self.bot.send_message(
            user_id,
            f"🚀 **Starting cleanup for {display_name}**\n\n⏳ Analyzing account...\n📊 Progress will be shown below",
        )

        from ...core.account_cleaner import AccountCleaner

        cleaner = AccountCleaner()

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

        succeeded = self._cleanup_result_succeeded(result)
        status = (
            "✅ Cleanup completed"
            if succeeded
            else "⚠️ Cleanup completed with errors"
        )
        result_text = (
            f"{status}\n\n📱 Account: {display_name}\n\n📊 **Results:**\n{result}"
        )
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
                            "cleanup_types": selected_types,
                            "timestamp": int(time.time()),
                            "result": "success" if succeeded else "partial_failure",
                        }
                    }
                },
            )
        except Exception as e:
            logger.error(f"Failed to add audit entry: {e}")
