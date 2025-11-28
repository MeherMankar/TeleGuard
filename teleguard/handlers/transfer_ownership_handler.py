"""Transfer Ownership Handler - Transfer accounts to another user"""
import logging
from telethon import Button, events
from ..core.mongo_database import mongodb
from bson import ObjectId

logger = logging.getLogger(__name__)

class TransferOwnershipHandler:
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.pending_transfers = {}  # {user_id: {selected_accounts: [], target_user: None}}
    
    def register_handlers(self):
        """Register transfer ownership command and callbacks"""
        
        @self.bot.on(events.NewMessage(pattern=r"/transfer"))
        async def transfer_command(event):
            user_id = event.sender_id
            try:
                accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
                if not accounts:
                    await event.reply("❌ No accounts found to transfer.")
                    return
                
                # Initialize transfer state
                self.pending_transfers[user_id] = {"selected_accounts": [], "target_user": None}
                
                text = (
                    "🔄 **Transfer Account Ownership**\n\n"
                    f"📊 You have {len(accounts)} account(s)\n\n"
                    "Select accounts to transfer:\n"
                    "✅ = Selected | ❌ = Not Selected"
                )
                
                buttons = []
                for account in accounts:
                    display_name = account.get('name', 'Unknown')
                    phone = account.get('phone', 'Unknown')
                    button_text = f"❌ {display_name} ({phone})"
                    buttons.append([Button.inline(button_text, f"transfer_toggle:{account['_id']}")])
                
                buttons.append([Button.inline("✅ Select All", "transfer_select_all")])
                buttons.append([Button.inline("❌ Deselect All", "transfer_deselect_all")])
                buttons.append([Button.inline("✔️ Done", "transfer_done")])
                buttons.append([Button.inline("🔙 Cancel", "transfer_cancel")])
                
                await event.reply(text, buttons=buttons)
            except Exception as e:
                logger.error(f"Transfer command error: {e}")
                await event.reply(f"❌ Error: {str(e)}")
        
        @self.bot.on(events.CallbackQuery(pattern=r"^transfer_toggle:(.+)$"))
        async def toggle_account(event):
            user_id = event.sender_id
            account_id = event.pattern_match.group(1).decode()
            
            if user_id not in self.pending_transfers:
                await event.answer("❌ Session expired. Use /transfer again.")
                return
            
            selected = self.pending_transfers[user_id]["selected_accounts"]
            if account_id in selected:
                selected.remove(account_id)
            else:
                selected.append(account_id)
            
            await self._update_selection_menu(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^transfer_select_all$"))
        async def select_all(event):
            user_id = event.sender_id
            if user_id not in self.pending_transfers:
                await event.answer("❌ Session expired. Use /transfer again.")
                return
            
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            self.pending_transfers[user_id]["selected_accounts"] = [str(acc['_id']) for acc in accounts]
            await self._update_selection_menu(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^transfer_deselect_all$"))
        async def deselect_all(event):
            user_id = event.sender_id
            if user_id not in self.pending_transfers:
                await event.answer("❌ Session expired. Use /transfer again.")
                return
            
            self.pending_transfers[user_id]["selected_accounts"] = []
            await self._update_selection_menu(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^transfer_done$"))
        async def done_selection(event):
            user_id = event.sender_id
            if user_id not in self.pending_transfers:
                await event.answer("❌ Session expired. Use /transfer again.")
                return
            
            selected = self.pending_transfers[user_id]["selected_accounts"]
            if not selected:
                await event.answer("❌ No accounts selected!", alert=True)
                return
            
            text = (
                "👤 **Enter Target User**\n\n"
                f"Selected: {len(selected)} account(s)\n\n"
                "Reply with the user ID or username of the person you want to transfer ownership to:\n\n"
                "Examples:\n"
                "• 123456789 (user ID)\n"
                "• @username"
            )
            await event.edit(text)
            await event.answer("✅ Reply with user ID or username")
        
        @self.bot.on(events.CallbackQuery(pattern=r"^transfer_cancel$"))
        async def cancel_transfer(event):
            user_id = event.sender_id
            if user_id in self.pending_transfers:
                del self.pending_transfers[user_id]
            await event.edit("❌ Transfer cancelled.")
            await event.answer("Transfer cancelled")
        
        @self.bot.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and not e.text.startswith('/')))
        async def handle_target_user(event):
            user_id = event.sender_id
            if user_id not in self.pending_transfers or self.pending_transfers[user_id].get("target_user") is not None:
                return
            
            if not self.pending_transfers[user_id]["selected_accounts"]:
                return
            
            text = event.text.strip()
            target_user_id = None
            
            try:
                # Try to parse as user ID
                if text.isdigit():
                    target_user_id = int(text)
                # Try to parse as username
                elif text.startswith('@'):
                    username = text[1:]
                    try:
                        entity = await self.bot.get_entity(username)
                        target_user_id = entity.id
                    except:
                        await event.reply("❌ User not found. Make sure they have started the bot.")
                        return
                else:
                    await event.reply("❌ Invalid format. Use user ID (123456789) or username (@username)")
                    return
                
                # Verify target user exists in bot database
                target_user = await mongodb.get_user(target_user_id)
                if not target_user:
                    await event.reply("❌ User not found in bot database. They must start the bot first.")
                    return
                
                # Get target user info
                try:
                    target_entity = await self.bot.get_entity(target_user_id)
                    target_name = target_entity.first_name or "Unknown"
                    target_username = f"@{target_entity.username}" if target_entity.username else "No username"
                except:
                    target_name = "Unknown"
                    target_username = "Unknown"
                
                self.pending_transfers[user_id]["target_user"] = target_user_id
                
                # Show confirmation
                selected_count = len(self.pending_transfers[user_id]["selected_accounts"])
                text = (
                    "⚠️ **Confirm Transfer**\n\n"
                    f"Transfer {selected_count} account(s) to:\n\n"
                    f"👤 Name: {target_name}\n"
                    f"🆔 ID: {target_user_id}\n"
                    f"📝 Username: {target_username}\n\n"
                    f"User mention: [{target_name}](tg://user?id={target_user_id})\n\n"
                    "⚠️ **WARNING:** This action cannot be undone!\n"
                    "All selected accounts will be permanently transferred."
                )
                
                buttons = [
                    [Button.inline("✅ Confirm Transfer", "transfer_confirm")],
                    [Button.inline("❌ Cancel", "transfer_cancel")]
                ]
                
                await event.reply(text, buttons=buttons)
                
            except Exception as e:
                logger.error(f"Target user parsing error: {e}")
                await event.reply(f"❌ Error: {str(e)}")
        
        @self.bot.on(events.CallbackQuery(pattern=r"^transfer_confirm$"))
        async def confirm_transfer(event):
            user_id = event.sender_id
            if user_id not in self.pending_transfers:
                await event.answer("❌ Session expired. Use /transfer again.")
                return
            
            transfer_data = self.pending_transfers[user_id]
            selected_accounts = transfer_data["selected_accounts"]
            target_user_id = transfer_data["target_user"]
            
            if not selected_accounts or not target_user_id:
                await event.answer("❌ Invalid transfer state!", alert=True)
                return
            
            await event.edit("⏳ Transferring accounts...")
            
            try:
                success_count = 0
                failed_accounts = []
                transferred_info = []
                
                for account_id in selected_accounts:
                    try:
                        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
                        if not account:
                            failed_accounts.append(account_id)
                            continue
                        
                        account_name = account.get('name', 'Unknown')
                        phone = account.get('phone', 'Unknown')
                        
                        # Get 2FA password if exists
                        twofa_password = None
                        if account.get('twofa_password'):
                            try:
                                from ..utils.data_encryption import decrypt_string
                                twofa_password = decrypt_string(account['twofa_password'])
                            except:
                                pass
                        
                        # Remove from original owner's client list (but don't disconnect session)
                        if user_id in self.bot_manager.user_clients:
                            for key in [account_name, phone, account.get('display_name')]:
                                if key and key in self.bot_manager.user_clients[user_id]:
                                    self.bot_manager.user_clients[user_id].pop(key, None)
                        
                        # Transfer ownership in database
                        result = await mongodb.db.accounts.update_one(
                            {"_id": ObjectId(account_id), "user_id": user_id},
                            {"$set": {"user_id": target_user_id}}
                        )
                        
                        if result.modified_count > 0:
                            success_count += 1
                            transferred_info.append({
                                'name': account_name,
                                'phone': phone,
                                'twofa': twofa_password
                            })
                        else:
                            failed_accounts.append(account_id)
                    except Exception as e:
                        logger.error(f"Failed to transfer account {account_id}: {e}")
                        failed_accounts.append(account_id)
                
                # Send detailed notification to recipient
                try:
                    target_entity = await self.bot.get_entity(target_user_id)
                    target_name = target_entity.first_name or "User"
                    
                    notification = (
                        f"🎉 **Account Transfer Received**\n\n"
                        f"You have received {success_count} account(s) from user {user_id}\n\n"
                        f"📋 **Account Details:**\n\n"
                    )
                    
                    for info in transferred_info:
                        notification += f"📱 **{info['name']}** ({info['phone']})\n"
                        if info['twofa']:
                            notification += f"🔐 2FA Password: `{info['twofa']}`\n"
                        else:
                            notification += f"🔓 2FA: Not set\n"
                        notification += "\n"
                    
                    notification += (
                        f"\n⚠️ **Important:**\n"
                        f"• Change 2FA passwords immediately for security\n"
                        f"• Use /accs to view your accounts\n"
                        f"• Accounts are now under your control"
                    )
                    
                    await self.bot.send_message(target_user_id, notification)
                except Exception as e:
                    logger.error(f"Failed to notify recipient: {e}")
                
                # Send result to sender
                result_text = (
                    f"✅ **Transfer Complete**\n\n"
                    f"Successfully transferred: {success_count}/{len(selected_accounts)} accounts\n"
                    f"Target: {target_name} (ID: {target_user_id})\n\n"
                )
                
                if failed_accounts:
                    result_text += f"❌ Failed: {len(failed_accounts)} accounts\n\n"
                
                result_text += (
                    f"🔒 **Your access has been removed**\n"
                    f"• All selected accounts are now owned by the recipient\n"
                    f"• 2FA passwords have been transferred\n"
                    f"• You no longer have access to these accounts\n"
                    f"• Sessions remain active (not disconnected)\n\n"
                    f"🔄 Use /accs to view your remaining accounts."
                )
                
                await event.edit(result_text)
                
                # Cleanup
                del self.pending_transfers[user_id]
                
            except Exception as e:
                logger.error(f"Transfer execution error: {e}")
                await event.edit(f"❌ Transfer failed: {str(e)}")ransfers:
                await event.answer("❌ Session expired. Use /transfer again.")
                return
            
            transfer_data = self.pending_transfers[user_id]
            selected_accounts = transfer_data["selected_accounts"]
            target_user_id = transfer_data["target_user"]
            
            if not selected_accounts or not target_user_id:
                await event.answer("❌ Invalid transfer state!", alert=True)
                return
            
            await event.edit("⏳ Transferring accounts...")
            
            try:
                success_count = 0
                failed_accounts = []
                transferred_info = []
                
                for account_id in selected_accounts:
                    try:
                        account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
                        if not account:
                            failed_accounts.append(account_id)
                            continue
                        
                        account_name = account.get('name', 'Unknown')
                        phone = account.get('phone', 'Unknown')
                        
                        # Get 2FA password if exists
                        twofa_password = None
                        if account.get('twofa_password'):
                            try:
                                from ..utils.data_encryption import decrypt_string
                                twofa_password = decrypt_string(account['twofa_password'])
                            except:
                                pass
                        
                        # Disconnect client from original owner
                        if user_id in self.bot_manager.user_clients:
                            for key in [account_name, phone, account.get('display_name')]:
                                if key and key in self.bot_manager.user_clients[user_id]:
                                    client = self.bot_manager.user_clients[user_id].pop(key, None)
                                    if client and hasattr(client, 'is_connected') and client.is_connected():
                                        try:
                                            await client.disconnect()
                                        except:
                                            pass
                        
                        # Transfer ownership in database
                        result = await mongodb.db.accounts.update_one(
                            {"_id": ObjectId(account_id), "user_id": user_id},
                            {"$set": {"user_id": target_user_id}}
                        )
                        
                        if result.modified_count > 0:
                            success_count += 1
                            transferred_info.append({
                                'name': account_name,
                                'phone': phone,
                                'twofa': twofa_password
                            })
                        else:
                            failed_accounts.append(account_id)
                    except Exception as e:
                        logger.error(f"Failed to transfer account {account_id}: {e}")
                        failed_accounts.append(account_id)
                
                # Send detailed notification to recipient
                try:
                    target_entity = await self.bot.get_entity(target_user_id)
                    target_name = target_entity.first_name or "User"
                    
                    notification = (
                        f"🎉 **Account Transfer Received**\n\n"
                        f"You have received {success_count} account(s) from user {user_id}\n\n"
                        f"📋 **Account Details:**\n\n"
                    )
                    
                    for info in transferred_info:
                        notification += f"📱 **{info['name']}** ({info['phone']})\n"
                        if info['twofa']:
                            notification += f"🔐 2FA Password: `{info['twofa']}`\n"
                        else:
                            notification += f"🔓 2FA: Not set\n"
                        notification += "\n"
                    
                    notification += (
                        f"\n⚠️ **Important:**\n"
                        f"• Change 2FA passwords immediately for security\n"
                        f"• Use /accs to view your accounts\n"
                        f"• Accounts are now under your control"
                    )
                    
                    await self.bot.send_message(target_user_id, notification)
                except Exception as e:
                    logger.error(f"Failed to notify recipient: {e}")
                
                # Send result to sender
                result_text = (
                    f"✅ **Transfer Complete**\n\n"
                    f"Successfully transferred: {success_count}/{len(selected_accounts)} accounts\n"
                    f"Target: {target_name} (ID: {target_user_id})\n\n"
                )
                
                if failed_accounts:
                    result_text += f"❌ Failed: {len(failed_accounts)} accounts\n\n"
                
                result_text += (
                    f"🔒 **Your access has been removed**\n"
                    f"• All selected accounts are now owned by the recipient\n"
                    f"• 2FA passwords have been transferred\n"
                    f"• You no longer have access to these accounts\n\n"
                    f"🔄 Use /accs to view your remaining accounts."
                )
                
                await event.edit(result_text)
                
                # Cleanup
                del self.pending_transfers[user_id]
                
            except Exception as e:
                logger.error(f"Transfer execution error: {e}")
                await event.edit(f"❌ Transfer failed: {str(e)}")ransfers:
                await event.answer("❌ Session expired. Use /transfer again.")
                return
            
            transfer_data = self.pending_transfers[user_id]
            selected_accounts = transfer_data["selected_accounts"]
            target_user_id = transfer_data["target_user"]
            
            if not selected_accounts or not target_user_id:
                await event.answer("❌ Invalid transfer state!", alert=True)
                return
            
            await event.edit("⏳ Transferring accounts...")
            
            try:
                success_count = 0
                failed_accounts = []
                
                for account_id in selected_accounts:
                    try:
                        result = await mongodb.db.accounts.update_one(
                            {"_id": ObjectId(account_id), "user_id": user_id},
                            {"$set": {"user_id": target_user_id}}
                        )
                        if result.modified_count > 0:
                            success_count += 1
                        else:
                            failed_accounts.append(account_id)
                    except Exception as e:
                        logger.error(f"Failed to transfer account {account_id}: {e}")
                        failed_accounts.append(account_id)
                
                # Notify target user
                try:
                    target_entity = await self.bot.get_entity(target_user_id)
                    target_name = target_entity.first_name or "User"
                    
                    notification = (
                        f"🎉 **Account Transfer Received**\n\n"
                        f"You have received {success_count} account(s) from user {user_id}\n\n"
                        f"Use /accs to view your accounts."
                    )
                    await self.bot.send_message(target_user_id, notification)
                except:
                    pass
                
                # Send result to sender
                result_text = (
                    f"✅ **Transfer Complete**\n\n"
                    f"Successfully transferred: {success_count}/{len(selected_accounts)} accounts\n"
                    f"Target: {target_name} (ID: {target_user_id})\n\n"
                )
                
                if failed_accounts:
                    result_text += f"❌ Failed: {len(failed_accounts)} accounts\n"
                
                result_text += "\n🔄 Use /accs to view your remaining accounts."
                
                await event.edit(result_text)
                
                # Cleanup
                del self.pending_transfers[user_id]
                
            except Exception as e:
                logger.error(f"Transfer execution error: {e}")
                await event.edit(f"❌ Transfer failed: {str(e)}")
    
    async def _update_selection_menu(self, event, user_id: int):
        """Update the account selection menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            selected = self.pending_transfers[user_id]["selected_accounts"]
            
            text = (
                "🔄 **Transfer Account Ownership**\n\n"
                f"📊 Total: {len(accounts)} | Selected: {len(selected)}\n\n"
                "Select accounts to transfer:\n"
                "✅ = Selected | ❌ = Not Selected"
            )
            
            buttons = []
            for account in accounts:
                display_name = account.get('name', 'Unknown')
                phone = account.get('phone', 'Unknown')
                is_selected = str(account['_id']) in selected
                icon = "✅" if is_selected else "❌"
                button_text = f"{icon} {display_name} ({phone})"
                buttons.append([Button.inline(button_text, f"transfer_toggle:{account['_id']}")])
            
            buttons.append([Button.inline("✅ Select All", "transfer_select_all")])
            buttons.append([Button.inline("❌ Deselect All", "transfer_deselect_all")])
            buttons.append([Button.inline("✔️ Done", "transfer_done")])
            buttons.append([Button.inline("🔙 Cancel", "transfer_cancel")])
            
            await event.edit(text, buttons=buttons)
            await event.answer()
        except Exception as e:
            logger.error(f"Update selection menu error: {e}")
            await event.answer("❌ Error updating menu")
