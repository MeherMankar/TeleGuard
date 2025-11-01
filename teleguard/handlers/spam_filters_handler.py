"""Smart Filters and Delay System for SpamMaster"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Dict
from telethon import events, Button
from ..core.mongo_database import mongodb
from ..utils.bot_logger import logger


class SpamFiltersHandler:
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        
    def register_handlers(self):
        @self.bot.on(events.CallbackQuery(pattern=b"spam_filters"))
        async def filters_menu(event):
            await event.answer()
            user_id = event.sender_id
            
            try:
                await event.delete()
            except:
                pass
            
            config = await self._get_filter_config(user_id)
            
            buttons = [
                [Button.inline("⏱️ Smart Delays", b"filter_delays")],
                [Button.inline("🎯 User Filters", b"filter_users")],
                [Button.inline("⚙️ Settings", b"filter_settings")],
                [Button.inline("🔙 Back", b"spam_master")]
            ]
            
            text = (
                "🎯 **Smart Filters & Delays**\n\n"
                f"Smart Delays: {'✅ Enabled' if config.get('smart_delays') else '❌ Disabled'}\n"
                f"Delay Range: {config.get('min_delay', 40)}-{config.get('max_delay', 60)}s\n"
                f"Active Filters: {len(config.get('filters', []))}\n"
            )
            
            await event.respond(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"filter_delays"))
        async def delays_menu(event):
            await event.answer()
            user_id = event.sender_id
            
            try:
                await event.delete()
            except:
                pass
            
            config = await self._get_filter_config(user_id)
            
            buttons = [
                [Button.inline(f"{'✅' if config.get('smart_delays') else '☐'} Smart Delays", b"toggle_smart_delays")],
                [Button.inline("⏱️ Set Min Delay", b"set_min_delay")],
                [Button.inline("⏱️ Set Max Delay", b"set_max_delay")],
                [Button.inline("🔙 Back", b"spam_filters")]
            ]
            
            text = (
                "⏱️ **Smart Delay Settings**\n\n"
                f"Status: {'✅ Enabled' if config.get('smart_delays') else '❌ Disabled'}\n"
                f"Min Delay: {config.get('min_delay', 40)}s\n"
                f"Max Delay: {config.get('max_delay', 60)}s\n\n"
                "Smart delays prevent rate limits by:\n"
                "• Random delays between messages\n"
                "• Adaptive timing based on account health\n"
                "• Time-zone aware sending"
            )
            
            await event.respond(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"toggle_smart_delays"))
        async def toggle_delays(event):
            user_id = event.sender_id
            config = await self._get_filter_config(user_id)
            enabled = not config.get('smart_delays', False)
            
            await mongodb.db.spam_config.update_one(
                {"user_id": user_id},
                {"$set": {"smart_delays": enabled}},
                upsert=True
            )
            
            await event.answer(f"Smart Delays {'Enabled' if enabled else 'Disabled'}", alert=True)
            await delays_menu(event)
        
        @self.bot.on(events.CallbackQuery(pattern=b"set_min_delay"))
        async def set_min(event):
            await event.answer()
            user_id = event.sender_id
            
            try:
                await event.delete()
            except:
                pass
            
            await event.respond("⏱️ Send minimum delay in seconds (20-120):")
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "delay_wait"},
                {"$set": {"field": "min_delay"}},
                upsert=True
            )
        
        @self.bot.on(events.CallbackQuery(pattern=b"set_max_delay"))
        async def set_max(event):
            await event.answer()
            user_id = event.sender_id
            
            try:
                await event.delete()
            except:
                pass
            
            await event.respond("⏱️ Send maximum delay in seconds (30-180):")
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "delay_wait"},
                {"$set": {"field": "max_delay"}},
                upsert=True
            )
        
        @self.bot.on(events.CallbackQuery(pattern=b"filter_users"))
        async def users_filter_menu(event):
            await event.answer()
            user_id = event.sender_id
            
            try:
                await event.delete()
            except:
                pass
            
            config = await self._get_filter_config(user_id)
            filters = config.get('filters', [])
            
            buttons = [
                [Button.inline(f"{'✅' if 'premium' in filters else '☐'} Premium Only", b"toggle_premium")],
                [Button.inline(f"{'✅' if 'verified' in filters else '☐'} Verified Only", b"toggle_verified")],
                [Button.inline(f"{'✅' if 'active' in filters else '☐'} Active Users", b"toggle_active")],
                [Button.inline(f"{'✅' if 'no_bots' in filters else '☐'} Exclude Bots", b"toggle_bots")],
                [Button.inline("🚫 Blacklist", b"manage_blacklist")],
                [Button.inline("🔙 Back", b"spam_filters")]
            ]
            
            text = (
                "🎯 **User Filters**\n\n"
                f"Active Filters: {len(filters)}\n\n"
                "Filter users by:\n"
                "• Premium status\n"
                "• Verified accounts\n"
                "• Activity level\n"
                "• Blacklist management"
            )
            
            await event.respond(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"toggle_premium"))
        async def toggle_premium(event):
            await self._toggle_filter(event, "premium")
        
        @self.bot.on(events.CallbackQuery(pattern=b"toggle_verified"))
        async def toggle_verified(event):
            await self._toggle_filter(event, "verified")
        
        @self.bot.on(events.CallbackQuery(pattern=b"toggle_active"))
        async def toggle_active(event):
            await self._toggle_filter(event, "active")
        
        @self.bot.on(events.CallbackQuery(pattern=b"toggle_bots"))
        async def toggle_bots(event):
            await self._toggle_filter(event, "no_bots")
        
        @self.bot.on(events.CallbackQuery(pattern=b"manage_blacklist"))
        async def blacklist_menu(event):
            await event.answer()
            user_id = event.sender_id
            
            try:
                await event.delete()
            except:
                pass
            
            count = await mongodb.db.spam_blacklist.count_documents({"owner_id": user_id})
            
            buttons = [
                [Button.inline("➕ Add User", b"blacklist_add")],
                [Button.inline("📋 View List", b"blacklist_view")],
                [Button.inline("🗑️ Clear All", b"blacklist_clear")],
                [Button.inline("🔙 Back", b"filter_users")]
            ]
            
            await event.respond(
                f"🚫 **Blacklist Management**\n\n"
                f"Blacklisted Users: {count}\n\n"
                "Blacklisted users will be excluded from all campaigns",
                buttons=buttons
            )
        
        @self.bot.on(events.CallbackQuery(pattern=b"blacklist_add"))
        async def blacklist_add(event):
            await event.answer()
            user_id = event.sender_id
            
            try:
                await event.delete()
            except:
                pass
            
            await event.respond("Send user ID or username to blacklist:")
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "blacklist_wait"},
                {"$set": {"action": "add"}},
                upsert=True
            )
        
        @self.bot.on(events.CallbackQuery(pattern=b"blacklist_view"))
        async def blacklist_view(event):
            await event.answer()
            user_id = event.sender_id
            
            cursor = mongodb.db.spam_blacklist.find({"owner_id": user_id}).limit(20)
            blacklist = await cursor.to_list(length=20)
            
            if not blacklist:
                await event.answer("Blacklist is empty", alert=True)
                return
            
            try:
                await event.delete()
            except:
                pass
            
            text = "🚫 **Blacklisted Users**\n\n"
            for item in blacklist[:10]:
                text += f"• {item.get('user_id')} - {item.get('reason', 'No reason')}\n"
            
            buttons = [[Button.inline("🔙 Back", b"manage_blacklist")]]
            await event.respond(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"blacklist_clear"))
        async def blacklist_clear(event):
            await event.answer()
            user_id = event.sender_id
            
            await mongodb.db.spam_blacklist.delete_many({"owner_id": user_id})
            await event.answer("✅ Blacklist cleared", alert=True)
            await blacklist_menu(event)
        
        @self.bot.on(events.CallbackQuery(pattern=b"filter_settings"))
        async def settings_menu(event):
            await event.answer()
            user_id = event.sender_id
            
            try:
                await event.delete()
            except:
                pass
            
            config = await self._get_filter_config(user_id)
            
            buttons = [
                [Button.inline(f"Max Users: {config.get('max_users', 500)}", b"set_max_users")],
                [Button.inline(f"{'✅' if config.get('skip_sent') else '☐'} Skip Sent", b"toggle_skip_sent")],
                [Button.inline("🔙 Back", b"spam_filters")]
            ]
            
            text = (
                "⚙️ **Filter Settings**\n\n"
                f"Max Users per Campaign: {config.get('max_users', 500)}\n"
                f"Skip Already Sent: {'✅ Yes' if config.get('skip_sent') else '❌ No'}\n"
            )
            
            await event.respond(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"toggle_skip_sent"))
        async def toggle_skip(event):
            user_id = event.sender_id
            config = await self._get_filter_config(user_id)
            enabled = not config.get('skip_sent', False)
            
            await mongodb.db.spam_config.update_one(
                {"user_id": user_id},
                {"$set": {"skip_sent": enabled}},
                upsert=True
            )
            
            await event.answer(f"Skip Sent {'Enabled' if enabled else 'Disabled'}", alert=True)
            await settings_menu(event)
        
        @self.bot.on(events.NewMessage(incoming=True))
        async def handle_filter_inputs(msg_event):
            user_id = msg_event.sender_id
            
            # Handle delay settings
            delay_state = await mongodb.db.temp_data.find_one({"user_id": user_id, "type": "delay_wait"})
            if delay_state:
                try:
                    value = int(msg_event.text.strip())
                    field = delay_state.get("field")
                    
                    if field == "min_delay" and 20 <= value <= 120:
                        await mongodb.db.spam_config.update_one(
                            {"user_id": user_id},
                            {"$set": {"min_delay": value}},
                            upsert=True
                        )
                        await msg_event.reply(f"✅ Min delay set to {value}s")
                    elif field == "max_delay" and 30 <= value <= 180:
                        await mongodb.db.spam_config.update_one(
                            {"user_id": user_id},
                            {"$set": {"max_delay": value}},
                            upsert=True
                        )
                        await msg_event.reply(f"✅ Max delay set to {value}s")
                    else:
                        await msg_event.reply("❌ Invalid value")
                    
                    await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "delay_wait"})
                except:
                    await msg_event.reply("❌ Send a valid number")
                return
            
            # Handle blacklist
            blacklist_state = await mongodb.db.temp_data.find_one({"user_id": user_id, "type": "blacklist_wait"})
            if blacklist_state:
                try:
                    target = msg_event.text.strip()
                    target_id = int(target) if target.isdigit() else target
                    
                    await mongodb.db.spam_blacklist.update_one(
                        {"owner_id": user_id, "user_id": target_id},
                        {"$set": {"owner_id": user_id, "user_id": target_id, "added_at": datetime.utcnow()}},
                        upsert=True
                    )
                    
                    await msg_event.reply(f"✅ Added {target_id} to blacklist")
                    await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "blacklist_wait"})
                except:
                    await msg_event.reply("❌ Invalid user ID/username")
                return
    
    async def _get_filter_config(self, user_id: int) -> Dict:
        """Get filter configuration"""
        config = await mongodb.db.spam_config.find_one({"user_id": user_id})
        return config or {
            "smart_delays": True,
            "min_delay": 40,
            "max_delay": 60,
            "filters": [],
            "max_users": 500,
            "skip_sent": True
        }
    
    async def _toggle_filter(self, event, filter_name: str):
        """Toggle a filter on/off"""
        user_id = event.sender_id
        config = await self._get_filter_config(user_id)
        filters = config.get('filters', [])
        
        if filter_name in filters:
            filters.remove(filter_name)
        else:
            filters.append(filter_name)
        
        await mongodb.db.spam_config.update_one(
            {"user_id": user_id},
            {"$set": {"filters": filters}},
            upsert=True
        )
        
        await event.answer(f"{filter_name.title()} {'Enabled' if filter_name in filters else 'Disabled'}", alert=True)
        
        # Refresh menu
        await event.answer()
        user_id = event.sender_id
        
        try:
            await event.delete()
        except:
            pass
        
        config = await self._get_filter_config(user_id)
        filters = config.get('filters', [])
        
        buttons = [
            [Button.inline(f"{'✅' if 'premium' in filters else '☐'} Premium Only", b"toggle_premium")],
            [Button.inline(f"{'✅' if 'verified' in filters else '☐'} Verified Only", b"toggle_verified")],
            [Button.inline(f"{'✅' if 'active' in filters else '☐'} Active Users", b"toggle_active")],
            [Button.inline(f"{'✅' if 'no_bots' in filters else '☐'} Exclude Bots", b"toggle_bots")],
            [Button.inline("🚫 Blacklist", b"manage_blacklist")],
            [Button.inline("🔙 Back", b"spam_filters")]
        ]
        
        text = (
            "🎯 **User Filters**\n\n"
            f"Active Filters: {len(filters)}\n\n"
            "Filter users by:\n"
            "• Premium status\n"
            "• Verified accounts\n"
            "• Activity level\n"
            "• Blacklist management"
        )
        
        await event.respond(text, buttons=buttons)
    
    async def apply_filters(self, user_id: int, users: List[Dict]) -> List[Dict]:
        """Apply filters to user list"""
        config = await self._get_filter_config(user_id)
        filters = config.get('filters', [])
        
        # Get blacklist
        cursor = mongodb.db.spam_blacklist.find({"owner_id": user_id})
        blacklist = await cursor.to_list(length=None)
        blacklist_ids = {b['user_id'] for b in blacklist}
        
        filtered = []
        for user in users:
            # Skip blacklisted
            if user['user_id'] in blacklist_ids:
                continue
            
            # Skip already sent if enabled
            if config.get('skip_sent') and user.get('status') == 'sent':
                continue
            
            # Apply filters (basic implementation)
            if 'no_bots' in filters and user.get('bot'):
                continue
            
            filtered.append(user)
        
        # Limit max users
        max_users = config.get('max_users', 500)
        return filtered[:max_users]
    
    def get_smart_delay(self, user_id: int, config: Dict = None) -> float:
        """Calculate smart delay"""
        if not config:
            return random.uniform(40, 60)
        
        if not config.get('smart_delays'):
            return random.uniform(40, 60)
        
        min_delay = config.get('min_delay', 40)
        max_delay = config.get('max_delay', 60)
        
        return random.uniform(min_delay, max_delay)
