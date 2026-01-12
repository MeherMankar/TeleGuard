"""Contact synchronization between Telegram and local database"""

import logging

from telethon.tl.types import User

from .contact_db import ContactDB
from .contact_models import Contact

logger = logging.getLogger(__name__)


class ContactSync:
    """Handle contact synchronization"""

    @staticmethod
    async def sync_from_telegram(client, managed_by_account: str) -> dict:
        """Sync contacts from Telegram to local database"""
        try:
            telegram_contacts = await client.get_contacts()
            added, updated, errors = 0, 0, 0
            for tg_contact in telegram_contacts:
                if not isinstance(tg_contact, User):
                    continue
                try:
                    result = await ContactSync._sync_single_contact(tg_contact, managed_by_account)
                    if result == "added":
                        added += 1
                    elif result == "updated":
                        updated += 1
                    elif result == "error":
                        errors += 1
                except Exception as e:
                    logger.error(f"Error syncing contact {tg_contact.id}: {e}")
                    errors += 1
            return {"success": True, "added": added, "updated": updated, "errors": errors, "total_telegram": len(telegram_contacts)}
        except Exception as e:
            logger.error(f"Error syncing from Telegram: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def sync_to_telegram(client, managed_by_account: str) -> dict:
        """Sync local contacts to Telegram"""
        try:
            local_contacts = await ContactDB.get_all_contacts(
                managed_by_account, limit=1000
            )
            telegram_contacts = await client.get_contacts()
            telegram_ids = {
                contact.id for contact in telegram_contacts if isinstance(contact, User)
            }
            added = 0
            errors = 0
            for local_contact in local_contacts:
                if local_contact.user_id not in telegram_ids:
                    try:
                        # Try to add contact to Telegram
                        if local_contact.username:
                            await client.add_contact(local_contact.username)
                        elif local_contact.phone:
                            await client.add_contact(local_contact.phone)
                        else:
                            # Skip contacts without username or phone
                            continue
                        added += 1
                    except Exception as e:
                        logger.error(
                            f"Error adding contact {
                                local_contact.user_id} to Telegram: {e}"
                        )
                        errors += 1
            return {
                "success": True,
                "added": added,
                "errors": errors,
                "total_local": len(local_contacts),
            }
        except Exception as e:
            logger.error(f"Error syncing to Telegram: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def two_way_sync(client, managed_by_account: str) -> dict:
        """Perform two-way synchronization"""
        try:
            # First sync from Telegram
            from_result = await ContactSync.sync_from_telegram(
                client, managed_by_account
            )
            # Then sync to Telegram
            to_result = await ContactSync.sync_to_telegram(client, managed_by_account)
            return {
                "success": from_result["success"] and to_result["success"],
                "from_telegram": from_result,
                "to_telegram": to_result,
            }
        except Exception as e:
            logger.error(f"Error in two-way sync: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def _sync_single_contact(tg_contact, managed_by_account: str) -> str:
        """Sync a single contact, returns 'added', 'updated', 'error', or 'skipped'"""
        existing = await ContactDB.get_contact(tg_contact.id, managed_by_account)
        if existing:
            update_data = {
                "first_name": tg_contact.first_name or existing.first_name,
                "last_name": tg_contact.last_name,
                "username": tg_contact.username,
                "phone": tg_contact.phone,
            }
            if any(getattr(existing, k) != v for k, v in update_data.items() if v is not None):
                await ContactDB.update_contact(tg_contact.id, managed_by_account, update_data)
                return "updated"
            return "skipped"
        else:
            contact = Contact(
                user_id=tg_contact.id,
                first_name=tg_contact.first_name or f"User_{tg_contact.id}",
                last_name=tg_contact.last_name,
                username=tg_contact.username,
                phone=tg_contact.phone,
                managed_by_account=managed_by_account,
            )
            success = await ContactDB.add_contact(contact)
            return "added" if success else "error"
