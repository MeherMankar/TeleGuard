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
        self.pending_transfers = {}
        self.pending_coowner = {}
    
    def register_handlers(self):
        """Register transfer ownership and co-owner commands"""
        
        @self.bot.on(events.NewMessage(pattern=r"/addcoowner"))
        async def addcoowner_command(event):
            user_id = event.sender_id
            try:
                accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
                if not accounts:
                    await event.reply("No accounts found. Add accounts first.")
                    return
                
                self.pending_coowner[user_id] = None
                await event.reply(
                    f"Add Co-Owner\n\n"
                    f"You have {len(accounts)} account(s)\n\n"
                    f"Reply with user ID or username:\n"
                    f"Examples: 123456789 or @username\n\n"
                    f"Note: Co-owner will have access to ALL current and future accounts!"
                )
            except Exception as e:
                logger.error(f"Add co-owner error: {e}")
                await event.reply(f"Error: {str(e)}")
        
        @self.bot.on(events.NewMessage(pattern=r"/transfer"))
        async def transfer_command(event):
            user_id = event.sender_id
            try:
                accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
                if not accounts:
                    await event.reply("No accounts found to transfer.")
                    return
                
                self.pending_transfers[user_id] = {"selected_accounts": [], "target_user": None}
                
                buttons = []
                for account in accounts:
                    name = account.get('name', 'Unknown')
                    phone = account.get('phone', 'Unknown')
                    buttons.append([Button.inline(f"Select {name} ({phone})", f"transfer_toggle:{account['_id']}")])
                
                buttons.append([Button.inline("Select All", "transfer_select_all")])
                buttons.append([Button.inline("Done", "transfer_done")])
                buttons.append([Button.inline("Cancel", "transfer_cancel")])
                
                await event.reply(f"Transfer Ownership\n\nYou have {len(accounts)} account(s)\nSelect accounts to transfer:", buttons=buttons)
            except Exception as e:
                logger.error(f"Transfer error: {e}")
                await event.reply(f"Error: {str(e)}")
        
        @self.bot.on(events.CallbackQuery(pattern=r"^transfer_toggle:(.+)$"))
        async def toggle_account(event):
            user_id = event.sender_id
            account_id = event.pattern_match.group(1).decode()
            
            if user_id not in self.pending_transfers:
                await event.answer("Session expired. Use /transfer again.")
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
                await event.answer("Session expired.")
                return
            
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            self.pending_transfers[user_id]["selected_accounts"] = [str(acc['_id']) for acc in accounts]
            await self._update_selection_menu(event, user_id)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^transfer_done$"))
        async def done_selection(event):
            user_id = event.sender_id
            if user_id not in self.pending_transfers:
                await event.answer("Session expired.")
                return
            
            selected = self.pending_transfers[user_id]["selected_accounts"]
            if not selected:
                await event.answer("No accounts selected!", alert=True)
                return
            
            await event.edit(f"Selected: {len(selected)} account(s)\n\nReply with user ID or username:")
            await event.answer("Reply with user ID or username")
        
        @self.bot.on(events.CallbackQuery(pattern=r"^transfer_cancel$"))
        async def cancel_transfer(event):
            user_id = event.sender_id
            if user_id in self.pending_transfers:
                del self.pending_transfers[user_id]
            await event.edit("Transfer cancelled.")
        
        @self.bot.on(events.CallbackQuery(pattern=r"^coowner_cancel$"))
        async def cancel_coowner(event):
            user_id = event.sender_id
            if user_id in self.pending_coowner:
                del self.pending_coowner[user_id]
            await event.edit("Co-owner addition cancelled.")
    
    async def _update_selection_menu(self, event, user_id: int):
        """Update account selection menu"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            selected = self.pending_transfers[user_id]["selected_accounts"]
            
            buttons = []
            for account in accounts:
                name = account.get('name', 'Unknown')
                phone = account.get('phone', 'Unknown')
                icon = "✓" if str(account['_id']) in selected else " "
                buttons.append([Button.inline(f"[{icon}] {name} ({phone})", f"transfer_toggle:{account['_id']}")])
            
            buttons.append([Button.inline("Select All", "transfer_select_all")])
            buttons.append([Button.inline("Done", "transfer_done")])
            buttons.append([Button.inline("Cancel", "transfer_cancel")])
            
            await event.edit(f"Selected: {len(selected)}/{len(accounts)}\n\nSelect accounts:", buttons=buttons)
            await event.answer()
        except Exception as e:
            logger.error(f"Update menu error: {e}")
    
    async def process_user_input(self, event, user_id: int, message: str):
        """Process user ID/username input for transfer or co-owner"""
        try:
            logger.info(f"Transfer handler processing input from user {user_id}: {message}")
            logger.info(f"Pending transfers: {list(self.pending_transfers.keys())}")
            logger.info(f"Pending coowners: {list(self.pending_coowner.keys())}")
            
            # Check if this is for transfer or co-owner
            if user_id in self.pending_transfers:
                logger.info(f"Processing transfer for user {user_id}")
                await self._process_transfer(event, user_id, message)
            elif user_id in self.pending_coowner:
                logger.info(f"Processing co-owner for user {user_id}")
                await self._process_coowner(event, user_id, message)
            else:
                logger.warning(f"User {user_id} not in pending transfers or coowners")
        except Exception as e:
            logger.error(f"Process user input error: {e}", exc_info=True)
            await event.reply(f"Error: {str(e)}")
    
    async def _process_transfer(self, event, user_id: int, target_input: str):
        """Process transfer ownership"""
        try:
            logger.info(f"[TRANSFER] Starting transfer process for user {user_id}, target: {target_input}")
            selected = self.pending_transfers[user_id]["selected_accounts"]
            logger.info(f"[TRANSFER] Selected accounts: {selected}")
            if not selected:
                await event.reply("❌ No accounts selected!")
                del self.pending_transfers[user_id]
                return
            
            # Send processing message
            await event.reply(f"🔄 Processing transfer to user {target_input}...")
            
            # Parse target user
            logger.info(f"[TRANSFER] Parsing target user: {target_input}")
            target_user_id = await self._parse_user_id(target_input)
            logger.info(f"[TRANSFER] Parsed target user ID: {target_user_id}")
            
            if not target_user_id:
                await event.reply("❌ Invalid user ID or username. Try again:")
                return
            
            # Verify target user exists in database
            logger.info(f"[TRANSFER] Checking if target user {target_user_id} exists in database")
            target_user = await mongodb.db.users.find_one({"telegram_id": target_user_id})
            logger.info(f"[TRANSFER] Target user found: {target_user is not None}")
            
            if not target_user:
                await event.reply(f"❌ User {target_input} hasn't started the bot. They must use /start first.")
                return
            
            # Transfer accounts
            from ..utils.data_encryption import decrypt_string
            transferred = []
            
            logger.info(f"[TRANSFER] Starting to transfer {len(selected)} accounts")
            for i, account_id in enumerate(selected, 1):
                logger.info(f"[TRANSFER] Processing account {i}/{len(selected)}: {account_id}")
                account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
                
                if not account:
                    logger.warning(f"[TRANSFER] Account {account_id} not found or doesn't belong to user {user_id}")
                    continue
                
                logger.info(f"[TRANSFER] Found account: {account.get('name')} ({account.get('phone')})")
                
                # Get 2FA password if exists
                twofa_password = None
                if account.get('twofa_password'):
                    try:
                        twofa_password = decrypt_string(account['twofa_password'])
                        logger.info(f"[TRANSFER] Decrypted 2FA password for account {account_id}")
                    except Exception as decrypt_err:
                        logger.error(f"[TRANSFER] Failed to decrypt 2FA: {decrypt_err}")
                
                # Update ownership
                logger.info(f"[TRANSFER] Updating ownership of account {account_id} to user {target_user_id}")
                update_result = await mongodb.db.accounts.update_one(
                    {"_id": ObjectId(account_id)},
                    {"$set": {"user_id": target_user_id}}
                )
                logger.info(f"[TRANSFER] Update result - matched: {update_result.matched_count}, modified: {update_result.modified_count}")
                
                # Remove from original owner's client list
                if user_id in self.bot_manager.user_clients:
                    account_name = account.get('name') or account.get('phone')
                    self.bot_manager.user_clients[user_id].pop(account_name, None)
                    logger.info(f"[TRANSFER] Removed {account_name} from user {user_id}'s client list")
                
                transferred.append({
                    "name": account.get('name', 'Unknown'),
                    "phone": account.get('phone', 'Unknown'),
                    "twofa": twofa_password
                })
            
            logger.info(f"[TRANSFER] Successfully transferred {len(transferred)} accounts")
            
            if not transferred:
                logger.error(f"[TRANSFER] No accounts were transferred!")
                await event.reply("❌ Failed to transfer accounts. Please try again.")
                del self.pending_transfers[user_id]
                return
            
            # Notify sender
            logger.info(f"[TRANSFER] Notifying sender {user_id}")
            sender_msg = (
                f"✅ **Transfer Complete!**\n\n"
                f"Successfully transferred {len(transferred)} account(s) to user {target_input}\n\n"
                f"**Transferred Accounts:**\n"
            )
            for acc in transferred:
                sender_msg += f"• {acc['name']} ({acc['phone']})\n"
            sender_msg += f"\n🔔 Recipient has been notified"
            
            await event.reply(sender_msg)
            logger.info(f"[TRANSFER] Sender notification sent")
            
            # Notify recipient
            logger.info(f"[TRANSFER] Notifying recipient {target_user_id}")
            recipient_msg = f"📱 **Account Transfer Received**\n\nYou received {len(transferred)} account(s):\n\n"
            for acc in transferred:
                recipient_msg += f"• {acc['name']} ({acc['phone']})\n"
                if acc['twofa']:
                    recipient_msg += f"  🔐 2FA: `{acc['twofa']}`\n"
            recipient_msg += "\n✅ Use /accs to view your accounts\n⚠️ Change 2FA passwords for security"
            
            try:
                await self.bot.send_message(target_user_id, recipient_msg)
                logger.info(f"[TRANSFER] Recipient {target_user_id} notified successfully")
            except Exception as notify_error:
                logger.error(f"[TRANSFER] Failed to notify recipient: {notify_error}")
                await event.reply(f"⚠️ Transfer complete but failed to notify recipient: {notify_error}")
            
            logger.info(f"[TRANSFER] Cleaning up pending transfer for user {user_id}")
            del self.pending_transfers[user_id]
            logger.info(f"[TRANSFER] Transfer process completed successfully")
            
        except Exception as e:
            logger.error(f"[TRANSFER] Transfer error for user {user_id}: {e}", exc_info=True)
            await event.reply(f"❌ Transfer failed: {str(e)}\n\nPlease try /transfer again.")
            if user_id in self.pending_transfers:
                del self.pending_transfers[user_id]
    
    async def _process_coowner(self, event, user_id: int, target_input: str):
        """Process add co-owner"""
        try:
            # Parse target user
            target_user_id = await self._parse_user_id(target_input)
            if not target_user_id:
                await event.reply("Invalid user ID or username. Try again:")
                return
            
            # Verify target user exists
            target_user = await mongodb.db.users.find_one({"telegram_id": target_user_id})
            if not target_user:
                await event.reply(f"User {target_input} hasn't started the bot. They must use /start first.")
                return
            
            # Add to co-owners list
            await mongodb.db.users.update_one(
                {"telegram_id": user_id},
                {"$addToSet": {"co_owners": target_user_id}}
            )
            
            # Share all current accounts
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            from ..utils.data_encryption import decrypt_string
            
            for account in accounts:
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$addToSet": {"co_owners": target_user_id}}
                )
            
            # Notify both users
            await event.reply(f"✅ Added {target_input} as co-owner\n\nThey now have access to all {len(accounts)} account(s)")
            
            # Notify co-owner
            msg = f"👥 **Co-Owner Access Granted**\n\nYou now have co-owner access to {len(accounts)} account(s):\n\n"
            for acc in accounts:
                name = acc.get('name', 'Unknown')
                phone = acc.get('phone', 'Unknown')
                msg += f"• {name} ({phone})\n"
                if acc.get('twofa_password'):
                    try:
                        twofa = decrypt_string(acc['twofa_password'])
                        msg += f"  🔐 2FA: `{twofa}`\n"
                    except:
                        pass
            msg += "\nYou'll automatically get access to all future accounts too!"
            
            await self.bot.send_message(target_user_id, msg)
            
            del self.pending_coowner[user_id]
            
        except Exception as e:
            logger.error(f"Co-owner error: {e}")
            await event.reply(f"Failed to add co-owner: {str(e)}")
    
    async def _parse_user_id(self, input_str: str) -> int:
        """Parse user ID from input (ID or username)"""
        try:
            # Try as numeric ID
            if input_str.isdigit():
                return int(input_str)
            
            # Try as username
            username = input_str.replace('@', '')
            try:
                entity = await self.bot.get_entity(username)
                return entity.id
            except:
                return None
        except:
            return None
