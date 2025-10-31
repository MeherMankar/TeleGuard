"""SpamMaster Integration - Bulk messaging and user gathering"""
import asyncio
import random
from typing import Dict, List, Optional
from telethon import events, Button
from ..core.mongo_database import mongodb
from ..utils.bot_logger import logger


class SpamMasterHandler:
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        self.active_campaigns = {}  # campaign_id -> stop_flag
        
    def register_handlers(self):
        @self.bot.on(events.CallbackQuery(pattern=b"spam_master"))
        async def spam_master_menu(event):
            buttons = [
                [Button.inline("📊 Gather Users", b"spam_gather")],
                [Button.inline("📤 Bulk Send", b"spam_send")],
                [Button.inline("🤖 Auto Reply", b"spam_reply")],
                [Button.inline("📈 Campaign Stats", b"spam_stats")],
                [Button.inline("🔙 Back", b"main_menu")]
            ]
            await event.edit("🎯 **SpamMaster**\n\nBulk messaging and automation", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"spam_gather"))
        async def gather_menu(event):
            user_id = event.sender_id
            accounts = await self._get_user_accounts(user_id)
            if not accounts:
                await event.answer("❌ No accounts found", alert=True)
                return
            
            buttons = [
                [Button.inline("🔄 Auto Gather All", b"gather_auto")],
                [Button.inline("📝 Manual Gather", b"gather_manual")],
                [Button.inline("🔙 Back", b"spam_master")]
            ]
            await event.edit("📊 **Gather Users**\n\nChoose gathering mode:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"gather_auto"))
        async def gather_auto(event):
            user_id = event.sender_id
            accounts = await self._get_user_accounts(user_id)
            if not accounts:
                await event.answer("❌ No accounts found", alert=True)
                return
            
            buttons = [[Button.inline(f"📱 {acc['name']}", f"auto_acc:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🔙 Back", b"spam_gather")])
            await event.edit("Select account for auto-gathering:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"auto_acc:(.+)"))
        async def auto_gather_account(event):
            account_name = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            await event.edit(f"⏳ Auto-gathering from all groups/channels...\n\nAccount: **{account_name}**")
            total = await self._auto_gather_all(user_id, account_name)
            await event.respond(f"✅ Auto-gathered {total} users from all groups/channels")
        
        @self.bot.on(events.CallbackQuery(pattern=b"gather_manual"))
        async def gather_manual(event):
            user_id = event.sender_id
            accounts = await self._get_user_accounts(user_id)
            
            buttons = [[Button.inline(f"📱 {acc['name']}", f"gather_acc:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🔙 Back", b"spam_gather")])
            await event.edit("Select account to gather users:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"gather_acc:(.+)"))
        async def gather_account(event):
            account_name = event.data.decode().split(":", 1)[1]
            await event.edit(f"📝 Send group username/link to gather users from:\n\nAccount: **{account_name}**")
            
            @self.bot.on(events.NewMessage(from_users=event.sender_id))
            async def handle_group(msg_event):
                group = msg_event.text.strip()
                self.bot.remove_event_handler(handle_group)
                
                await msg_event.reply("⏳ Gathering users...")
                count = await self._gather_users(event.sender_id, account_name, group)
                await msg_event.reply(f"✅ Gathered {count} users from {group}")
        
        @self.bot.on(events.CallbackQuery(pattern=b"spam_send"))
        async def send_menu(event):
            user_id = event.sender_id
            accounts = await self._get_user_accounts(user_id)
            if not accounts:
                await event.answer("❌ No accounts found", alert=True)
                return
            
            buttons = [[Button.inline(f"📱 {acc['name']}", f"send_acc:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🔙 Back", b"spam_master")])
            await event.edit("Select account for bulk send:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"send_acc:(.+)"))
        async def send_account(event):
            account_name = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            users = await self._get_gathered_users(user_id)
            if not users:
                await event.answer("❌ No users gathered yet", alert=True)
                return
            
            await event.edit(
                f"📤 **Bulk Send Setup**\n\n"
                f"Account: **{account_name}**\n"
                f"Users: **{len(users)}**\n\n"
                f"Send your message (text/media):"
            )
            
            @self.bot.on(events.NewMessage(from_users=user_id))
            async def handle_message(msg_event):
                self.bot.remove_event_handler(handle_message)
                
                buttons = [[Button.inline("🛑 Stop Campaign", b"stop_temp")]]
                progress_msg = await msg_event.reply(
                    f"🚀 **Campaign Started**\n\n"
                    f"Account: **{account_name}**\n"
                    f"Total Users: **{len(users)}**\n"
                    f"Sent: **0/{len(users)}**\n"
                    f"Progress: □□□□□□□□□□ 0%",
                    buttons=buttons
                )
                
                campaign_id = await self._start_campaign(
                    user_id, account_name, users, msg_event, progress_msg
                )
        
        @self.bot.on(events.CallbackQuery(pattern=b"spam_reply"))
        async def reply_menu(event):
            user_id = event.sender_id
            config = await self._get_reply_config(user_id)
            
            status = "✅ Enabled" if config.get("enabled") else "❌ Disabled"
            buttons = [
                [Button.inline("🔄 Toggle", b"reply_toggle")],
                [Button.inline("📝 Set Templates", b"reply_templates")],
                [Button.inline("🔙 Back", b"spam_master")]
            ]
            
            await event.edit(
                f"🤖 **Auto Reply**\n\n"
                f"Status: {status}\n"
                f"Templates: {len(config.get('templates', []))}\n\n"
                f"Auto-replies to user messages",
                buttons=buttons
            )
        
        @self.bot.on(events.CallbackQuery(pattern=b"reply_toggle"))
        async def toggle_reply(event):
            user_id = event.sender_id
            enabled = await self._toggle_auto_reply(user_id)
            status = "enabled" if enabled else "disabled"
            await event.answer(f"✅ Auto-reply {status}", alert=True)
            await reply_menu(event)
        
        @self.bot.on(events.CallbackQuery(pattern=b"spam_stats"))
        async def show_stats(event):
            user_id = event.sender_id
            stats = await self._get_campaign_stats(user_id)
            
            text = "📈 **Campaign Statistics**\n\n"
            if not stats:
                text += "No active campaigns"
            else:
                for campaign in stats[:5]:
                    status = "⏸️ Stopped" if campaign.get('stopped') else "▶️ Running"
                    text += (
                        f"**{campaign['account']}** {status}\n"
                        f"Sent: {campaign['sent']}/{campaign['total']}\n"
                        f"Replies: {campaign['replies']}\n\n"
                    )
            
            buttons = [[Button.inline("🔙 Back", b"spam_master")]]
            await event.edit(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"stop_camp:(.+)"))
        async def stop_campaign(event):
            campaign_id = event.data.decode().split(":", 1)[1]
            self.active_campaigns[campaign_id] = True
            
            from bson import ObjectId
            await mongodb.db.spam_campaigns.update_one(
                {"_id": ObjectId(campaign_id)},
                {"$set": {"stopped": True}}
            )
            await event.answer("🛑 Campaign stopped", alert=True)
            await event.edit(f"🛑 Campaign {campaign_id} stopped")
    
    async def _get_user_accounts(self, user_id: int) -> List[Dict]:
        """Get user's accounts with names"""
        if user_id not in self.user_clients:
            return []
        
        accounts = []
        for phone in self.user_clients[user_id].keys():
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "phone": phone})
            if account:
                name = account.get("first_name", phone)
                accounts.append({"phone": phone, "name": name})
        return accounts
    
    async def _auto_gather_all(self, user_id: int, account_name: str) -> int:
        """Auto-gather users from all groups/channels"""
        try:
            client = self.user_clients[user_id][account_name]
            total = 0
            
            async for dialog in client.iter_dialogs():
                if dialog.is_group and not getattr(dialog.entity, 'forum', False):
                    count = await self._gather_users(user_id, account_name, dialog.entity)
                    total += count
                    await asyncio.sleep(2)
            
            return total
        except Exception as e:
            logger.error(f"Auto-gather failed: {e}")
            return 0
    
    async def _gather_users(self, user_id: int, account_name: str, group) -> int:
        """Gather users from a group"""
        try:
            client = self.user_clients[user_id][account_name]
            if isinstance(group, str):
                entity = await client.get_entity(group)
            else:
                entity = group
            
            group_name = getattr(entity, 'title', getattr(entity, 'username', str(entity.id)))
            users = []
            
            try:
                # Try normal participant gathering
                async for user in client.iter_participants(entity, limit=5000):
                    if not user.bot and not user.deleted:
                        users.append({
                            "user_id": user.id,
                            "username": user.username,
                            "first_name": user.first_name
                        })
            except Exception:
                # Fallback: Scan chat history for message senders
                users = await self._gather_from_messages(client, entity)
            
            if users:
                await mongodb.db.spam_users.insert_many([
                    {**u, "owner_id": user_id, "group": group_name, "status": "new", "account": account_name}
                    for u in users
                ])
            
            return len(users)
        except Exception:
            return 0
    
    async def _gather_from_messages(self, client, entity) -> List[Dict]:
        """Gather users from chat message history"""
        users_dict = {}
        try:
            async for message in client.iter_messages(entity, limit=1000):
                if message.sender and not message.sender.bot and not message.sender.deleted:
                    users_dict[message.sender.id] = {
                        "user_id": message.sender.id,
                        "username": message.sender.username,
                        "first_name": message.sender.first_name
                    }
        except Exception:
            pass
        return list(users_dict.values())
    
    async def _get_gathered_users(self, user_id: int) -> List[Dict]:
        """Get gathered users for bulk send"""
        cursor = mongodb.db.spam_users.find(
            {"owner_id": user_id, "status": "new"},
            limit=500
        )
        return await cursor.to_list(length=500)
    
    async def _start_campaign(self, user_id: int, account_name: str, users: List, msg_event, progress_msg) -> str:
        """Start bulk send campaign"""
        campaign = {
            "user_id": user_id,
            "account": account_name,
            "total": len(users),
            "sent": 0,
            "replies": 0,
            "message": msg_event.text,
            "media": None
        }
        
        result = await mongodb.db.spam_campaigns.insert_one(campaign)
        campaign_id = str(result.inserted_id)
        
        asyncio.create_task(self._run_campaign(campaign_id, user_id, account_name, users, msg_event, progress_msg))
        return campaign_id
    
    async def _run_campaign(self, campaign_id: str, user_id: int, account_name: str, users: List, msg_event, progress_msg):
        """Execute bulk send campaign"""
        try:
            client = self.user_clients[user_id][account_name]
            self.active_campaigns[campaign_id] = False
            total = len(users)
            sent = 0
            
            for idx, user in enumerate(users, 1):
                if self.active_campaigns.get(campaign_id):
                    await progress_msg.edit(
                        f"🛑 **Campaign Stopped**\n\n"
                        f"Account: **{account_name}**\n"
                        f"Total Users: **{total}**\n"
                        f"Sent: **{sent}/{total}**\n"
                        f"Status: Stopped by user"
                    )
                    break
                
                try:
                    if msg_event.photo:
                        await client.send_file(user["user_id"], msg_event.photo, caption=msg_event.text)
                    elif msg_event.video:
                        await client.send_file(user["user_id"], msg_event.video, caption=msg_event.text)
                    elif msg_event.document:
                        await client.send_file(user["user_id"], msg_event.document, caption=msg_event.text)
                    else:
                        await client.send_message(user["user_id"], msg_event.text)
                    
                    sent += 1
                    
                    await mongodb.db.spam_users.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"status": "sent", "account": account_name}}
                    )
                    
                    from bson import ObjectId
                    await mongodb.db.spam_campaigns.update_one(
                        {"_id": ObjectId(campaign_id)},
                        {"$inc": {"sent": 1}}
                    )
                    
                    if idx % 5 == 0 or idx == total:
                        percent = int((sent / total) * 100)
                        filled = int(percent / 10)
                        bar = "■" * filled + "□" * (10 - filled)
                        buttons = [[Button.inline("🛑 Stop", f"stop_camp:{campaign_id}".encode())]]
                        await progress_msg.edit(
                            f"🚀 **Campaign Running**\n\n"
                            f"Account: **{account_name}**\n"
                            f"Total Users: **{total}**\n"
                            f"Sent: **{sent}/{total}**\n"
                            f"Progress: {bar} {percent}%",
                            buttons=buttons
                        )
                    
                    await asyncio.sleep(random.uniform(40, 60))
                except Exception:
                    await asyncio.sleep(5)
            
            if not self.active_campaigns.get(campaign_id):
                await progress_msg.edit(
                    f"✅ **Campaign Completed**\n\n"
                    f"Account: **{account_name}**\n"
                    f"Total Users: **{total}**\n"
                    f"Sent: **{sent}/{total}**\n"
                    f"Progress: ■■■■■■■■■■ 100%"
                )
        except Exception as e:
            logger.error(f"Campaign failed: {e}")
        finally:
            self.active_campaigns.pop(campaign_id, None)
    
    async def _get_reply_config(self, user_id: int) -> Dict:
        """Get auto-reply configuration"""
        config = await mongodb.db.spam_config.find_one({"user_id": user_id})
        return config or {"enabled": False, "templates": []}
    
    async def _toggle_auto_reply(self, user_id: int) -> bool:
        """Toggle auto-reply on/off"""
        config = await self._get_reply_config(user_id)
        enabled = not config.get("enabled", False)
        
        await mongodb.db.spam_config.update_one(
            {"user_id": user_id},
            {"$set": {"enabled": enabled}},
            upsert=True
        )
        return enabled
    
    async def _get_campaign_stats(self, user_id: int) -> List[Dict]:
        """Get campaign statistics"""
        cursor = mongodb.db.spam_campaigns.find(
            {"user_id": user_id}
        ).sort("_id", -1).limit(5)
        return await cursor.to_list(length=5)
