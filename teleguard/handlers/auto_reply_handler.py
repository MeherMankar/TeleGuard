"""Advanced auto-reply handler with keyword detection and analytics - FIXED VERSION"""

import asyncio
import html
import logging
import re
import time as time_module
from datetime import datetime, time

from telethon import events
from telethon.tl.custom import Button

from ..core.mongo_database import mongodb
from ..utils.crypto_utils import DataEncryption

logger = logging.getLogger(__name__)
# Constants for validation
MIN_KEYWORD_LENGTH = 2
MIN_MESSAGE_LENGTH = 5
RECONNECT_DELAY = 1.0


class AutoReplyHandler:
    """Advanced auto-reply system with keyword detection and user categorization"""

    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        self.handled_clients = set()
        self.user_keywords = {}  # Store keywords per user
        self._client_handlers = {}  # Maps client_key -> handler function for precise removal
        self.business_hours = {
            "start": time(9, 0),
            "end": time(17, 0),
            "days": [0, 1, 2, 3, 4],
        }
        self.analytics = {
            "total_messages": 0,
            "auto_replies_sent": 0,
            "keyword_hits": {},
            "unmatched_queries": 0,
        }
        self.pending_actions = {}  # Track user input states
        self.last_toggle_time = {}  # Prevent rapid toggles
        self.setup_text_handler()
        self.setup_auto_reply_menu()

    def setup_auto_reply_handlers(self):
        """Set up auto-reply handlers for all user clients — safe to call multiple times."""
        for user_id, clients in self.user_clients.items():
            asyncio.create_task(self.load_user_keywords(user_id))
            for account_name, client in clients.items():
                if client and client.is_connected():
                    # _setup_client_handler is now idempotent: it removes the old
                    # handler by reference before registering a new one, so calling
                    # this method again never stacks duplicate handlers.
                    self._setup_client_handler(user_id, account_name, client)

    async def force_cleanup_user_handlers(self, user_id: int):
        """Force cleanup all handlers for a specific user"""
        try:
            self.user_keywords.pop(user_id, None)
            clients_to_remove = [
                key for key in self.handled_clients if key.startswith(f"{user_id}:")
            ]
            for client_key in clients_to_remove:
                self.handled_clients.discard(client_key)
                # Remove the specific handler function if we have a reference
                old_handler = self._client_handlers.pop(client_key, None)
                if old_handler and user_id in self.user_clients:
                    for account_name, client in self.user_clients[user_id].items():
                        if f"{user_id}:{account_name}" == client_key:
                            try:
                                client.remove_event_handler(old_handler)
                                logger.info(f"Removed auto-reply handler for {client_key}")
                            except Exception as e:
                                logger.debug(f"Could not remove handler for {client_key}: {e}")
            logger.info(f"Force cleanup completed for user {user_id}")
        except Exception as e:
            logger.error(f"Error during force cleanup for user {user_id}: {e}")

    def _setup_client_handler(self, user_id: int, account_name: str, client):
        """Set up auto-reply handler for a specific client — idempotent."""
        client_key = f"{user_id}:{account_name}"

        # Remove any previously registered handler for this client to prevent
        # duplicate replies when this method is called more than once.
        if client_key in self._client_handlers:
            old_handler = self._client_handlers.pop(client_key)
            try:
                client.remove_event_handler(old_handler)
                logger.debug(f"Removed old auto-reply handler for {client_key}")
            except Exception as e:
                logger.debug(f"Could not remove old handler for {client_key}: {e}")
        elif client_key in self.handled_clients:
            # Handler was registered but we lost the reference — skip to avoid
            # adding a second handler on top of an unknown existing one.
            logger.info(f"Handler already exists for {client_key} (no ref), skipping")
            return

        self.handled_clients.add(client_key)
        logger.info(f"Setting up auto-reply handler for {client_key}")

        @client.on(
            events.NewMessage(
                incoming=True, func=lambda e: not e.is_group and not e.is_channel
            )
        )
        async def auto_reply_handler(event):
            try:
                # Try to find account by encrypted name first, then by plain name
                account_doc = None
                try:
                    account_doc = await mongodb.db.accounts.find_one(
                        {
                            "user_id": user_id,
                            "name_enc": DataEncryption.encrypt_field(account_name),
                        }
                    )
                except BaseException:
                    pass
                # If not found with encrypted name, try plain name
                if not account_doc:
                    account_doc = await mongodb.db.accounts.find_one(
                        {"user_id": user_id, "name": account_name}
                    )
                if not account_doc:
                    return
                account = DataEncryption.decrypt_account_data(account_doc)
                if not account.get("auto_reply_enabled", False):
                    return
                # Skip auto-reply for bots to prevent unwanted interactions
                sender = await event.get_sender()
                if sender and getattr(sender, "bot", False):
                    logger.debug(
                        f"Skipping auto-reply to bot: {sender.username or sender.id}"
                    )
                    return
                # Skip common bot usernames
                if sender and hasattr(sender, "username") and sender.username:
                    bot_usernames = ["spambot", "botfather", "userinfobot", "telegram"]
                    if (
                        sender.username.lower() in bot_usernames
                        or sender.username.lower().endswith("bot")
                    ):
                        logger.debug(
                            f"Skipping auto-reply to known bot: {sender.username}"
                        )
                        return
                settings = (
                    await mongodb.db.auto_reply_settings.find_one(
                        {"user_id": int(user_id)}
                    )
                    or {}
                )
                message_text = event.message.text.lower() if event.message.text else ""
                sender_id = event.sender_id
                self.analytics["total_messages"] += 1
                user_keywords = await self._get_user_keywords(user_id)
                matched_keyword = None
                response = None

                # Keyword replies take priority — check first
                if settings.get("keyword_replies_enabled", False) and user_keywords:
                    for keyword, reply_msg in user_keywords.items():
                        escaped_keyword = re.escape(keyword.lower())
                        try:
                            if re.search(r"\b" + escaped_keyword + r"\b", message_text):
                                matched_keyword = keyword
                                response = html.escape(reply_msg)
                                break
                        except re.error:
                            continue

                if matched_keyword:
                    self.analytics["keyword_hits"][matched_keyword] = (
                        self.analytics["keyword_hits"].get(matched_keyword, 0) + 1
                    )
                elif settings.get("time_based_replies_enabled", False):
                    # Only fire time-based reply if NO keyword matched
                    self.analytics["unmatched_queries"] += 1
                    now = datetime.now()
                    is_business_hours = self._is_business_hours(now)
                    if is_business_hours:
                        response = "I'm currently available and will respond soon."
                    else:
                        response = (
                            "I'm not available right now. I'll get back to you later."
                        )
                else:
                    return  # Nothing to reply

                contact_type = await self._get_contact_type(sender_id)
                if contact_type == "family":
                    response = "Hey! " + response
                elif contact_type == "work":
                    response = "Hi, " + response
                await event.reply(response)
                self.analytics["auto_replies_sent"] += 1
                logger.info(f"Auto-reply sent from {account_name} to {sender_id}")
            except Exception as e:
                logger.error(f"Auto-reply error for {account_name}: {e}")

        # Store the handler reference so we can remove it precisely later
        self._client_handlers[client_key] = auto_reply_handler

    async def setup_new_client_handler(self, user_id: int, account_name: str, client):
        """Set up auto-reply handler for a newly added client"""
        if client and client.is_connected():
            self._setup_client_handler(user_id, account_name, client)

    async def _get_contact_type(self, sender_id: int) -> str:
        """Determine contact type"""
        try:
            contact_data = await mongodb.db.contacts.find_one({"sender_id": sender_id})
            if contact_data:
                return contact_data.get("type", "general")
            return "general"
        except Exception as e:
            logger.error(f"Error getting contact type for {sender_id}: {e}")
            return "general"

    async def _get_user_keywords(self, user_id: int) -> dict:
        """Get user-specific keywords"""
        try:
            settings = await mongodb.db.auto_reply_settings.find_one(
                {"user_id": int(user_id)}
            )
            return settings.get("keywords", {}) if settings else {}
        except Exception as e:
            logger.error(f"Error loading keywords for user {user_id}: {e}")
            return {}

    async def _add_user_keyword(self, user_id: int, keyword: str, message: str):
        """Add keyword for specific user"""
        try:
            # Sanitize inputs
            safe_keyword = keyword.strip().lower()
            safe_message = message.strip()
            if not isinstance(user_id, int):
                raise ValueError("Invalid user_id")
            await mongodb.db.auto_reply_settings.update_one(
                {"user_id": user_id},
                {"$set": {f"keywords.{safe_keyword}": safe_message}},
                upsert=True,
            )
        except Exception as e:
            logger.error(f"Error adding keyword for user {user_id}: {e}")
            raise

    async def _remove_user_keyword(self, user_id: int, keyword: str):
        """Remove keyword for specific user"""
        try:
            safe_keyword = keyword.strip().lower()
            if not isinstance(user_id, int):
                raise ValueError("Invalid user_id")
            await mongodb.db.auto_reply_settings.update_one(
                {"user_id": user_id}, {"$unset": {f"keywords.{safe_keyword}": ""}}
            )
        except Exception as e:
            logger.error(f"Error removing keyword for user {user_id}: {e}")
            raise

    def setup_text_handler(self):
        """Setup text input handler for custom keywords"""

        @self.bot.on(events.NewMessage(pattern=r"^/clear_auto_reply$"))
        async def clear_auto_reply_command(event):
            user_id = event.sender_id
            try:
                # Emergency clear all auto-reply data
                await mongodb.db.auto_reply_settings.delete_one({"user_id": user_id})
                await mongodb.db.accounts.update_many(
                    {"user_id": user_id}, {"$unset": {"auto_reply_enabled": ""}}
                )
                # Force cleanup handlers
                await self.force_cleanup_user_handlers(user_id)
                await event.reply(
                    "✅ **Emergency Auto-Reply Clear Complete**\n\nAll auto-reply systems disabled and cleared. Old messages should stop."
                )
            except Exception as e:
                logger.error(f"Error in clear_auto_reply_command: {e}")
                await event.reply(f"❌ **Error during clear:** {str(e)}")

        @self.bot.on(events.NewMessage(pattern=r"^/force_restart_auto_reply$"))
        async def force_restart_auto_reply_command(event):
            user_id = event.sender_id
            try:
                # 1. Clear all user data
                await mongodb.db.auto_reply_settings.delete_one({"user_id": user_id})
                await mongodb.db.accounts.update_many(
                    {"user_id": user_id}, {"$unset": {"auto_reply_enabled": ""}}
                )
                # 2. Force cleanup handlers
                await self.force_cleanup_user_handlers(user_id)
                await event.reply(
                    "✅ **Force Restart Complete**\n\nAll auto-reply handlers cleared and reset. Old messages should stop now."
                )
            except Exception as e:
                await event.reply(f"❌ **Error during restart:** {str(e)}")
                logger.error(f"Force restart error: {e}")

        @self.bot.on(events.NewMessage(pattern=r"^/debug_auto_reply$"))
        async def debug_auto_reply_command(event):
            user_id = event.sender_id
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                None
            )
            settings = await mongodb.db.auto_reply_settings.find_one(
                {"user_id": user_id}
            )
            debug_text = "🔍 **Auto-Reply Debug Info**\n\n"
            debug_text += f"**Accounts ({len(accounts)}):**\n"
            for acc in accounts:
                status = acc.get("auto_reply_enabled", "NOT_SET")
                debug_text += f"• {acc.get('name', 'Unknown')}: {status}\n"
            debug_text += f"\n**Settings:** {settings}\n"
            debug_text += (
                f"**Keywords Cache:** {self.user_keywords.get(user_id, 'None')}\n"
            )
            debug_text += f"**Handled Clients:** {
                [
                    k for k in self.handled_clients if k.startswith(
                        f'{user_id}:')]}"
            await event.reply(debug_text)

        @self.bot.on(events.NewMessage(pattern=r"^/fix_duplicate_replies$"))
        async def fix_duplicate_replies_command(event):
            user_id = event.sender_id
            try:
                # Force cleanup all handlers
                await self.force_cleanup_user_handlers(user_id)
                # Disable all auto-reply temporarily
                await mongodb.db.accounts.update_many(
                    {"user_id": user_id},
                    {
                        "$unset": {
                            "auto_reply_enabled_enc": "",
                            "auto_reply_enabled": "",
                        }
                    },
                )
                await event.reply(
                    "✅ **Duplicate Reply Fix Applied**\n\nAll auto-reply handlers cleared. Please re-enable auto-reply for your accounts to avoid duplicates."
                )
            except Exception as e:
                await event.reply(f"❌ **Error fixing duplicates:** {str(e)}")
                logger.error(f"Fix duplicate replies error: {e}")

        @self.bot.on(events.NewMessage(pattern=r"^(?!/)"))
        async def handle_text_input(event):
            user_id = event.sender_id
            if user_id not in self.pending_actions:
                return
            action_data = self.pending_actions[user_id]
            text = event.message.text
            if text.lower().strip() in ["cancel", "/cancel", "stop", "/stop"]:
                del self.pending_actions[user_id]
                buttons = [
                    [Button.inline("🔙 Back to Keywords", "auto_reply:keywords")]
                ]
                await event.reply("❌ **Operation Cancelled**", buttons=buttons)
                return
            if action_data["action"] == "add_keyword":
                if action_data["step"] == "keyword":
                    raw = text.strip()

                    # Split on commas, then strip surrounding quotes/spaces from each token
                    raw_parts = [p.strip().strip("'\"").strip().lower() for p in raw.split(",")]
                    # Filter out empty or too-short tokens
                    valid_keywords = [k for k in raw_parts if len(k) >= MIN_KEYWORD_LENGTH]
                    invalid_keywords = [k for k in raw_parts if k and len(k) < MIN_KEYWORD_LENGTH]

                    if not valid_keywords:
                        await event.reply(
                            f"❌ No valid keywords found. Each keyword must be at least {MIN_KEYWORD_LENGTH} characters.\n\nPlease try again:"
                        )
                        return

                    # Store all valid keywords; warn about any that were too short
                    action_data["keywords"] = valid_keywords
                    action_data["step"] = "message"

                    kw_preview = ", ".join(f"`{k}`" for k in valid_keywords[:10])
                    if len(valid_keywords) > 10:
                        kw_preview += f" … (+{len(valid_keywords) - 10} more)"

                    warn = ""
                    if invalid_keywords:
                        warn = f"\n⚠️ Skipped (too short): {', '.join(invalid_keywords)}"

                    await event.reply(
                        f"✅ **{len(valid_keywords)} keyword(s) queued:**\n{kw_preview}{warn}\n\n"
                        f"📝 Now send the auto-reply message (minimum 5 characters):\n\n"
                        f"💡 Example: 'Thanks for your message! I'll get back to you soon.'",
                        parse_mode="markdown",
                    )
                elif action_data["step"] == "message":
                    keywords = action_data.get("keywords", [])
                    # Backwards-compat: single keyword stored as "keyword" key
                    if not keywords and action_data.get("keyword"):
                        keywords = [action_data["keyword"]]

                    if len(text.strip()) < MIN_MESSAGE_LENGTH:
                        kw_list = ", ".join(f"`{k}`" for k in keywords[:5])
                        await event.reply(
                            f"❌ Reply message too short (minimum {MIN_MESSAGE_LENGTH} characters).\n\n"
                            f"📝 Send the auto-reply message for: {kw_list}"
                        )
                        return

                    # Save each keyword individually with the same reply message
                    for kw in keywords:
                        await self._add_user_keyword(user_id, kw, text)

                    del self.pending_actions[user_id]
                    buttons = [
                        [Button.inline("🔙 Back to Keywords", "auto_reply:keywords")]
                    ]
                    message_preview = text[:50] + "..." if len(text) > 50 else text
                    kw_summary = ", ".join(f"`{k}`" for k in keywords[:8])
                    if len(keywords) > 8:
                        kw_summary += f" … (+{len(keywords) - 8} more)"
                    await event.reply(
                        f"✅ **{len(keywords)} Keyword(s) Added!**\n\n"
                        f"🔑 Keywords: {kw_summary}\n"
                        f"💬 Reply: {message_preview}",
                        buttons=buttons,
                    )

    async def _refresh_main_menu(self, event, user_id):
        """Refresh the main auto-reply menu"""
        try:
            encrypted_accounts = await mongodb.db.accounts.find(
                {"user_id": user_id}
            ).to_list(100)
            accounts = [
                DataEncryption.decrypt_account_data(acc) for acc in encrypted_accounts
            ]
            enabled_count = sum(
                1 for acc in accounts if acc.get("auto_reply_enabled", False)
            )
            total_count = len(accounts)
            settings = (
                await mongodb.db.auto_reply_settings.find_one({"user_id": user_id})
                or {}
            )
            keyword_status = (
                "🟢 On" if settings.get("keyword_replies_enabled", False) else "🔴 Off"
            )
            time_status = (
                "🟢 On"
                if settings.get("time_based_replies_enabled", False)
                else "🔴 Off"
            )
            text = "🤖 **Auto-Reply Settings**\n\n"
            text += f"📱 Accounts: {enabled_count}/{total_count} enabled\n"
            text += f"🔑 Keyword Replies: {keyword_status}\n"
            text += f"⏰ Time-based Replies: {time_status}\n\n"
            text += "Configure your automatic responses:"
            buttons = [
                [Button.inline("📱 Toggle Per Account", "auto_reply:toggle")],
                [Button.inline("🔑 Keyword Settings", "auto_reply:keyword_settings")],
                [Button.inline("⏰ Time Settings", "auto_reply:time_settings")],
                [Button.inline("📊 View Stats", "auto_reply:analytics")],
                [Button.inline("🗑️ Reset All", "auto_reply:reset")],
            ]
            await event.edit(text, buttons=buttons)
        except Exception as e:
            if "MessageNotModifiedError" not in str(e):
                logger.error(f"Error refreshing main menu: {e}")

    async def _refresh_keyword_settings(self, event, user_id):
        """Refresh the keyword settings menu"""
        try:
            settings = (
                await mongodb.db.auto_reply_settings.find_one({"user_id": user_id})
                or {}
            )
            status = (
                "🟢 Enabled"
                if settings.get("keyword_replies_enabled", False)
                else "🔴 Disabled"
            )
            toggle_text = (
                "🔴 Disable"
                if settings.get("keyword_replies_enabled", False)
                else "🟢 Enable"
            )
            buttons = [
                [
                    Button.inline(
                        f"{toggle_text} Keyword Replies", "auto_reply:toggle_keywords"
                    )
                ],
                [Button.inline("⚙️ Configure Keywords", "auto_reply:keywords")],
                [Button.inline("🔙 Back", "auto_reply:main")],
            ]
            await event.edit(
                f"🔑 **Keyword Replies**\n\nStatus: {status}\n\nKeyword-based auto-replies respond to specific words in messages.",
                buttons=buttons,
            )
        except Exception as e:
            if "MessageNotModifiedError" not in str(e):
                logger.error(f"Error refreshing keyword settings: {e}")

    async def _refresh_time_settings(self, event, user_id):
        """Refresh the time settings menu"""
        try:
            settings = (
                await mongodb.db.auto_reply_settings.find_one({"user_id": user_id})
                or {}
            )
            status = (
                "🟢 Enabled"
                if settings.get("time_based_replies_enabled", False)
                else "🔴 Disabled"
            )
            toggle_text = (
                "🔴 Disable"
                if settings.get("time_based_replies_enabled", False)
                else "🟢 Enable"
            )
            buttons = [
                [
                    Button.inline(
                        f"{toggle_text} Time-based Replies", "auto_reply:toggle_time"
                    )
                ],
                [Button.inline("🕒 View Hours", "auto_reply:hours")],
                [Button.inline("🔙 Back", "auto_reply:main")],
            ]
            await event.edit(
                f"⏰ **Time-based Replies**\n\nStatus: {status}\n\nTime-based replies respond based on business hours when no keywords match.",
                buttons=buttons,
            )
        except Exception as e:
            if "MessageNotModifiedError" not in str(e):
                logger.error(f"Error refreshing time settings: {e}")

    def setup_auto_reply_menu(self):
        """Setup auto-reply menu handlers"""
        self._register_auto_reply_callback()

    def _register_auto_reply_callback(self):
        @self.bot.on(events.CallbackQuery(pattern=r"^auto_reply:"))
        async def handle_auto_reply_menu(event):
            user_id = event.sender_id
            data = event.data.decode("utf-8")
            try:
                if data == "auto_reply:main":
                    await self._refresh_main_menu(event, user_id)
                elif data == "auto_reply:toggle":
                    await self._handle_toggle_accounts(event, user_id)
                elif data == "auto_reply:keyword_settings":
                    await self._refresh_keyword_settings(event, user_id)
                elif data == "auto_reply:time_settings":
                    await self._refresh_time_settings(event, user_id)
                elif data == "auto_reply:toggle_keywords":
                    await self._handle_toggle_keywords(event, user_id)
                elif data == "auto_reply:toggle_time":
                    await self._handle_toggle_time(event, user_id)
                elif data == "auto_reply:keywords":
                    await self._handle_keywords_menu(event, user_id)
                elif data == "auto_reply:add_keyword":
                    self.pending_actions[user_id] = {
                        "action": "add_keyword",
                        "step": "keyword",
                    }
                    buttons = [[Button.inline("❌ Cancel", "auto_reply:keywords")]]
                    await event.edit(
                        "➕ **Add New Keyword(s)**\n\n"
                        "Send one keyword **or** multiple keywords separated by commas:\n\n"
                        "**Single:** `busy`\n"
                        "**Multiple:** `hi, hello, hey, hola`\n\n"
                        "💡 Quotes are optional — `'hi', 'hello'` and `hi, hello` both work.\n"
                        "All keywords will share the same auto-reply message.\n\n"
                        "📝 Type 'cancel' to abort",
                        buttons=buttons,
                    )
                elif data == "auto_reply:remove_keyword":
                    await self._handle_remove_keyword_menu(event, user_id)
                elif data.startswith("auto_reply:delete:"):
                    await self._handle_delete_keyword(event, user_id, data)
                elif data == "auto_reply:analytics":
                    await self._handle_analytics(event)
                elif data == "auto_reply:hours":
                    await self._handle_hours(event)
                elif data.startswith("auto_reply:toggle_account:"):
                    await self._handle_toggle_account(event, user_id, data)
                elif data == "auto_reply:reset":
                    await self._handle_reset(event, user_id)
            except Exception as e:
                if "MessageNotModifiedError" not in str(
                    e
                ) and "Content of the message was not modified" not in str(e):
                    logger.error(f"Error in auto-reply menu handler: {e}")
                    # Show error to user for debugging
                    try:
                        await event.answer(f"❌ Error: {str(e)[:100]}")
                    except Exception as answer_error:
                        logger.error(f"Failed to send error message: {answer_error}")

    async def load_user_keywords(self, user_id: int):
        """Load user's custom keywords from database"""
        try:
            settings = await mongodb.db.auto_reply_settings.find_one(
                {"user_id": user_id}
            )
            if settings and "keywords" in settings:
                self.user_keywords[user_id] = settings["keywords"]
        except Exception as e:
            logger.error(f"Error loading keywords for user {user_id}: {e}")

    def _is_business_hours(self, current_time: datetime = None) -> bool:
        """Check if currently in business hours"""
        if current_time is None:
            current_time = datetime.now()
        return (
            current_time.weekday() in self.business_hours["days"]
            and self.business_hours["start"]
            <= current_time.time()
            <= self.business_hours["end"]
        )

    async def _handle_toggle_accounts(self, event, user_id):
        encrypted_accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        if encrypted_accounts:
            accounts = [DataEncryption.decrypt_account_data(acc) for acc in encrypted_accounts]
            buttons = []
            for account in accounts:
                acc_name = account.get('name')
                if not acc_name:
                    continue
                status = "🟢" if account.get("auto_reply_enabled", False) else "🔴"
                buttons.append([Button.inline(f"{status} {acc_name}", f"auto_reply:toggle_account:{acc_name}")])
            buttons.append([Button.inline("🔙 Back", "auto_reply:main")])
            await event.edit("📱 **Select Account to Toggle Auto-Reply:**", buttons=buttons)
        else:
            await event.answer("No accounts found!")

    async def _handle_toggle_keywords(self, event, user_id):
        settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
        new_status = not settings.get("keyword_replies_enabled", False)
        await mongodb.db.auto_reply_settings.update_one({"user_id": user_id}, {"$set": {"keyword_replies_enabled": new_status}}, upsert=True)
        status_text = "enabled" if new_status else "disabled"
        await event.answer(f"Keyword replies {status_text}!")
        await self._refresh_keyword_settings(event, user_id)

    async def _handle_toggle_time(self, event, user_id):
        settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
        new_status = not settings.get("time_based_replies_enabled", False)
        await mongodb.db.auto_reply_settings.update_one({"user_id": user_id}, {"$set": {"time_based_replies_enabled": new_status}}, upsert=True)
        status_text = "enabled" if new_status else "disabled"
        await event.answer(f"Time-based replies {status_text}!")
        await self._refresh_time_settings(event, user_id)

    async def _handle_keywords_menu(self, event, user_id):
        user_keywords = await self._get_user_keywords(user_id)
        if user_keywords:
            keyword_list = "\n".join([f"• {k}: {v[:50]}..." for k, v in user_keywords.items()])
        else:
            keyword_list = "No keywords configured."
        buttons = [
            [Button.inline("➕ Add Keyword", "auto_reply:add_keyword")],
            [Button.inline("➖ Remove Keyword", "auto_reply:remove_keyword")],
            [Button.inline("🔙 Back", "auto_reply:main")],
        ]
        await event.edit(f"🔑 **Active Keywords:**\n\n{keyword_list}", buttons=buttons)

    async def _handle_remove_keyword_menu(self, event, user_id):
        user_keywords = await self._get_user_keywords(user_id)
        if user_keywords:
            buttons = [[Button.inline(f"❌ {k}", f"auto_reply:delete:{k}")] for k in user_keywords.keys()]
            buttons.append([Button.inline("🔙 Back", "auto_reply:keywords")])
            await event.edit("➖ **Remove Keyword**\n\nSelect keyword to delete:", buttons=buttons)
        else:
            await event.edit("⚠️ No keywords to remove.", buttons=[[Button.inline("🔙 Back", "auto_reply:keywords")]])

    async def _handle_delete_keyword(self, event, user_id, data):
        keyword = data.split(":", 2)[2]
        user_keywords = await self._get_user_keywords(user_id)
        if keyword in user_keywords:
            await self._remove_user_keyword(user_id, keyword)
            await event.edit(f"✅ Keyword '{keyword}' removed!", buttons=[[Button.inline("🔙 Back", "auto_reply:keywords")]])
        else:
            await event.edit("❌ Keyword not found.", buttons=[[Button.inline("🔙 Back", "auto_reply:keywords")]])

    async def _handle_analytics(self, event):
        stats = "📊 **Auto-Reply Analytics**\n\n"
        stats += f"📨 Total Messages: {self.analytics['total_messages']}\n"
        stats += f"🤖 Auto-Replies Sent: {self.analytics['auto_replies_sent']}\n"
        stats += f"❓ Unmatched Queries: {self.analytics['unmatched_queries']}\n\n"
        stats += "🔑 **Keyword Hits:**\n"
        for keyword, count in self.analytics["keyword_hits"].items():
            stats += f"• {keyword}: {count}\n"
        buttons = [[Button.inline("🔙 Back", "auto_reply:main")]]
        await event.edit(stats, buttons=buttons)

    async def _handle_hours(self, event):
        current_hours = f"{self.business_hours['start'].strftime('%H:%M')} - {self.business_hours['end'].strftime('%H:%M')}"
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        active_days = ", ".join([days[i] for i in self.business_hours["days"]])
        text = "🕒 **Availability Hours**\n\n"
        text += f"⏰ Hours: {current_hours}\n"
        text += f"📅 Days: {active_days}\n\n"
        text += "During these hours, responses will indicate availability."
        buttons = [[Button.inline("🔙 Back", "auto_reply:main")]]
        await event.edit(text, buttons=buttons)

    async def _handle_toggle_account(self, event, user_id, data):
        account_name = data.replace("auto_reply:toggle_account:", "", 1)
        current_time = time_module.time()
        toggle_key = f"{user_id}:{account_name}"
        if toggle_key in self.last_toggle_time:
            if current_time - self.last_toggle_time[toggle_key] < 2:
                await event.answer("⏳ Please wait before toggling again...")
                return
        self.last_toggle_time[toggle_key] = current_time
        try:
            account_doc = None
            try:
                account_doc = await mongodb.db.accounts.find_one({"user_id": user_id, "name_enc": DataEncryption.encrypt_field(account_name)})
            except BaseException:
                pass
            if not account_doc:
                account_doc = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            if account_doc:
                account = DataEncryption.decrypt_account_data(account_doc)
                current_status = account.get("auto_reply_enabled", False)
                new_status = not current_status
                update_query = {"user_id": user_id}
                if "name_enc" in account_doc:
                    update_query["name_enc"] = account_doc["name_enc"]
                    update_data = {"$set": {"auto_reply_enabled_enc": DataEncryption.encrypt_field(new_status)}}
                else:
                    update_query["name"] = account_name
                    update_data = {"$set": {"auto_reply_enabled": new_status}}
                result = await mongodb.db.accounts.update_one(update_query, update_data)
                if result.modified_count > 0:
                    logger.info(f"Auto-reply toggle for {account_name}: {current_status} -> {new_status}")
                    status_text = "🟢 enabled" if new_status else "🔴 disabled"
                    await event.answer(f"Auto-reply {status_text} for {account_name}!")
                    encrypted_accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(100)
                    accounts = [DataEncryption.decrypt_account_data(acc) for acc in encrypted_accounts]
                    buttons = []
                    for acc in accounts:
                        acc_name = acc.get('name')
                        if not acc_name:
                            continue
                        acc_status = acc.get("auto_reply_enabled", False)
                        status_icon = "🟢" if acc_status else "🔴"
                        buttons.append([Button.inline(f"{status_icon} {acc_name}", f"auto_reply:toggle_account:{acc_name}")])  
                    buttons.append([Button.inline("🔙 Back", "auto_reply:main")])
                    try:
                        await event.edit("📱 **Select Account to Toggle Auto-Reply:**", buttons=buttons)
                    except Exception as edit_error:
                        if "MessageNotModifiedError" not in str(edit_error) and "Content of the message was not modified" not in str(edit_error):
                            logger.error(f"Error refreshing account list: {edit_error}")
                else:
                    await event.answer("❌ Failed to update account status")
                    logger.error(f"Database update failed for account {account_name}")
            else:
                await event.answer("❌ Account not found!")
                logger.warning(f"Account {account_name} not found for user {user_id}")
        except Exception as toggle_error:
            logger.error(f"Error toggling auto-reply for {account_name}: {toggle_error}")
            await event.answer("❌ Error toggling auto-reply")

    async def _handle_reset(self, event, user_id):
        try:
            await mongodb.db.auto_reply_settings.delete_one({"user_id": user_id})
            await mongodb.db.accounts.update_many({"user_id": user_id}, {"$unset": {"auto_reply_enabled_enc": "", "auto_reply_enabled": ""}})
            await self.force_cleanup_user_handlers(user_id)
            await event.edit("✅ **Complete Auto-Reply Reset**\n\nAll settings, keywords, and handlers cleared. Duplicate replies should stop now.", buttons=[[Button.inline("🔙 Back", "auto_reply:main")]])
        except Exception as reset_error:
            logger.error(f"Error during auto-reply reset for user {user_id}: {reset_error}")
            await event.answer("❌ Error during reset")
