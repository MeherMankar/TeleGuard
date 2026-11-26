"""Backup and restore handler"""

import binascii
import io
import json
import logging
import struct
import time
from datetime import datetime, timezone

from telethon import Button, events
from telethon.sessions import StringSession

from ..core.config import MAX_ACCOUNTS
from ..core.mongo_database import mongodb
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
            [Button.inline("💾 Create Backup", "backup_create")],
            [Button.inline("📥 Restore Backup", "backup_restore")],
            [Button.inline("🔙 Back", "menu:main")],
        ]

        await event.edit(
            "💾 **Backup & Restore**\n\n"
            "Create and restore account-session backups.\n\n"
            "Select an option:",
            buttons=buttons,
        )

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

    async def _create_backup(self, event):
        """Create backup"""
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
