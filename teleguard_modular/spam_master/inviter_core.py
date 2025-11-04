"""Split from mass_inviter.py - inviter_core"""
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
