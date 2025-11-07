"""Callback handlers for various actions"""
import logging
from ...core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class CallbackHandlers:
    def __init__(self, menu_system):
        self.menu = menu_system
        self.bot = menu_system.bot
        self.account_manager = menu_system.account_manager
    
    async def handle_otp_callback(self, event, user_id, data):
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"
        if action == "manage":
            await self.menu.send_otp_account_management(user_id, account_id, event.message_id)
        elif action == "enable":
            from bson import ObjectId
            await mongodb.db.accounts.update_one({"_id": ObjectId(account_id), "user_id": user_id}, {"$set": {"otp_destroyer_enabled": True, "otp_forward_enabled": False}})
            await event.answer("🛡️ OTP Destroyer enabled! Forward disabled.")
            await self.menu._handle_otp_setting_callback(event, user_id, "otp_setting:destroyer")
        elif action == "disable":
            from bson import ObjectId
            await mongodb.db.accounts.update_one({"_id": ObjectId(account_id), "user_id": user_id}, {"$set": {"otp_destroyer_enabled": False}})
            await event.answer("🔴 OTP Destroyer disabled!")
            await self.menu._handle_otp_setting_callback(event, user_id, "otp_setting:destroyer")
        elif action == "forward_enable":
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if account and account.get("otp_destroyer_enabled", False):
                await event.answer("❌ Cannot enable forward while OTP Destroyer is active")
                return
            await mongodb.db.accounts.update_one({"_id": ObjectId(account_id), "user_id": user_id}, {"$set": {"otp_forward_enabled": True}})
            await event.answer("📤 OTP Forward enabled!")
            await self.menu._handle_otp_setting_callback(event, user_id, "otp_setting:forward")
        elif action == "forward_disable":
            from bson import ObjectId
            await mongodb.db.accounts.update_one({"_id": ObjectId(account_id), "user_id": user_id}, {"$set": {"otp_forward_enabled": False}})
            await event.answer("🔴 OTP Forward disabled!")
            await self.menu._handle_otp_setting_callback(event, user_id, "otp_setting:forward")
        elif action == "temp":
            await self._handle_temp_otp(event, user_id, account_id)
        elif action == "audit":
            await self.menu.send_audit_log(user_id, account_id)
    
    async def _handle_temp_otp(self, event, user_id, account_id):
        from bson import ObjectId
        import time
        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
        if not account:
            await event.answer("❌ Account not found")
            return
        temp_active = False
        if account.get("otp_temp_passthrough", False):
            expiry = account.get("temp_passthrough_expiry", 0)
            if time.time() < expiry:
                temp_active = True
        if temp_active:
            original_destroyer_state = account.get("original_destroyer_state", True)
            original_forward_state = account.get("original_forward_state", False)
            await mongodb.db.accounts.update_one({"_id": ObjectId(account_id)}, {"$set": {"otp_destroyer_enabled": original_destroyer_state, "otp_forward_enabled": original_forward_state}, "$unset": {"otp_temp_passthrough": "", "temp_passthrough_expiry": "", "original_destroyer_state": "", "original_forward_state": ""}})
            await mongodb.add_audit_entry(account_id, {"action": "temp_passthrough_stopped", "timestamp": int(time.time())})
            await event.answer("❌ Temp OTP stopped! Original settings restored.")
            await self.menu._handle_otp_setting_callback(event, user_id, "otp_setting:temp")
            return
        expiry_time = time.time() + 300
        original_destroyer_state = account.get("otp_destroyer_enabled", False)
        original_forward_state = account.get("otp_forward_enabled", False)
        await mongodb.db.accounts.update_one({"_id": ObjectId(account_id)}, {"$set": {"otp_temp_passthrough": True, "temp_passthrough_expiry": expiry_time, "otp_destroyer_enabled": False, "otp_forward_enabled": True, "original_destroyer_state": original_destroyer_state, "original_forward_state": original_forward_state}})
        await mongodb.add_audit_entry(account_id, {"action": "temp_passthrough_enabled", "duration": "5_minutes", "timestamp": int(time.time())})
        await event.answer("⏰ Temp OTP enabled! Forward ON, Destroyer OFF for 5 minutes.")
        await self.menu._handle_otp_setting_callback(event, user_id, "otp_setting:temp")
    
    async def handle_online_callback(self, event, user_id, data):
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"
        if action == "toggle":
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if account:
                new_status = not account.get("online_maker_enabled", False)
                await mongodb.db.accounts.update_one({"_id": ObjectId(account_id)}, {"$set": {"online_maker_enabled": new_status}})
                if hasattr(self.account_manager, 'online_maker'):
                    account_identifier = account.get("phone") or account.get("name", "unknown")
                    if new_status:
                        await self.account_manager.online_maker.start_online_maker(user_id, account_identifier)
                    else:
                        await self.account_manager.online_maker.stop_online_maker(user_id, account_identifier)
                status = "started" if new_status else "stopped"
                status_emoji = "✅" if new_status else "❌"
                await event.answer(f"{status_emoji} Online maker {status}!")
                await self.menu.send_account_management(user_id, account_id, event.message_id)
    
    async def handle_simulate_callback(self, event, user_id, data):
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"
        if action == "toggle":
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if account:
                new_status = not account.get("simulation_enabled", False)
                await mongodb.db.accounts.update_one({"_id": ObjectId(account_id)}, {"$set": {"simulation_enabled": new_status}})
                if hasattr(self.account_manager, "activity_simulator"):
                    if new_status:
                        await self.account_manager.activity_simulator._start_account_simulation(user_id, account_id, account["name"])
                    else:
                        task_key = f"{user_id}_{account_id}"
                        if task_key in self.account_manager.activity_simulator.simulation_tasks:
                            self.account_manager.activity_simulator.simulation_tasks[task_key].cancel()
                            del self.account_manager.activity_simulator.simulation_tasks[task_key]
                status = "enabled" if new_status else "disabled"
                status_emoji = "🎭" if new_status else "🔴"
                await event.answer(f"{status_emoji} Activity simulation {status}!")
                await self.menu.send_account_management(user_id, account_id, event.message_id)
            else:
                await event.answer("❌ Account not found")
        elif action == "status":
            await self._show_simulation_status(user_id, account_id, event.message_id)
        elif action == "stats":
            await self._show_simulation_stats(user_id, account_id, event.message_id)
    
    async def _show_simulation_status(self, user_id, account_id, message_id):
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
        if account:
            status = "✅ Active" if account.get("simulation_enabled", False) else "❌ Inactive"
            text = f"🎭 **Activity Simulator: {account['name']}**\n\nStatus: {status}\n\nThe simulator performs human-like activities:\n• Views random channels/groups\n• Reacts to posts with emojis\n• Votes in polls occasionally\n• Browses user profiles\n• Rarely joins/leaves channels\n\nSessions every 30-90 minutes with 2-5 actions each."
            toggle_text = "🔴 Disable" if account.get("simulation_enabled", False) else "🟢 Enable"
            buttons = [[self.bot.Button.inline(f"{toggle_text} Simulation", f"simulate:toggle:{account_id}")], [self.bot.Button.inline("🔙 Back", f"account:manage:{account_id}")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        else:
            await self.bot.send_message(user_id, "❌ Account not found")
    
    async def _show_simulation_stats(self, user_id, account_id, message_id):
        from bson import ObjectId
        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
        if account:
            stats_text = "Loading statistics..."
            if hasattr(self.account_manager, 'activity_simulator'):
                task_key = f"{user_id}_{account_id}"
                if task_key in self.account_manager.activity_simulator.simulation_tasks:
                    stats = self.account_manager.activity_simulator.stats.get(task_key, {})
                    total_actions = stats.get('total_actions', 0)
                    last_session = stats.get('last_session', 'Never')
                    avg_actions = stats.get('avg_actions_per_session', 0)
                    stats_text = f"**Statistics:**\n• Total Actions: {total_actions}\n• Last Session: {last_session}\n• Avg Actions/Session: {avg_actions:.1f}\n• Status: {'Active' if account.get('simulation_enabled') else 'Inactive'}"
                else:
                    stats_text = "No active simulation session found."
            text = f"📊 **Simulation Stats: {account['name']}**\n\n{stats_text}\n\n**Activity Types:**\n• Channel/Group browsing\n• Emoji reactions\n• Poll voting\n• Profile viewing\n• Occasional joins/leaves"
            buttons = [[self.bot.Button.inline("🔄 Refresh", f"simulate:stats:{account_id}")], [self.bot.Button.inline("🔙 Back", f"account:manage:{account_id}")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        else:
            await self.bot.send_message(user_id, "❌ Account not found")
