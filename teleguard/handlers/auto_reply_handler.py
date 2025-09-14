"""Advanced auto-reply handler with keyword detection and analytics"""

import logging
import re
from datetime import datetime, time
from telethon import events
from telethon.tl.custom import Button
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class AutoReplyHandler:
    """Advanced auto-reply system with keyword detection and user categorization"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        self.handled_clients = set()
        self.keywords = {
            'hello': "Hey! I'm currently busy but I'll get back to you soon.",
            'urgent': "If this is urgent, please call me. Otherwise I'll reply when I'm free.",
            'meeting': "I'm in a meeting right now. I'll respond as soon as I'm available.",
            'work': "I'm at work currently. I'll check messages later today."
        }
        self.business_hours = {'start': time(9, 0), 'end': time(17, 0), 'days': [0, 1, 2, 3, 4]}
        self.analytics = {'total_messages': 0, 'auto_replies_sent': 0, 'keyword_hits': {}, 'unmatched_queries': 0}
        self.pending_actions = {}  # Track user input states
        
    def setup_auto_reply_handlers(self):
        """Set up auto-reply handlers for all user clients"""
        for user_id, clients in self.user_clients.items():
            for account_name, client in clients.items():
                if client and client.is_connected():
                    self._setup_client_handler(user_id, account_name, client)
    
    def _setup_client_handler(self, user_id: int, account_name: str, client):
        """Set up auto-reply handler for a specific client"""
        
        # Check if handler already exists for this client
        client_key = f"{user_id}:{account_name}"
        if client_key in self.handled_clients:
            return
            
        self.handled_clients.add(client_key)
        
        @client.on(events.NewMessage(incoming=True, func=lambda e: not e.is_group and not e.is_channel))
        async def auto_reply_handler(event):
            try:
                account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                if not account or not account.get("auto_reply_enabled", False):
                    return
                
                message_text = event.message.text.lower() if event.message.text else ""
                sender_id = event.sender_id
                
                self.analytics['total_messages'] += 1
                
                # Check for keyword matches
                matched_keyword = None
                for keyword in self.keywords:
                    if re.search(r'\b' + keyword + r'\b', message_text):
                        matched_keyword = keyword
                        break
                
                if matched_keyword:
                    self.analytics['keyword_hits'][matched_keyword] = self.analytics['keyword_hits'].get(matched_keyword, 0) + 1
                    response = self.keywords[matched_keyword]
                else:
                    self.analytics['unmatched_queries'] += 1
                    now = datetime.now()
                    is_business_hours = (
                        now.weekday() in self.business_hours['days'] and
                        self.business_hours['start'] <= now.time() <= self.business_hours['end']
                    )
                    
                    if is_business_hours:
                        response = "I'm currently available and will respond soon."
                    else:
                        response = "I'm not available right now. I'll get back to you later."
                
                # Add contact type detection
                contact_type = await self._get_contact_type(sender_id)
                if contact_type == 'family':
                    response = "Hey! " + response
                elif contact_type == 'work':
                    response = "Hi, " + response
                
                await event.reply(response)
                self.analytics['auto_replies_sent'] += 1
                logger.info(f"Auto-reply sent from {account_name} to {sender_id}")
                
            except Exception as e:
                logger.error(f"Auto-reply error for {account_name}: {e}")
    
    async def setup_new_client_handler(self, user_id: int, account_name: str, client):
        """Set up auto-reply handler for a newly added client"""
        if client and client.is_connected():
            self._setup_client_handler(user_id, account_name, client)
    
    async def _get_contact_type(self, sender_id: int) -> str:
        """Determine contact type"""
        try:
            contact_data = await mongodb.db.contacts.find_one({"sender_id": sender_id})
            if contact_data:
                return contact_data.get('type', 'general')
            return 'general'
        except Exception:
            return 'general'
    
    async def _save_keywords(self, user_id: int):
        """Save custom keywords to database"""
        try:
            await mongodb.db.auto_reply_settings.update_one(
                {"user_id": user_id},
                {"$set": {"keywords": self.keywords}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error saving keywords: {e}")
    
    def setup_text_handler(self):
        """Setup text input handler for custom keywords"""
        @self.bot.on(events.NewMessage(pattern=r"^(?!/)"))
        async def handle_text_input(event):
            user_id = event.sender_id
            if user_id not in self.pending_actions:
                return
                
            action_data = self.pending_actions[user_id]
            text = event.message.text
            
            if action_data['action'] == 'add_keyword':
                if action_data['step'] == 'keyword':
                    action_data['keyword'] = text.lower().strip()
                    action_data['step'] = 'message'
                    await event.reply(f"✅ Keyword: '{text}'\n\n📝 Now send the auto-reply message:")
                    
                elif action_data['step'] == 'message':
                    keyword = action_data['keyword']
                    self.keywords[keyword] = text
                    await self._save_keywords(user_id)
                    del self.pending_actions[user_id]
                    
                    buttons = [[Button.inline("🔙 Back to Keywords", "auto_reply:keywords")]]
                    await event.reply(f"✅ **Keyword Added!**\n\nKeyword: '{keyword}'\nMessage: {text[:100]}...", buttons=buttons)
    
    def setup_auto_reply_menu(self):
        """Setup auto-reply menu handlers"""
        @self.bot.on(events.CallbackQuery(pattern=r"^auto_reply:"))
        async def handle_auto_reply_menu(event):
            user_id = event.sender_id
            data = event.data.decode("utf-8")
            
            if data == "auto_reply:main":
                buttons = [
                    [Button.inline("⚙️ Configure Messages", "auto_reply:keywords")],
                    [Button.inline("📊 View Stats", "auto_reply:analytics")],
                    [Button.inline("🕒 Availability Hours", "auto_reply:hours")]
                ]
                await event.edit("🤖 **Auto-Reply Settings**\n\nManage your automatic responses:", buttons=buttons)
                
            elif data == "auto_reply:keywords":
                keyword_list = "\n".join([f"• {k}: {v[:50]}..." for k, v in self.keywords.items()])
                buttons = [
                    [Button.inline("➕ Add Keyword", "auto_reply:add_keyword")],
                    [Button.inline("➖ Remove Keyword", "auto_reply:remove_keyword")],
                    [Button.inline("🔙 Back", "auto_reply:main")]
                ]
                await event.edit(f"🔑 **Active Keywords:**\n\n{keyword_list}", buttons=buttons)
                
            elif data == "auto_reply:add_keyword":
                self.pending_actions[user_id] = {'action': 'add_keyword', 'step': 'keyword'}
                await event.edit("➕ **Add New Keyword**\n\nSend the keyword you want to detect (e.g., 'busy', 'vacation'):")
                
            elif data == "auto_reply:remove_keyword":
                if self.keywords:
                    buttons = [[Button.inline(f"❌ {k}", f"auto_reply:delete:{k}")] for k in self.keywords.keys()]
                    buttons.append([Button.inline("🔙 Back", "auto_reply:keywords")])
                    await event.edit("➖ **Remove Keyword**\n\nSelect keyword to delete:", buttons=buttons)
                else:
                    await event.edit("⚠️ No keywords to remove.", buttons=[[Button.inline("🔙 Back", "auto_reply:keywords")]])
                    
            elif data.startswith("auto_reply:delete:"):
                keyword = data.split(":", 2)[2]
                if keyword in self.keywords:
                    del self.keywords[keyword]
                    await self._save_keywords(user_id)
                    await event.edit(f"✅ Keyword '{keyword}' removed!", buttons=[[Button.inline("🔙 Back", "auto_reply:keywords")]])
                else:
                    await event.edit("❌ Keyword not found.", buttons=[[Button.inline("🔙 Back", "auto_reply:keywords")]])
                    
            elif data == "auto_reply:analytics":
                stats = f"📊 **Auto-Reply Analytics**\n\n"
                stats += f"📨 Total Messages: {self.analytics['total_messages']}\n"
                stats += f"🤖 Auto-Replies Sent: {self.analytics['auto_replies_sent']}\n"
                stats += f"❓ Unmatched Queries: {self.analytics['unmatched_queries']}\n\n"
                stats += f"🔑 **Keyword Hits:**\n"
                for keyword, count in self.analytics['keyword_hits'].items():
                    stats += f"• {keyword}: {count}\n"
                buttons = [[Button.inline("🔙 Back", "auto_reply:main")]]
                await event.edit(stats, buttons=buttons)
                
            elif data == "auto_reply:hours":
                current_hours = f"{self.business_hours['start'].strftime('%H:%M')} - {self.business_hours['end'].strftime('%H:%M')}"
                days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                active_days = ', '.join([days[i] for i in self.business_hours['days']])
                
                text = f"🕒 **Availability Hours**\n\n"
                text += f"⏰ Hours: {current_hours}\n"
                text += f"📅 Days: {active_days}\n\n"
                text += f"During these hours, responses will indicate availability."
                
                buttons = [[Button.inline("🔙 Back", "auto_reply:main")]]
                await event.edit(text, buttons=buttons)

    async def load_user_keywords(self, user_id: int):
        """Load user's custom keywords from database"""
        try:
            settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id})
            if settings and 'keywords' in settings:
                self.keywords.update(settings['keywords'])
        except Exception as e:
            logger.error(f"Error loading keywords for user {user_id}: {e}")= data.split(":", 2)[2]
                if keyword in self.keywords:
                    del self.keywords[keyword]
                    await event.edit(f"✅ Keyword '{keyword}' deleted!", buttons=[[Button.inline("🔙 Back", "auto_reply:keywords")]])
                else:
                    await event.edit("❌ Keyword not found.", buttons=[[Button.inline("🔙 Back", "auto_reply:keywords")]])
                
            elif data == "auto_reply:analytics":
                stats = self.analytics
                analytics_text = f"📊 **Analytics:**\n\n" \
                               f"📨 Total Messages: {stats['total_messages']}\n" \
                               f"🤖 Auto-Replies Sent: {stats['auto_replies_sent']}\n" \
                               f"❓ Unmatched: {stats['unmatched_queries']}\n\n" \
                               f"🔥 **Top Keywords:**\n" + "\n".join([f"• {k}: {v}" for k, v in list(stats['keyword_hits'].items())[:3]])
                buttons = [[Button.inline("🔙 Back", "auto_reply:main")]]
                await event.edit(analytics_text, buttons=buttons)
                
            elif data == "auto_reply:hours":
                hours_text = f"🕒 **Availability Hours:**\n\n" \
                           f"Available: Monday - Friday, 9:00 AM - 5:00 PM\n" \
                           f"Offline: Weekends\n\n" \
                           f"Current Status: {'Available' if self._is_business_hours() else 'Away'}"
                buttons = [[Button.inline("🔙 Back", "auto_reply:main")]]
                await event.edit(hours_text, buttons=buttons)
    
    def _is_business_hours(self) -> bool:
        """Check if currently in business hours"""
        now = datetime.now()
        return (
            now.weekday() in self.business_hours['days'] and
            self.business_hours['start'] <= now.time() <= self.business_hours['end']
        )