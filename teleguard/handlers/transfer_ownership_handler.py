"""Transfer Ownership Handler - Transfer accounts to another user"""

import logging

from bson import ObjectId
from telethon import Button, events

from ..core.mongo_database import mongodb

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
                accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                    None
                )
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
                accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                    None
                )
                if not accounts:
                    await event.reply("No accounts found to transfer.")
                    return

                self.pending_transfers[user_id] = {
                    "selected_accounts": [],
                    "target_user": None,
                }

                buttons = []
                for account in accounts:
                    name = account.get("name", "Unknown")
                    phone = account.get("phone", "Unknown")
                    buttons.append(
                        [
                            Button.inline(
                                f"Select {name} ({phone})",
                                f"transfer_toggle:{account['_id']}",
                            )
                        ]
                    )

                buttons.append([Button.inline("Select All", "transfer_select_all")])
                buttons.append([Button.inline("Done", "transfer_done")])
                buttons.append([Button.inline("Cancel", "transfer_cancel")])

                await event.reply(
                    f"Transfer Ownership\n\nYou have {
                        len(accounts)} account(s)\nSelect accounts to transfer:",
                    buttons=buttons,
                )
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

            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                None
            )
            self.pending_transfers[user_id]["selected_accounts"] = [
                str(acc["_id"]) for acc in accounts
            ]
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

            await event.edit(
                f"Selected: {
                    len(selected)} account(s)\n\nReply with user ID or username:"
            )
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
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                None
            )
            selected = self.pending_transfers[user_id]["selected_accounts"]

            buttons = []
            for account in accounts:
                name = account.get("name", "Unknown")
                phone = account.get("phone", "Unknown")
                icon = "✓" if str(account["_id"]) in selected else " "
                buttons.append(
                    [
                        Button.inline(
                            f"[{icon}] {name} ({phone})",
                            f"transfer_toggle:{account['_id']}",
                        )
                    ]
                )

            buttons.append([Button.inline("Select All", "transfer_select_all")])
            buttons.append([Button.inline("Done", "transfer_done")])
            buttons.append([Button.inline("Cancel", "transfer_cancel")])

            await event.edit(
                f"Selected: {len(selected)}/{len(accounts)}\n\nSelect accounts:",
                buttons=buttons,
            )
            await event.answer()
        except Exception as e:
            logger.error(f"Update menu error: {e}")

    async def process_user_input(self, event, user_id: int, message: str):
        """Process user ID/username input for transfer or co-owner"""
        try:
            logger.info(
                f"Transfer handler processing input from user {user_id}: {message}"
            )
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
            if not selected:
                await event.reply("❌ No accounts selected!")
                del self.pending_transfers[user_id]
                return
            await event.reply(f"🔄 Processing transfer to user {target_input}...")
            target_user_id = await self._parse_user_id(target_input)
            if not target_user_id or not await self._verify_target_user(target_user_id, target_input, event):
                return
            transferred = await self._transfer_accounts(user_id, selected, target_user_id)
            if not transferred:
                await event.reply("❌ Failed to transfer accounts. Please try again.")
                del self.pending_transfers[user_id]
                return
            await self._notify_transfer_complete(event, user_id, target_input, target_user_id, transferred)
            del self.pending_transfers[user_id]
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
            target_user = await mongodb.db.users.find_one(
                {"telegram_id": target_user_id}
            )
            if not target_user:
                await event.reply(
                    f"User {target_input} hasn't started the bot. They must use /start first."
                )
                return

            # Add to co-owners list
            await mongodb.db.users.update_one(
                {"telegram_id": user_id}, {"$addToSet": {"co_owners": target_user_id}}
            )

            # Share all current accounts
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                None
            )
            from ..utils.crypto_utils import DataEncryption as _DE

            for account in accounts:
                await mongodb.db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$addToSet": {"co_owners": target_user_id}},
                )

            # Notify both users
            await event.reply(
                f"✅ Added {target_input} as co-owner\n\nThey now have access to all {
                    len(accounts)} account(s)"
            )

            # Notify co-owner
            msg = f"👥 **Co-Owner Access Granted**\n\nYou now have co-owner access to {
                len(accounts)} account(s):\n\n"
            for acc in accounts:
                name = acc.get("name", "Unknown")
                phone = acc.get("phone", "Unknown")
                msg += f"• {name} ({phone})\n"
                if acc.get("twofa_password"):
                    try:
                        twofa = decrypt_string(acc["twofa_password"])
                        msg += f"  🔐 2FA: `{twofa}`\n"
                    except BaseException:
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
            username = input_str.replace("@", "")
            try:
                entity = await self.bot.get_entity(username)
                return entity.id
            except BaseException:
                return None
        except BaseException:
            return None

    async def _verify_target_user(self, target_user_id: int, target_input: str, event) -> bool:
        """Verify target user exists in database"""
        if not target_user_id:
            await event.reply("❌ Invalid user ID or username. Try again:")
            return False
        target_user = await mongodb.db.users.find_one({"telegram_id": target_user_id})
        if not target_user:
            await event.reply(f"❌ User {target_input} hasn't started the bot. They must use /start first.")
            return False
        return True

    async def _transfer_accounts(self, user_id: int, selected: list, target_user_id: int) -> list:
        """Transfer selected accounts to target user"""
        from ..utils.crypto_utils import DataEncryption as _DE
        transferred = []
        for account_id in selected:
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                continue
            twofa_password = None
            if account.get("twofa_password"):
                try:
                    twofa_password = _DE.decrypt_field(account["twofa_password"])
                except Exception:
                    pass
            
            account_name = account.get("name") or account.get("phone")
            
            # 1. If client exists - unregister OTP handler, disconnect and remove client from original owner
            client = None
            if user_id in self.bot_manager.user_clients and account_name in self.bot_manager.user_clients[user_id]:
                client = self.bot_manager.user_clients[user_id][account_name]
                # Unregister OTP handler specifically for this client to avoid orphaned handlers
                try:
                    if hasattr(self.bot_manager, 'protection_manager') and hasattr(self.bot_manager.protection_manager, 'unregister_handler_for_client'):
                        try:
                            self.bot_manager.protection_manager.unregister_handler_for_client(user_id, account_name, client)
                        except Exception as unregister_error:
                            logger.error(f"Error unregistering OTP handler for {user_id}:{account_name}: {unregister_error}")
                except Exception:
                    pass
                try:
                    if client and hasattr(client, 'disconnect'):
                        await client.disconnect()
                        logger.info(f"Disconnected client for {account_name} from user {user_id}")
                except Exception as e:
                    logger.error(f"Error disconnecting client: {e}")
                self.bot_manager.user_clients[user_id].pop(account_name, None)
            
            # 3. Remove from session protection
            try:
                from ..utils.session_protection import session_protection
                session_id = f"{user_id}_{account_name}"
                session_protection.unregister_session(session_id)
                logger.info(f"Unregistered session protection for {session_id}")
            except Exception as e:
                logger.error(f"Error unregistering session: {e}")
            
            # 4. Remove from session monitor
            if hasattr(self.bot_manager, 'session_monitor') and self.bot_manager.session_monitor:
                try:
                    self.bot_manager.session_monitor.remove_client_from_monitor(user_id, account_name)
                    logger.info(f"Removed from session monitor: {account_name}")
                except Exception as e:
                    logger.error(f"Error removing from session monitor: {e}")
            
            # 5. Update account ownership in database
            await mongodb.db.accounts.update_one(
                {"_id": ObjectId(account_id)}, 
                {
                    "$set": {"user_id": target_user_id, "is_active": False},
                    "$unset": {"co_owners": ""}
                }
            )
            
            transferred.append({"name": account.get("name", "Unknown"), "phone": account.get("phone", "Unknown"), "twofa": twofa_password})
        
        # 6. Re-register OTP handlers to update all references
        if hasattr(self.bot_manager, 'protection_manager'):
            try:
                self.bot_manager.protection_manager.register_handlers()
                logger.info("Re-registered OTP handlers after transfer")
            except Exception as e:
                logger.error(f"Error re-registering OTP handlers: {e}")
        
        return transferred

    async def _notify_transfer_complete(self, event, user_id: int, target_input: str, target_user_id: int, transferred: list):
        """Notify both sender and recipient of transfer"""
        sender_msg = f"✅ **Transfer Complete!**\n\nSuccessfully transferred {len(transferred)} account(s) to user {target_input}\n\n**Transferred Accounts:**\n"
        for acc in transferred:
            sender_msg += f"• {acc['name']} ({acc['phone']})\n"
        sender_msg += "\n🔔 Recipient has been notified\n⚠️ Your access to these accounts has been completely removed\n🔒 All sessions and handlers have been disconnected"
        await event.reply(sender_msg)
        recipient_msg = f"📱 **Account Transfer Received**\n\nYou received {len(transferred)} account(s):\n\n"
        for acc in transferred:
            recipient_msg += f"• {acc['name']} ({acc['phone']})\n"
            if acc["twofa"]:
                recipient_msg += f"  🔐 2FA: `{acc['twofa']}`\n"
        recipient_msg += "\n✅ Use /accs to view your accounts\n🔄 Use /reconnect to connect the accounts\n🛡️ OTP protection will work after reconnection\n⚠️ Change 2FA passwords for security"
        try:
            await self.bot.send_message(target_user_id, recipient_msg)
        except Exception as notify_error:
            await event.reply(f"⚠️ Transfer complete but failed to notify recipient: {notify_error}")
