"""Profile management operations"""
import logging
from telethon import Button, events
from ...core.mongo_database import mongodb
from ...utils.network_helpers import format_phone_number

logger = logging.getLogger(__name__)

class ProfileOperations:
    def __init__(self, menu_system):
        self.menu = menu_system
        self.bot = menu_system.bot
        self.account_manager = menu_system.account_manager
    
    async def send_profile_management(self, user_id, account_id, message_id):
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
        if not account:
            await self.bot.send_message(user_id, "❌ Account not found")
            return
        current_info = await self._get_current_profile_info(user_id, account["name"])
        if current_info:
            username_display = f"@{current_info.get('username', '')}" if current_info.get("username") else "Not set"
            first_name = current_info.get("first_name", "")
            last_name = current_info.get("last_name", "")
            name_display = f"{first_name} {last_name}".strip() or "Not set"
            bio_display = current_info.get("about", "") or "Not set"
        else:
            username_display = f"@{account.get('username', '')}" if account.get("username") else "Not set"
            name_display = f"{account.get('profile_first_name', '')} {account.get('profile_last_name', '')}".strip() or "Not set"
            bio_display = account.get("about", "") or "Not set"
        text = f"👤 **Profile: {account['name']}**\n\n📞 Phone: {format_phone_number(account['phone'])}\n👤 Name: {name_display}\n🆔 Username: {username_display}\n📝 Bio: {bio_display}\n\nSelect what to update:"
        buttons = [[Button.inline("🖼️ Change Photo", f"profile:photo:{account_id}"), Button.inline("👤 Change Name", f"profile:name:{account_id}")], [Button.inline("🆔 Set Username", f"profile:username:{account_id}"), Button.inline("📝 Update Bio", f"profile:bio:{account_id}")], [Button.inline("🔙 Back", "account:manage:" + account_id)]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
    async def _get_current_profile_info(self, user_id, account_name):
        try:
            if not self.account_manager or user_id not in self.account_manager.user_clients:
                return None
            user_clients = self.account_manager.user_clients.get(user_id, {})
            client = user_clients.get(account_name)
            if not client or not client.is_connected():
                return None
            me = await client.get_me()
            return {"first_name": me.first_name or "", "last_name": me.last_name or "", "username": me.username or "", "about": getattr(me, "about", "") or ""}
        except Exception:
            return None
    
    async def handle_profile_name_change(self, user_id, account_id, event):
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
        if not account:
            await event.answer("Account not found")
            return
        await event.answer("Enter new name")
        await self.bot.send_message(user_id, "Reply with your new name (Example: John Doe):")
        @self.bot.on(events.NewMessage(from_users=user_id))
        async def handle_name_input(name_event):
            if name_event.raw_text.startswith("/"):
                return
            names = name_event.raw_text.split(" ", 1)
            first_name = names[0]
            last_name = names[1] if len(names) > 1 else ""
            client = None
            if hasattr(self.account_manager, "user_clients"):
                client = self.account_manager.user_clients.get(user_id, {}).get(account["name"])
            if client:
                try:
                    from telethon import functions
                    await client(functions.account.UpdateProfileRequest(first_name=first_name, last_name=last_name))
                    await name_event.reply(f"Profile name updated to: {first_name} {last_name}")
                except Exception as e:
                    await name_event.reply(f"Failed to update name: {e}")
            else:
                await name_event.reply("Account client not found")
            self.bot.remove_event_handler(handle_name_input)
    
    async def handle_profile_username_change(self, user_id, account_id, event):
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
        if not account:
            await event.answer("Account not found")
            return
        await event.answer("Enter username")
        await self.bot.send_message(user_id, "Reply with your new username (without @):")
        @self.bot.on(events.NewMessage(from_users=user_id))
        async def handle_username_input(username_event):
            if username_event.raw_text.startswith("/"):
                return
            username = username_event.raw_text.replace("@", "").strip()
            client = None
            if hasattr(self.account_manager, "user_clients"):
                client = self.account_manager.user_clients.get(user_id, {}).get(account["name"])
            if client:
                try:
                    from telethon import functions
                    await client(functions.account.UpdateUsernameRequest(username=username))
                    await username_event.reply(f"Username updated to: @{username}")
                except Exception as e:
                    await username_event.reply(f"Failed to update username: {e}")
            else:
                await username_event.reply(f"Account client not found. Account: {account['name']}, User: {user_id}")
            self.bot.remove_event_handler(handle_username_input)
    
    async def handle_profile_bio_change(self, user_id, account_id, event):
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
        if not account:
            await event.answer("Account not found")
            return
        await event.answer("Enter bio")
        await self.bot.send_message(user_id, "Reply with your new bio (max 70 characters):")
        @self.bot.on(events.NewMessage(from_users=user_id))
        async def handle_bio_input(bio_event):
            if bio_event.raw_text.startswith("/"):
                return
            bio_text = bio_event.raw_text.strip()
            client = None
            if hasattr(self.account_manager, "user_clients"):
                client = self.account_manager.user_clients.get(user_id, {}).get(account["name"])
            if client:
                try:
                    from telethon import functions
                    await client(functions.account.UpdateProfileRequest(about=bio_text))
                    await bio_event.reply("Bio updated successfully")
                except Exception as e:
                    await bio_event.reply(f"Failed to update bio: {e}")
            else:
                await bio_event.reply(f"Account client not found. Account: {account['name']}, User: {user_id}")
            self.bot.remove_event_handler(handle_bio_input)
    
    async def handle_profile_photo_change(self, user_id, account_id, event):
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
        if not account:
            await event.answer("Account not found")
            return
        await event.answer("Send photo")
        await self.bot.send_message(user_id, "Send a photo to set as your profile picture:")
        @self.bot.on(events.NewMessage(from_users=user_id, func=lambda e: e.photo))
        async def handle_photo_input(photo_event):
            client = None
            if hasattr(self.account_manager, "user_clients"):
                client = self.account_manager.user_clients.get(user_id, {}).get(account["name"])
            if client:
                try:
                    photo_path = await photo_event.download_media()
                    from telethon import functions
                    uploaded_file = await client.upload_file(photo_path)
                    await client(functions.photos.UploadProfilePhotoRequest(file=uploaded_file))
                    import os
                    if os.path.exists(photo_path):
                        os.remove(photo_path)
                    await photo_event.reply("Profile photo updated successfully")
                except Exception as e:
                    await photo_event.reply(f"Failed to update photo: {e}")
            else:
                await photo_event.reply(f"Account client not found. Account: {account['name']}, User: {user_id}")
            self.bot.remove_event_handler(handle_photo_input)
