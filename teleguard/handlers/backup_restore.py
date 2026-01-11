"""Backup and restore handler"""

import json
import logging
import tempfile
from datetime import datetime

from telethon import Button, events

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class BackupRestore:
    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager

    def register_handlers(self):
        """Register backup/restore handlers"""
        self.bot.add_event_handler(
            self._show_backup_menu, events.CallbackQuery(pattern=r"^backup_menu$")
        )
        self.bot.add_event_handler(
            self._create_backup, events.CallbackQuery(pattern=r"^backup_create$")
        )
        logger.info("Backup/restore handlers registered")

    async def _show_backup_menu(self, event):
        """Show backup menu"""
        buttons = [
            [Button.inline("💾 Create Backup", "backup_create")],
            [Button.inline("📥 Restore Backup", "backup_restore")],
            [Button.inline("🔙 Back", "menu:main")],
        ]

        await event.edit(
            "💾 **Backup & Restore**\n\n"
            "Create backups of your accounts and settings.\n\n"
            "Select an option:",
            buttons=buttons,
        )

    async def _create_backup(self, event):
        """Create backup"""
        user_id = event.sender_id

        try:
            await event.edit("⏳ Creating backup...")

            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            backup_data = {
                "version": "2.0",
                "created_at": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "accounts": [],
            }

            for acc in accounts:
                backup_data["accounts"].append(
                    {
                        "name": acc.get("name"),
                        "phone": acc.get("phone"),
                        "session_string": acc.get("session_string"),
                        "is_active": acc.get("is_active"),
                    }
                )

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(backup_data, f, indent=2)
                backup_file = f.name

            from telethon.tl.types import DocumentAttributeFilename

            await self.bot.send_file(
                user_id,
                backup_file,
                caption=(
                    f"💾 **Backup Created**\n\n"
                    f"📊 Accounts: {len(accounts)}\n"
                    f"📅 Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"⚠️ Keep this file secure!"
                ),
                attributes=[
                    DocumentAttributeFilename(
                        f"teleguard_backup_{int(datetime.utcnow().timestamp())}.json"
                    )
                ],
            )

            import os

            os.remove(backup_file)

            await event.edit("✅ Backup created and sent!")
        except Exception as e:
            logger.error(f"Backup error: {e}")
            await event.edit(f"❌ Backup failed: {str(e)}")
