"""Session Operations Handler - Advanced session management operations
Developed by:
- @Meher_Mankar
- @Gutkesh
GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""
import logging
import os
import asyncio
import io
import json
import zipfile
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from telethon import events, Button
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.contacts import GetContactsRequest, ImportContactsRequest
from telethon.tl.functions.messages import GetHistoryRequest, SendMessageRequest
from telethon.tl.functions.account import GetPasswordRequest
from telethon.tl.types import InputPhoneContact, User, Channel, Chat
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class SessionOperationsHandler:
    """Advanced session operations from SessionMaster"""
    
    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager
        self.user_clients = bot_manager.user_clients
        self.pending_operations = {}
    
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
    
    async def _delete_dialogs_by_type(self, event, user_id, account_id, dialog_type):
        """Delete dialogs by type with confirmation"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account:
                await event.answer("❌ Account not found")
                return
            
            # Show confirmation
            type_names = {
                "channels": "📢 All Channels",
                "groups": "👥 All Groups", 
                "bots": "🤖 All Bots",
                "private": "💭 Private Chats"
            }
            
            text = (
                f"⚠️ **Confirm Deletion**\n\n"
                f"Account: {account['name']}\n"
                f"Delete: {type_names.get(dialog_type, dialog_type)}\n\n"
                f"**This action cannot be undone!**\n\n"
                f"Are you sure you want to proceed?"
            )
            
            buttons = [
                [Button.inline("✅ Yes, Delete", f"confirm_delete:{dialog_type}:{account_id}")],
                [Button.inline("❌ Cancel", f"session_operations:{account_id}")]
            ]
            
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Delete dialogs confirmation error: {e}")
            await event.answer("❌ Error showing confirmation")
    
    async def _export_session_string(self, event, user_id, account_id):
        """Export session string"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account:
                await event.answer("❌ Account not found")
                return
            
            session_string = account.get("session_string")
            if not session_string:
                await event.answer("❌ Session string not available")
                return
            
            # Create session file
            session_file = io.BytesIO(session_string.encode("utf-8"))
            session_file.name = f"session_{account['name']}.txt"
            
            await self.bot.send_file(
                user_id,
                session_file,
                caption=(
                    f"📝 **Session String Export**\n\n"
                    f"Account: {account['name']}\n"
                    f"Phone: {account['phone']}\n\n"
                    f"**Security Warning:**\n"
                    f"Keep this session string secure!\n"
                    f"Anyone with this string can access your account."
                )
            )
            
            await event.answer("📝 Session string exported!")
            
        except Exception as e:
            logger.error(f"Export session string error: {e}")
            await event.answer("❌ Error exporting session string")
    
    async def _show_bulk_operations(self, event, user_id, account_id):
        """Show bulk operations menu"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account:
                await event.edit("❌ Account not found")
                return
            
            text = (
                f"📊 **Bulk Operations: {account['name']}**\n\n"
                "Perform bulk operations on your account:\n\n"
                "**📢 Channel Operations**\n"
                "• Bulk subscribe to channels\n"
                "• Mass leave channels\n"
                "• Channel member extraction\n\n"
                "**💬 Message Operations**\n"
                "• Bulk message sending\n"
                "• Message scraping\n"
                "• Auto-reply setup\n\n"
                "**👥 Contact Operations**\n"
                "• Bulk contact import\n"
                "• Contact list management\n"
                "• Contact synchronization\n\n"
                "**🔍 Data Mining**\n"
                "• Member list extraction\n"
                "• Message history export\n"
                "• Activity monitoring"
            )
            
            buttons = [
                [
                    Button.inline("📢 Bulk Subscribe", f"bulk_subscribe:{account_id}"),
                    Button.inline("📤 Bulk Messages", f"bulk_messages:{account_id}")
                ],
                [
                    Button.inline("👥 Extract Members", f"extract_members:{account_id}"),
                    Button.inline("📋 Scrape Messages", f"scrape_messages:{account_id}")
                ],
                [
                    Button.inline("🔍 Monitor Keywords", f"monitor_keywords:{account_id}"),
                    Button.inline("🧹 Auto Cleanup", f"auto_cleanup:{account_id}")
                ],
                [Button.inline("🔙 Back", f"session_operations:{account_id}")]
            ]
            
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Show bulk operations error: {e}")
            await event.edit("❌ Error loading bulk operations")
    
    async def _show_session_analytics(self, event, user_id, account_id):
        """Show session analytics"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account:
                await event.edit("❌ Account not found")
                return
            
            # Get analytics data
            analytics = await self._get_session_analytics(user_id, account)
            
            text = (
                f"📊 **Session Analytics: {account['name']}**\n\n"
                f"**📈 Account Statistics**\n"
                f"• Total Dialogs: {analytics.get('total_dialogs', 0)}\n"
                f"• Channels: {analytics.get('channels', 0)}\n"
                f"• Groups: {analytics.get('groups', 0)}\n"
                f"• Private Chats: {analytics.get('private_chats', 0)}\n"
                f"• Bots: {analytics.get('bots', 0)}\n\n"
                f"**📅 Activity Data**\n"
                f"• Account Age: {analytics.get('account_age', 'Unknown')}\n"
                f"• Last Active: {analytics.get('last_active', 'Unknown')}\n"
                f"• Messages Sent: {analytics.get('messages_sent', 0)}\n"
                f"• Messages Received: {analytics.get('messages_received', 0)}\n\n"
                f"**🔒 Security Status**\n"
                f"• 2FA Enabled: {analytics.get('has_2fa', 'Unknown')}\n"
                f"• Sessions Count: {analytics.get('active_sessions', 0)}\n"
                f"• Premium Status: {analytics.get('is_premium', False)}\n"
                f"• Verified: {analytics.get('is_verified', False)}"
            )
            
            buttons = [
                [
                    Button.inline("🔄 Refresh", f"session_analytics:{account_id}"),
                    Button.inline("📊 Detailed Stats", f"detailed_stats:{account_id}")
                ],
                [
                    Button.inline("📈 Export Report", f"export_analytics:{account_id}"),
                    Button.inline("⚙️ Configure", f"config_analytics:{account_id}")
                ],
                [Button.inline("🔙 Back", f"session_operations:{account_id}")]
            ]
            
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Show session analytics error: {e}")
            await event.edit("❌ Error loading analytics")
    
    async def _show_session_automation(self, event, user_id, account_id):
        """Show session automation options"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account:
                await event.edit("❌ Account not found")
                return
            
            # Get automation status
            automation_status = await self._get_automation_status(user_id, account_id)
            
            text = (
                f"🤖 **Session Automation: {account['name']}**\n\n"
                "Configure automated tasks for your account:\n\n"
                f"**🟢 Online Maker**\n"
                f"Status: {'✅ Active' if automation_status.get('online_maker') else '❌ Inactive'}\n"
                f"Keep account online automatically\n\n"
                f"**🎭 Activity Simulator**\n"
                f"Status: {'✅ Active' if automation_status.get('activity_sim') else '❌ Inactive'}\n"
                f"Simulate human-like activity\n\n"
                f"**🤖 Auto-Reply**\n"
                f"Status: {'✅ Active' if automation_status.get('auto_reply') else '❌ Inactive'}\n"
                f"Automatic message responses\n\n"
                f"**📢 Auto-Subscribe**\n"
                f"Status: {'✅ Active' if automation_status.get('auto_subscribe') else '❌ Inactive'}\n"
                f"Automatic channel subscriptions\n\n"
                f"**🧹 Auto-Cleanup**\n"
                f"Status: {'✅ Active' if automation_status.get('auto_cleanup') else '❌ Inactive'}\n"
                f"Automatic dialog cleanup"
            )
            
            buttons = [
                [
                    Button.inline("🟢 Online Maker", f"toggle_online:{account_id}"),
                    Button.inline("🎭 Activity Sim", f"toggle_activity:{account_id}")
                ],
                [
                    Button.inline("🤖 Auto-Reply", f"toggle_reply:{account_id}"),
                    Button.inline("📢 Auto-Subscribe", f"toggle_subscribe:{account_id}")
                ],
                [
                    Button.inline("🧹 Auto-Cleanup", f"toggle_cleanup:{account_id}"),
                    Button.inline("⚙️ Schedule Tasks", f"schedule_tasks:{account_id}")
                ],
                [Button.inline("🔙 Back", f"session_operations:{account_id}")]
            ]
            
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Show session automation error: {e}")
            await event.edit("❌ Error loading automation")
    
    async def _get_session_analytics(self, user_id, account):
        """Get comprehensive session analytics"""
        try:
            if user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
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
            
            # Calculate account age
            account_age = "Unknown"
            if hasattr(me, 'id') and me.id:
                # Rough estimate based on user ID (not accurate but gives an idea)
                if me.id < 1000000:
                    account_age = "Very Old (2013-2014)"
                elif me.id < 100000000:
                    account_age = "Old (2015-2017)"
                elif me.id < 1000000000:
                    account_age = "Medium (2018-2020)"
                else:
                    account_age = "New (2021+)"
            
            return {
                "total_dialogs": len(dialogs),
                "account_age": account_age,
                "last_active": "Recently",
                "messages_sent": 0,  # Would need message history analysis
                "messages_received": 0,  # Would need message history analysis
                "has_2fa": "Unknown",  # Would need to check 2FA status
                "active_sessions": 1,  # Current session
                "is_premium": getattr(me, "premium", False),
                "is_verified": getattr(me, "verified", False),
                **stats
            }
            
        except Exception as e:
            logger.error(f"Get session analytics error: {e}")
            return {"error": str(e)}
    
    async def _get_automation_status(self, user_id, account_id):
        """Get automation status for account"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account:
                return {}
            
            return {
                "online_maker": account.get("online_maker_enabled", False),
                "activity_sim": account.get("simulation_enabled", False),
                "auto_reply": account.get("auto_reply_enabled", False),
                "auto_subscribe": account.get("auto_subscribe_enabled", False),
                "auto_cleanup": account.get("auto_cleanup_enabled", False)
            }
            
        except Exception as e:
            logger.error(f"Get automation status error: {e}")
            return {}
    
    async def bulk_subscribe_to_channels(self, user_id, account_id, channel_links, delay=5):
        """Bulk subscribe to multiple channels"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
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
                "message": f"✅ Subscribed to {results['success']} channels, {results['failed']} failed"
            }
            
        except Exception as e:
            logger.error(f"Bulk subscribe error: {e}")
            return {"success": False, "error": str(e)}
    
    async def bulk_send_messages(self, user_id, account_id, recipients, message_text, delay=5):
        """Bulk send messages to multiple recipients"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
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
                "message": f"✅ Sent to {results['success']} recipients, {results['failed']} failed"
            }
            
        except Exception as e:
            logger.error(f"Bulk send messages error: {e}")
            return {"success": False, "error": str(e)}
    
    async def extract_channel_members(self, user_id, account_id, channel_link, limit=1000):
        """Extract members from a channel/group"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                return {"success": False, "error": "Account not available"}
            
            client = self.user_clients[user_id][account["name"]]
            
            # Get channel entity
            entity = await client.get_entity(channel_link)
            members = []
            
            # Extract members
            async for user in client.iter_participants(entity, limit=limit):
                if isinstance(user, User):
                    members.append({
                        "id": user.id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "phone": user.phone,
                        "is_bot": user.bot,
                        "is_premium": getattr(user, "premium", False)
                    })
            
            # Create members file
            members_json = json.dumps(members, indent=2, ensure_ascii=False)
            members_file = io.BytesIO(members_json.encode("utf-8"))
            members_file.name = f"members_{channel_link.replace('@', '').replace('/', '_')}.json"
            
            return {
                "success": True,
                "members": members,
                "file": members_file,
                "count": len(members)
            }
            
        except Exception as e:
            logger.error(f"Extract channel members error: {e}")
            return {"success": False, "error": str(e)}
    
    async def scrape_channel_messages(self, user_id, account_id, channel_link, limit=100, offset_date=None):
        """Scrape messages from a channel"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                return {"success": False, "error": "Account not available"}
            
            client = self.user_clients[user_id][account["name"]]
            
            # Get channel entity
            entity = await client.get_entity(channel_link)
            messages = []
            
            # Scrape messages
            async for message in client.iter_messages(entity, limit=limit, offset_date=offset_date):
                if message.message:
                    messages.append({
                        "id": message.id,
                        "date": message.date.isoformat(),
                        "text": message.message,
                        "views": getattr(message, "views", 0),
                        "forwards": getattr(message, "forwards", 0),
                        "replies": getattr(message.replies, "replies", 0) if message.replies else 0,
                        "sender_id": message.sender_id
                    })
            
            # Create messages file
            messages_json = json.dumps(messages, indent=2, ensure_ascii=False)
            messages_file = io.BytesIO(messages_json.encode("utf-8"))
            messages_file.name = f"messages_{channel_link.replace('@', '').replace('/', '_')}.json"
            
            return {
                "success": True,
                "messages": messages,
                "file": messages_file,
                "count": len(messages)
            }
            
        except Exception as e:
            logger.error(f"Scrape channel messages error: {e}")
            return {"success": False, "error": str(e)}
    
    async def monitor_keywords(self, user_id, account_id, keywords, channels, duration_hours=24):
        """Monitor keywords in specified channels"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                return {"success": False, "error": "Account not available"}
            
            client = self.user_clients[user_id][account["name"]]
            matches = []
            
            for channel_link in channels:
                try:
                    entity = await client.get_entity(channel_link)
                    
                    # Get recent messages
                    since_date = datetime.now() - timedelta(hours=duration_hours)
                    async for message in client.iter_messages(entity, limit=100, offset_date=since_date):
                        if message.message:
                            message_text = message.message.lower()
                            for keyword in keywords:
                                if keyword.lower() in message_text:
                                    matches.append({
                                        "channel": channel_link,
                                        "keyword": keyword,
                                        "message": message.message,
                                        "date": message.date.isoformat(),
                                        "message_id": message.id,
                                        "views": getattr(message, "views", 0)
                                    })
                except Exception as e:
                    logger.warning(f"Error monitoring {channel_link}: {e}")
                    continue
            
            return {
                "success": True,
                "matches": matches,
                "count": len(matches),
                "keywords": keywords,
                "channels": channels
            }
            
        except Exception as e:
            logger.error(f"Monitor keywords error: {e}")
            return {"success": False, "error": str(e)}
    
    async def auto_leave_inactive_groups(self, user_id, account_id, days_inactive=30):
        """Leave groups with no recent activity"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                return {"success": False, "error": "Account not available"}
            
            client = self.user_clients[user_id][account["name"]]
            dialogs = await client.get_dialogs()
            cutoff_date = datetime.now() - timedelta(days=days_inactive)
            left_count = 0
            
            for dialog in dialogs:
                if isinstance(dialog.entity, (Channel, Chat)) and not getattr(dialog.entity, "broadcast", False):
                    if dialog.date < cutoff_date:
                        try:
                            await client(LeaveChannelRequest(dialog.entity))
                            left_count += 1
                            await asyncio.sleep(2)  # Rate limiting
                        except Exception as e:
                            logger.warning(f"Failed to leave group {dialog.entity.id}: {e}")
            
            return {
                "success": True,
                "left_count": left_count,
                "message": f"✅ Left {left_count} inactive groups"
            }
            
        except Exception as e:
            logger.error(f"Auto leave inactive groups error: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_tdata_archive(self, user_id, account_id):
        """Create TData archive (placeholder implementation)"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
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
                "note": "Generated by TeleGuard SessionMaster"
            }
            
            with open(os.path.join(tdata_dir, "info.json"), "w") as f:
                json.dump(info, f, indent=2)
            
            # Create ZIP archive
            zip_path = os.path.join(temp_dir, f"tdata_{account['name']}.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(tdata_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)
            
            return {
                "success": True,
                "zip_path": zip_path,
                "temp_dir": temp_dir
            }
            
        except Exception as e:
            logger.error(f"Create TData archive error: {e}")
            return {"success": False, "error": str(e)}
    
    async def import_contacts_from_file(self, user_id, account_id, contacts_data):
        """Import contacts from data"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id
            })
            
            if not account or user_id not in self.user_clients or account["name"] not in self.user_clients[user_id]:
                return {"success": False, "error": "Account not available"}
            
            client = self.user_clients[user_id][account["name"]]
            
            # Prepare contacts for import
            input_contacts = []
            for i, contact in enumerate(contacts_data):
                if contact.get("phone"):
                    input_contacts.append(InputPhoneContact(
                        client_id=i,
                        phone=contact["phone"],
                        first_name=contact.get("first_name", ""),
                        last_name=contact.get("last_name", "")
                    ))
            
            if input_contacts:
                result = await client(ImportContactsRequest(input_contacts))
                imported_count = len(result.imported)
                
                return {
                    "success": True,
                    "imported_count": imported_count,
                    "message": f"✅ Imported {imported_count} contacts"
                }
            else:
                return {"success": False, "error": "No valid contacts to import"}
                
        except Exception as e:
            logger.error(f"Import contacts error: {e}")
            return {"success": False, "error": str(e)}
