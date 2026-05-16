# -*- coding: utf-8 -*-
"""Callback handlers for various actions"""
import logging

from ...core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class CallbackHandlers:
    def __init__(self, menu_system):
        self.menu = menu_system
        self.bot = menu_system.bot
        self.account_manager = menu_system.account_manager

    async def handle_account_callback(self, event, user_id, data):
        """Handle account-related callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"

        try:
            if action == "manage":
                await self.menu.send_account_management(
                    user_id, account_id, event.message_id
                )
            elif action == "add":
                await self._handle_add_account(event, user_id)
            elif action == "remove":
                await self._handle_remove_account(event, user_id)
            elif action == "refresh":
                await self._refresh_account_statuses(event, user_id)
            elif action == "list":
                await self.menu.send_accounts_list(user_id, event.message_id)
        except Exception as e:
            logger.error(f"Account callback error: {e}")
            await event.answer("❌ Error processing account request")

    async def _handle_add_account(self, event, user_id):
        """Handle add account request"""
        try:
            from ...core.config import MAX_ACCOUNTS

            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            if not user:
                await event.answer("🚀 Please start the bot first")
                return
            account_count = await mongodb.db.accounts.count_documents(
                {"user_id": user_id}
            )
            if account_count >= MAX_ACCOUNTS:
                await event.answer(f"⚠️ Maximum account limit ({MAX_ACCOUNTS}) reached")
                return
            if self.account_manager:
                # Guard: if already waiting for phone number, don't send again
                existing = self.account_manager.pending_actions.get(user_id, {})
                if existing.get("action") == "add_account":
                    await event.answer("📞 Already waiting for phone number")
                    return

                self.account_manager.pending_actions[user_id] = {
                    "action": "add_account"
                }
                text = "➕ **Add New Account**\n\nReply with the phone number for the new account.\n\n📞 Format: +1234567890 (include country code)\n💡 Tip: Enter OTP codes as 1-2-3-4-5 (with hyphens)"
                await event.answer("➕ Reply with phone number")
                # Edit the existing message instead of sending a new one
                try:
                    from telethon import Button
                    await event.edit(text, buttons=[
                        [Button.inline("❌ Cancel", "menu:accounts")]
                    ])
                except Exception:
                    await self.bot.send_message(user_id, text)
            else:
                await event.answer("❌ Service unavailable")
        except Exception as e:
            logger.error(f"Failed to handle add account: {e}")
            await event.answer("❌ Error processing request")

    async def _handle_remove_account(self, event, user_id):
        """Handle remove account request"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                None
            )
            if not accounts:
                await self.bot.send_message(user_id, "❌ No accounts to remove.")
                return
            text = "🗑️ **Remove Account**\n\nSelect an account to remove:"
            buttons = []
            from telethon import Button

            for account in accounts:
                display_name = self.menu.format_display_name(account)
                phone = account.get("phone", "Unknown")
                buttons.append(
                    [
                        Button.inline(
                            f"🗑️ {display_name} ({phone})",
                            f"remove:confirm:{account['_id']}",
                        )
                    ]
                )
            buttons.append([Button.inline("🔙 Back to Accounts", "menu:accounts")])
            await self.bot.send_message(user_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Failed to handle remove account: {e}")
            await event.reply("⚠️ Error processing remove account request")

    async def handle_remove_callback(self, event, user_id, data):
        """Handle remove account confirmation"""
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"

        if action == "confirm":
            await self._execute_remove_account(event, user_id, account_id)

    async def _execute_remove_account(self, event, user_id, account_id):
        """Execute account removal"""
        try:
            if self.account_manager:
                try:
                    from ...core.database_manager import db_manager

                    await db_manager.remove_2fa_password(user_id, account_id)
                except Exception:
                    pass
                success, message = await self.account_manager.remove_account_by_id(
                    user_id, account_id
                )
                if success:
                    await event.answer("✅ Account removed successfully!")
                    from telethon import Button

                    await self.bot.edit_message(
                        user_id,
                        event.message_id,
                        "✅ **Account Removed**\n\nThe account has been successfully removed from TeleGuard.\n\n🔐 Session terminated from Telegram\n🔐 Stored 2FA password also removed for security",
                        buttons=[
                            [Button.inline("🔙 Back to Accounts", "menu:accounts")]
                        ],
                    )
                else:
                    await event.answer(f"❌ Failed to remove account: {message}")
                    from telethon import Button

                    await self.bot.edit_message(
                        user_id,
                        event.message_id,
                        f"❌ **Removal Failed**\n\n{message}",
                        buttons=[
                            [Button.inline("🔙 Back to Accounts", "menu:accounts")]
                        ],
                    )
            else:
                await event.answer("❌ Service unavailable")
        except Exception as e:
            logger.error(f"Failed to execute remove account: {e}")
            await event.answer("⚠️ Error executing account removal")

    async def handle_otp_callback(self, event, user_id, data):
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"

        try:
            if action == "manage":
                await self.menu.send_otp_account_management(user_id, account_id, event.message_id)
            elif action in ["enable", "disable"]:
                await self._handle_otp_toggle(event, user_id, account_id, action)
            elif action in ["forward_enable", "forward_disable"]:
                await self._handle_otp_forward_toggle(event, user_id, account_id, action)
            elif action == "temp":
                await self._handle_otp_temp(event, user_id, account_id)
            elif action == "audit":
                await self._show_audit_log(user_id, account_id, event.message_id)
            elif action == "stats":
                await self._show_otp_statistics(user_id, event.message_id)
            elif action == "enable_all":
                await self._handle_otp_bulk_toggle(event, user_id, True)
            elif action == "disable_all":
                await self._handle_otp_bulk_toggle(event, user_id, False)
            elif action == "audit_all":
                await self._show_global_audit_log(user_id, event.message_id)
        except Exception as e:
            logger.error(f"OTP callback error: {e}")
            await event.answer("❌ Error processing OTP request")

    async def _refresh_account_statuses(self, event, user_id):
        """Perform real-time health check on all accounts and refresh menu"""
        try:
            await event.answer("🔄 Refreshing account statuses...")
            
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            if not accounts:
                await self.menu.handlers.handle_account_settings(event)
                return

            from ...core.session_health import session_health
            
            updates = 0
            for account in accounts:
                phone = account.get("phone")
                account_name = account.get("name") or phone
                
                # Check if client is in memory
                client = self.account_manager.user_clients.get(user_id, {}).get(account_name)
                
                is_active = False
                if client and client.is_connected():
                    try:
                        # Real health check
                        is_active, _ = await session_health.check_session(client, phone)
                    except Exception:
                        is_active = False
                
                if is_active != account.get("is_active"):
                    await mongodb.db.accounts.update_one(
                        {"_id": account["_id"]},
                        {"$set": {"is_active": is_active}}
                    )
                    updates += 1
            
            await event.answer(f"✅ Refresh complete! ({updates} status updates)")
            await self.menu.handlers.handle_account_settings(event)
            
        except Exception as e:
            logger.error(f"Failed to refresh account statuses: {e}")
            await event.answer("⚠️ Error refreshing statuses")

    async def _handle_otp_bulk_toggle(self, event, user_id, enabled):
        """Handle bulk protection toggle for all accounts"""
        try:
            from ...core.mongo_database import mongodb
            from ...sync.session_destroyer_db import SessionDestroyerDB

            if enabled:
                await mongodb.db.accounts.update_many(
                    {"user_id": user_id},
                    {"$set": {"otp_destroyer_enabled": True, "otp_forward_enabled": False}}
                )
                await SessionDestroyerDB.update_settings(user_id, True)
                await event.answer("🛡️ All accounts secured with Protection Manager!", alert=True)
            else:
                await mongodb.db.accounts.update_many(
                    {"user_id": user_id},
                    {"$set": {"otp_destroyer_enabled": False, "otp_forward_enabled": False}}
                )
                await SessionDestroyerDB.update_settings(user_id, False)
                await event.answer("🔴 All protections disabled.", alert=True)

            # Refresh the menu
            await self.menu.handlers.handle_otp_manager(event)
        except Exception as e:
            logger.error(f"Bulk protection toggle error: {e}")
            await event.answer("❌ Error performing bulk update")

    async def _handle_otp_toggle(self, event, user_id, account_id, action):
        """Handle OTP destroyer enable/disable"""
        enabled = action == "enable"
        success, message = await self._toggle_otp_destroyer(user_id, account_id, enabled)
        await event.answer(f"{'🛡️' if success else '❌'} {message}")
        if success:
            await self.menu.router.handle_otp_setting_callback(event, user_id, "otp_setting:destroyer")

    async def _handle_otp_forward_toggle(self, event, user_id, account_id, action):
        """Handle OTP forward enable/disable"""
        enabled = action == "forward_enable"
        success, message = await self._toggle_otp_forward(user_id, account_id, enabled)
        await event.answer(f"{'📤' if success else '❌'} {message}")
        if success:
            await self.menu.router.handle_otp_setting_callback(event, user_id, "otp_setting:forward")

    async def _handle_otp_temp(self, event, user_id, account_id):
        """Handle temp OTP request"""
        success, message = await self._handle_temp_otp(user_id, account_id)
        await event.answer(f"{'⏰' if success else '❌'} {message}")
        if success:
            await self.menu.router.handle_otp_setting_callback(event, user_id, "otp_setting:temp")

    async def _toggle_otp_destroyer(self, user_id, account_id, enabled):
        """Toggle OTP destroyer with proper integration"""
        try:
            if (
                hasattr(self.account_manager, "otp_manager")
                and self.account_manager.otp_manager
            ):
                return await self.account_manager.otp_manager.toggle_destroyer(
                    user_id, account_id, enabled
                )
            else:
                # Fallback to direct database update
                from bson import ObjectId

                update_fields = {"otp_destroyer_enabled": enabled}
                if enabled:
                    # Enabling destroyer disables forward
                    update_fields["otp_forward_enabled"] = False

                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id), "user_id": user_id},
                    {"$set": update_fields},
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
            if (
                hasattr(self.account_manager, "otp_manager")
                and self.account_manager.otp_manager
            ):
                return await self.account_manager.otp_manager.toggle_forward(
                    user_id, account_id, enabled
                )
            else:
                # Fallback to direct database update
                from bson import ObjectId

                account = await mongodb.db.accounts.find_one(
                    {"_id": ObjectId(account_id), "user_id": user_id}
                )
                if not account:
                    return False, "Account not found"

                if enabled and account.get("otp_destroyer_enabled", False):
                    return False, "Cannot enable forward while OTP Destroyer is active"

                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"otp_forward_enabled": enabled}},
                )
                message = f"OTP Forward {'enabled' if enabled else 'disabled'}!"
                return True, message
        except Exception as e:
            logger.error(f"Error toggling OTP forward: {e}")
            return False, f"Error: {str(e)}"

    async def _handle_temp_otp(self, user_id, account_id):
        """Handle temp OTP with proper integration"""
        try:
            if (
                hasattr(self.account_manager, "otp_manager")
                and self.account_manager.otp_manager
            ):
                return await self.account_manager.otp_manager.enable_temp_passthrough(
                    user_id, account_id
                )
            else:
                # Fallback implementation
                import time

                from bson import ObjectId

                account = await mongodb.db.accounts.find_one(
                    {"_id": ObjectId(account_id), "user_id": user_id}
                )
                if not account:
                    return False, "Account not found"

                if not account.get("otp_destroyer_enabled", False):
                    return False, "OTP Destroyer must be enabled to use temp OTP"

                # Enable temp passthrough for 5 minutes
                expiry_time = time.time() + 300

                # Store in database
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {
                        "$set": {"otp_temp_passthrough": True, "otp_temp_expiry": int(expiry_time)},
                        "$push": {
                            "audit_log": {
                                "action": "temp_otp_enabled",
                                "duration": "5_minutes",
                                "timestamp": int(time.time()),
                            }
                        },
                    },
                )

                return (
                    True,
                    "Temp OTP enabled for 5 minutes! OTP codes will be forwarded.",
                )
        except Exception as e:
            logger.error(f"Error handling temp OTP: {e}")
            return False, f"Error: {str(e)}"

    async def _show_audit_log(self, user_id, account_id, message_id):
        """Show audit log for account"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                text = "❌ Account not found"
                from telethon import Button

                buttons = [[Button.inline("🔙 Back", "menu:otp")]]
            else:
                audit_log = account.get("audit_log", [])
                if not audit_log:
                    text = f"📋 **Audit Log - {account.get('name',
                                                          'Unknown')}**\n\n💭 No audit entries found."
                else:
                    text = f"📋 **Audit Log - {account.get('name', 'Unknown')}**\n\n"
                    # Show last 10 entries
                    recent_entries = (
                        audit_log[-10:] if len(audit_log) > 10 else audit_log
                    )
                    for entry in reversed(recent_entries):
                        import time

                        timestamp = time.strftime(
                            "%Y-%m-%d %H:%M", time.localtime(entry.get("timestamp", 0))
                        )
                        action = entry.get("action", "unknown")
                        text += f"• {timestamp} - {action}\n"

                from telethon import Button

                buttons = [[Button.inline("🔙 Back", f"otp:manage:{account_id}")]]

            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing audit log: {e}")
            text = "❌ Error loading audit log"
            from telethon import Button

            buttons = [[Button.inline("🔙 Back", "menu:otp")]]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

    async def handle_online_callback(self, event, user_id, data):
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"
        if action == "toggle":
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if account:
                new_status = not account.get("online_maker_enabled", False)
                await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"online_maker_enabled": new_status}},
                )
                if hasattr(self.account_manager, "online_maker"):
                    account_identifier = account.get("phone") or account.get(
                        "name", "unknown"
                    )
                    if new_status:
                        await self.account_manager.online_maker.start_online_maker(
                            user_id, account_identifier
                        )
                    else:
                        await self.account_manager.online_maker.stop_online_maker(
                            user_id, account_identifier
                        )
                status = "started" if new_status else "stopped"
                status_emoji = "✅" if new_status else "❌"
                await event.answer(f"{status_emoji} Online maker {status}!")
                await self.menu.send_account_management(
                    user_id, account_id, event.message_id
                )

    async def handle_simulate_callback(self, event, user_id, data):
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"
        
        if action == "toggle":
            await self._handle_simulate_toggle(event, user_id, account_id)
        elif action == "status":
            await self._show_simulation_status(user_id, account_id, event.message_id)
        elif action == "stats":
            await self._show_simulation_stats(user_id, account_id, event.message_id)

    async def _handle_simulate_toggle(self, event, user_id, account_id):
        """Handle simulation toggle"""
        from bson import ObjectId

        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
        if not account:
            await event.answer("❌ Account not found")
            return

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

    async def _show_simulation_status(self, user_id, account_id, message_id):
        from bson import ObjectId

        account = await mongodb.db.accounts.find_one(
            {"_id": ObjectId(account_id), "user_id": user_id}
        )
        if account:
            status = (
                "✅ Active"
                if account.get("simulation_enabled", False)
                else "❌ Inactive"
            )
            text = f"🎭 **Activity Simulator: {account['name']}**\n\nStatus: {status}\n\nThe simulator performs human-like activities:\n• Views random channels/groups\n• Reacts to posts with emojis\n• Votes in polls occasionally\n• Browses user profiles\n• Rarely joins/leaves channels\n\nSessions every 30-90 minutes with 2-5 actions each."
            toggle_text = (
                "🔴 Disable"
                if account.get("simulation_enabled", False)
                else "🟢 Enable"
            )
            from telethon import Button

            buttons = [
                [
                    Button.inline(
                        f"{toggle_text} Simulation", f"simulate:toggle:{account_id}"
                    )
                ],
                [Button.inline("🔙 Back", f"account:manage:{account_id}")],
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        else:
            await self.bot.send_message(user_id, "❌ Account not found")

    async def _show_simulation_stats(self, user_id, account_id, message_id):
        from bson import ObjectId

        account = await mongodb.db.accounts.find_one(
            {"_id": ObjectId(account_id), "user_id": user_id}
        )
        if account:
            stats_text = "Loading statistics..."
            if hasattr(self.account_manager, "activity_simulator"):
                task_key = f"{user_id}_{account_id}"
                if task_key in self.account_manager.activity_simulator.simulation_tasks:
                    stats = self.account_manager.activity_simulator.stats.get(
                        task_key, {}
                    )
                    total_actions = stats.get("total_actions", 0)
                    last_session = stats.get("last_session", "Never")
                    avg_actions = stats.get("avg_actions_per_session", 0)
                    stats_text = f"**Statistics:**\n• Total Actions: {total_actions}\n• Last Session: {last_session}\n• Avg Actions/Session: {
                        avg_actions:.1f}\n• Status: {
                        'Active' if account.get('simulation_enabled') else 'Inactive'}"
                else:
                    stats_text = "No active simulation session found."
            text = f"📊 **Simulation Stats: {
                account['name']}**\n\n{stats_text}\n\n**Activity Types:**\n• Channel/Group browsing\n• Emoji reactions\n• Poll voting\n• Profile viewing\n• Occasional joins/leaves"
            from telethon import Button

            buttons = [
                [Button.inline("🔄 Refresh", f"simulate:stats:{account_id}")],
                [Button.inline("🔙 Back", f"account:manage:{account_id}")],
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        else:
            await self.bot.send_message(user_id, "❌ Account not found")

    async def handle_profile_callback(self, event, user_id, data):
        """Handle profile management callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"

        try:
            if action == "manage":
                if hasattr(self.menu, "profile_operations"):
                    await self.menu.profile_operations.send_profile_management(
                        user_id, account_id, event.message_id
                    )
                else:
                    await event.answer("❌ Profile operations unavailable")
            elif action == "name":
                await self._handle_profile_name_change(event, user_id, account_id)
            elif action == "username":
                await self._handle_profile_username_change(event, user_id, account_id)
            elif action == "bio":
                await self._handle_profile_bio_change(event, user_id, account_id)
            elif action == "photo":
                await self._handle_profile_photo_change(event, user_id, account_id)
        except Exception as e:
            logger.error(f"Profile callback error: {e}")
            await event.answer("❌ Error processing profile request")

    async def _handle_profile_name_change(self, event, user_id, account_id):
        """Handle profile name change request"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "change_name",
                "account_id": account_id,
            }
            await event.answer("✏️ Reply with new name")
            await self.bot.send_message(
                user_id,
                "✏️ **Change Name**\n\nReply with the new name for your profile:",
            )
        else:
            await event.answer("❌ Service unavailable")

    async def _handle_profile_username_change(self, event, user_id, account_id):
        """Handle profile username change request"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "change_username",
                "account_id": account_id,
            }
            await event.answer("@️ Reply with new username")
            await self.bot.send_message(
                user_id,
                "@️ **Change Username**\n\nReply with the new username (without @):",
            )
        else:
            await event.answer("❌ Service unavailable")

    async def _handle_profile_bio_change(self, event, user_id, account_id):
        """Handle profile bio change request"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "change_bio",
                "account_id": account_id,
            }
            await event.answer("📝 Reply with new bio")
            await self.bot.send_message(
                user_id, "📝 **Change Bio**\n\nReply with the new bio for your profile:"
            )
        else:
            await event.answer("❌ Service unavailable")

    async def _handle_profile_photo_change(self, event, user_id, account_id):
        """Handle profile photo change request"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "change_photo",
                "account_id": account_id,
            }
            await event.answer("📷 Send new photo")
            await self.bot.send_message(
                user_id,
                "📷 **Change Profile Photo**\n\nSend the new photo for your profile:",
            )
        else:
            await event.answer("❌ Service unavailable")

    async def handle_session_callback(self, event, user_id, data):
        """Handle session management callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"

        try:
            if action == "export":
                await self._handle_session_export(event, user_id, account_id)
            elif action == "terminate":
                await self._handle_session_terminate(event, user_id, account_id)
            elif action == "list":
                await self._handle_session_list(event, user_id, account_id)
        except Exception as e:
            if "not modified" in str(e).lower():
                # Message content unchanged — safe to ignore
                await event.answer()
            else:
                logger.error(f"Session callback error: {e}")
                await event.answer("❌ Error processing session request")

    async def _handle_session_export(self, event, user_id, account_id):
        """Handle session export request"""
        try:
            from bson import ObjectId

            account = await mongodb.db.accounts.find_one(
                {"_id": ObjectId(account_id), "user_id": user_id}
            )
            if not account:
                await event.answer("❌ Account not found")
                return

            session_string = account.get("session_string", "")
            if not session_string:
                await event.answer("❌ No session string found")
                return

            # Decrypt session string if encrypted
            if hasattr(self.account_manager, "encryption_manager"):
                try:
                    session_string = (
                        self.account_manager.encryption_manager.decrypt_data(
                            session_string
                        )
                    )
                except Exception:
                    pass

            dc_id = account.get("dc_id", "Unknown")
            phone = account.get("phone", "Unknown")

            export_text = f"📤 **Session Export**\n\n**Account:** {phone}\n**DC ID:** {dc_id}\n\n**Session String:**\n`{session_string}`\n\n⚠️ **Security Warning:** Keep this session string private!"

            await event.answer("📤 Session exported")
            await self.bot.send_message(user_id, export_text)
        except Exception as e:
            logger.error(f"Error exporting session: {e}")
            await event.answer("❌ Error exporting session")

    async def _handle_session_terminate(self, event, user_id, account_id):
        """Handle session termination request"""
        try:
            if hasattr(self.account_manager, "session_manager"):
                success, message = (
                    await self.account_manager.session_manager.terminate_sessions(
                        user_id, account_id
                    )
                )
                await event.answer(f"{'✅' if success else '❌'} {message}")
            else:
                await event.answer("❌ Session manager unavailable")
        except Exception as e:
            logger.error(f"Error terminating sessions: {e}")
            await event.answer("❌ Error terminating sessions")

    async def _handle_session_list(self, event, user_id, account_id):
        """Handle session list request via Telethon"""
        from bson import ObjectId
        from telethon import Button
        from telethon.tl.functions.account import GetAuthorizationsRequest

        account = await mongodb.db.accounts.find_one(
            {"_id": ObjectId(account_id), "user_id": user_id}
        )
        if not account:
            await event.answer("❌ Account not found")
            return

        client = None
        if self.account_manager:
            client = self.account_manager.user_clients.get(user_id, {}).get(
                account.get("name") or account.get("phone")
            )

        text = f"🔐 **Active Sessions — {account.get('name', account.get('phone'))}**\n\n"
        try:
            if client and client.is_connected():
                result = await client(GetAuthorizationsRequest())
                auths = result.authorizations
                text += f"Total sessions: {len(auths)}\n\n"
                for auth in auths[:10]:
                    current = " ✅ (current)" if auth.current else ""
                    text += (
                        f"• {auth.app_name} — {auth.device_model}\n"
                        f"  {auth.country}, {auth.ip}\n"
                        f"  {auth.platform}{current}\n\n"
                    )
                if len(auths) > 10:
                    text += f"... and {len(auths) - 10} more"
            else:
                text += "⚠️ Account not connected. Start the account first."
        except Exception as e:
            logger.error(f"Error fetching sessions: {e}")
            text += f"❌ Could not fetch sessions: {e}"

        buttons = [
            [Button.inline("🔄 Refresh", f"sessions:list:{account_id}")],
            [Button.inline("🚫 Terminate All Other", f"session:terminate:{account_id}")],
            [Button.inline("🔙 Back", f"account:manage:{account_id}")],
        ]
        await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

    async def handle_2fa_callback(self, event, user_id, data):
        """Handle 2FA management callbacks"""
        parts = data.split(":")
        action = parts[1]
        account_id = parts[2] if len(parts) > 2 else "0"

        try:
            if action == "status":
                await self._handle_2fa_status(event, user_id, account_id)
            elif action == "set":
                await self._handle_2fa_set(event, user_id, account_id)
            elif action == "remove":
                await self._handle_2fa_remove(event, user_id, account_id)
            elif action == "view":
                await self._handle_2fa_view(event, user_id, account_id)
        except Exception as e:
            logger.error(f"2FA callback error: {e}")
            await event.answer("❌ Error processing 2FA request")

    async def _handle_2fa_status(self, event, user_id, account_id):
        """Show 2FA status and management menu"""
        from bson import ObjectId
        from telethon import Button

        account = await mongodb.db.accounts.find_one(
            {"_id": ObjectId(account_id), "user_id": user_id}
        )
        if not account:
            await event.answer("❌ Account not found")
            return

        has_2fa = bool(account.get("twofa_password"))
        status_text = "✅ Stored" if has_2fa else "❌ Not stored"
        text = (
            f"🔐 **2FA Settings — {account.get('name', account.get('phone'))}**\n\n"
            f"Saved 2FA password: {status_text}\n\n"
            f"The stored password is used automatically during login."
        )
        buttons = [
            [Button.inline("✏️ Set / Update Password", f"2fa:set:{account_id}")],
        ]
        if has_2fa:
            buttons.append([Button.inline("👁 View Password", f"2fa:view:{account_id}")])
            buttons.append([Button.inline("🗑️ Remove Password", f"2fa:remove:{account_id}")])
        buttons.append([Button.inline("🔙 Back", f"account:manage:{account_id}")])
        await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)

    async def _handle_2fa_set(self, event, user_id, account_id):
        """Handle 2FA password set request"""
        if self.account_manager:
            self.account_manager.pending_actions[user_id] = {
                "action": "set_2fa",
                "account_id": account_id,
            }
            await event.answer("🔐 Reply with 2FA password")
            await self.bot.send_message(
                user_id,
                "🔐 **Set 2FA Password**\n\nReply with the 2FA password for this account:",
            )
        else:
            await event.answer("❌ Service unavailable")

    async def _handle_2fa_remove(self, event, user_id, account_id):
        """Handle 2FA password removal request"""
        try:
            if hasattr(self.account_manager, "db_manager"):
                success = await self.account_manager.db_manager.remove_2fa_password(
                    user_id, account_id
                )
                if success:
                    await event.answer("✅ 2FA password removed")
                else:
                    await event.answer("❌ Failed to remove 2FA password")
            else:
                await event.answer("❌ Database manager unavailable")
        except Exception as e:
            logger.error(f"Error removing 2FA: {e}")
            await event.answer("❌ Error removing 2FA password")

    async def _handle_2fa_view(self, event, user_id, account_id):
        """Handle 2FA password view request"""
        try:
            if hasattr(self.account_manager, "db_manager"):
                password = await self.account_manager.db_manager.get_2fa_password(
                    user_id, account_id
                )
                if password:
                    await self.bot.send_message(
                        user_id,
                        f"🔐 **2FA Password**\n\n`{password}`\n\n⚠️ Keep this password secure!",
                    )
                    await event.answer("🔐 2FA password sent")
                else:
                    await event.answer("❌ No 2FA password stored")
            else:
                await event.answer("❌ Database manager unavailable")
        except Exception as e:
            logger.error(f"Error viewing 2FA: {e}")
            await event.answer("❌ Error retrieving 2FA password")

    async def _show_otp_statistics(self, user_id: int, message_id: int):
        """Show OTP statistics for all accounts"""
        try:
            import time
            from telethon import Button

            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            if not accounts:
                await self.bot.edit_message(
                    user_id, message_id,
                    "📊 **OTP Statistics**\n\n❌ No accounts found.",
                    buttons=[[Button.inline("🔙 Back", "menu:otp")]]
                )
                return

            total = len(accounts)
            destroyer_on = sum(1 for a in accounts if a.get("otp_destroyer_enabled"))
            forward_on = sum(1 for a in accounts if a.get("otp_forward_enabled"))
            temp_active = sum(1 for a in accounts if a.get("otp_temp_passthrough"))
            security_score = int((destroyer_on / total) * 100) if total else 0
            score_emoji = "🟢" if security_score >= 80 else "🟡" if security_score >= 50 else "🔴"

            # Count total audit events across all accounts
            total_events = sum(len(a.get("audit_log", [])) for a in accounts)
            # Count recent events (last 24h)
            cutoff = int(time.time()) - 86400
            recent_events = sum(
                sum(1 for e in a.get("audit_log", []) if e.get("timestamp", 0) >= cutoff)
                for a in accounts
            )

            text = (
                "📊 **OTP Security Statistics**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📱 **Accounts:** {total}\n"
                f"{score_emoji} **Security Score:** {security_score}%\n\n"
                "🛡️ **Protection Status:**\n"
                f"• OTP Destroyer: {destroyer_on}/{total} accounts\n"
                f"• OTP Forward: {forward_on}/{total} accounts\n"
                f"• Temp Bypass Active: {temp_active}\n\n"
                "📋 **Audit Activity:**\n"
                f"• Total Events: {total_events}\n"
                f"• Last 24h: {recent_events}\n\n"
                "📈 **Per-Account Breakdown:**\n"
            )
            for acc in accounts[:8]:
                d = "🛡️" if acc.get("otp_destroyer_enabled") else "⚪"
                f = "📤" if acc.get("otp_forward_enabled") else "⚪"
                events = len(acc.get("audit_log", []))
                from ...utils.network_helpers import format_display_name
                name = format_display_name(acc)
                text += f"• {name}: {d}{f} | {events} events\n"

            buttons = [
                [Button.inline("🔄 Refresh", "otp:stats")],
                [Button.inline("📋 Global Audit Log", "otp:audit_all")],
                [Button.inline("🔙 Back to OTP Manager", "menu:otp")],
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing OTP statistics: {e}")
            from telethon import Button
            await self.bot.edit_message(
                user_id, message_id,
                "❌ Error loading OTP statistics",
                buttons=[[Button.inline("🔙 Back", "menu:otp")]]
            )

    async def _show_global_audit_log(self, user_id: int, message_id: int):
        """Show global audit log across all accounts"""
        try:
            import time
            from telethon import Button

            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            if not accounts:
                await self.bot.edit_message(
                    user_id, message_id,
                    "📋 **Global Audit Log**\n\n❌ No accounts found.",
                    buttons=[[Button.inline("🔙 Back", "menu:otp")]]
                )
                return

            # Collect all audit entries with account name
            all_entries = []
            for acc in accounts:
                from ...utils.network_helpers import format_display_name
                acc_name = format_display_name(acc)
                for entry in acc.get("audit_log", []):
                    all_entries.append({
                        "account": acc_name,
                        "action": entry.get("action", "unknown"),
                        "timestamp": entry.get("timestamp", 0),
                    })

            # Sort by timestamp descending
            all_entries.sort(key=lambda x: x["timestamp"], reverse=True)

            if not all_entries:
                text = "📋 **Global Security Audit Log**\n\n💭 No audit entries found across all accounts."
            else:
                text = "📋 **Global Security Audit Log**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                for entry in all_entries[:20]:
                    ts = time.strftime("%m-%d %H:%M", time.localtime(entry["timestamp"]))
                    text += f"• `{ts}` **{entry['account']}** — {entry['action']}\n"
                if len(all_entries) > 20:
                    text += f"\n_...and {len(all_entries) - 20} more entries_"

            buttons = [
                [Button.inline("🔄 Refresh", "otp:audit_all")],
                [Button.inline("📊 Statistics", "otp:stats")],
                [Button.inline("🔙 Back to Protection Manager", "menu:protection")],
            ]
            await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error showing global audit log: {e}")
            from telethon import Button
            await self.bot.edit_message(
                user_id, message_id,
                "❌ Error loading audit log",
                buttons=[[Button.inline("🔙 Back", "menu:otp")]]
            )
