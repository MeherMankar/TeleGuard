"""Advanced messaging manager with template system

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from .mongo_database import mongodb
from ..utils.data_encryption import DataEncryption

logger = logging.getLogger(__name__)


class MessagingManager:
    """Manages message templates and sending"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
    
    async def create_template(self, user_id: int, name: str, content: str, 
                            category: str = "General", media_url: str = None, 
                            buttons: List[Dict] = None) -> str:
        """Create a new message template"""
        try:
            template_data = {
                "user_id": user_id,
                "name": name,
                "content": content,
                "category": category,
                "media_url": media_url,
                "buttons": buttons or [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            encrypted_data = DataEncryption.encrypt_settings_data(template_data)
            result = await mongodb.db.message_templates.insert_one(encrypted_data)
            
            logger.info(f"Template created: {name} for user {user_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Failed to create template: {e}")
            raise
    
    async def update_template(self, template_id: str, updates: Dict) -> bool:
        """Update an existing template"""
        try:
            from bson import ObjectId
            
            updates["updated_at"] = datetime.utcnow()
            encrypted_updates = DataEncryption.encrypt_settings_data(updates)
            
            result = await mongodb.db.message_templates.update_one(
                {"_id": ObjectId(template_id)},
                {"$set": encrypted_updates}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to update template: {e}")
            return False
    
    async def get_template(self, template_id: str) -> Optional[Dict]:
        """Get a template by ID"""
        try:
            from bson import ObjectId
            
            template = await mongodb.db.message_templates.find_one(
                {"_id": ObjectId(template_id)}
            )
            
            if template:
                # Check if encrypted or unencrypted
                if any(k.endswith('_enc') for k in template.keys()):
                    return DataEncryption.decrypt_settings_data(template)
                else:
                    return template
            return None
            
        except Exception as e:
            logger.error(f"Failed to get template: {e}")
            return None
    
    async def get_user_templates(self, user_id: int) -> List[Dict]:
        """Get all templates for a user"""
        try:
            cursor = mongodb.db.message_templates.find({"user_id": user_id})
            templates_raw = await cursor.to_list(length=None)
            
            templates = []
            for template in templates_raw:
                # Check if template is encrypted or unencrypted
                if any(k.endswith('_enc') for k in template.keys()):
                    # Encrypted template
                    decrypted = DataEncryption.decrypt_settings_data(template)
                    decrypted["_id"] = str(template["_id"])
                    templates.append(decrypted)
                else:
                    # Unencrypted template (legacy)
                    template["_id"] = str(template["_id"])
                    templates.append(template)
            
            return templates
            
        except Exception as e:
            logger.error(f"Failed to get user templates: {e}")
            return []
    
    async def get_templates_by_category(self, user_id: int, category: str) -> List[Dict]:
        """Get templates filtered by category"""
        try:
            # Get all user templates and filter by category
            all_templates = await self.get_user_templates(user_id)
            
            # Filter by category
            templates = [t for t in all_templates if t.get("category", "General") == category]
            
            return templates
            
        except Exception as e:
            logger.error(f"Failed to get templates by category: {e}")
            return []
    
    async def get_template_categories(self, user_id: int) -> List[str]:
        """Get all unique categories for a user"""
        try:
            templates = await self.get_user_templates(user_id)
            categories = list(set(template.get("category", "General") for template in templates))
            return sorted(categories)
            
        except Exception as e:
            logger.error(f"Failed to get template categories: {e}")
            return ["General"]
    
    async def delete_template(self, template_id: str) -> bool:
        """Delete a template"""
        try:
            from bson import ObjectId
            
            result = await mongodb.db.message_templates.delete_one(
                {"_id": ObjectId(template_id)}
            )
            
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"Failed to delete template: {e}")
            return False
    
    def _replace_variables(self, content: str, target_info: Dict = None) -> str:
        """Replace template variables with actual values"""
        try:
            now = datetime.now()
            
            # Sanitize target_info to prevent injection
            safe_target_info = {}
            if target_info:
                for key, value in target_info.items():
                    if isinstance(value, str):
                        # Remove potentially dangerous characters
                        safe_value = re.sub(r'[<>"\\{}]', '', str(value)[:100])
                        safe_target_info[key] = safe_value
                    else:
                        safe_target_info[key] = str(value)[:100]
            
            # Default replacements with safe values
            replacements = {
                "{time}": now.strftime("%H:%M"),
                "{date}": now.strftime("%Y-%m-%d"),
                "{datetime}": now.strftime("%Y-%m-%d %H:%M"),
                "{name}": safe_target_info.get("first_name", "Friend"),
                "{username}": f"@{safe_target_info.get('username')}" if safe_target_info.get("username") else "Friend",
                "{full_name}": f"{safe_target_info.get('first_name', '')} {safe_target_info.get('last_name', '')}".strip() or "Friend"
            }
            
            # Replace variables safely
            for var, value in replacements.items():
                if var in content:
                    content = content.replace(var, str(value))
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to replace variables: {e}")
            return content
    
    async def send_template(self, user_id: int, account_name: str, target: str, template_id: str) -> bool:
        """Send a template message"""
        try:
            # Get template
            template = await self.get_template(template_id)
            if not template:
                return False
            
            # Get user client
            if user_id not in self.user_clients or account_name not in self.user_clients[user_id]:
                return False
            
            client = self.user_clients[user_id][account_name]
            if not client or not client.is_connected():
                return False
            
            # Get target info for variable replacement
            target_info = None
            try:
                if target.startswith("@"):
                    target_entity = await client.get_entity(target)
                else:
                    target_entity = await client.get_entity(int(target))
                
                target_info = {
                    "first_name": getattr(target_entity, "first_name", ""),
                    "last_name": getattr(target_entity, "last_name", ""),
                    "username": getattr(target_entity, "username", "")
                }
            except:
                pass
            
            # Replace variables in content
            content = self._replace_variables(template["content"], target_info)
            
            # Prepare buttons
            buttons = None
            if template.get("buttons"):
                from telethon.tl.custom import Button
                button_rows = []
                for btn in template["buttons"]:
                    if btn.get("url"):
                        button_rows.append([Button.url(btn["text"], btn["url"])])
                    else:
                        button_rows.append([Button.inline(btn["text"], f"template_btn:{btn['text']}")])
                buttons = button_rows
            
            # Send message
            if template.get("media_url"):
                await client.send_file(
                    target,
                    template["media_url"],
                    caption=content,
                    buttons=buttons
                )
            else:
                await client.send_message(
                    target,
                    content,
                    buttons=buttons
                )
            
            logger.info(f"Template sent: {template['name']} to {target}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send template: {e}")
            return False