"""Contact database operations"""

import logging
from typing import List, Optional
from datetime import datetime
from .contact_models import Contact, ContactGroup
from .mongo_database import mongodb

logger = logging.getLogger(__name__)

class ContactDB:
    """Contact database operations"""
    
    @staticmethod
    async def add_contact(contact: Contact) -> bool:
        """Add new contact"""
        try:
            await mongodb.db.contacts.create_index([("user_id", 1), ("managed_by_account", 1)], unique=True)
            result = await mongodb.db.contacts.insert_one(contact.to_dict())
            return bool(result.inserted_id)
        except Exception as e:
            logger.error(f"Error adding contact: {e}")
            return False

    @staticmethod
    async def get_contact(user_id: int, managed_by_account: str) -> Optional[Contact]:
        """Get contact by user_id and account"""
        try:
            data = await mongodb.db.contacts.find_one({"user_id": user_id, "managed_by_account": managed_by_account})
            return Contact.from_dict(data) if data else None
        except Exception as e:
            logger.error(f"Error getting contact: {e}")
            return None

    @staticmethod
    async def update_contact(user_id: int, managed_by_account: str, update_data: dict) -> bool:
        """Update contact"""
        try:
            update_data["updated_at"] = datetime.now()
            result = await mongodb.db.contacts.update_one(
                {"user_id": user_id, "managed_by_account": managed_by_account},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating contact: {e}")
            return False

    @staticmethod
    async def delete_contact(user_id: int, managed_by_account: str) -> bool:
        """Delete contact"""
        try:
            result = await mongodb.db.contacts.delete_one({"user_id": user_id, "managed_by_account": managed_by_account})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting contact: {e}")
            return False

    @staticmethod
    async def get_all_contacts(managed_by_account: str, limit: int = 100) -> List[Contact]:
        """Get all contacts for account"""
        try:
            cursor = mongodb.db.contacts.find({"managed_by_account": managed_by_account}).limit(limit)
            contacts = []
            async for data in cursor:
                contacts.append(Contact.from_dict(data))
            return contacts
        except Exception as e:
            logger.error(f"Error getting contacts: {e}")
            return []

    @staticmethod
    async def search_contacts(managed_by_account: str, query: str) -> List[Contact]:
        """Search contacts by name or username"""
        try:
            # Sanitize query to prevent regex injection
            import re
            safe_query = re.escape(query.strip())
            
            # Validate inputs
            if not managed_by_account or not safe_query:
                return []
                
            filter_query = {
                "managed_by_account": managed_by_account,
                "$or": [
                    {"first_name": {"$regex": safe_query, "$options": "i"}},
                    {"last_name": {"$regex": safe_query, "$options": "i"}},
                    {"username": {"$regex": safe_query, "$options": "i"}}
                ]
            }
            cursor = mongodb.db.contacts.find(filter_query).limit(50)
            contacts = []
            async for data in cursor:
                contacts.append(Contact.from_dict(data))
            return contacts
        except Exception as e:
            logger.error(f"Error searching contacts: {e}")
            return []

    @staticmethod
    async def get_contacts_by_tag(managed_by_account: str, tag: str) -> List[Contact]:
        """Get contacts by tag"""
        try:
            # Validate inputs to prevent injection
            if not managed_by_account or not tag:
                return []
                
            # Sanitize tag input
            safe_tag = str(tag).strip()
            
            cursor = mongodb.db.contacts.find({"managed_by_account": managed_by_account, "tags": safe_tag}).limit(50)
            contacts = []
            async for data in cursor:
                contacts.append(Contact.from_dict(data))
            return contacts
        except Exception as e:
            logger.error(f"Error getting contacts by tag: {e}")
            return []

    @staticmethod
    async def set_contact_blacklist_status(user_id: int, managed_by_account: str, status: bool) -> bool:
        """Set blacklist status"""
        return await ContactDB.update_contact(user_id, managed_by_account, {"is_blacklisted": status})

    @staticmethod
    async def set_contact_whitelist_status(user_id: int, managed_by_account: str, status: bool) -> bool:
        """Set whitelist status"""
        return await ContactDB.update_contact(user_id, managed_by_account, {"is_whitelisted": status})

    # Group operations
    @staticmethod
    async def add_group(group: ContactGroup) -> bool:
        """Add new group"""
        try:
            await mongodb.db.contact_groups.create_index([("name", 1), ("managed_by_account", 1)], unique=True)
            result = await mongodb.db.contact_groups.insert_one(group.to_dict())
            return bool(result.inserted_id)
        except Exception as e:
            logger.error(f"Error adding group: {e}")
            return False

    @staticmethod
    async def get_group(name: str, managed_by_account: str) -> Optional[ContactGroup]:
        """Get group by name"""
        try:
            data = await mongodb.db.contact_groups.find_one({"name": name, "managed_by_account": managed_by_account})
            return ContactGroup.from_dict(data) if data else None
        except Exception as e:
            logger.error(f"Error getting group: {e}")
            return None

    @staticmethod
    async def add_contact_to_group(user_id: int, group_name: str, managed_by_account: str) -> bool:
        """Add contact to group"""
        try:
            result = await mongodb.db.contact_groups.update_one(
                {"name": group_name, "managed_by_account": managed_by_account},
                {"$addToSet": {"contact_ids": user_id}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error adding contact to group: {e}")
            return False

    @staticmethod
    async def get_all_groups(managed_by_account: str) -> List[ContactGroup]:
        """Get all groups for account"""
        try:
            cursor = mongodb.db.contact_groups.find({"managed_by_account": managed_by_account})
            groups = []
            async for data in cursor:
                groups.append(ContactGroup.from_dict(data))
            return groups
        except Exception as e:
            logger.error(f"Error getting groups: {e}")
            return []