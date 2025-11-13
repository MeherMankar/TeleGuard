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
        
        try:
            if action == "manage":
                await self.menu.send_otp_account_management(user_id, account_id, event.message_id)
            elif action == "enable":
                success, message = await self._toggle_otp_destroyer(user_id, account_id, True)
                await event.answer(f"{'🛡️' if success else '❌'} {message}")
                if success:
                    await self.menu._handle_otp_setting_callback(event, user_id, "otp_setting:destroyer")
            elif action == "disable":
                success, message = await self._toggle_otp_destroyer(user_id, account_id, False)
                await event.answer(f"{'🔴' if success else '❌'} {message}")
                if success:
                    await self.menu._handle_otp_setting_callback(event, user_id, "otp_setting:destroyer")
            elif action == "forward_enable":
                success, message = await self._toggle_otp_forward(user_id, account_id, True)
                await event.answer(f"{'📤' if success else '❌'} {message}")
                if success:
                    await self.menu._handle_otp_setting_callback(event, user_id, "otp_setting:forward")
            elif action == "forward_disable":
                success, message = await self._toggle_otp_forward(user_id, account_id, False)
                await event.answer(f"{'🔴' if success else '❌'} {message}")
                if success:
                    await self.menu._handle_otp_setting_callback(event, user_id, "otp_setting:forward")
            elif action == "temp":
                success, message = await self._handle_temp_otp(user_id, account_id)
                await event.answer(f"{'⏰' if success else '❌'} {message}")
                if success:
                    await self.menu._handle_otp_setting_callback(event, user_id, "otp_setting:temp")
            elif action == "audit":
                await self._show_audit_log(user_id, account_id, event.message_id)
        except Exception as e:
            logger.error(f"OTP callback error: {e}")
            await event.answer("❌ Error processing OTP request")
    
    async def _toggle_otp_destroyer(self, user_id, account_id, enabled):
        """Toggle OTP destroyer with proper integration"""
        try:
            if hasattr(self.account_manager, 'otp_manager') and self.account_manager.otp_manager:
                return await self.account_manager.otp_manager.toggle_destroyer(user_id, account_id, enabled)
            else:
                # Fallback to direct database update
                from bson import ObjectId
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id), "user_id": user_id},
                    {"$set": {
                        "otp_destroyer_enabled": enabled,
                        "otp_forward_enabled": False if enabled else mongodb.db.accounts.find_one({"_id": ObjectId(account_id)}).get("otp_forward_enabled", False)
                    }}
                )
                message = f"OTP Destroyer {'enabled' if enabled else 'disabled'}!"
                if enabled:
                    message += " Forward disabled."
                return True, message
        except Exception as e:
            logger.error(f"Error toggling OTP destroyer: {e}")
            return False, f"Error: {str(e)}"
    
    async def _toggle_otp_forward(self, user_id, account_id, enabled):
        """Toggle OTP forward with proper integration"""
        try:
            if hasattr(self.account_manager, 'otp_manager') and self.account_manager.otp_manager:
                return await self.account_manager.otp_manager.toggle_forward(user_id, account_id, enabled)
            else:
                # Fallback to direct database update
                from bson import ObjectId
                account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
                if not account:
                    return False, "Account not found"
                
                if enabled and account.get("otp_destroyer_enabled", False):
                    return False, "Cannot enable forward while OTP Destroyer is active"
                
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"otp_forward_enabled": enabled}}
                )
                message = f"OTP Forward {'enabled' if enabled else 'disabled'}!"
                return True, message
        except Exception as e:
            logger.error(f"Error toggling OTP forward: {e}")
            return False, f"Error: {str(e)}"
    
    async def _handle_temp_otp(self, user_id, account_id):
        """Handle temp OTP with proper integration"""
        try:
            if hasattr(self.account_manager, 'otp_manager') and self.account_manager.otp_manager:
                return await self.account_manager.otp_manager.enable_temp_passthrough(user_id, account_id)
            else:
                # Fallback implementation
                from bson import ObjectId
                import time
                
                account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
                if not account:
                    return False, "Account not found"
                
                if not account.get("otp_destroyer_enabled", False):
                    return False, "OTP Destroyer must be enabled to use temp OTP"
                
                # Enable temp passthrough for 5 minutes
                expiry_time = time.time() + 300
                account_name = account.get('name') or account.get('phone') or 'Unknown'
                
                # Store in OTP manager temp passthrough if available
                if hasattr(self.account_manager, 'otp_manager') and self.account_manager.otp_manager:
                    temp_key = f"{account_name}_temp_otp"
                    self.account_manager.otp_manager.temp_passthrough.setdefault(user_id, {})[temp_key] = {"expiry": expiry_time}
                
                # Log the action
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$push": {"audit_log": {
                        "action": "temp_otp_enabled",
                        "duration": "5_minutes",
                        "timestamp": int(time.time())
                    }}}
                )
                
                return True, "Temp OTP enabled for 5 minutes! OTP codes will be forwarded."
        except Exception as e:
            logger.error(f"Error handling temp OTP: {e}")
            return False, f"Error: {str(e)}"
    
    async def _show_audit_log(self, user_id, account_id, message_id):
        """Show audit log for account"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                text = "❌ Account not found"
                buttons = [[self.bot.Button.inline("🔙 Back", "menu:otp")]]
            else:
                audit_log = account.get('audit_log', [])
                if not audit_log:
                    text = f"📋 **Audit Log - {account.get('name', 'Unknown')}**\n\n💭 No audit entries found."
                else:
                    text = f"📋 **Audit Log - {account.get('name', 'Unknown')}**\n\n"
                    # Show last 10 entries
                    recent_entries = audit_log[-10:] if len(audit_log) > 10 else audit_log
                    for entry in reversed(recent_entries):
                        import time
                        timestamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.get('timestamp', 0)))
                        action = entry.get('action', 'unknown')
                        text += f"• {timestamp} - {action}\n"
                
                buttons = [[self.bot.Button.inline("🔙 Back", f"otp:manage:{account_id}")]]
            
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing audit log: {e}")
            text = "❌ Error loading audit log"
            buttons = [[self.bot.Button.inline("🔙 Back", "menu:otp")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    
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
