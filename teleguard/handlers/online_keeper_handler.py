"""Online Keeper Handler - UI for keeping accounts online
Integrated from SessTg project
"""

import asyncio
import logging

from telethon import Button, events

from ..workers.online_keeper_worker import OnlineKeeperWorker

logger = logging.getLogger(__name__)


class OnlineKeeperHandler:
    """Handler for online keeper UI"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.worker = OnlineKeeperWorker(bot_manager)
    
    def register_handlers(self):
        """Register callback handlers"""
        
        @self.bot.on(events.CallbackQuery(pattern=b"online_keeper"))
        async def show_keeper_menu(event):
            user_id = event.sender_id
            
            # Get running accounts
            running = self.worker.get_running_accounts(user_id)
            
            status_text = ""
            if running:
                status_text = f"\n🟢 Running: {len(running)} account(s)\n"
                for acc in running[:5]:
                    status_text += f"   • {acc}\n"
                if len(running) > 5:
                    status_text += f"   ... and {len(running) - 5} more\n"
            else:
                status_text = "\n⚪ No accounts online\n"
            
            text = (
                "🟢 **Online Keeper**\n\n"
                "Keep your accounts online continuously.\n"
                f"{status_text}\n"
                "Choose an action:"
            )
            
            buttons = [
                [Button.inline("▶️ Start Account", b"keeper:select_start")],
                [Button.inline("⏸️ Stop Account", b"keeper:select_stop")],
                [Button.inline("▶️ Start All", b"keeper:start_all")],
                [Button.inline("⏹️ Stop All", b"keeper:stop_all")],
                [Button.inline("📊 Status", b"keeper:status")],
                [Button.inline("🔙 Back", b"menu:main")]
            ]
            
            await event.edit(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"keeper:select_start"))
        async def select_start(event):
            user_id = event.sender_id
            
            # Get user accounts
            accounts = await self.bot_manager.mongodb.db.accounts.find(
                {"user_id": user_id, "is_active": True}
            ).to_list(length=None)
            
            if not accounts:
                await event.answer("❌ No accounts found", alert=True)
                return
            
            text = "▶️ **Start Online Keeper**\n\nSelect account:"
            
            buttons = []
            for acc in accounts:
                name = acc['name']
                is_running = self.worker.is_running(user_id, name)
                status = "🟢" if is_running else "⚪"
                
                buttons.append([
                    Button.inline(
                        f"{status} {name}",
                        f"keeper:start:{name}".encode()
                    )
                ])
            
            buttons.append([Button.inline("🔙 Back", b"online_keeper")])
            
            await event.edit(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"keeper:start:(.+)"))
        async def start_account(event):
            user_id = event.sender_id
            account_name = event.pattern_match.group(1).decode()
            
            await event.answer("⏳ Starting...", alert=False)
            
            # Check if client is loaded
            if user_id not in self.bot_manager.user_clients or \
               account_name not in self.bot_manager.user_clients[user_id]:
                # Load client
                await self.bot_manager.start_user_client(user_id, account_name)
            
            # Start keeper
            success = await self.worker.start_keeping_online(user_id, account_name)
            
            if success:
                await event.edit(
                    f"✅ Online keeper started for **{account_name}**\n\n"
                    f"The account will stay online continuously.",
                    buttons=[[Button.inline("🔙 Back", b"online_keeper")]]
                )
            else:
                await event.edit(
                    f"❌ Failed to start online keeper for **{account_name}**",
                    buttons=[[Button.inline("🔙 Back", b"online_keeper")]]
                )
        
        @self.bot.on(events.CallbackQuery(pattern=b"keeper:select_stop"))
        async def select_stop(event):
            user_id = event.sender_id
            
            # Get running accounts
            running = self.worker.get_running_accounts(user_id)
            
            if not running:
                await event.answer("❌ No accounts running", alert=True)
                return
            
            text = "⏸️ **Stop Online Keeper**\n\nSelect account:"
            
            buttons = []
            for name in running:
                buttons.append([
                    Button.inline(
                        f"🟢 {name}",
                        f"keeper:stop:{name}".encode()
                    )
                ])
            
            buttons.append([Button.inline("🔙 Back", b"online_keeper")])
            
            await event.edit(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=b"keeper:stop:(.+)"))
        async def stop_account(event):
            user_id = event.sender_id
            account_name = event.pattern_match.group(1).decode()
            
            await event.answer("⏳ Stopping...", alert=False)
            
            success = await self.worker.stop_keeping_online(user_id, account_name)
            
            if success:
                await event.edit(
                    f"✅ Online keeper stopped for **{account_name}**",
                    buttons=[[Button.inline("🔙 Back", b"online_keeper")]]
                )
            else:
                await event.edit(
                    f"❌ Failed to stop online keeper for **{account_name}**",
                    buttons=[[Button.inline("🔙 Back", b"online_keeper")]]
                )
        
        @self.bot.on(events.CallbackQuery(pattern=b"keeper:start_all"))
        async def start_all(event):
            user_id = event.sender_id
            
            await event.answer("⏳ Starting all accounts...", alert=False)
            
            results = await self.worker.start_all(user_id)
            
            if not results:
                await event.edit(
                    "❌ No accounts found",
                    buttons=[[Button.inline("🔙 Back", b"online_keeper")]]
                )
                return
            
            success_count = sum(1 for v in results.values() if v)
            
            text = (
                f"✅ Started online keeper for {success_count}/{len(results)} accounts\n\n"
            )
            
            for name, success in results.items():
                status = "✅" if success else "❌"
                text += f"{status} {name}\n"
            
            await event.edit(
                text,
                buttons=[[Button.inline("🔙 Back", b"online_keeper")]]
            )
        
        @self.bot.on(events.CallbackQuery(pattern=b"keeper:stop_all"))
        async def stop_all(event):
            user_id = event.sender_id
            
            await event.answer("⏳ Stopping all accounts...", alert=False)
            
            results = await self.worker.stop_all(user_id)
            
            if not results:
                await event.edit(
                    "❌ No accounts running",
                    buttons=[[Button.inline("🔙 Back", b"online_keeper")]]
                )
                return
            
            text = f"✅ Stopped online keeper for {len(results)} account(s)"
            
            await event.edit(
                text,
                buttons=[[Button.inline("🔙 Back", b"online_keeper")]]
            )
        
        @self.bot.on(events.CallbackQuery(pattern=b"keeper:status"))
        async def show_status(event):
            user_id = event.sender_id
            
            running = self.worker.get_running_accounts(user_id)
            
            if not running:
                text = "⚪ **No accounts online**"
            else:
                text = f"🟢 **Online Status**\n\n{len(running)} account(s) online:\n\n"
                for name in running:
                    text += f"🟢 {name}\n"
            
            await event.edit(
                text,
                buttons=[[Button.inline("🔙 Back", b"online_keeper")]]
            )
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.worker.cleanup()
