"""Advanced SpamMaster - All features from external SpamMaster"""
import asyncio
import random
import logging
import csv
import string
from typing import Dict, List, Set, Optional
from telethon import events, Button
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, ChatWriteForbiddenError, SlowModeWaitError
from telethon.tl.functions.channels import InviteToChannelRequest
from ..core.mongo_database import mongodb
from ..utils.bot_logger import logger


class AdvancedSpamHandler:
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        self.active_raids = {}
        self.scraped_data = {}
    
    async def _handle_spam_master_menu(self, event):
        """Handle SpamMaster menu display"""
        try:
            user_id = event.sender_id
        except Exception as e:
            logger.error(f"Error getting user_id: {e}")
            return
        
        # Check warning acceptance
        try:
            warning_accepted = await mongodb.db.spam_config.find_one(
                {"user_id": user_id, "warning_accepted": True}
            )
        except Exception as e:
            logger.error(f"Error checking warning acceptance: {e}")
            warning_accepted = None
        
        if not warning_accepted:
            buttons = [
                [Button.inline("✅ I Accept All Terms & Risks", b"accept_spam_warning")],
                [Button.inline("❌ Decline & Go Back", b"decline_spam_warning")]
            ]
            warning_text = (
                "🚨 **CRITICAL WARNING - READ CAREFULLY** 🚨\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "⚠️ **TERMS OF SERVICE VIOLATION**\n"
                "Using SpamMaster features **VIOLATES** Telegram's Terms of Service.\n"
                "These operations are **ILLEGAL** under Telegram's policies.\n\n"
                "🚫 **SEVERE CONSEQUENCES:**\n"
                "• ⛔ **Immediate Account Ban** - Permanent suspension\n"
                "• 📵 **Phone Number Blacklist** - Cannot create new accounts\n"
                "• 🌐 **IP Address Ban** - Network-level restrictions\n"
                "• 💳 **Payment Restrictions** - Premium features blocked\n"
                "• 🔒 **Device Fingerprint Ban** - Hardware-level blocks\n"
                "• ⚖️ **Legal Action** - Potential legal consequences\n\n"
                "⛔ **ABSOLUTE DISCLAIMER:**\n"
                "The developers and TeleGuard project:\n"
                "• ❌ Take **ZERO** responsibility for any consequences\n"
                "• ❌ Will **NOT** help recover banned accounts\n"
                "• ❌ Are **NOT** liable for any damages or losses\n"
                "• ❌ Do **NOT** encourage or endorse these activities\n"
                "• ❌ Provide **NO** warranty or guarantees\n\n"
                "📜 **LEGAL AGREEMENT:**\n"
                "By clicking 'I Accept', you **LEGALLY AGREE** that:\n"
                "✓ You understand this violates Telegram's ToS\n"
                "✓ You accept **FULL** personal responsibility\n"
                "✓ You will **ONLY** use test/throwaway accounts\n"
                "✓ You acknowledge all risks and consequences\n"
                "✓ You release developers from **ALL** liability\n"
                "✓ You are **18+ years old** and legally competent\n\n"
                "🛡️ **STRONG RECOMMENDATION:**\n"
                "• Use **ONLY** disposable test accounts\n"
                "• **NEVER** use your main/personal accounts\n"
                "• Expect accounts to be **BANNED IMMEDIATELY**\n"
                "• Consider this a **LEARNING TOOL ONLY**\n\n"
                "⚠️ **YOU HAVE BEEN WARNED** ⚠️\n\n"
                "Only proceed if you **FULLY UNDERSTAND** and **ACCEPT** all risks."
            )
            await self.bot.send_message(user_id, warning_text, buttons=buttons)
            return
        
        # Show main menu
        try:
            accounts = await self._get_accounts(user_id)
        except Exception as e:
            logger.error(f"Error getting accounts: {e}")
            accounts = []
        
        buttons = [
            [Button.inline("📤 Mass Inviter", b"mass_invite"), Button.inline("📇 Contact Scraper", b"contact_scrape")],
            [Button.inline("🔍 Username Checker", b"username_check"), Button.inline("💣 Forward Bomber", b"forward_bomb")],
            [Button.inline("🌊 Message Flooder", b"message_flood"), Button.inline("⚔️ Raid Coordinator", b"raid_coord")],
            [Button.inline("🥷 Stealth Raid", b"stealth_raid"), Button.inline("🎯 Multi-Target Raid", b"multi_raid")],
            [Button.inline("📢 Send to All Groups", b"send_all_groups")],
            [Button.inline("🔙 Back", b"menu:main")]
        ]
        
        text = (
            "🔥 **ADVANCED SPAM OPERATIONS** 🔥\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ **WARNING: EXTREME RISK OPERATIONS**\n\n"
            "**Available Tools:**\n"
            "• 📤 Mass Inviter - Bulk invite users to groups\n"
            "• 📇 Contact Scraper - Extract contacts from groups\n"
            "• 🔍 Username Checker - Find available usernames\n"
            "• 💣 Forward Bomber - Mass forward messages\n"
            "• 🌊 Message Flooder - Rapid message flooding\n"
            "• ⚔️ Raid Coordinator - Multi-account raids\n"
            "• 🥷 Stealth Raid - Human-like raid patterns\n"
            "• 🎯 Multi-Target - Attack multiple groups\n\n"
            f"📊 **Status:** {len(accounts)} accounts ready\n\n"
            "⚠️ Use at your own risk!"
        )
        
        try:
            await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error sending SpamMaster menu: {e}")
            await self.bot.send_message(user_id, f"❌ Error loading SpamMaster menu: {str(e)}")
        
    def register_handlers(self):
        handler_self = self
        
        @self.bot.on(events.CallbackQuery(pattern=b"accept_spam_warning"))
        async def accept_warning(event):
            user_id = event.sender_id
            
            await mongodb.db.spam_config.update_one(
                {"user_id": user_id},
                {"$set": {"warning_accepted": True}},
                upsert=True
            )
            
            await event.answer("✅ Terms accepted. Redirecting...", alert=True)
            
            # Show main menu with operations
            accounts = await handler_self._get_accounts(user_id)
            
            buttons = [
                [Button.inline("📤 Mass Inviter", b"mass_invite"), Button.inline("📇 Contact Scraper", b"contact_scrape")],
                [Button.inline("🔍 Username Checker", b"username_check"), Button.inline("💣 Forward Bomber", b"forward_bomb")],
                [Button.inline("🌊 Message Flooder", b"message_flood"), Button.inline("⚔️ Raid Coordinator", b"raid_coord")],
                [Button.inline("🥷 Stealth Raid", b"stealth_raid"), Button.inline("🎯 Multi-Target Raid", b"multi_raid")],
                [Button.inline("📢 Send to All Groups", b"send_all_groups")],
                [Button.inline("🔙 Back to Main Menu", b"menu:main")]
            ]
            
            text = (
                "🔥 **SPAMMASTER - ADVANCED OPERATIONS** 🔥\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "⚠️ **EXTREME RISK - USE AT YOUR OWN RISK** ⚠️\n\n"
                "🛠️ **Available Operations:**\n\n"
                "📤 **Mass Inviter**\n"
                "   Bulk invite users to target groups\n"
                "   ⚠️ High ban risk | Requires user database\n\n"
                "📇 **Contact Scraper**\n"
                "   Extract member contacts from groups\n"
                "   📊 Exports to CSV | Up to 5000 users\n\n"
                "🔍 **Username Checker**\n"
                "   Find available Telegram usernames\n"
                "   🎯 Checks 100+ variations | Fast scanning\n\n"
                "💣 **Forward Bomber**\n"
                "   Mass forward messages to users\n"
                "   ⚡ Rapid delivery | Flood protection bypass\n\n"
                "🌊 **Message Flooder**\n"
                "   Rapid message spam to groups\n"
                "   💥 50+ messages/session | Instant flood\n\n"
                "⚔️ **Raid Coordinator**\n"
                "   Multi-account coordinated raids\n"
                "   👥 Requires 2+ accounts | 60s duration\n\n"
                "🥷 **Stealth Raid**\n"
                "   Human-like raid patterns\n"
                "   🕵️ Delayed messages | Evasion tactics\n\n"
                "🎯 **Multi-Target Raid**\n"
                "   Attack multiple groups simultaneously\n"
                "   🎯 Requires 3+ accounts | Distributed attack\n\n"
                f"📊 **System Status:**\n"
                f"• Active Accounts: {len(accounts)}\n"
                f"• Operations: Ready\n"
                f"• Risk Level: 🔴 EXTREME\n\n"
                "⚠️ Remember: You accepted full responsibility!"
            )
            
            await event.edit(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"decline_spam_warning"))
        async def decline_warning(event):
            await event.answer("❌ Access denied", alert=True)
            # Redirect to main menu by calling menu handler
            if hasattr(self.bot_manager, 'menu_system'):
                await self.bot_manager.menu_system._handle_help(type("Event", (), {"sender_id": event.sender_id, "reply": lambda x, buttons=None: self.bot.send_message(event.sender_id, x, buttons=buttons)})())
            else:
                await event.edit("🔙 Returning to main menu...", buttons=[[Button.inline("🏠 Main Menu", b"menu:main")]])
        
        @self.bot.on(events.CallbackQuery(pattern=b"advanced_spam"))
        async def advanced_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            buttons = [
                [Button.inline("📤 Mass Inviter", b"mass_invite"), Button.inline("📇 Contact Scraper", b"contact_scrape")],
                [Button.inline("🔍 Username Checker", b"username_check"), Button.inline("💣 Forward Bomber", b"forward_bomb")],
                [Button.inline("🌊 Message Flooder", b"message_flood"), Button.inline("⚔️ Raid Coordinator", b"raid_coord")],
                [Button.inline("🥷 Stealth Raid", b"stealth_raid"), Button.inline("🎯 Multi-Target Raid", b"multi_raid")],
                [Button.inline("📢 Send to All Groups", b"send_all_groups")],
                [Button.inline("🔙 Back", b"spam_master")]
            ]
            
            text = (
                "🔥 **ADVANCED SPAM OPERATIONS** 🔥\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "⚠️ **WARNING: EXTREME RISK OPERATIONS**\n\n"
                "**Available Tools:**\n"
                "• 📤 Mass Inviter - Bulk invite users to groups\n"
                "• 📇 Contact Scraper - Extract contacts from groups\n"
                "• 🔍 Username Checker - Find available usernames\n"
                "• 💣 Forward Bomber - Mass forward messages\n"
                "• 🌊 Message Flooder - Rapid message flooding\n"
                "• ⚔️ Raid Coordinator - Multi-account raids\n"
                "• 🥷 Stealth Raid - Human-like raid patterns\n"
                "• 🎯 Multi-Target - Attack multiple groups\n\n"
                "⚠️ Use at your own risk!"
            )
            
            await event.edit(text, buttons=buttons)
        
        # Mass Inviter
        @self.bot.on(events.CallbackQuery(pattern=b"mass_invite"))
        async def mass_invite_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            if not accounts:
                await event.answer("❌ No accounts", alert=True)
                return
            
            buttons = [[Button.inline(f"📱 {acc['name']}", f"mi_acc:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🔙 Back", b"advanced_spam")])
            
            await event.edit("📤 **Mass Inviter**\n\nSelect account:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"mi_acc:(.+)"))
        async def mass_invite_setup(event):
            phone = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            buttons = [
                [Button.inline("🌐 All Groups", f"mi_all:{phone}".encode())],
                [Button.inline("🎯 Specific Group", f"mi_spec:{phone}".encode())],
                [Button.inline("🔙 Back", b"mass_invite")]
            ]
            
            await event.edit(
                f"📤 **Mass Inviter Setup**\n\n"
                f"Account: `{phone}`\n\n"
                f"Choose target:",
                buttons=buttons
            )
        
        @self.bot.on(events.CallbackQuery(pattern=rb"mi_spec:(.+)"))
        async def mass_invite_specific(event):
            phone = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "mass_invite"},
                {"$set": {"phone": phone, "step": "target"}},
                upsert=True
            )
            
            await event.edit(
                f"📤 **Mass Inviter - Specific Group**\n\n"
                f"Account: `{phone}`\n\n"
                f"Send target group username/link:"
            )
        
        @self.bot.on(events.CallbackQuery(pattern=rb"mi_all:(.+)"))
        async def mass_invite_all(event):
            phone = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            await event.answer("🌐 Starting mass invite to all groups...", alert=True)
            await handler_self._execute_mass_invite_all(event, phone, user_id)
        
        # Contact Scraper
        @self.bot.on(events.CallbackQuery(pattern=b"contact_scrape"))
        async def contact_scrape_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            if not accounts:
                await event.answer("❌ No accounts", alert=True)
                return
            
            buttons = [[Button.inline(f"📱 {acc['name']}", f"cs_acc:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🌐 Scrape All Groups", b"cs_all_groups")])
            buttons.append([Button.inline("🔙 Back", b"advanced_spam")])
            
            await event.edit("📇 **Contact Scraper**\n\nSelect account or scrape all:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"cs_acc:(.+)"))
        async def contact_scrape_setup(event):
            phone = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "contact_scrape"},
                {"$set": {"phone": phone, "step": "group"}},
                upsert=True
            )
            
            await event.edit(
                f"📇 **Contact Scraper Setup**\n\n"
                f"Account: `{phone}`\n\n"
                f"Send group username/link to scrape:"
            )
        
        @self.bot.on(events.CallbackQuery(pattern=b"cs_all_groups"))
        async def contact_scrape_all_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            if not accounts:
                await event.answer("❌ No accounts", alert=True)
                return
            
            buttons = [[Button.inline(f"📱 {acc['name']}", f"cs_all:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🔙 Back", b"contact_scrape")])
            
            await event.edit("🌐 **Scrape All Groups**\n\nSelect account:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"cs_all:(.+)"))
        async def contact_scrape_all_execute(event):
            phone = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            await event.answer("🌐 Starting scrape from all groups...", alert=True)
            await handler_self._execute_contact_scrape_all(event, phone, user_id)
        
        # Username Checker
        @self.bot.on(events.CallbackQuery(pattern=b"username_check"))
        async def username_check_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            if not accounts:
                await event.answer("❌ No accounts", alert=True)
                return
            
            buttons = [[Button.inline(f"📱 {acc['name']}", f"uc_acc:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🔙 Back", b"advanced_spam")])
            
            await event.edit("🔍 **Username Checker**\n\nSelect account:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"uc_acc:(.+)"))
        async def username_check_setup(event):
            phone = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "username_check"},
                {"$set": {"phone": phone, "step": "base"}},
                upsert=True
            )
            
            await event.edit(
                f"🔍 **Username Checker Setup**\n\n"
                f"Account: `{phone}`\n\n"
                f"Send base username (e.g., 'test'):"
            )
        
        # Forward Bomber
        @self.bot.on(events.CallbackQuery(pattern=b"forward_bomb"))
        async def forward_bomb_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            if not accounts:
                await event.answer("❌ No accounts", alert=True)
                return
            
            buttons = [[Button.inline(f"📱 {acc['name']}", f"fb_acc:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🔙 Back", b"advanced_spam")])
            
            await event.edit("💣 **Forward Bomber**\n\nSelect account:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"fb_acc:(.+)"))
        async def forward_bomb_setup(event):
            phone = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            buttons = [
                [Button.inline("🌐 All Groups", f"fb_all:{phone}".encode())],
                [Button.inline("🎯 Specific Target", f"fb_spec:{phone}".encode())],
                [Button.inline("🔙 Back", b"forward_bomb")]
            ]
            
            await event.edit(
                f"💣 **Forward Bomber Setup**\n\n"
                f"Account: `{phone}`\n\n"
                f"Choose target:",
                buttons=buttons
            )
        
        @self.bot.on(events.CallbackQuery(pattern=rb"fb_spec:(.+)"))
        async def forward_bomb_specific(event):
            phone = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "forward_bomb"},
                {"$set": {"phone": phone, "step": "source"}},
                upsert=True
            )
            
            await event.edit(
                f"💣 **Forward Bomber - Specific Target**\n\n"
                f"Account: `{phone}`\n\n"
                f"Send source chat username/link:"
            )
        
        @self.bot.on(events.CallbackQuery(pattern=rb"fb_all:(.+)"))
        async def forward_bomb_all_setup(event):
            phone = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "forward_bomb_all"},
                {"$set": {"phone": phone, "step": "source"}},
                upsert=True
            )
            
            await event.edit(
                f"💣 **Forward Bomber - All Groups**\n\n"
                f"Account: `{phone}`\n\n"
                f"Send source chat username/link:"
            )
        
        # Message Flooder
        @self.bot.on(events.CallbackQuery(pattern=b"message_flood"))
        async def message_flood_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            if not accounts:
                await event.answer("❌ No accounts", alert=True)
                return
            
            buttons = [[Button.inline(f"📱 {acc['name']}", f"mf_acc:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🔙 Back", b"advanced_spam")])
            
            await event.edit("🌊 **Message Flooder**\n\nSelect account:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"mf_acc:(.+)"))
        async def message_flood_setup(event):
            phone = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            buttons = [
                [Button.inline("🌐 All Groups", f"mf_all:{phone}".encode())],
                [Button.inline("🎯 Specific Group", f"mf_spec:{phone}".encode())],
                [Button.inline("🔙 Back", b"message_flood")]
            ]
            
            await event.edit(
                f"🌊 **Message Flooder Setup**\n\n"
                f"Account: `{phone}`\n\n"
                f"Choose target:",
                buttons=buttons
            )
        
        @self.bot.on(events.CallbackQuery(pattern=rb"mf_spec:(.+)"))
        async def message_flood_specific(event):
            phone = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "message_flood"},
                {"$set": {"phone": phone, "step": "target"}},
                upsert=True
            )
            
            await event.edit(
                f"🌊 **Message Flooder - Specific Group**\n\n"
                f"Account: `{phone}`\n\n"
                f"Send target group username/link:"
            )
        
        @self.bot.on(events.CallbackQuery(pattern=rb"mf_all:(.+)"))
        async def message_flood_all(event):
            phone = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "message_flood_all"},
                {"$set": {"phone": phone, "step": "message"}},
                upsert=True
            )
            
            await event.edit(
                f"🌊 **Message Flooder - All Groups**\n\n"
                f"Account: `{phone}`\n\n"
                f"Send the message to flood:"
            )
        
        # Raid Coordinator
        @self.bot.on(events.CallbackQuery(pattern=b"raid_coord"))
        async def raid_coord_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            if len(accounts) < 2:
                await event.answer("❌ Need at least 2 accounts", alert=True)
                return
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "raid_coord"},
                {"$set": {"step": "target", "accounts": len(accounts)}},
                upsert=True
            )
            
            await event.edit(
                f"⚔️ **Raid Coordinator Setup**\n\n"
                f"Using: {len(accounts)} accounts\n\n"
                f"Send target group username/link:"
            )
        
        # Stealth Raid
        @self.bot.on(events.CallbackQuery(pattern=b"stealth_raid"))
        async def stealth_raid_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            if len(accounts) < 2:
                await event.answer("❌ Need at least 2 accounts", alert=True)
                return
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "stealth_raid"},
                {"$set": {"step": "target", "accounts": len(accounts)}},
                upsert=True
            )
            
            await event.edit(
                f"🥷 **Stealth Raid Setup**\n\n"
                f"Using: {len(accounts)} accounts\n\n"
                f"Send target group username/link:"
            )
        
        # Multi-Target Raid
        @self.bot.on(events.CallbackQuery(pattern=b"multi_raid"))
        async def multi_raid_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            if len(accounts) < 3:
                await event.answer("❌ Need at least 3 accounts", alert=True)
                return
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "multi_raid"},
                {"$set": {"step": "targets", "accounts": len(accounts)}},
                upsert=True
            )
            
            await event.edit(
                f"🎯 **Multi-Target Raid Setup**\n\n"
                f"Using: {len(accounts)} accounts\n\n"
                f"Send target groups (one per line):"
            )
        
        # Send to All Groups
        @self.bot.on(events.CallbackQuery(pattern=b"send_all_groups"))
        async def send_all_groups_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            if not accounts:
                await event.answer("❌ No accounts", alert=True)
                return
            
            buttons = [[Button.inline(f"📱 {acc['name']}", f"sag_acc:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🔙 Back", b"advanced_spam")])
            
            await event.edit("📢 **Send to All Groups**\n\nSelect account:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"sag_acc:(.+)"))
        async def send_all_groups_setup(event):
            phone = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "send_all_groups"},
                {"$set": {"phone": phone, "step": "message"}},
                upsert=True
            )
            
            await event.edit(
                f"📢 **Send to All Groups Setup**\n\n"
                f"Account: `{phone}`\n\n"
                f"Send the message you want to broadcast to all groups:"
            )
        
        # Message handler for operations
        @self.bot.on(events.NewMessage(func=lambda e: e.is_private))
        async def operation_handler(event):
            user_id = event.sender_id
            temp_data = await mongodb.db.temp_data.find_one({"user_id": user_id})
            
            if not temp_data:
                return
            
            op_type = temp_data.get("type")
            
            if op_type == "mass_invite" and temp_data.get("step") == "target":
                await self._execute_mass_invite(event, temp_data)
            elif op_type == "contact_scrape" and temp_data.get("step") == "group":
                await self._execute_contact_scrape(event, temp_data)
            elif op_type == "username_check" and temp_data.get("step") == "base":
                await self._execute_username_check(event, temp_data)
            elif op_type == "forward_bomb" and temp_data.get("step") == "source":
                await self._handle_forward_bomb_source(event, temp_data)
            elif op_type == "forward_bomb" and temp_data.get("step") == "msgid":
                await self._execute_forward_bomb(event, temp_data)
            elif op_type == "message_flood" and temp_data.get("step") == "target":
                await self._execute_message_flood(event, temp_data)
            elif op_type == "raid_coord" and temp_data.get("step") == "target":
                await self._execute_raid_coord(event, temp_data)
            elif op_type == "stealth_raid" and temp_data.get("step") == "target":
                await self._execute_stealth_raid(event, temp_data)
            elif op_type == "multi_raid" and temp_data.get("step") == "targets":
                await self._execute_multi_raid(event, temp_data)
            elif op_type == "send_all_groups" and temp_data.get("step") == "message":
                await self._execute_send_all_groups(event, temp_data)
            elif op_type == "message_flood_all" and temp_data.get("step") == "message":
                await self._execute_message_flood_all(event, temp_data)
            elif op_type == "forward_bomb_all" and temp_data.get("step") == "source":
                await self._handle_forward_bomb_all_source(event, temp_data)
            elif op_type == "forward_bomb_all" and temp_data.get("step") == "msgid":
                await self._execute_forward_bomb_all(event, temp_data)
    
    async def _get_accounts(self, user_id):
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        return [{"phone": acc["phone"], "name": acc.get("name", acc.get("first_name", acc["phone"]))} for acc in accounts]
    
    def _get_client(self, phone):
        phone = str(phone)
        if phone in self.user_clients:
            return self.user_clients[phone]
        phone_clean = phone.lstrip('+')
        if phone_clean in self.user_clients:
            return self.user_clients[phone_clean]
        phone_plus = f"+{phone_clean}"
        if phone_plus in self.user_clients:
            return self.user_clients[phone_plus]
        for key in self.user_clients:
            key_str = str(key).lstrip('+')
            if phone_clean in key_str or key_str in phone_clean:
                return self.user_clients[key]
        return None
    
    async def _execute_mass_invite(self, event, temp_data):
        phone = temp_data["phone"]
        target = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply(f"📤 Starting mass invite to {target}...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            group = await client.get_entity(target)
            users = await mongodb.db.spam_users.find({"owner_id": user_id}).limit(50).to_list(None)
            
            invited = 0
            failed = 0
            
            for user in users:
                try:
                    await client(InviteToChannelRequest(group, [user["user_id"]]))
                    invited += 1
                    await asyncio.sleep(random.randint(5, 15))
                except (FloodWaitError, UserPrivacyRestrictedError):
                    failed += 1
                except Exception as e:
                    logger.error(f"Invite error: {e}")
                    failed += 1
            
            await msg.edit(f"✅ Mass invite completed!\n\nInvited: {invited}\nFailed: {failed}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "mass_invite"})
    
    async def _execute_contact_scrape(self, event, temp_data):
        phone = temp_data["phone"]
        group = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply(f"📇 Scraping contacts from {group}...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            entity = await client.get_entity(group)
            contacts = []
            
            async for participant in client.iter_participants(entity, limit=5000):
                if not participant.bot:
                    contacts.append({
                        "user_id": participant.id,
                        "username": participant.username,
                        "first_name": participant.first_name,
                        "last_name": participant.last_name,
                        "phone": participant.phone
                    })
                    
                    if len(contacts) % 100 == 0:
                        await asyncio.sleep(1)
            
            # Export to CSV
            filename = f"contacts_{group.replace('@', '')}_{user_id}.csv"
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['user_id', 'username', 'first_name', 'last_name', 'phone'])
                writer.writeheader()
                writer.writerows(contacts)
            
            await self.bot.send_file(user_id, filename, caption=f"📇 Scraped {len(contacts)} contacts")
            await msg.edit(f"✅ Scraped {len(contacts)} contacts!\n\nFile sent above.")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "contact_scrape"})
    
    async def _execute_contact_scrape_all(self, event, phone, user_id):
        msg = await self.bot.send_message(user_id, "🌐 Scraping contacts from all groups...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            
            all_contacts = {}
            groups_scraped = 0
            
            for group in groups:
                try:
                    async for participant in client.iter_participants(group.entity, limit=5000):
                        if not participant.bot and participant.id not in all_contacts:
                            all_contacts[participant.id] = {
                                "user_id": participant.id,
                                "username": participant.username,
                                "first_name": participant.first_name,
                                "last_name": participant.last_name,
                                "phone": participant.phone
                            }
                    groups_scraped += 1
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Error scraping {group.name}: {e}")
            
            contacts = list(all_contacts.values())
            filename = f"contacts_all_groups_{user_id}.csv"
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['user_id', 'username', 'first_name', 'last_name', 'phone'])
                writer.writeheader()
                writer.writerows(contacts)
            
            await self.bot.send_file(user_id, filename, caption=f"🌐 Scraped {len(contacts)} unique contacts from {groups_scraped} groups")
            await msg.edit(f"✅ All groups scraped!\n\nGroups: {groups_scraped}\nContacts: {len(contacts)}\n\nFile sent above.")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
    
    async def _execute_username_check(self, event, temp_data):
        phone = temp_data["phone"]
        base = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply(f"🔍 Checking usernames for base: {base}...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            available = []
            checked = 0
            
            for i in range(100):
                username = f"{base}{random.randint(1, 9999)}"
                try:
                    await client.get_entity(username)
                except:
                    available.append(username)
                
                checked += 1
                if checked % 10 == 0:
                    await asyncio.sleep(1)
            
            result = f"✅ Username Check Complete!\n\nChecked: {checked}\nAvailable: {len(available)}\n\n"
            result += "\n".join([f"@{u}" for u in available[:20]])
            
            await msg.edit(result)
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "username_check"})
    
    async def _handle_forward_bomb_source(self, event, temp_data):
        source = event.text.strip()
        user_id = event.sender_id
        
        await mongodb.db.temp_data.update_one(
            {"user_id": user_id, "type": "forward_bomb"},
            {"$set": {"source": source, "step": "msgid"}}
        )
        
        await event.reply(f"💣 Source set: {source}\n\nNow send message ID to forward:")
    
    async def _execute_forward_bomb(self, event, temp_data):
        phone = temp_data["phone"]
        source = temp_data["source"]
        msg_id = int(event.text.strip())
        user_id = event.sender_id
        
        msg = await event.reply(f"💣 Starting forward bombing...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            users = await mongodb.db.spam_users.find({"owner_id": user_id}).limit(100).to_list(None)
            forwarded = 0
            
            for user in users:
                try:
                    await client.forward_messages(user["user_id"], msg_id, source)
                    forwarded += 1
                    await asyncio.sleep(random.randint(2, 8))
                except:
                    pass
            
            await msg.edit(f"✅ Forward bombing completed!\n\nForwarded: {forwarded}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "forward_bomb"})
    
    async def _execute_message_flood(self, event, temp_data):
        phone = temp_data["phone"]
        target = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply(f"🌊 Starting message flood to {target}...")
        
        flood_msgs = [
            "🔥🔥🔥 SPAM ATTACK 🔥🔥🔥",
            "💥 FLOODING IN PROGRESS 💥",
            "⚡ RAID MODE ACTIVATED ⚡",
            "🚨 SYSTEM OVERLOAD 🚨"
        ]
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            group = await client.get_entity(target)
            sent = 0
            
            for i in range(50):
                try:
                    await client.send_message(group, random.choice(flood_msgs))
                    sent += 1
                    await asyncio.sleep(random.uniform(0.1, 0.5))
                except (FloodWaitError, SlowModeWaitError, ChatWriteForbiddenError):
                    break
            
            await msg.edit(f"✅ Message flood completed!\n\nSent: {sent}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "message_flood"})
    
    async def _execute_raid_coord(self, event, temp_data):
        target = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply(f"⚔️ Starting coordinated raid on {target}...")
        
        try:
            accounts = await self._get_accounts(user_id)
            clients = [self._get_client(acc["phone"]) for acc in accounts if self._get_client(acc["phone"])]
            
            if not clients:
                await msg.edit("❌ No clients available")
                return
            
            tasks = []
            for client in clients:
                task = asyncio.create_task(self._raid_worker(client, target, 60))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            total = sum(r for r in results if isinstance(r, int))
            
            await msg.edit(f"✅ Raid completed!\n\nTotal messages: {total}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "raid_coord"})
    
    async def _raid_worker(self, client, target, duration):
        sent = 0
        start = asyncio.get_event_loop().time()
        
        try:
            group = await client.get_entity(target)
            while (asyncio.get_event_loop().time() - start) < duration:
                try:
                    await client.send_message(group, "⚔️ RAID ATTACK ⚔️")
                    sent += 1
                    await asyncio.sleep(0.2)
                except:
                    break
        except:
            pass
        
        return sent
    
    async def _execute_stealth_raid(self, event, temp_data):
        target = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply(f"🥷 Starting stealth raid on {target}...")
        
        try:
            accounts = await self._get_accounts(user_id)
            clients = [self._get_client(acc["phone"]) for acc in accounts if self._get_client(acc["phone"])]
            
            if not clients:
                await msg.edit("❌ No clients available")
                return
            
            tasks = []
            for client in clients:
                task = asyncio.create_task(self._stealth_worker(client, target, 20))
                tasks.append(task)
                await asyncio.sleep(random.uniform(5, 20))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            total = sum(r for r in results if isinstance(r, int))
            
            await msg.edit(f"✅ Stealth raid completed!\n\nTotal messages: {total}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "stealth_raid"})
    
    async def _stealth_worker(self, client, target, count):
        sent = 0
        human_messages = [
            "Hey everyone!", "What's up?", "Anyone here?", "Good morning!",
            "How's it going?", "Nice group!", "Hello there", "Greetings!",
            "What's happening?", "Hey guys", "Sup", "Yo", "Hi all",
            "Good to be here", "Interesting discussion", "I agree",
            "That's cool", "Nice", "Awesome", "Great point",
            "Thanks for sharing", "Appreciate it", "Cool stuff", "Interesting",
            "Makes sense", "True that", "Exactly", "For sure", "Definitely",
            "I see", "Got it", "Understood", "Fair enough", "Good idea"
        ]
        
        try:
            group = await client.get_entity(target)
            for i in range(count):
                try:
                    # Random typing indicator (50% chance)
                    if random.random() > 0.5:
                        async with client.action(group, 'typing'):
                            await asyncio.sleep(random.uniform(1, 4))
                    
                    # Send varied message
                    message = random.choice(human_messages)
                    await client.send_message(group, message)
                    sent += 1
                    
                    # Human-like delays: shorter at start, longer as time goes
                    base_delay = random.uniform(15, 45)
                    fatigue_factor = 1 + (i * 0.1)  # Gets slower over time
                    delay = base_delay * fatigue_factor
                    
                    # Random "distraction" - longer pause (20% chance)
                    if random.random() > 0.8:
                        delay += random.uniform(30, 120)
                    
                    await asyncio.sleep(delay)
                except:
                    break
        except:
            pass
        return sent
    
    async def _execute_multi_raid(self, event, temp_data):
        targets = event.text.strip().split("\n")
        user_id = event.sender_id
        
        msg = await event.reply(f"🎯 Starting multi-target raid on {len(targets)} groups...")
        
        try:
            accounts = await self._get_accounts(user_id)
            clients = [self._get_client(acc["phone"]) for acc in accounts if self._get_client(acc["phone"])]
            
            if not clients:
                await msg.edit("❌ No clients available")
                return
            
            tasks = []
            for i, target in enumerate(targets):
                client = clients[i % len(clients)]
                task = asyncio.create_task(self._raid_worker(client, target, 30))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            total = sum(r for r in results if isinstance(r, int))
            
            await msg.edit(f"✅ Multi-target raid completed!\n\nTotal messages: {total}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "multi_raid"})
    
    async def _execute_send_all_groups(self, event, temp_data):
        phone = temp_data["phone"]
        message = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply(f"📢 Sending message to all groups...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            # Get all dialogs (groups and channels)
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            
            sent = 0
            failed = 0
            
            for group in groups:
                try:
                    await client.send_message(group.entity, message)
                    sent += 1
                    await asyncio.sleep(random.uniform(2, 5))
                except (FloodWaitError, ChatWriteForbiddenError) as e:
                    failed += 1
                    if isinstance(e, FloodWaitError):
                        await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.error(f"Send error: {e}")
                    failed += 1
            
            await msg.edit(f"✅ Broadcast completed!\n\nSent: {sent}\nFailed: {failed}\nTotal groups: {len(groups)}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "send_all_groups"})
    
    async def _execute_mass_invite_all(self, event, phone, user_id):
        msg = await self.bot.send_message(user_id, "🌐 Starting mass invite to all groups...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            users = await mongodb.db.spam_users.find({"owner_id": user_id}).limit(50).to_list(None)
            
            total_invited = 0
            total_failed = 0
            
            for group in groups:
                try:
                    for user in users:
                        try:
                            await client(InviteToChannelRequest(group.entity, [user["user_id"]]))
                            total_invited += 1
                            await asyncio.sleep(random.randint(5, 15))
                        except:
                            total_failed += 1
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Error inviting to {group.name}: {e}")
            
            await msg.edit(f"✅ Mass invite completed!\n\nGroups: {len(groups)}\nInvited: {total_invited}\nFailed: {total_failed}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
    
    async def _handle_forward_bomb_all_source(self, event, temp_data):
        source = event.text.strip()
        user_id = event.sender_id
        
        await mongodb.db.temp_data.update_one(
            {"user_id": user_id, "type": "forward_bomb_all"},
            {"$set": {"source": source, "step": "msgid"}}
        )
        
        await event.reply(f"💣 Source set: {source}\n\nNow send message ID to forward:")
    
    async def _execute_forward_bomb_all(self, event, temp_data):
        phone = temp_data["phone"]
        source = temp_data["source"]
        msg_id = int(event.text.strip())
        user_id = event.sender_id
        
        msg = await event.reply("💣 Starting forward bomb to all groups...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            
            forwarded = 0
            
            for group in groups:
                try:
                    await client.forward_messages(group.entity, msg_id, source)
                    forwarded += 1
                    await asyncio.sleep(random.randint(2, 8))
                except:
                    pass
            
            await msg.edit(f"✅ Forward bomb completed!\n\nGroups: {len(groups)}\nForwarded: {forwarded}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "forward_bomb_all"})
    
    async def _execute_message_flood_all(self, event, temp_data):
        phone = temp_data["phone"]
        message = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply("🌊 Starting flood to all groups...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            
            total_sent = 0
            
            for group in groups:
                try:
                    for i in range(50):
                        try:
                            await client.send_message(group.entity, message)
                            total_sent += 1
                            await asyncio.sleep(random.uniform(0.1, 0.5))
                        except (FloodWaitError, SlowModeWaitError, ChatWriteForbiddenError):
                            break
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Flood error: {e}")
            
            await msg.edit(f"✅ Flood completed!\n\nGroups: {len(groups)}\nMessages sent: {total_sent}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "message_flood_all"})
