"""Contact management data models"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

@dataclass
class Contact:
    """Contact data model"""
    user_id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    is_blacklisted: bool = False
    is_whitelisted: bool = False
    managed_by_account: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB"""
        return {
            "user_id": self.user_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "username": self.username,
            "phone": self.phone,
            "notes": self.notes,
            "tags": self.tags,
            "is_blacklisted": self.is_blacklisted,
            "is_whitelisted": self.is_whitelisted,
            "managed_by_account": self.managed_by_account,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Contact':
        """Create from dictionary"""
        return cls(
            user_id=data["user_id"],
            first_name=data["first_name"],
            last_name=data.get("last_name"),
            username=data.get("username"),
            phone=data.get("phone"),
            notes=data.get("notes", ""),
            tags=data.get("tags", []),
            is_blacklisted=data.get("is_blacklisted", False),
            is_whitelisted=data.get("is_whitelisted", False),
            managed_by_account=data.get("managed_by_account", ""),
            created_at=data.get("created_at", datetime.now()),
            updated_at=data.get("updated_at", datetime.now())
        )

@dataclass
class ContactGroup:
    """Contact group data model"""
    name: str
    description: str = ""
    contact_ids: List[int] = field(default_factory=list)
    managed_by_account: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB"""
        return {
            "name": self.name,
            "description": self.description,
            "contact_ids": self.contact_ids,
            "managed_by_account": self.managed_by_account,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ContactGroup':
        """Create from dictionary"""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            contact_ids=data.get("contact_ids", []),
            managed_by_account=data.get("managed_by_account", ""),
            created_at=data.get("created_at", datetime.now())
        )