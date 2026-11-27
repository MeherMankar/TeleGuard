"""Backup and restore handler"""

import asyncio
import binascii
import io
import json
import logging
import struct
import time
from datetime import datetime, timezone

from telethon import Button, TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from ..core.config import MAX_ACCOUNTS, config
from ..core.mongo_database import mongodb
from ..core.otp_protection import otp_expiry_fields
from ..utils.crypto_utils import DataEncryption

logger = logging.getLogger(__name__)


class BackupRestore:
    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager
        self.pending_restore_users = set()

    def register_handlers(self):
        """Register backup/restore handlers"""
        self.bot.add_event_handler(
            self._show_backup_menu, events.CallbackQuery(pattern=r"^backup_menu$")
        )
        self.bot.add_event_handler(
            self._create_backup, events.CallbackQuery(pattern=r"^backup_create$")
        )
        self.bot.add_event_handler(
            self._create_fresh_backup, events.CallbackQuery(pattern=r"^backup_create_fresh$")
        )
        self.bot.add_event_handler(
            self._begin_restore, events.CallbackQuery(pattern=r"^backup_restore$")
        )
        self.bot.add_event_handler(
            self._cancel_restore, events.CallbackQuery(pattern=r"^backup_cancel$")
        )
        self.bot.add_event_handler(
            self._handle_restore_upload, events.NewMessage(incoming=True)
        )
        logger.info("Backup/restore handlers registered")

    async def _show_backup_menu(self, event):
        """Show backup menu"""
        if hasattr(event, "answer"):
            await event.answer()
        buttons = [
            [Button.inline("💾 Backup (current sessions)", "backup_create")],
            [Button.inline("🔄 Backup (fresh sessions)", "backup_create_fresh")],
            [Button.inline("📥 Restore Backup", "backup_restore")],
            [Button.inline("🔙 Back", "menu:main")],
        ]

        await event.edit(
            "💾 **Backup & Restore**\n\n"
            "**Current sessions** — exports existing session strings as-is.\n"
            "**Fresh sessions** — re-authenticates each account via auto-OTP "
            "and stored 2FA to create brand-new session strings.\n\n"
            "Select an option:",
            buttons=buttons,
        )

    # ------------------------------------------------------------------ #
    #  Fresh-session backup                                                #
    # ------------------------------------------------------------------ #

    async def _create_fresh_backup(self, event):
        """Create backup by re-authenticating each account to get a fresh session."""
        user_id = event.sender_id
        await event.answer()

        session_login = getattr(self.bot_manager, "session_login_handler", None)
        if session_login is None:
            await event.edit("❌ Session login handler not available.")
            return

        accounts = await mongodb.db.accounts.find(
            {"user_id": user_id, "is_active": True}
        ).to_list(length=None)

        if not accounts:
            await event.edit("❌ No active accounts found to back up.")
            return

        decrypted = [DataEncryption.decrypt_account_data(acc) for acc in accounts]

        await event.edit(
            f"🔄 **Fresh-Session Backup**\n\n"
            f"Re-authenticating {len(decrypted)} account(s).\n"
            f"This will request a new OTP for each account and use your "
            f"stored 2FA passwords automatically.\n\n"
            f"⏳ Starting..."
        )

        backup_accounts = []
        results = {"ok": 0, "failed": 0, "skipped": 0}

        for acc in decrypted:
            phone = acc.get("phone", "")
            name = acc.get("name", phone)
            try:
                await self.bot.send_message(
                    user_id, f"🔐 Re-authenticating **{name}** ({phone})..."
                )
                session_string, reason = await self._fresh_session_for_account(
                    user_id, phone, name, session_login
                )
                if session_string:
                    backup_accounts.append(
                        {
                            "name": name,
                            "phone": phone,
                            "session_string": session_string,
                            "is_active": True,
                        }
                    )
                    results["ok"] += 1
                    await self.bot.send_message(
                        user_id, f"✅ **{name}** — fresh session created."
                    )
                else:
                    # Fall back to existing session string
                    existing = acc.get("session_string")
                    reason_text = f"\nReason: _{reason}_" if reason else ""
                    if existing:
                        backup_accounts.append(
                            {
                                "name": name,
                                "phone": phone,
                                "session_string": existing,
                                "is_active": True,
                            }
                        )
                        results["skipped"] += 1
                        await self.bot.send_message(
                            user_id,
                            f"⚠️ **{name}** — could not create fresh session, "
                            f"using existing session string.{reason_text}",
                        )
                    else:
                        results["failed"] += 1
                        await self.bot.send_message(
                            user_id,
                            f"❌ **{name}** — skipped (no session available).{reason_text}",
                        )
            except Exception:
                logger.exception(
                    "Fresh session backup failed for %s (user %s)", phone, user_id
                )
                existing = acc.get("session_string")
                if existing:
                    backup_accounts.append(
                        {
                            "name": name,
                            "phone": phone,
                            "session_string": existing,
                            "is_active": True,
                        }
                    )
                    results["skipped"] += 1
                    await self.bot.send_message(
                        user_id,
                        f"⚠️ **{name}** — error during re-auth, "
                        f"falling back to existing session.",
                    )
                else:
                    results["failed"] += 1
                    await self.bot.send_message(
                        user_id, f"❌ **{name}** — failed, no fallback available."
                    )

        if not backup_accounts:
            await self.bot.send_message(
                user_id, "❌ No accounts could be backed up."
            )
            return

        created_at = datetime.now(timezone.utc)
        backup_data = {
            "version": "2.0",
            "created_at": created_at.isoformat(),
            "user_id": user_id,
            "backup_type": "fresh_sessions",
            "accounts": backup_accounts,
        }

        from telethon.tl.types import DocumentAttributeFilename

        backup_file = io.BytesIO(
            json.dumps(backup_data, indent=2).encode("utf-8")
        )
        backup_file.name = f"teleguard_fresh_backup_{int(time.time())}.json"
        await self.bot.send_file(
            user_id,
            backup_file,
            caption=(
                f"💾 **Fresh-Session Backup Created**\n\n"
                f"✅ Fresh sessions: {results['ok']}\n"
                f"⚠️ Fallback (existing): {results['skipped']}\n"
                f"❌ Failed: {results['failed']}\n"
                f"📅 Date: {created_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                f"⚠️ Keep this file secure!"
            ),
            attributes=[DocumentAttributeFilename(backup_file.name)],
        )

    async def _fresh_session_for_account(
        self,
        user_id: int,
        phone: str,
        account_name: str,
        session_login,
    ):
        """
        Re-authenticate one account to produce a fresh session string.

        Uses the same mechanism as session_login_handler:
          1. Temporarily disable OTP destroyer and set OTP bypass allowlist
          2. Request OTP via send_code_request on a fresh client
          3. Auto-fetch OTP from connected accounts (777000), only accepting
             messages that arrived AFTER the OTP was requested (avoids picking
             up a stale code from the previous account's login flow)
          4. Sign in; if 2FA needed, try stored password from DB
          5. Restore OTP destroyer state and clean up

        Returns (session_string, failure_reason):
          - (str, None)  on success
          - (None, str)  on failure, where failure_reason is a human-readable string
        """
        client = None
        account = None
        destroyer_was_enabled = False

        try:
            # Step 1: prepare (disable OTP destroyer, add bypass allowlist entry)
            account = await session_login._prepare_session_creation(user_id, phone)
            if account:
                destroyer_was_enabled = account.get("otp_destroyer_enabled", False)

            # Record the time just before requesting the OTP so we can filter
            # out any stale codes that were already sitting in the inbox.
            import time as _time
            otp_request_time = _time.time()

            # Step 2: request OTP
            client, phone_code_hash = await session_login._request_otp_code(phone)
            if not client or not phone_code_hash:
                logger.warning("Could not request OTP for %s", phone)
                return None, "OTP request failed — Telegram did not return a code hash"

            # Step 3: fetch OTP from connected accounts, only messages newer than
            # the moment we fired send_code_request.
            otp_code = None
            for attempt in range(15):
                otp_code = await self._fetch_otp_after(
                    session_login, user_id, phone, otp_request_time
                )
                if otp_code:
                    break
                await asyncio.sleep(2)

            if not otp_code:
                # Fallback: widen the window to 5 minutes but still require the
                # code to be newer than otp_request_time.
                otp_code = await self._fetch_otp_after(
                    session_login, user_id, phone, otp_request_time, window=300
                )

            if not otp_code:
                logger.warning("Could not auto-fetch OTP for %s", phone)
                return None, "OTP not received — no Telegram code appeared within 30s"

            # Step 4: sign in with OTP
            try:
                await client.sign_in(phone, otp_code, phone_code_hash=phone_code_hash)
                session_string = StringSession.save(client.session)
                return session_string, None

            except SessionPasswordNeededError:
                # Try stored 2FA password from DB
                from ..utils.twofa_helper import twofa_helper

                success, session_str, error = await twofa_helper.try_sign_in_with_2fa(
                    client, user_id, phone
                )
                if success:
                    return session_str, None
                if error == "no_stored_password":
                    return None, (
                        "2FA password not stored — open Account Settings → "
                        "2FA Settings and save the password first"
                    )
                if error == "stored_password_invalid":
                    return None, (
                        "Stored 2FA password is wrong (changed externally) — "
                        "update it in Account Settings → 2FA Settings"
                    )
                return None, f"2FA sign-in failed: {error}"

        finally:
            # Step 5: always clean up regardless of success/failure
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            if account:
                try:
                    await session_login._cleanup_session_creation(
                        account, destroyer_was_enabled, user_id
                    )
                except Exception:
                    logger.debug("Cleanup error for %s", phone)

    @staticmethod
    async def _fetch_otp_after(
        session_login, user_id: int, phone: str, after_ts: float, window: float = 30
    ):
        """
        Fetch the OTP for `phone` from 777000 messages that arrived after
        `after_ts` (Unix timestamp).  Wraps session_login's OTP fetchers but
        adds a time-based filter so we never use a code from a previous login.
        """
        import re
        import time as _time

        if user_id not in session_login.user_clients:
            return None

        phone_clean = phone.replace("+", "")
        current_time = _time.time()

        for client in session_login.user_clients[user_id].values():
            if not client or not client.is_connected():
                continue
            try:
                messages = await asyncio.wait_for(
                    client.get_messages(777000, limit=10), timeout=10.0
                )
                for msg in messages:
                    if not msg.message or not hasattr(msg, "date"):
                        continue
                    msg_ts = msg.date.timestamp()
                    # Only consider messages that arrived after we requested the OTP
                    # and within the allowed look-back window.
                    if msg_ts < after_ts or (current_time - msg_ts) > window:
                        continue
                    text = msg.message
                    text_lower = text.lower()
                    if "login code" not in text_lower and "код" not in text_lower:
                        continue
                    match = re.search(r"Login code:\s*(\d{4,6})", text)
                    if not match:
                        match = re.search(r"\b(\d{5})\b", text)
                    if match:
                        code = match.group(1)
                        logger.info(
                            "Fresh OTP %s for %s (msg age %.1fs)",
                            code, phone, current_time - msg_ts
                        )
                        return code
            except Exception as e:
                logger.debug("OTP fetch error for %s: %s", phone, e)
        return None

    # ------------------------------------------------------------------ #
    #  Restore                                                             #
    # ------------------------------------------------------------------ #

    async def _begin_restore(self, event):
        user_id = event.sender_id
        self.pending_restore_users.add(user_id)
        await event.answer()
        await event.edit(
            "📥 **Restore Backup**\n\n"
            "Upload a TeleGuard JSON backup created for this Telegram account. "
            "Existing accounts are skipped and never overwritten.\n\n"
            "You can send /cancel to stop.",
            buttons=[[Button.inline("Cancel", "backup_cancel")]],
        )

    async def _cancel_restore(self, event):
        self.pending_restore_users.discard(event.sender_id)
        await event.answer("Restore cancelled")
        await self._show_backup_menu(event)

    async def _handle_restore_upload(self, event):
        user_id = event.sender_id
        if user_id not in self.pending_restore_users or not event.is_private:
            return

        if event.raw_text and event.raw_text.strip().lower() == "/cancel":
            self.pending_restore_users.discard(user_id)
            await event.reply("Backup restore cancelled.")
            return

        uploaded_file = event.file
        if not uploaded_file:
            await event.reply("Upload a `.json` backup file, or send /cancel.")
            return

        if (
            not uploaded_file.name
            or not uploaded_file.name.lower().endswith(".json")
            or uploaded_file.size is None
            or uploaded_file.size > 2 * 1024 * 1024
        ):
            self.pending_restore_users.discard(user_id)
            await event.reply("The backup must be a JSON file no larger than 2 MB.")
            return

        try:
            contents = await event.message.download_media(file=bytes)
            if not isinstance(contents, bytes):
                raise ValueError("Could not read the uploaded file")
            backup = json.loads(contents.decode("utf-8"))
            accounts = self._validate_backup(backup, user_id)
            result = await self._restore_accounts(user_id, accounts)
            self.pending_restore_users.discard(user_id)
            await event.reply(
                "✅ Restore finished.\n"
                f"Imported: {result['restored']}\n"
                f"Already present: {result['skipped']}\n"
                f"Could not connect (account saved for retry): {result['failed']}"
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
            self.pending_restore_users.discard(user_id)
            logger.info("Rejected invalid backup upload from user %s: %s", user_id, e)
            await event.reply(f"❌ Backup could not be restored: {e}")
        except Exception:
            self.pending_restore_users.discard(user_id)
            logger.exception("Backup restore failed for user %s", user_id)
            await event.reply("❌ Backup restore failed. Check the bot logs.")

    @staticmethod
    def _validate_backup(backup, user_id):
        if not isinstance(backup, dict) or backup.get("version") != "2.0":
            raise ValueError("Unsupported backup format.")
        backup_user_id = backup.get("user_id")
        if type(backup_user_id) is not int or backup_user_id != user_id:
            raise ValueError("This backup belongs to a different Telegram account.")

        accounts = backup.get("accounts")
        if not isinstance(accounts, list) or len(accounts) > MAX_ACCOUNTS:
            raise ValueError("Backup contains an invalid number of accounts.")

        validated = []
        seen_phones = set()
        for account in accounts:
            if not isinstance(account, dict):
                raise ValueError("Backup contains an invalid account record.")

            name = account.get("name")
            phone = account.get("phone")
            session_string = account.get("session_string")
            if (
                not isinstance(name, str)
                or not name.strip()
                or len(name) > 100
                or not isinstance(phone, str)
                or not phone.strip()
                or len(phone) > 40
                or not isinstance(session_string, str)
                or len(session_string) < 50
                or len(session_string) > 4096
            ):
                raise ValueError("Backup contains incomplete account data.")

            phone = phone.strip()
            name = name.strip()
            if phone in seen_phones:
                raise ValueError("Backup contains duplicate phone numbers.")
            seen_phones.add(phone)

            try:
                StringSession(session_string)
            except (
                binascii.Error,
                IndexError,
                struct.error,
                TypeError,
                ValueError,
            ) as e:
                raise ValueError("Backup contains an invalid session.") from e

            is_active = account.get("is_active", True)
            if not isinstance(is_active, bool):
                raise ValueError("Backup contains an invalid account status.")
            validated.append(
                {
                    "name": name,
                    "phone": phone,
                    "session_string": session_string,
                    "is_active": is_active,
                }
            )
        return validated

    async def _restore_accounts(self, user_id, accounts):
        existing_accounts = await mongodb.db.accounts.find(
            {"user_id": user_id}
        ).to_list(length=MAX_ACCOUNTS + 1)

        existing_phones = {account.get("phone") for account in existing_accounts}
        existing_names = {account.get("name") for account in existing_accounts}
        to_restore = []
        for account in accounts:
            if account["phone"] in existing_phones:
                continue
            name = account["name"]
            if name in existing_names:
                name = f"{name} ({account['phone'][-4:]})"
            if name in existing_names:
                raise ValueError(
                    "Backup contains account names that cannot be made unique."
                )
            existing_names.add(name)
            existing_phones.add(account["phone"])
            to_restore.append({**account, "name": name})

        if len(existing_accounts) + len(to_restore) > MAX_ACCOUNTS:
            raise ValueError(f"Account limit ({MAX_ACCOUNTS}) would be exceeded.")

        result = {
            "restored": 0,
            "skipped": len(accounts) - len(to_restore),
            "failed": 0,
        }
        for account in to_restore:
            account_data = {
                "user_id": user_id,
                "phone": account["phone"],
                "name": account["name"],
                "session_string": account["session_string"],
                "is_active": account["is_active"],
                "otp_destroyer_enabled": False,
                "added_via": "backup_restore",
                "created_at": int(time.time()),
            }
            insert = await mongodb.db.accounts.insert_one(
                DataEncryption.encrypt_account_data(account_data)
            )
            if not account["is_active"]:
                result["restored"] += 1
                continue
            try:
                await self.bot_manager.start_user_client(
                    user_id, account["name"], account["session_string"]
                )
                client = self.bot_manager.user_clients.get(user_id, {}).get(
                    account["name"]
                )
                if not client or not client.is_connected():
                    raise RuntimeError("Account client did not connect")
                result["restored"] += 1
            except Exception:
                result["failed"] += 1
                logger.exception(
                    "Could not start restored account %s for user %s",
                    account["name"],
                    user_id,
                )
                await mongodb.db.accounts.update_one(
                    {"_id": insert.inserted_id, "user_id": user_id},
                    {
                        "$set": {
                            "is_active": False,
                            "reauth_required": True,
                        }
                    },
                )
        return result

    # ------------------------------------------------------------------ #
    #  Current-session backup (original behaviour)                        #
    # ------------------------------------------------------------------ #

    async def _create_backup(self, event):
        """Create backup using existing session strings (no re-auth)."""
        user_id = event.sender_id

        try:
            await event.edit("⏳ Creating backup...")

            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )
            created_at = datetime.now(timezone.utc)

            backup_data = {
                "version": "2.0",
                "created_at": created_at.isoformat(),
                "user_id": user_id,
                "backup_type": "current_sessions",
                "accounts": [],
            }

            for acc in accounts:
                acc = DataEncryption.decrypt_account_data(acc)
                is_active = acc.get("is_active", True)
                if not isinstance(is_active, bool):
                    is_active = False
                backup_data["accounts"].append(
                    {
                        "name": acc.get("name"),
                        "phone": acc.get("phone"),
                        "session_string": acc.get("session_string"),
                        "is_active": is_active,
                    }
                )

            from telethon.tl.types import DocumentAttributeFilename

            backup_file = io.BytesIO(
                json.dumps(backup_data, indent=2).encode("utf-8")
            )
            backup_file.name = f"teleguard_backup_{int(time.time())}.json"
            await self.bot.send_file(
                user_id,
                backup_file,
                caption=(
                    f"💾 **Backup Created**\n\n"
                    f"📊 Accounts: {len(accounts)}\n"
                    f"📅 Date: {created_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                    f"⚠️ Keep this file secure!"
                ),
                attributes=[DocumentAttributeFilename(backup_file.name)],
            )

            await event.edit("✅ Backup created and sent!")
        except Exception as e:
            logger.error(f"Backup error: {e}")
            await event.edit(f"❌ Backup failed: {str(e)}")

