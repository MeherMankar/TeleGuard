"""Session Operations Handler - Advanced session management operations
Developed by:
- @MeherPatil
- @Gutkesh
GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import asyncio
import io
import json
import logging
import os
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone

from telethon import Button, events
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import Channel, Chat, InputPhoneContact, User

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class SessionOperationsHandler:
    """Advanced session operations from SessionMaster"""

    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager
        self.user_clients = bot_manager.user_clients

    def register_handlers(self):
        """Register session operation handlers"""

        @self.bot.on(events.CallbackQuery(pattern=r"^session_delete:(.+):(.+)$"))
        async def handle_delete_dialogs(event):
            user_id = event.sender_id
            dialog_type = event.pattern_match.group(1).decode()
            account_id = event.pattern_match.group(2).decode()
            await self._delete_dialogs_by_type(event, user_id, account_id, dialog_type)

        @self.bot.on(events.CallbackQuery(pattern=r"^session_export_string:(.+)$"))
        async def export_session_string(event):
            user_id = event.sender_id
            account_id = event.pattern_match.group(1).decode()
            await self._export_session_string(event, user_id, account_id)

        @self.bot.on(events.CallbackQuery(pattern=r"^session_bulk_ops:(.+)$"))
        async def bulk_operations(event):
            user_id = event.sender_id
            account_id = event.pattern_match.group(1).decode()
            await self._show_bulk_operations(event, user_id, account_id)

        @self.bot.on(events.CallbackQuery(pattern=r"^session_analytics:(.+)$"))
        async def session_analytics(event):
            user_id = event.sender_id
            account_id = event.pattern_match.group(1).decode()
            await self._show_session_analytics(event, user_id, account_id)

        @self.bot.on(events.CallbackQuery(pattern=r"^session_automation:(.+)$"))
        async def session_automation(event):
            user_id = event.sender_id
            account_id = event.pattern_match.group(1).decode()
            await self._show_session_automation(event, user_id, account_id)

        @self.bot.on(events.CallbackQuery(pattern=r"^confirm_delete:([^:]+):(.+)$"))
        async def confirm_delete(event):
            user_id = event.sender_id
            dialog_type = event.pattern_match.group(1).decode()
            account_id = event.pattern_match.group(2).decode()
            await self._execute_dialog_deletion(
                event, user_id, account_id, dialog_type
            )

        @self.bot.on(events.CallbackQuery(pattern=r"^session_operation_cancel:(.+)$"))
        async def cancel_operation(event):
            user_id = event.sender_id
            account_id = event.pattern_match.group(1).decode()
            await event.answer("Cancelled")
            login_handler = getattr(self.bot_manager, "session_login_handler", None)
            if login_handler:
                await login_handler._show_session_operations(
                    event, user_id, account_id
                )
            else:
                await event.edit(
                    "Operation cancelled.",
                    buttons=[
                        [
                            Button.inline(
                                "Back to Session Operations",
                                f"session_operations:{account_id}",
                            )
                        ]
                    ],
                )

        @self.bot.on(
            events.CallbackQuery(
                pattern=r"^(bulk_subscribe|bulk_messages|extract_members|"
                r"scrape_messages|monitor_keywords):.+$"
            )
        )
        async def disabled_bulk_operation(event):
            await event.answer(
                "This bulk or data-collection action is unavailable.",
                alert=True,
            )

        @self.bot.on(events.CallbackQuery(pattern=r"^auto_cleanup:(.+)$"))
        async def auto_cleanup(event):
            account_id = event.pattern_match.group(1).decode()
            await event.answer()
            await event.edit(
                "⚠️ **Confirm Auto Cleanup**\n\n"
                "This leaves groups with no activity for at least 30 days. "
                "This action cannot be undone.",
                buttons=[
                    [
                        Button.inline(
                            "Yes, leave inactive groups",
                            f"auto_cleanup_confirm:{account_id}",
                        )
                    ],
                    [
                        Button.inline(
                            "Cancel", f"session_operation_cancel:{account_id}"
                        )
                    ],
                ],
            )

        @self.bot.on(events.CallbackQuery(pattern=r"^auto_cleanup_confirm:(.+)$"))
        async def confirm_auto_cleanup(event):
            user_id = event.sender_id
            account_id = event.pattern_match.group(1).decode()
            await event.answer("Cleaning inactive groups...")
            result = await self.auto_leave_inactive_groups(
                user_id, account_id, days_inactive=30
            )
            text = (
                result.get("message", "Cleanup completed.")
                if result.get("success")
                else f"❌ {result.get('error', 'Cleanup failed.')}"
            )
            await event.edit(
                text,
                buttons=[
                    [
                        Button.inline(
                            "Back to Session Operations",
                            f"session_operations:{account_id}",
                        )
                    ]
                ],
            )

        @self.bot.on(events.CallbackQuery(pattern=r"^detailed_stats:(.+)$"))
        async def detailed_stats(event):
            user_id = event.sender_id
            account_id = event.pattern_match.group(1).decode()
            await self._show_detailed_stats(event, user_id, account_id)

        @self.bot.on(events.CallbackQuery(pattern=r"^export_analytics:(.+)$"))
        async def export_analytics(event):
            user_id = event.sender_id
            account_id = event.pattern_match.group(1).decode()
            await self._export_analytics(event, user_id, account_id)

    async def _owned_account(self, user_id, account_id):
        from bson import ObjectId
        from bson.errors import InvalidId

        try:
            object_id = ObjectId(account_id)
        except (InvalidId, TypeError):
            return None
        return await mongodb.db.accounts.find_one(
            {"_id": object_id, "user_id": user_id}
        )

    async def _execute_dialog_deletion(
        self, event, user_id, account_id, dialog_type
    ):
        allowed_types = {"channels", "groups", "bots", "private"}
        if dialog_type not in allowed_types:
            await event.answer("❌ Invalid dialog type", alert=True)
            return

        account = await self._owned_account(user_id, account_id)
        client = (
            self.user_clients.get(user_id, {}).get(account.get("name"))
            if account
            else None
        )
        if not account or not client or not client.is_connected():
            await event.answer("❌ Account not available", alert=True)
            return

        await event.answer("Deleting selected dialogs...")
        deleted = 0
        try:
            for dialog in await client.get_dialogs():
                entity = dialog.entity
                if dialog_type == "channels":
                    matches = isinstance(entity, Channel) and getattr(
                        entity, "broadcast", False
                    )
                elif dialog_type == "groups":
                    matches = isinstance(entity, Chat) or (
                        isinstance(entity, Channel)
                        and not getattr(entity, "broadcast", False)
                    )
                elif dialog_type == "bots":
                    matches = isinstance(entity, User) and getattr(
                        entity, "bot", False
                    )
                else:
                    matches = isinstance(entity, User) and not getattr(
                        entity, "bot", False
                    )
                if matches:
                    await client.delete_dialog(entity)
                    deleted += 1
            await event.edit(
                f"✅ Deleted {deleted} {dialog_type} dialogs.",
                buttons=[
                    [
                        Button.inline(
                            "Back to Session Operations",
                            f"session_operations:{account_id}",
                        )
                    ]
                ],
            )
        except Exception:
            logger.exception(
                "Dialog deletion failed for user %s account %s",
                user_id,
                account_id,
            )
            await event.edit(
                f"❌ Deletion stopped after {deleted} dialogs. Check the bot logs.",
                buttons=[
                    [
                        Button.inline(
                            "Back to Session Operations",
                            f"session_operations:{account_id}",
                        )
                    ]
                ],
            )

    async def _delete_dialogs_by_type(self, event, user_id, account_id, dialog_type):
        """Delete dialogs by type with confirmation"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                await event.answer("❌ Account not found")
                return

            # Show confirmation
            type_names = {
                "channels": "📢 All Channels",
                "groups": "👥 All Groups",
                "bots": "🤖 All Bots",
                "private": "💭 Private Chats",
            }

            text = (
                f"⚠️ **Confirm Deletion**\n\n"
                f"Account: {account['name']}\n"
                f"Delete: {type_names.get(dialog_type, dialog_type)}\n\n"
                f"**This action cannot be undone!**\n\n"
                f"Are you sure you want to proceed?"
            )

            buttons = [
                [
                    Button.inline(
                        "✅ Yes, Delete", f"confirm_delete:{dialog_type}:{account_id}"
                    )
                ],
                [Button.inline("❌ Cancel", f"session_operations:{account_id}")],
            ]

            await event.edit(text, buttons=buttons)

        except Exception as e:
            logger.error(f"Delete dialogs confirmation error: {e}")
            await event.answer("❌ Error showing confirmation")

    async def _export_session_string(self, event, user_id, account_id):
        """Export session string"""
        try:
            from bson import ObjectId
            from ..utils.crypto_utils import DataEncryption

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                await event.answer("❌ Account not found")
                return

            account = DataEncryption.decrypt_account_data(account)
            session_string = account.get("session_string")
            if not session_string:
                await event.answer("❌ Session string not available")
                return

            # Create session file
            session_file = io.BytesIO(session_string.encode("utf-8"))
            session_file.name = f"session_{account.get('name', account_id)}.txt"

            await self.bot.send_file(
                user_id,
                session_file,
                caption=(
                    f"📝 **Session String Export**\n\n"
                    f"Account: {account.get('name', 'Unknown')}\n"
                    f"Phone: {account.get('phone', 'Unknown')}\n\n"
                    f"**Security Warning:**\n"
                    f"Keep this session string secure!\n"
                    f"Anyone with this string can access your account."
                ),
            )

            await event.answer("📝 Session string exported!")

        except Exception as e:
            logger.error(f"Export session string error: {e}")
            await event.answer("❌ Error exporting session string")

    async def _show_bulk_operations(self, event, user_id, account_id):
        """Show bulk operations menu"""
        try:
            await event.answer()
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                await event.edit("❌ Account not found")
                return

            text = (
                f"🧹 **Session Maintenance: {account['name']}**\n\n"
                "Leave groups with no activity for at least 30 days. "
                "This removes the account from those groups and cannot be undone. "
                "Review the confirmation before proceeding."
            )

            buttons = [
                [
                    Button.inline(
                        "🧹 Leave Inactive Groups", f"auto_cleanup:{account_id}"
                    )
                ],
                [Button.inline("🔙 Back", f"session_operations:{account_id}")],
            ]

            await event.edit(text, buttons=buttons)

        except Exception as e:
            logger.error(f"Show bulk operations error: {e}")
            await event.edit("❌ Error loading bulk operations")

    async def _show_session_analytics(self, event, user_id, account_id):
        """Show session analytics"""
        try:
            await event.answer()
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                await event.edit("❌ Account not found")
                return

            # Get analytics data
            analytics = await self._get_session_analytics(user_id, account)
            if analytics.get("error"):
                await event.edit(
                    f"❌ Could not load analytics: {analytics['error']}",
                    buttons=[
                        [
                            Button.inline(
                                "🔙 Back", f"session_operations:{account_id}"
                            )
                        ]
                    ],
                )
                return

            text = (
                f"📊 **Session Analytics: {account['name']}**\n\n"
                f"**📈 Account Statistics**\n"
                f"• Total Dialogs: {analytics.get('total_dialogs', 0)}\n"
                f"• Channels: {analytics.get('channels', 0)}\n"
                f"• Groups: {analytics.get('groups', 0)}\n"
                f"• Private Chats: {analytics.get('private_chats', 0)}\n"
                f"• Bots: {analytics.get('bots', 0)}\n\n"
                f"**🔒 Security Status**\n"
                f"• 2FA Enabled: {self._display_status(analytics.get('has_2fa'))}\n"
                f"• Active Sessions: {analytics.get('active_sessions', 'Unknown')}\n"
                f"• Premium: {self._display_status(analytics.get('is_premium'))}\n"
                f"• Verified: {self._display_status(analytics.get('is_verified'))}\n"
                f"• Managed Since: {analytics.get('managed_since', 'Not recorded')}"
            )

            buttons = [
                [
                    Button.inline("🔄 Refresh", f"session_analytics:{account_id}"),
                    Button.inline("📊 Detailed Stats", f"detailed_stats:{account_id}"),
                ],
                [
                    Button.inline("📈 Export Report", f"export_analytics:{account_id}"),
                ],
                [Button.inline("🔙 Back", f"session_operations:{account_id}")],
            ]

            await event.edit(text, buttons=buttons)

        except Exception as e:
            logger.error(f"Show session analytics error: {e}")
            await event.edit("❌ Error loading analytics")

    async def _show_session_automation(self, event, user_id, account_id):
        """Show session automation options"""
        try:
            await event.answer()
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                await event.edit("❌ Account not found")
                return

            automation_status = await self._get_automation_status(user_id, account_id)
            online_status = self._display_status(
                automation_status.get("online_maker")
            )
            simulation_status = self._display_status(
                automation_status.get("activity_sim")
            )
            auto_reply_status = self._display_status(
                automation_status.get("auto_reply")
            )

            text = (
                f"🤖 **Session Automation: {account['name']}**\n\n"
                "Manage the available automation features:\n\n"
                f"• Online Maker: {online_status}\n"
                f"• Activity Simulation: {simulation_status}\n"
                f"• Auto-Reply: {auto_reply_status}\n\n"
                "Use the controls below to open or toggle each feature. "
                "Group cleanup is available from Session Maintenance."
            )

            buttons = [
                [
                    Button.inline("🟢 Online Maker", f"online:toggle:{account_id}"),
                    Button.inline("🎭 Activity Sim", f"simulate:toggle:{account_id}"),
                ],
                [
                    Button.inline("🤖 Auto-Reply Settings", "auto_reply:main"),
                    Button.inline("⏰ Scheduled Messages", "schedule_msg"),
                ],
                [
                    Button.inline(
                        "🧹 Session Maintenance", f"session_bulk_ops:{account_id}"
                    ),
                ],
                [Button.inline("🔙 Back", f"session_operations:{account_id}")],
            ]

            await event.edit(text, buttons=buttons)

        except Exception as e:
            logger.error(f"Show session automation error: {e}")
            await event.edit("❌ Error loading automation")

    async def _get_session_analytics(self, user_id, account):
        """Get comprehensive session analytics"""
        try:
            if (
                user_id not in self.user_clients
                or account["name"] not in self.user_clients[user_id]
            ):
                return {"error": "Account not connected"}

            client = self.user_clients[user_id][account["name"]]
            if not client or not client.is_connected():
                return {"error": "Client not connected"}

            # Get basic info
            me = await client.get_me()
            dialogs = await client.get_dialogs()

            # Count dialog types
            stats = {"channels": 0, "groups": 0, "bots": 0, "private_chats": 0}
            for dialog in dialogs:
                entity = dialog.entity
                if isinstance(entity, User):
                    if getattr(entity, "bot", False):
                        stats["bots"] += 1
                    else:
                        stats["private_chats"] += 1
                elif isinstance(entity, Channel):
                    if getattr(entity, "broadcast", False):
                        stats["channels"] += 1
                    else:
                        stats["groups"] += 1
                elif isinstance(entity, Chat):
                    stats["groups"] += 1

            active_sessions = "Unknown"
            has_2fa = None
            try:
                from telethon.tl.functions.account import (
                    GetAuthorizationsRequest,
                    GetPasswordRequest,
                )

                authorizations = await client(GetAuthorizationsRequest())
                active_sessions = len(authorizations.authorizations)
                password_state = await client(GetPasswordRequest())
                has_2fa = bool(password_state.has_password)
            except Exception:
                logger.warning(
                    "Could not load authorization or 2FA analytics for account %s",
                    account.get("name", "Unknown"),
                    exc_info=True,
                )

            created_at = account.get("created_at")
            if isinstance(created_at, (int, float)):
                managed_since = datetime.fromtimestamp(
                    created_at, tz=timezone.utc
                ).strftime("%Y-%m-%d")
            elif isinstance(created_at, datetime):
                managed_since = created_at.strftime("%Y-%m-%d")
            else:
                managed_since = "Not recorded"

            return {
                "total_dialogs": len(dialogs),
                "managed_since": managed_since,
                "has_2fa": has_2fa,
                "active_sessions": active_sessions,
                "is_premium": getattr(me, "premium", False),
                "is_verified": getattr(me, "verified", False),
                **stats,
            }

        except Exception as e:
            logger.error(f"Get session analytics error: {e}")
            return {"error": str(e)}

    async def _get_automation_status(self, user_id, account_id):
        """Get automation status for account"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                return {}

            return {
                "online_maker": account.get("online_maker_enabled", False),
                "activity_sim": account.get("simulation_enabled", False),
                "auto_reply": account.get("auto_reply_enabled", False),
            }

        except Exception as e:
            logger.error(f"Get automation status error: {e}")
            return {}

    @staticmethod
    def _display_status(value):
        if value is True:
            return "Yes"
        if value is False:
            return "No"
        return "Unknown"

    async def _show_detailed_stats(self, event, user_id, account_id):
        try:
            account = await self._owned_account(user_id, account_id)
            if not account:
                await event.answer("❌ Account not found", alert=True)
                return
            analytics = await self._get_session_analytics(user_id, account)
            if analytics.get("error"):
                await event.answer("❌ Could not load analytics", alert=True)
                return

            text = (
                f"📊 **Detailed Stats: {account['name']}**\n\n"
                f"Dialogs: {analytics['total_dialogs']}\n"
                f"Channels: {analytics['channels']}\n"
                f"Groups: {analytics['groups']}\n"
                f"Private chats: {analytics['private_chats']}\n"
                f"Bots: {analytics['bots']}\n\n"
                f"Premium: {self._display_status(analytics['is_premium'])}\n"
                f"Verified: {self._display_status(analytics['is_verified'])}\n"
                f"2FA: {self._display_status(analytics['has_2fa'])}\n"
                f"Active sessions: {analytics['active_sessions']}\n"
                f"Managed since: {analytics['managed_since']}"
            )
            await event.answer()
            await event.edit(
                text,
                buttons=[
                    [Button.inline("🔄 Refresh", f"detailed_stats:{account_id}")],
                    [Button.inline("🔙 Back", f"session_analytics:{account_id}")],
                ],
            )
        except Exception:
            logger.exception(
                "Could not load detailed analytics for account %s", account_id
            )
            await event.answer("❌ Could not load analytics", alert=True)

    async def _export_analytics(self, event, user_id, account_id):
        try:
            account = await self._owned_account(user_id, account_id)
            if not account:
                await event.answer("❌ Account not found", alert=True)
                return
            analytics = await self._get_session_analytics(user_id, account)
            if analytics.get("error"):
                await event.answer("❌ Could not load analytics", alert=True)
                return

            report = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "account": {
                    "name": account.get("name"),
                    "phone": account.get("phone"),
                },
                "analytics": analytics,
            }
            report_file = io.BytesIO(json.dumps(report, indent=2).encode("utf-8"))
            report_file.name = f"session_analytics_{account_id}.json"
            await event.answer("Preparing report…")
            await self.bot.send_file(
                user_id, report_file, caption="📊 Session analytics export"
            )
        except Exception:
            logger.exception(
                "Could not export analytics for account %s", account_id
            )
            await self.bot.send_message(
                user_id, "❌ Could not export analytics. Check the bot logs."
            )

    async def bulk_subscribe_to_channels(
        self, user_id, account_id, channel_links, delay=5
    ):
        """Bulk subscribe to multiple channels"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if (
                not account
                or user_id not in self.user_clients
                or account["name"] not in self.user_clients[user_id]
            ):
                return {"success": False, "error": "Account not available"}

            client = self.user_clients[user_id][account["name"]]
            results = {"success": 0, "failed": 0, "errors": []}

            for channel_link in channel_links:
                try:
                    await client(JoinChannelRequest(channel_link))
                    results["success"] += 1
                    await asyncio.sleep(delay)
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(f"{channel_link}: {str(e)}")
                    logger.warning(f"Failed to subscribe to {channel_link}: {e}")

            return {
                "success": True,
                "results": results,
                "message": f"✅ Subscribed to {results['success']} channels, {results['failed']} failed",
            }

        except Exception as e:
            logger.error(f"Bulk subscribe error: {e}")
            return {"success": False, "error": str(e)}

    async def bulk_send_messages(
        self, user_id, account_id, recipients, message_text, delay=5
    ):
        """Bulk send messages to multiple recipients"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if (
                not account
                or user_id not in self.user_clients
                or account["name"] not in self.user_clients[user_id]
            ):
                return {"success": False, "error": "Account not available"}

            client = self.user_clients[user_id][account["name"]]
            results = {"success": 0, "failed": 0, "errors": []}

            for recipient in recipients:
                try:
                    await client.send_message(recipient, message_text)
                    results["success"] += 1
                    await asyncio.sleep(delay)
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(f"{recipient}: {str(e)}")
                    logger.warning(f"Failed to send message to {recipient}: {e}")

            return {
                "success": True,
                "results": results,
                "message": f"✅ Sent to {results['success']} recipients, {results['failed']} failed",
            }

        except Exception as e:
            logger.error(f"Bulk send messages error: {e}")
            return {"success": False, "error": str(e)}

    async def extract_channel_members(
        self, user_id, account_id, channel_link, limit=1000
    ):
        """Extract members from a channel/group"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if (
                not account
                or user_id not in self.user_clients
                or account["name"] not in self.user_clients[user_id]
            ):
                return {"success": False, "error": "Account not available"}

            client = self.user_clients[user_id][account["name"]]

            # Get channel entity
            entity = await client.get_entity(channel_link)
            members = []

            # Extract members
            async for user in client.iter_participants(entity, limit=limit):
                if isinstance(user, User):
                    members.append(
                        {
                            "id": user.id,
                            "username": user.username,
                            "first_name": user.first_name,
                            "last_name": user.last_name,
                            "phone": user.phone,
                            "is_bot": user.bot,
                            "is_premium": getattr(user, "premium", False),
                        }
                    )

            # Create members file
            members_json = json.dumps(members, indent=2, ensure_ascii=False)
            members_file = io.BytesIO(members_json.encode("utf-8"))
            members_file.name = (
                f"members_{channel_link.replace('@', '').replace('/', '_')}.json"
            )

            return {
                "success": True,
                "members": members,
                "file": members_file,
                "count": len(members),
            }

        except Exception as e:
            logger.error(f"Extract channel members error: {e}")
            return {"success": False, "error": str(e)}

    async def scrape_channel_messages(
        self, user_id, account_id, channel_link, limit=100, offset_date=None
    ):
        """Scrape messages from a channel"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if (
                not account
                or user_id not in self.user_clients
                or account["name"] not in self.user_clients[user_id]
            ):
                return {"success": False, "error": "Account not available"}

            client = self.user_clients[user_id][account["name"]]

            # Get channel entity
            entity = await client.get_entity(channel_link)
            messages = []

            # Scrape messages
            async for message in client.iter_messages(
                entity, limit=limit, offset_date=offset_date
            ):
                if message.message:
                    messages.append(
                        {
                            "id": message.id,
                            "date": message.date.isoformat(),
                            "text": message.message,
                            "views": getattr(message, "views", 0),
                            "forwards": getattr(message, "forwards", 0),
                            "replies": (
                                getattr(message.replies, "replies", 0)
                                if message.replies
                                else 0
                            ),
                            "sender_id": message.sender_id,
                        }
                    )

            # Create messages file
            messages_json = json.dumps(messages, indent=2, ensure_ascii=False)
            messages_file = io.BytesIO(messages_json.encode("utf-8"))
            messages_file.name = (
                f"messages_{channel_link.replace('@', '').replace('/', '_')}.json"
            )

            return {
                "success": True,
                "messages": messages,
                "file": messages_file,
                "count": len(messages),
            }

        except Exception as e:
            logger.error(f"Scrape channel messages error: {e}")
            return {"success": False, "error": str(e)}

    async def monitor_keywords(
        self, user_id, account_id, keywords, channels, duration_hours=24
    ):
        """Monitor keywords in specified channels"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if (
                not account
                or user_id not in self.user_clients
                or account["name"] not in self.user_clients[user_id]
            ):
                return {"success": False, "error": "Account not available"}

            client = self.user_clients[user_id][account["name"]]
            matches = []

            for channel_link in channels:
                try:
                    entity = await client.get_entity(channel_link)

                    # Get recent messages
                    since_date = datetime.now() - timedelta(hours=duration_hours)
                    async for message in client.iter_messages(
                        entity, limit=100, offset_date=since_date
                    ):
                        if message.message:
                            message_text = message.message.lower()
                            for keyword in keywords:
                                if keyword.lower() in message_text:
                                    matches.append(
                                        {
                                            "channel": channel_link,
                                            "keyword": keyword,
                                            "message": message.message,
                                            "date": message.date.isoformat(),
                                            "message_id": message.id,
                                            "views": getattr(message, "views", 0),
                                        }
                                    )
                except Exception as e:
                    logger.warning(f"Error monitoring {channel_link}: {e}")
                    continue

            return {
                "success": True,
                "matches": matches,
                "count": len(matches),
                "keywords": keywords,
                "channels": channels,
            }

        except Exception as e:
            logger.error(f"Monitor keywords error: {e}")
            return {"success": False, "error": str(e)}

    async def auto_leave_inactive_groups(self, user_id, account_id, days_inactive=30):
        """Leave groups with no recent activity"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if (
                not account
                or user_id not in self.user_clients
                or account["name"] not in self.user_clients[user_id]
            ):
                return {"success": False, "error": "Account not available"}

            client = self.user_clients[user_id][account["name"]]
            dialogs = await client.get_dialogs()
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_inactive)
            left_count = 0

            for dialog in dialogs:
                entity = dialog.entity
                is_group = isinstance(entity, Chat) or (
                    isinstance(entity, Channel)
                    and not getattr(entity, "broadcast", False)
                )
                dialog_date = dialog.date
                if dialog_date and dialog_date.tzinfo is None:
                    dialog_date = dialog_date.replace(tzinfo=timezone.utc)
                if is_group and dialog_date and dialog_date < cutoff_date:
                    try:
                        await client.delete_dialog(entity)
                        left_count += 1
                        await asyncio.sleep(2)
                    except Exception as e:
                        logger.warning(
                            f"Failed to leave group {entity.id}: {e}"
                        )

            return {
                "success": True,
                "left_count": left_count,
                "message": f"✅ Left {left_count} inactive groups",
            }

        except Exception as e:
            logger.error(f"Auto leave inactive groups error: {e}")
            return {"success": False, "error": str(e)}

    async def create_tdata_archive(self, user_id, account_id):
        """Create TData archive (placeholder implementation)"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if not account:
                return {"success": False, "error": "Account not found"}

            # Create temporary directory
            temp_dir = tempfile.mkdtemp()
            tdata_dir = os.path.join(temp_dir, "tdata")
            os.makedirs(tdata_dir, exist_ok=True)

            # Create basic TData structure (simplified)
            # In a real implementation, this would involve:
            # 1. Converting session to TData format
            # 2. Creating proper key files
            # 3. Setting up directory structure

            # Create placeholder files
            with open(os.path.join(tdata_dir, "key_data"), "w") as f:
                f.write("# TData key file placeholder\n")

            with open(os.path.join(tdata_dir, "settings"), "w") as f:
                f.write("# TData settings placeholder\n")

            # Create info file
            info = {
                "account_name": account["name"],
                "phone": account["phone"],
                "created_at": datetime.now().isoformat(),
                "note": "Generated by TeleGuard SessionMaster",
            }

            with open(os.path.join(tdata_dir, "info.json"), "w") as f:
                json.dump(info, f, indent=2)

            # Create ZIP archive
            zip_path = os.path.join(temp_dir, f"tdata_{account['name']}.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(tdata_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)

            return {"success": True, "zip_path": zip_path, "temp_dir": temp_dir}

        except Exception as e:
            logger.error(f"Create TData archive error: {e}")
            return {"success": False, "error": str(e)}

    async def import_contacts_from_file(self, user_id, account_id, contacts_data):
        """Import contacts from data"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )

            if (
                not account
                or user_id not in self.user_clients
                or account["name"] not in self.user_clients[user_id]
            ):
                return {"success": False, "error": "Account not available"}

            client = self.user_clients[user_id][account["name"]]

            # Prepare contacts for import
            input_contacts = []
            for i, contact in enumerate(contacts_data):
                if contact.get("phone"):
                    input_contacts.append(
                        InputPhoneContact(
                            client_id=i,
                            phone=contact["phone"],
                            first_name=contact.get("first_name", ""),
                            last_name=contact.get("last_name", ""),
                        )
                    )

            if input_contacts:
                result = await client(ImportContactsRequest(input_contacts))
                imported_count = len(result.imported)

                return {
                    "success": True,
                    "imported_count": imported_count,
                    "message": f"✅ Imported {imported_count} contacts",
                }
            else:
                return {"success": False, "error": "No valid contacts to import"}

        except Exception as e:
            logger.error(f"Import contacts error: {e}")
            return {"success": False, "error": str(e)}
