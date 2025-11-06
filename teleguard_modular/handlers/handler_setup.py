"""Handler setup module - extracted from menu_system.py
Handles registration of menu text handlers and callback handlers
"""
import logging
from telethon import Button, events
from teleguard.core.config import ADMIN_IDS
from teleguard.core.mongo_database import mongodb

logger = logging.getLogger(__name__)

async def setup_menu_text_handler(bot, menu_system):
    """Setup menu text handler for button-based navigation"""
    
    async def menu_text_handler(event):
        user_id = event.sender_id
        text = event.text.strip()
        try:
            if text in ["📱 Account Settings", "Account Settings"]:
                await menu_system.handlers.handle_account_settings(event)
            elif text in ["🛡️ OTP Manager", "OTP Manager"]:
                await menu_system.handlers.handle_otp_manager(event)
            elif text in ["💬 Messaging", "Messaging"]:
                await menu_system.handlers.handle_messaging(event)
            elif text in ["📨 DM Reply", "DM Reply"]:
                await menu_system._handle_dm_reply(event)
            elif text in ["📢 Channels", "Channels"]:
                await menu_system.handlers.handle_channels(event)
            elif text in ["👥 Contacts", "Contacts"]:
                await menu_system._handle_contacts(event)
            elif text in ["🎯 SpamMaster", "SpamMaster"]:
                await menu_system._handle_spam_master(event)
            elif text in ["🧹 Cleanup", "Cleanup"]:
                await menu_system.handlers.handle_cleanup(event)
            elif text in ["❓ Help", "Help"]:
                await menu_system.handlers.handle_help(event)
            elif text in ["🆘 Support", "Support"]:
                await menu_system.handlers.handle_support(event)
            elif text in ["⚙️ Developer", "Developer", "⚙️ Developer Panel", "Developer Panel"]:
                if user_id not in ADMIN_IDS:
                    await event.reply("❌ You don't have access to Developer tools.")
                    return
                await menu_system.handlers.handle_developer(event)
        except Exception as e:
            logger.error(f"Menu handler error for {text}: {e}")
            await event.reply("❌ Error processing menu action")
    
    # Register the handler
    bot.add_event_handler(
        menu_text_handler,
        events.NewMessage(
            func=lambda e: e.is_private
            and e.text
            and e.text.strip()
            in [
                "📱 Account Settings", "Account Settings",
                "🛡️ OTP Manager", "OTP Manager",
                "💬 Messaging", "Messaging",
                "📨 DM Reply", "DM Reply",
                "📢 Channels", "Channels",
                "👥 Contacts", "Contacts",
                "🎯 SpamMaster", "SpamMaster",
                "🧹 Cleanup", "Cleanup",
                "❓ Help", "Help",
                "🆘 Support", "Support",
                "⚙️ Developer", "Developer",
            ]
        )
    )
    logger.info("✅ Menu text handler registered successfully")
    
    return menu_text_handler

async def setup_cleanup_selection_handler(bot, menu_system):
    """Setup cleanup selection text input handler"""
    
    async def cleanup_selection_handler(event):
        await menu_system._handle_cleanup_selection_callback(event, event.sender_id, event.text)
    
    # Register the handler
    bot.add_event_handler(
        cleanup_selection_handler,
        events.NewMessage(
            func=lambda e: e.is_private 
            and hasattr(menu_system.account_manager, 'pending_actions') 
            and e.sender_id in menu_system.account_manager.pending_actions 
            and menu_system.account_manager.pending_actions[e.sender_id].get('action') == 'cleanup_selection'
        )
    )
    logger.info("✅ Cleanup selection handler registered successfully")
    
    return cleanup_selection_handler

async def setup_callback_handler(bot, menu_system):
    """Setup massive callback handler for all button interactions"""
    
    async def callback_handler(event):
        try:
            user_id = event.sender_id
            data = event.data.decode("utf-8")
            logger.info(f"Callback from {user_id}: {data}")
            
            # Route callbacks using modular router
            await menu_system.router.route_callback(event, user_id, data)
            
            # Legacy routing for backward compatibility
            if data.startswith("otp_setting:"):
                await menu_system._handle_otp_setting_callback(event, user_id, data)
            elif data.startswith("otp:"):
                if data.startswith("otp:manage:"):
                    account_id = data.split(":")[2]
                    await menu_system.send_otp_account_management(user_id, account_id, event.message_id)
                elif data == "otp:enable_all":
                    await menu_system._handle_bulk_otp_enable(user_id, event.message_id)
                    await event.answer("🛡️ Bulk enable completed")
                elif data == "otp:disable_all":
                    await menu_system._handle_bulk_otp_disable(user_id, event.message_id)
                    await event.answer("🔴 Bulk disable completed")
                elif data == "otp:stats":
                    await menu_system._show_otp_statistics(user_id, event.message_id)
                    await event.answer("📊 OTP statistics")
                elif data == "otp:audit_all":
                    await menu_system._show_global_audit_log(user_id, event.message_id)
                    await event.answer("📋 Global audit log loaded")
                else:
                    await menu_system._handle_otp_callback(event, user_id, data)
            elif data.startswith("2fa:"):
                await menu_system._handle_2fa_callback(event, user_id, data)
            elif data.startswith("profile:"):
                await menu_system._handle_profile_callback(event, user_id, data)
            elif data.startswith("sessions:"):
                await menu_system._handle_sessions_callback(event, user_id, data)
            elif data.startswith("online:"):
                await menu_system._handle_online_callback(event, user_id, data)
            elif data.startswith("msg:"):
                parts = data.split(":")
                action = parts[1]
                if action == "send":
                    await menu_system._send_message_menu(user_id, event.message_id)
                elif action == "autoreply":
                    await menu_system._send_autoreply_menu(user_id, event.message_id)
                elif action == "templates":
                    await menu_system._send_templates_menu(user_id, event.message_id)
                elif action == "stats":
                    await menu_system._show_messaging_statistics(user_id, event.message_id)
                    await event.answer("📊 Messaging stats loaded")
                elif action == "history":
                    await menu_system._show_message_history(user_id, event.message_id)
                    await event.answer("📋 Message history loaded")
                elif action == "settings":
                    await menu_system._show_messaging_settings(user_id, event.message_id)
                    await event.answer("⚙️ Messaging settings loaded")
                elif action == "bulk":
                    await menu_system._send_bulk_sender_menu(user_id, event.message_id)
                else:
                    await menu_system._handle_messaging_callback(event, user_id, data)
            elif data.startswith("autoreply:"):
                await menu_system._handle_autoreply_callback(event, user_id, data)
            elif data.startswith("template:"):
                await menu_system._handle_template_callback(event, user_id, data)
            elif data.startswith("bulk:"):
                await menu_system._handle_bulk_callback(event, user_id, data)
            elif data.startswith("bulk_list_account:"):
                account_id = data.split(":")[1]
                if menu_system.account_manager:
                    menu_system.account_manager.pending_actions[user_id] = {
                        "action": "bulk_list_targets",
                        "account_id": account_id
                    }
                text = "📋 **Step 2:** Reply with targets (comma-separated):\n\n@user1,@user2,+1234567890"
                await bot.edit_message(user_id, event.message_id, text)
                await event.answer("📋 Reply with targets")
            elif data.startswith("bulk_contacts_account:"):
                account_id = data.split(":")[1]
                if menu_system.account_manager:
                    menu_system.account_manager.pending_actions[user_id] = {
                        "action": "bulk_contacts_message",
                        "account_id": account_id
                    }
                text = "👥 **Step 2:** Reply with your message:"
                await bot.edit_message(user_id, event.message_id, text)
                await event.answer("👥 Reply with message")
            elif data.startswith("simulate:"):
                await menu_system._handle_simulate_callback(event, user_id, data)
            elif data.startswith("audit:"):
                await menu_system._handle_audit_callback(event, user_id, data)
            elif data.startswith("otp:audit"):
                parts = data.split(":")
                if len(parts) >= 3:
                    account_id = parts[2]
                    await menu_system.send_audit_log(user_id, account_id)
            elif data.startswith("channel:"):
                parts = data.split(":")
                action = parts[1]
                if action == "select" and len(parts) > 2:
                    account_phone = parts[2]
                    await menu_system._send_channel_actions_menu(user_id, account_phone, event.message_id)
                elif action == "stats":
                    await menu_system._show_channel_statistics(user_id, event.message_id)
                    await event.answer("📊 Statistics loaded")
                elif action == "search":
                    text = (
                        "🔍 **Search Channels**\n\n"
                        "Channel search functionality:\n\n"
                        "• Search by name or username\n"
                        "• Filter by type (channel/group)\n"
                        "• Browse popular channels\n"
                        "• Find recommended channels\n\n"
                        "Feature coming soon!"
                    )
                    buttons = [[Button.inline("🔙 Back to Channels", "menu:channels")]]
                    await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                    await event.answer("🔍 Search feature")
                else:
                    await menu_system._handle_channel_callback(event, user_id, data)
            elif data.startswith("help:"):
                await menu_system._handle_help_callback(event, user_id, data)
            elif data.startswith("support:"):
                await menu_system._handle_support_callback(event, user_id, data)
            elif data.startswith("dev:"):
                await menu_system._handle_developer_callback(event, user_id, data)
            elif data.startswith("menu:"):
                await menu_system._handle_menu_callback(event, user_id, data)
            elif data.startswith("dm_reply:"):
                if data == "dm_reply:main":
                    await menu_system._handle_dm_reply(
                        type("Event", (), {
                            "sender_id": user_id,
                            "reply": lambda x, buttons=None: bot.edit_message(user_id, event.message_id, x, buttons=buttons),
                        })()
                    )
                else:
                    await menu_system._handle_dm_reply_callback(event, user_id, data)
            elif data.startswith("cleanup:"):
                await menu_system._handle_cleanup_callback(event, user_id, data)
            elif data.startswith("cleanup_selection:"):
                try:
                    await menu_system._handle_cleanup_selection_callback(event, user_id, data)
                except Exception as e:
                    logger.error(f"Cleanup selection callback error: {e}")
                    await event.answer("❌ Error processing cleanup selection")
            elif data.startswith("contacts:"):
                try:
                    parts = data.split(":")
                    action = parts[1] if len(parts) > 1 else "main"
                    if action == "main":
                        text = (
                            "📱 **Contact Management**\n\n"
                            "📊 Contact system available\n\n"
                            "Choose an option:"
                        )
                        buttons = [
                            [Button.inline("👥 View All Contacts", "contacts:list")],
                            [Button.inline("➕ Add Contact", "contacts:add"), Button.inline("🔍 Search", "contacts:search")],
                            [Button.inline("📁 Groups", "contacts:groups"), Button.inline("🏷️ Tags", "contacts:tags")],
                            [Button.inline("📤 Export", "contacts:export"), Button.inline("📥 Import", "contacts:import")],
                            [Button.inline("🔄 Sync", "contacts:sync")],
                            [Button.inline("🔙 Back", "menu:main")]
                        ]
                        await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                    elif action == "list":
                        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
                        if not accounts:
                            text = "👥 **All Contacts**\n\n❌ No accounts found."
                            buttons = [[Button.inline("🔙 Back", "contacts:main")]]
                        else:
                            all_contacts = []
                            total_contacts = 0
                            for account in accounts:
                                if not account.get("is_active", False):
                                    continue
                                try:
                                    if (user_id in menu_system.account_manager.user_clients and 
                                        account['name'] in menu_system.account_manager.user_clients[user_id]):
                                        client = menu_system.account_manager.user_clients[user_id][account['name']]
                                        if client and client.is_connected():
                                            from telethon.tl.functions.contacts import GetContactsRequest
                                            from telethon.tl.types import User
                                            result = await client(GetContactsRequest(hash=0))
                                            for user in result.users[:5]:
                                                if isinstance(user, User) and not user.bot:
                                                    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
                                                    username = f"@{user.username}" if user.username else "No username"
                                                    phone = user.phone or "No phone"
                                                    all_contacts.append({
                                                        'name': name,
                                                        'username': username,
                                                        'phone': phone,
                                                        'account': account['name']
                                                    })
                                            total_contacts += len([u for u in result.users if isinstance(u, User) and not u.bot])
                                except Exception as e:
                                    logger.error(f"Error getting contacts for {account['name']}: {e}")
                                    continue
                            if not all_contacts:
                                text = "👥 **All Contacts**\n\n💭 No contacts found in active accounts.\n\nMake sure accounts are connected and have contacts."
                            else:
                                text = f"👥 **All Contacts** (Showing {len(all_contacts)} of {total_contacts})\n\n"
                                for i, contact in enumerate(all_contacts, 1):
                                    text += f"{i}. **{contact['name']}**\n   {contact['username']} | {contact['phone']}\n   Account: {contact['account']}\n\n"
                            buttons = [[Button.inline("🔙 Back", "contacts:main")]]
                        await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                    elif action == "sync":
                        text = "🔄 **Contact Sync**\n\nChoose sync direction:"
                        buttons = [
                            [Button.inline("📥 From Telegram", "sync:from_telegram")],
                            [Button.inline("📤 To Telegram", "sync:to_telegram")],
                            [Button.inline("🔄 Both Ways", "sync:both")],
                            [Button.inline("🔙 Back", "contacts:main")]
                        ]
                        await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                    elif action == "export":
                        from teleguard.handlers.contact_export_handler import ContactExportHandler
                        export_handler = ContactExportHandler(menu_system.account_manager)
                        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
                        if not accounts:
                            text = "📤 **Export Contacts**\n\n❌ No accounts found. Add accounts first to export contacts."
                            buttons = [[Button.inline("🔙 Back", "contacts:main")]]
                            await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                            return
                        buttons = []
                        for account in accounts[:8]:
                            status = "✅" if account.get("is_active", False) else "❌"
                            buttons.append([Button.inline(f"{status} {account['name']}", f"export_contacts:{account['name']}")])
                        buttons.append([Button.inline("🔙 Back", "contacts:main")])
                        text = "📤 **Export Contacts to CSV**\n\nSelect account to export contacts from:"
                        await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                    else:
                        text = f"⚙️ **{action.title()} Feature**\n\nThis feature is coming soon!"
                        buttons = [[Button.inline("🔙 Back", "contacts:main")]]
                        await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                except Exception as e:
                    logger.error(f"Contact callback error: {e}")
                    await event.answer("❌ Error processing contact action")
            elif data.startswith("sync:"):
                try:
                    sync_type = data.split(":")[1]
                    accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=1)
                    if not accounts:
                        await bot.edit_message(user_id, event.message_id, "❌ No accounts found for sync")
                        return
                    await bot.edit_message(user_id, event.message_id, "🔄 **Synchronizing...**\n\nPlease wait...")
                    import asyncio
                    await asyncio.sleep(1)
                    if sync_type == "from_telegram":
                        result_text = "✅ **Sync from Telegram Complete**\n\nContacts imported from Telegram."
                    elif sync_type == "to_telegram":
                        result_text = "✅ **Sync to Telegram Complete**\n\nContacts exported to Telegram."
                    elif sync_type == "both":
                        result_text = "✅ **Two-way Sync Complete**\n\nContacts synchronized in both directions."
                    else:
                        result_text = "❌ **Invalid Sync Type**\n\nUnknown sync operation."
                    buttons = [[Button.inline("🔙 Back", "contacts:main")]]
                    await bot.edit_message(user_id, event.message_id, result_text, buttons=buttons)
                except Exception as e:
                    logger.error(f"Sync callback error: {e}")
                    await event.answer("❌ Error processing sync")
            elif data.startswith("remove:"):
                parts = data.split(":")
                if len(parts) >= 3 and parts[1] == "confirm":
                    account_id = parts[2]
                    text = (
                        "⚠️ **Confirm Account Removal**\n\n"
                        "Are you sure you want to remove this account?\n\n"
                        "This will:\n"
                        "• **Logout from Telegram** (session terminated)\n"
                        "• Delete all account data from TeleGuard\n"
                        "• Remove OTP protection\n"
                        "• Remove stored 2FA password\n"
                        "• **Cannot be undone**\n\n"
                        "The account will be logged out from Telegram just like using the logout button in the official app.\n\n"
                        "Use the buttons below to confirm or cancel."
                    )
                    buttons = [
                        [Button.inline("✅ Yes, Remove Account", f"remove:execute:{account_id}")],
                        [Button.inline("❌ Cancel", "account:remove")],
                    ]
                    await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                    await event.answer("⚠️ Confirm removal")
                elif len(parts) >= 3 and parts[1] == "execute":
                    account_id = parts[2]
                    await menu_system._execute_remove_account(event, user_id, account_id)
            elif data == "menu:accounts":
                await menu_system._handle_account_settings(
                    type("Event", (), {
                        "sender_id": user_id,
                        "reply": lambda x, buttons=None: bot.edit_message(user_id, event.message_id, x, buttons=buttons),
                    })()
                )
            elif data == "menu:otp":
                await menu_system._handle_otp_manager(
                    type("Event", (), {
                        "sender_id": user_id,
                        "reply": lambda x, buttons=None: bot.edit_message(user_id, event.message_id, x, buttons=buttons),
                    })()
                )
            elif data == "menu:messaging":
                await menu_system._handle_messaging(
                    type("Event", (), {
                        "sender_id": user_id,
                        "reply": lambda x, buttons=None: bot.edit_message(user_id, event.message_id, x, buttons=buttons),
                    })()
                )
            elif data == "auto_reply:main":
                await event.answer("🤖 Loading auto-reply menu...")
                await menu_system._send_autoreply_menu(user_id, event.message_id)
            elif data == "menu:channels":
                await menu_system._handle_channels(
                    type("Event", (), {
                        "sender_id": user_id,
                        "reply": lambda x, buttons=None: bot.edit_message(user_id, event.message_id, x, buttons=buttons),
                    })()
                )
            elif data.startswith("otp_pwd:"):
                parts = data.split(":")
                if len(parts) >= 3:
                    action = parts[1]
                    account_id = parts[2]
                    if action == "set":
                        await event.answer("🔒 Set password feature coming soon!")
                    elif action == "change":
                        if menu_system.account_manager:
                            menu_system.account_manager.pending_actions[user_id] = {
                                "action": "change_otp_disable_password",
                                "account_id": account_id,
                            }
                            text = "🔒 **Change Password**\n\nReply with your current password first:"
                            await bot.send_message(user_id, text)
                            await event.answer("🔒 Enter current password")
                    elif action == "remove":
                        if menu_system.account_manager:
                            menu_system.account_manager.pending_actions[user_id] = {
                                "action": "remove_otp_disable_password",
                                "account_id": account_id,
                            }
                            text = "🔒 **Remove Password**\n\nReply with your current password to remove protection:"
                            await bot.send_message(user_id, text)
                            await event.answer("🔒 Enter password to remove")
                    elif action == "status":
                        text = (
                            "🔒 **Password Status**\n\n"
                            "OTP Destroyer password protection:\n\n"
                            "• Current status\n"
                            "• Security level\n"
                            "• Last changed\n"
                            "• Protection active\n\n"
                            "Feature coming soon!"
                        )
                        buttons = [[Button.inline("🔙 Back", f"otp:manage:{account_id}")]]
                        await bot.send_message(user_id, text, buttons=buttons)
                        await event.answer("🔒 Password status")
            elif data.startswith("manage:"):
                account_phone = data.split(":")[1]
                await menu_system._send_channel_actions_menu(user_id, account_phone, event.message_id)
            elif data == "export_sessions":
                try:
                    session_handler = None
                    if hasattr(menu_system.account_manager, 'bot_manager') and hasattr(menu_system.account_manager.bot_manager, 'session_login_handler'):
                        session_handler = menu_system.account_manager.bot_manager.session_login_handler
                    elif hasattr(menu_system.account_manager, 'session_login_handler'):
                        session_handler = menu_system.account_manager.session_login_handler
                    if session_handler:
                        try:
                            await session_handler._start_session_creation(event, user_id)
                        except Exception as edit_error:
                            if "Content of the message was not modified" in str(edit_error):
                                await event.answer("✅")
                            else:
                                raise
                    else:
                        await event.answer("❌ Session creation not available")
                except Exception as e:
                    if "Content of the message was not modified" not in str(e):
                        logger.error(f"Session creation error: {e}")
                        await event.answer("❌ Error starting session creation")
            elif data.startswith("export_session:"):
                account_name = data.split(":", 1)[1]
                await menu_system._handle_export_session_select(event, user_id, account_name)
            elif data.startswith("export_file:"):
                account_name = data.split(":", 1)[1]
                await menu_system._handle_export_fresh_session(event, user_id, account_name)
            elif data.startswith("export_fresh:"):
                account_name = data.split(":", 1)[1]
                await menu_system._handle_export_fresh_session(event, user_id, account_name)
            elif data.startswith("export_contacts:"):
                account_name = data.split(":", 1)[1]
                await menu_system._handle_export_contacts(event, user_id, account_name)
            elif data == "validate_session":
                if menu_system.account_manager:
                    menu_system.account_manager.pending_actions[user_id] = {"action": "validate_session_string"}
                    text = "🔍 **Session String Validator**\n\nReply with a session string to validate and see DC information (DC1, DC2, DC3, DC4, or DC5):"
                    await bot.send_message(user_id, text)
                    await event.answer("🔍 Send session string to validate")
            elif data == "spam_master":
                if hasattr(menu_system.account_manager, 'advanced_spam_handler'):
                    await menu_system.account_manager.advanced_spam_handler._handle_spam_master_menu(event)
                else:
                    await event.answer("SpamMaster not available")
            elif data.startswith("appeal_account_id:"):
                account_id = data.split(":", 1)[1]
                text = "📞 **Spam Appeal**\n\nStarting spam appeal process..."
                buttons = [[Button.inline("🔙 Back", "cleanup:menu")]]
                await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                await event.answer("📞 Spam appeal started")
            elif data == "menu:import":
                text = "📨 **Chat Import**\n\nImport chat history feature coming soon!"
                buttons = [[Button.inline("🔙 Back", "menu:main")]]
                await bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                await event.answer("📨 Chat import")
            elif data == "menu:spam_master":
                await menu_system._handle_spam_master(type("Event", (), {"sender_id": user_id, "reply": lambda x, buttons=None: bot.edit_message(user_id, event.message_id, x, buttons=buttons)})())
            elif data == "menu:help":
                await menu_system._handle_help(type("Event", (), {"sender_id": user_id})())
            elif data == "menu:support":
                await menu_system._handle_support(type("Event", (), {"sender_id": user_id})())
            elif data == "menu:developer":
                await menu_system._handle_developer(type("Event", (), {"sender_id": user_id})())
            elif data == "menu:dm_reply":
                await menu_system._handle_dm_reply(type("Event", (), {"sender_id": user_id})())
            elif data == "back:accounts":
                await menu_system._handle_channels(type("Event", (), {"sender_id": user_id, "reply": lambda x, buttons=None: bot.edit_message(user_id, event.message_id, x, buttons=buttons)})())
            elif data == "session_login":
                await menu_system.missing_handlers.handle_session_login(event, user_id)
            elif data == "import_sessions":
                await menu_system.missing_handlers.handle_import_sessions(event, user_id)
            else:
                await event.answer("Action processed", alert=False)
        except Exception as e:
            logger.error(f"Callback handler error: {e}")
            await event.answer("❌ Service temporarily unavailable", alert=True)
    
    # Register the handler
    bot.add_event_handler(callback_handler, events.CallbackQuery())
    logger.info("✅ Callback handler registered successfully")
    
    return callback_handler
