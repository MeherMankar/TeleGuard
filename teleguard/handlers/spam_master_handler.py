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
        self.pending_campaigns = {}  # user_id -> campaign_data
        
    def register_handlers(self):
        @self.bot.on(events.CallbackQuery(pattern=b"spam_master"))
        async def spam_master_menu(event):
            await event.answer()
            buttons = [
                [Button.inline("📊 Gather Users", b"spam_gather")],
                [Button.inline("📤 Bulk Send", b"spam_send")],
                [Button.inline("💬 Group Spam", b"group_spam")],
                [Button.inline("🤖 Auto Reply", b"spam_reply")],
                [Button.inline("📈 Campaign Stats", b"spam_stats")],
                [Button.inline("🔙 Back", b"main_menu")]
            ]
            await event.edit("🎯 **SpamMaster**\n\nBulk messaging and automation", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"spam_gather"))
        async def gather_menu(event):
            await event.answer()
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
            await event.answer()
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
            await event.answer()
            account_name = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            await event.edit(f"⏳ Auto-gathering from all groups/channels...\n\nAccount: **{account_name}**")
            total = await self._auto_gather_all(user_id, account_name)
            await event.respond(f"✅ Auto-gathered {total} users from all groups/channels")
        
        @self.bot.on(events.CallbackQuery(pattern=b"gather_manual"))
        async def gather_manual(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await self._get_user_accounts(user_id)
            
            buttons = [[Button.inline(f"📱 {acc['name']}", f"gather_acc:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🔙 Back", b"spam_gather")])
            await event.edit("Select account to gather users:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"gather_acc:(.+)"))
        async def gather_account(event):
            await event.answer()
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
            await event.answer()
            user_id = event.sender_id
            accounts = await self._get_user_accounts(user_id)
            if not accounts:
                await event.answer("❌ No accounts found", alert=True)
                return
            
            buttons = [
                [Button.inline("🔄 Multi-Account (Rotate)", b"send_multi")],
                [Button.inline("📱 Single Account", b"send_single")],
                [Button.inline("🔙 Back", b"spam_master")]
            ]
            await event.edit(
                f"📤 **Bulk Send Mode**\n\n"
                f"Available Accounts: **{len(accounts)}**\n\n"
                f"🔄 Multi-Account: Rotate between accounts (prevents limits)\n"
                f"📱 Single Account: Use one account only",
                buttons=buttons
            )
        
        @self.bot.on(events.CallbackQuery(pattern=b"send_single"))
        async def send_single(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await self._get_user_accounts(user_id)
            
            buttons = [[Button.inline(f"📱 {acc['name']}", f"send_acc:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🔙 Back", b"spam_send")])
            await event.edit("Select account:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"send_multi"))
        async def send_multi(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await self._get_user_accounts(user_id)
            
            if len(accounts) < 2:
                await event.answer("❌ Need at least 2 accounts for rotation", alert=True)
                return
            
            # Show account selection with checkboxes
            text = "🔄 **Select Accounts to Rotate**\n\nChoose which accounts to use:"
            buttons = []
            for acc in accounts[:10]:
                buttons.append([Button.inline(f"☐ {acc['name']}", f"toggle_acc:{acc['phone']}".encode())])
            buttons.append([Button.inline("✅ Confirm Selection", b"confirm_multi")])
            buttons.append([Button.inline("🔙 Back", b"spam_send")])
            
            # Store selection state
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "multi_select"},
                {"$set": {"selected": [], "all_accounts": [a['phone'] for a in accounts]}},
                upsert=True
            )
            
            await event.edit(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"toggle_acc:(.+)"))
        async def toggle_account(event):
            await event.answer()
            user_id = event.sender_id
            phone = event.data.decode().split(":", 1)[1]
            
            # Get current selection
            data = await mongodb.db.temp_data.find_one({"user_id": user_id, "type": "multi_select"})
            selected = data.get("selected", [])
            
            # Toggle selection
            if phone in selected:
                selected.remove(phone)
            else:
                selected.append(phone)
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "multi_select"},
                {"$set": {"selected": selected}}
            )
            
            # Update display
            accounts = await self._get_user_accounts(user_id)
            text = f"🔄 **Select Accounts to Rotate**\n\nSelected: **{len(selected)}** accounts\n\nChoose which accounts to use:"
            buttons = []
            for acc in accounts[:10]:
                check = "☑" if acc['phone'] in selected else "☐"
                buttons.append([Button.inline(f"{check} {acc['name']}", f"toggle_acc:{acc['phone']}".encode())])
            buttons.append([Button.inline("✅ Confirm Selection", b"confirm_multi")])
            buttons.append([Button.inline("🔙 Back", b"spam_send")])
            
            await event.edit(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"confirm_multi"))
        async def confirm_multi(event):
            user_id = event.sender_id
            
            data = await mongodb.db.temp_data.find_one({"user_id": user_id, "type": "multi_select"})
            selected = data.get("selected", []) if data else []
            
            if len(selected) < 2:
                await event.answer("❌ Select at least 2 accounts", alert=True)
                return
            
            users = await self._get_gathered_users(user_id)
            if not users:
                await event.answer("❌ No users gathered yet. Use Gather Users first.", alert=True)
                return
            
            await event.answer()
            await event.edit(
                f"📤 **Multi-Account Setup**\n\n"
                f"Accounts: **{len(selected)}**\n"
                f"Users: **{len(users)}**\n\n"
                f"Send your message (text/media):"
            )
            
            self.pending_campaigns[user_id] = {
                'type': 'multi',
                'accounts': selected,
                'users': users
            }
        
        @self.bot.on(events.CallbackQuery(pattern=rb"send_acc:(.+)"))
        async def send_account(event):
            account_name = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            users = await self._get_gathered_users(user_id)
            if not users:
                await event.answer("❌ No users gathered yet. Use Gather Users first.", alert=True)
                return
            
            await event.answer()
            await event.edit(
                f"📤 **Bulk Send Setup**\n\n"
                f"Account: **{account_name}**\n"
                f"Users: **{len(users)}**\n\n"
                f"Send your message (text/media):"
            )
            
            self.pending_campaigns[user_id] = {
                'type': 'single',
                'account': account_name,
                'users': users
            }
        
        @self.bot.on(events.NewMessage(incoming=True))
        async def handle_campaign_message(msg_event):
            user_id = msg_event.sender_id
            if user_id not in self.pending_campaigns:
                return
            
            campaign_data = self.pending_campaigns.pop(user_id)
            
            if campaign_data['type'] == 'single':
                buttons = [[Button.inline("🛑 Stop Campaign", b"stop_temp")]]
                progress_msg = await msg_event.reply(
                    f"🚀 **Campaign Started**\n\n"
                    f"Account: **{campaign_data['account']}**\n"
                    f"Total Users: **{len(campaign_data['users'])}**\n"
                    f"Sent: **0/{len(campaign_data['users'])}**\n"
                    f"Progress: □□□□□□□□□□ 0%",
                    buttons=buttons
                )
                
                await self._start_campaign(
                    user_id, campaign_data['account'], campaign_data['users'], msg_event, progress_msg
                )
            elif campaign_data['type'] == 'multi':
                buttons = [[Button.inline("🛑 Stop Campaign", b"stop_temp")]]
                progress_msg = await msg_event.reply(
                    f"🚀 **Multi-Account Campaign**\n\n"
                    f"Accounts: **{len(campaign_data['accounts'])}**\n"
                    f"Total Users: **{len(campaign_data['users'])}**\n"
                    f"Sent: **0/{len(campaign_data['users'])}**\n"
                    f"Progress: □□□□□□□□□□ 0%",
                    buttons=buttons
                )
                
                await self._start_multi_campaign(
                    user_id, campaign_data['accounts'], campaign_data['users'], msg_event, progress_msg
                )
        
        @self.bot.on(events.CallbackQuery(pattern=b"spam_reply"))
        async def reply_menu(event):
            await event.answer()
            user_id = event.sender_id
            
            # Get reply statistics
            total_sent = await mongodb.db.spam_users.count_documents({"owner_id": user_id, "status": "sent"})
            total_replied = await mongodb.db.spam_users.count_documents({"owner_id": user_id, "replied": {"$exists": True}})
            reply_rate = f"{int((total_replied/total_sent)*100)}%" if total_sent > 0 else "0%"
            
            buttons = [
                [Button.inline("📊 View Replies", b"view_replies")],
                [Button.inline("🗑️ Clear Data", b"clear_spam_data")],
                [Button.inline("🔙 Back", b"spam_master")]
            ]
            
            await event.edit(
                f"📈 **Reply Statistics**\n\n"
                f"Messages Sent: **{total_sent}**\n"
                f"Replies Received: **{total_replied}**\n"
                f"Reply Rate: **{reply_rate}**\n\n"
                f"Track user responses to your campaigns",
                buttons=buttons
            )
        
        @self.bot.on(events.CallbackQuery(pattern=b"view_replies"))
        async def view_replies(event):
            await event.answer()
            user_id = event.sender_id
            
            cursor = mongodb.db.spam_users.find(
                {"owner_id": user_id, "replied": {"$exists": True}}
            ).sort("replied_at", -1).limit(20)
            replies = await cursor.to_list(length=20)
            
            if not replies:
                await event.answer("No replies yet", alert=True)
                return
            
            text = "💬 **Recent Replies**\n\n"
            for r in replies[:10]:
                name = r.get("first_name", "Unknown")
                reply = r.get("replied", "N/A")
                text += f"• {name}: {reply}\n"
            
            buttons = [[Button.inline("🔙 Back", b"spam_reply")]]
            await event.edit(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"clear_spam_data"))
        async def clear_data(event):
            await event.answer()
            user_id = event.sender_id
            
            await mongodb.db.spam_users.delete_many({"owner_id": user_id})
            await mongodb.db.spam_campaigns.delete_many({"user_id": user_id})
            
            await event.answer("✅ All spam data cleared", alert=True)
            await reply_menu(event)
        
        @self.bot.on(events.CallbackQuery(pattern=b"group_spam"))
        async def group_spam_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await self._get_user_accounts(user_id)
            if not accounts:
                await event.answer("❌ No accounts found", alert=True)
                return
            
            buttons = [[Button.inline(f"📱 {acc['name']}", f"grp_acc:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🔙 Back", b"spam_master")])
            await event.edit("💬 **Group Spam**\n\nSelect account:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"grp_acc:(.+)"))
        async def group_spam_account(event):
            await event.answer()
            account_name = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            await event.edit(
                f"💬 **Group Spam Setup**\n\n"
                f"Account: **{account_name}**\n\n"
                f"Send your message (text/media):"
            )
            
            @self.bot.on(events.NewMessage(from_users=user_id))
            async def handle_group_message(msg_event):
                self.bot.remove_event_handler(handle_group_message)
                
                await msg_event.reply("⏳ Starting group spam...")
                count = await self._spam_all_groups(user_id, account_name, msg_event)
                await msg_event.reply(f"✅ Sent to {count} groups")
        
        @self.bot.on(events.CallbackQuery(pattern=b"spam_stats"))
        async def show_stats(event):
            await event.answer()
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
            await event.answer()
            campaign_id = event.data.decode().split(":", 1)[1]
            self.active_campaigns[campaign_id] = True
            
            from bson import ObjectId
            await mongodb.db.spam_campaigns.update_one(
                {"_id": ObjectId(campaign_id)},
                {"$set": {"stopped": True}}
            )
            await event.answer("🛑 Campaign stopped", alert=True)
            await event.edit(f"🛑 Campaign {campaign_id} stopped")
        
        @self.bot.on(events.CallbackQuery(pattern=b"stop_temp"))
        async def stop_temp_campaign(event):
            # Find and stop the most recent campaign for this user
            user_id = event.sender_id
            campaign = await mongodb.db.spam_campaigns.find_one(
                {"user_id": user_id},
                sort=[("_id", -1)]
            )
            if campaign:
                campaign_id = str(campaign["_id"])
                self.active_campaigns[campaign_id] = True
                await mongodb.db.spam_campaigns.update_one(
                    {"_id": campaign["_id"]},
                    {"$set": {"stopped": True}}
                )
                await event.answer("🛑 Campaign stopped", alert=True)
    
    async def _get_user_accounts(self, user_id: int) -> List[Dict]:
        """Get user's accounts with names"""
        if user_id not in self.user_clients:
            return []
        
        accounts = []
        for account_name in self.user_clients[user_id].keys():
            # Use account_name as both identifier and display name
            accounts.append({"phone": account_name, "name": account_name})
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
        """Get gathered users for bulk send - deduplicated and filtered"""
        cursor = mongodb.db.spam_users.find(
            {"owner_id": user_id, "status": "new"}
        )
        all_users = await cursor.to_list(length=None)
        
        # Deduplicate by user_id
        seen = set()
        unique_users = []
        for user in all_users:
            if user["user_id"] not in seen:
                seen.add(user["user_id"])
                unique_users.append(user)
        
        return unique_users[:500]
    
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
    
    async def _start_multi_campaign(self, user_id: int, account_phones: List[str], users: List, msg_event, progress_msg) -> str:
        """Start multi-account campaign with rotation"""
        campaign = {
            "user_id": user_id,
            "accounts": account_phones,
            "total": len(users),
            "sent": 0,
            "replies": 0,
            "message": msg_event.text,
            "multi": True
        }
        
        result = await mongodb.db.spam_campaigns.insert_one(campaign)
        campaign_id = str(result.inserted_id)
        
        asyncio.create_task(self._run_multi_campaign(campaign_id, user_id, account_phones, users, msg_event, progress_msg))
        return campaign_id
    
    async def _run_multi_campaign(self, campaign_id: str, user_id: int, account_phones: List[str], users: List, msg_event, progress_msg):
        """Execute multi-account campaign with rotation"""
        try:
            self.active_campaigns[campaign_id] = False
            total = len(users)
            sent = 0
            account_idx = 0
            
            for idx, user in enumerate(users, 1):
                if self.active_campaigns.get(campaign_id):
                    await progress_msg.edit(
                        f"🛑 **Campaign Stopped**\n\n"
                        f"Accounts: **{len(account_phones)}**\n"
                        f"Total Users: **{total}**\n"
                        f"Sent: **{sent}/{total}**\n"
                        f"Status: Stopped by user"
                    )
                    break
                
                # Rotate accounts
                current_phone = account_phones[account_idx]
                client = self.user_clients[user_id][current_phone]
                me = await client.get_me()
                
                # Skip self
                if user["user_id"] == me.id:
                    continue
                
                try:
                    if msg_event.photo:
                        await client.send_file(user["user_id"], msg_event.photo, caption=msg_event.text)
                    elif msg_event.video:
                        await client.send_file(user["user_id"], msg_event.video, caption=msg_event.text)
                    elif msg_event.document:
                        await client.send_file(user["user_id"], msg_event.document, caption=msg_event.text)
                    else:
                        await client.send_message(user["user_id"], msg_event.text)
                    
                    asyncio.create_task(self._listen_for_reply(client, user["user_id"], user["_id"]))
                    sent += 1
                    
                    await mongodb.db.spam_users.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"status": "sent", "account": current_phone}}
                    )
                    
                    from bson import ObjectId
                    await mongodb.db.spam_campaigns.update_one(
                        {"_id": ObjectId(campaign_id)},
                        {"$inc": {"sent": 1}}
                    )
                    
                    # Rotate to next account
                    account_idx = (account_idx + 1) % len(account_phones)
                    
                    if idx % 5 == 0 or idx == total:
                        percent = int((sent / total) * 100)
                        filled = int(percent / 10)
                        bar = "■" * filled + "□" * (10 - filled)
                        buttons = [[Button.inline("🛑 Stop", f"stop_camp:{campaign_id}".encode())]]
                        await progress_msg.edit(
                            f"🚀 **Multi-Account Campaign**\n\n"
                            f"Accounts: **{len(account_phones)}**\n"
                            f"Total Users: **{total}**\n"
                            f"Sent: **{sent}/{total}**\n"
                            f"Progress: {bar} {percent}%",
                            buttons=buttons
                        )
                    
                    await asyncio.sleep(random.uniform(30, 45))
                except Exception:
                    await asyncio.sleep(5)
            
            if not self.active_campaigns.get(campaign_id):
                await progress_msg.edit(
                    f"✅ **Campaign Completed**\n\n"
                    f"Accounts: **{len(account_phones)}**\n"
                    f"Total Users: **{total}**\n"
                    f"Sent: **{sent}/{total}**\n"
                    f"Progress: ■■■■■■■■■■ 100%"
                )
        except Exception as e:
            logger.error(f"Multi-campaign failed: {e}")
        finally:
            self.active_campaigns.pop(campaign_id, None)
    
    async def _run_campaign(self, campaign_id: str, user_id: int, account_name: str, users: List, msg_event, progress_msg):
        """Execute bulk send campaign"""
        try:
            client = self.user_clients[user_id][account_name]
            self.active_campaigns[campaign_id] = False
            total = len(users)
            sent = 0
            
            # Get account's own ID to exclude saved messages
            me = await client.get_me()
            my_id = me.id
            
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
                
                # Skip if user is self (saved messages)
                if user["user_id"] == my_id:
                    continue
                
                try:
                    if msg_event.photo:
                        sent_msg = await client.send_file(user["user_id"], msg_event.photo, caption=msg_event.text)
                    elif msg_event.video:
                        sent_msg = await client.send_file(user["user_id"], msg_event.video, caption=msg_event.text)
                    elif msg_event.document:
                        sent_msg = await client.send_file(user["user_id"], msg_event.document, caption=msg_event.text)
                    else:
                        sent_msg = await client.send_message(user["user_id"], msg_event.text)
                    
                    # Setup reply listener
                    asyncio.create_task(self._listen_for_reply(client, user["user_id"], user["_id"]))
                    
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
    
    async def _listen_for_reply(self, client, target_user_id: int, db_user_id):
        """Listen for reply from a specific user"""
        try:
            from datetime import datetime, timedelta
            
            @client.on(events.NewMessage(from_users=target_user_id, incoming=True))
            async def reply_handler(event):
                try:
                    # Update database with reply
                    await mongodb.db.spam_users.update_one(
                        {"_id": db_user_id},
                        {"$set": {
                            "replied": event.text or "[Media]",
                            "replied_at": datetime.utcnow()
                        }}
                    )
                    
                    # Remove handler after first reply
                    client.remove_event_handler(reply_handler)
                except Exception as e:
                    logger.error(f"Reply tracking error: {e}")
            
            # Auto-remove handler after 24 hours
            await asyncio.sleep(86400)
            try:
                client.remove_event_handler(reply_handler)
            except:
                pass
        except Exception as e:
            logger.error(f"Reply listener setup error: {e}")
    
    async def _spam_all_groups(self, user_id: int, account_name: str, msg_event) -> int:
        """Send message to all groups"""
        try:
            client = self.user_clients[user_id][account_name]
            count = 0
            
            async for dialog in client.iter_dialogs():
                if dialog.is_group and not getattr(dialog.entity, 'forum', False):
                    try:
                        if msg_event.photo:
                            await client.send_file(dialog.id, msg_event.photo, caption=msg_event.text)
                        elif msg_event.video:
                            await client.send_file(dialog.id, msg_event.video, caption=msg_event.text)
                        elif msg_event.document:
                            await client.send_file(dialog.id, msg_event.document, caption=msg_event.text)
                        else:
                            await client.send_message(dialog.id, msg_event.text)
                        
                        count += 1
                        await asyncio.sleep(random.uniform(5, 10))
                    except Exception:
                        await asyncio.sleep(2)
            
            return count
        except Exception as e:
            logger.error(f"Group spam failed: {e}")
            return 0
