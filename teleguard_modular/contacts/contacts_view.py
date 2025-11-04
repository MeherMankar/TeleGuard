"""Split from view_contacts.py - contacts_view"""
"""Contact management handler with interactive buttons"""
import logging
import csv
import io
from telethon import events
from telethon.tl.custom import Button
from ..core.contact_db import ContactDB
from ..core.contact_models import Contact, ContactGroup
logger = logging.getLogger(__name__)
class ContactHandler:
    """Contact management with interactive UI"""
    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager
        self.pending_actions = {}  # Track user input states
    def register_handlers(self):
        """Register all contact handlers"""
        @self.bot.on(events.NewMessage(pattern=r"^/contacts$"))
        async def contacts_menu(event):
            """Main contacts menu"""
            user_id = event.sender_id
            account = await self._get_user_account(user_id)
            if not account:
                await event.reply("❌ No active account found.")
                return
            buttons = [
                [Button.inline("👥 View All Contacts", "contacts:list")],
                [Button.inline("➕ Add Contact", "contacts:add"), Button.inline("🔍 Search", "contacts:search")],
                [Button.inline("📁 Groups", "contacts:groups"), Button.inline("🏷️ Tags", "contacts:tags")],
                [Button.inline("📤 Export", "contacts:export"), Button.inline("📥 Import", "contacts:import")],
                [Button.inline("🔄 Sync", "contacts:sync")]
            ]
            contacts = await ContactDB.get_all_contacts(account, limit=5)
            count = len(contacts)
            await event.reply(
                f"📱 **Contact Management**\n\n"
                f"📊 Total Contacts: {count}\n"
                f"🔧 Account: {account}\n\n"
                f"Choose an option:",
                buttons=buttons
            )
        @self.bot.on(events.CallbackQuery(pattern=r"^contacts:"))
        async def handle_contacts_callback(event):
            """Handle contact button callbacks"""
            user_id = event.sender_id
            data = event.data.decode()
            try:
                if data == "contacts:list":
                    await self._show_contacts_list(event, user_id)
                elif data == "contacts:add":
                    await self._start_add_contact(event, user_id)
                elif data == "contacts:search":
                    await self._start_search(event, user_id)
                elif data == "contacts:groups":
                    await self._show_groups(event, user_id)
                elif data == "contacts:tags":
                    await self._show_tags(event, user_id)
                elif data == "contacts:export":
                    await self._export_contacts(event, user_id)
                elif data == "contacts:import":
                    await self._start_import(event, user_id)
                elif data == "contacts:sync":
                    await self._show_sync_menu(event, user_id)
                elif data.startswith("contact:view:"):
                    contact_id = int(data.split(":")[2])
                    await self._view_contact(event, user_id, contact_id)
                elif data.startswith("contact:edit:"):
                    contact_id = int(data.split(":")[2])
                    await self._edit_contact_menu(event, user_id, contact_id)
                elif data.startswith("contact:delete:"):
                    contact_id = int(data.split(":")[2])
                    await self._delete_contact(event, user_id, contact_id)
                elif data.startswith("contact:blacklist:"):
                    contact_id = int(data.split(":")[2])
                    await self._toggle_blacklist(event, user_id, contact_id)
                elif data.startswith("contact:whitelist:"):
                    contact_id = int(data.split(":")[2])
                    await self._toggle_whitelist(event, user_id, contact_id)
                elif data.startswith("contact:delete_confirm:"):
                    contact_id = int(data.split(":")[2])
                    await self._confirm_delete_contact(event, user_id, contact_id)
                elif data.startswith("contact:add_notes:"):
                    contact_id = int(data.split(":")[2])
                    await self._start_add_notes(event, user_id, contact_id)
                elif data.startswith("contact:add_tags:"):
                    contact_id = int(data.split(":")[2])
                    await self._start_add_tags(event, user_id, contact_id)
                elif data.startswith("tag:view:"):
                    tag = data.split(":", 2)[2]
                    await self._view_tag_contacts(event, user_id, tag)
                elif data.startswith("group:view:"):
                    group_name = data.split(":", 2)[2]
                    await self._view_group(event, user_id, group_name)
                elif data == "group:create":
                    await self._start_create_group(event, user_id)
                elif data == "contacts:main":
                    await self._show_main_menu(event, user_id)
                elif data.startswith("export_acc:"):
                    account_idx = int(data.split(":")[1])
                    await self._process_export(event, user_id, account_idx)
                elif data.startswith("sync:"):
                    sync_type = data.split(":")[1]
                    await self._handle_sync(event, user_id, sync_type)
            except Exception as e:
                logger.error(f"Contact callback error: {e}")
                await event.answer("❌ Error processing request")
        @self.bot.on(events.NewMessage(func=lambda e: e.sender_id in self.pending_actions and not e.message.text.startswith('/') and self.pending_actions.get(e.sender_id, {}).get('type') in ['add_contact', 'search', 'add_notes', 'add_tags', 'import']))
        async def handle_input(event):
            """Handle text input, file uploads, and forwarded messages for contact operations"""
            user_id = event.sender_id
            action = self.pending_actions.get(user_id)
            if not action or action.get('type') not in ['add_contact', 'search', 'add_notes', 'add_tags', 'import']:
                return
            if action['type'] == 'import' and event.message.document:
                await self._process_import_file(event, user_id)
                return
            if event.message.forward:
                if action['type'] == 'add_contact':
                    await self._process_forwarded_contact(event, user_id, action)
                    return
            text = event.message.text.strip() if event.message.text else ""
            if text.lower() in ['cancel', '/cancel']:
                del self.pending_actions[user_id]
                await event.reply("❌ Operation cancelled", buttons=[[Button.inline("🔙 Back", "contacts:main")]])
                return
            try:
                if action['type'] == 'add_contact':
                    await self._process_add_contact(event, user_id, text, action)
                elif action['type'] == 'search':
                    await self._process_search(event, user_id, text)
                elif action['type'] == 'add_notes':
                    await self._process_add_notes(event, user_id, text, action)
                elif action['type'] == 'add_tags':
                    await self._process_add_tags(event, user_id, text, action)
            except Exception as e:
                logger.error(f"Input error: {e}")
                await event.reply("❌ Error processing input")
    async def _get_user_account(self, user_id: int) -> str:
        """Get user's active account"""
        try:
            user_clients = self.bot_manager.user_clients.get(user_id, {})
            if user_clients:
                return list(user_clients.keys())[0]
            return ""
        except Exception:
            return ""
    async def _show_contacts_list(self, event, user_id: int):
        """Show paginated contacts list"""
        from ..core.mongo_database import mongodb
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
        if not accounts:
            await event.edit("👥 **All Contacts**\n\n❌ No accounts found.", buttons=[[Button.inline("🔙 Back", "contacts:main")]])
            return
        all_contacts = []
        total_contacts = 0
        for account in accounts:
            if not account.get("is_active", False):
                continue
            try:
                if (user_id in self.bot_manager.user_clients and 
                    account['name'] in self.bot_manager.user_clients[user_id]):
                    client = self.bot_manager.user_clients[user_id][account['name']]
                    if client and client.is_connected():
                        from telethon.tl.functions.contacts import GetContactsRequest
                        from telethon.tl.types import User
                        result = await client(GetContactsRequest(hash=0))
                        account_contacts = 0
                        for user in result.users[:10]:  # Limit to first 10 per account
                            if isinstance(user, User) and not user.bot:
                                name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
                                username = f"@{user.username}" if user.username else "No username"
                                phone = user.phone or "No phone"
                                all_contacts.append({
                                    'name': name,
                                    'username': username,
                                    'phone': phone,
                                    'account': account['name'],
                                    'user_id': user.id
                                })
                                account_contacts += 1
                        total_contacts += len([u for u in result.users if isinstance(u, User) and not u.bot])
            except Exception as e:
                logger.error(f"Error getting contacts for {account['name']}: {e}")
                continue
        if not all_contacts:
            await event.edit("👥 **All Contacts**\n\n💭 No contacts found in active accounts.\n\nMake sure accounts are connected and have contacts.", buttons=[[Button.inline("🔙 Back", "contacts:main")]])
            return
        text = f"👥 **All Contacts** (Showing {len(all_contacts)} of {total_contacts})\n\n"
        buttons = []
        for i, contact in enumerate(all_contacts[:8], 1):  # Show max 8 contacts
            text += f"{i}. **{contact['name']}**\n   {contact['username']} | {contact['phone']}\n   Account: {contact['account']}\n\n"
        buttons.append([Button.inline("🔙 Back", "contacts:main")])
        await event.edit(text, buttons=buttons)
    async def _start_add_contact(self, event, user_id: int):
        """Start add contact process"""
        self.pending_actions[user_id] = {'type': 'add_contact', 'step': 'user_id'}
        await event.edit(
            "➕ **Add New Contact**\n\n"
            "Send the user ID, username (@username), phone number, or **forward a message** from the user:\n\n"
            "📝 Examples:\n"
            "• `123456789` (user ID)\n"
            "• `@username`\n"
            "• `+1234567890` (phone number)\n"
            "• `+91 97996 59003` (phone with spaces)\n"
            "• Forward any message from the user\n\n"
            "Type 'cancel' to abort",
            buttons=[[Button.inline("❌ Cancel", "contacts:main")]]
        )
    async def _process_forwarded_contact(self, event, user_id: int, action: dict):
        """Process forwarded message to add contact"""
        account = await self._get_user_account(user_id)
        try:
            forward_info = event.message.forward
            if hasattr(forward_info, 'from_id') and forward_info.from_id:
                contact_user_id = forward_info.from_id.user_id
                # Try to get user info
                client = self._get_user_client(user_id)
                if client:
                    try:
                        user_entity = await client.get_entity(contact_user_id)
                        first_name = user_entity.first_name or f"User_{contact_user_id}"
                        last_name = user_entity.last_name
                        username = user_entity.username
                    except Exception:
                        first_name = f"User_{contact_user_id}"
                        last_name = None
                        username = None
                else:
                    first_name = f"User_{contact_user_id}"
                    last_name = None
                    username = None
                existing = await ContactDB.get_contact(contact_user_id, account)
                if existing:
                    await event.reply("⚠️ Contact already exists!")
                    return
                contact = Contact(
                    user_id=contact_user_id,
                    first_name=first_name,
                    last_name=last_name,
                    username=username,
                    managed_by_account=account
                )
                success = await ContactDB.add_contact(contact)
                if success:
                    del self.pending_actions[user_id]
                    buttons = [
                        [Button.inline("👤 View Contact", f"contact:view:{contact_user_id}")],
                        [Button.inline("🔙 Back", "contacts:main")]
                    ]
                    await event.reply(f"✅ Contact added from forwarded message: {first_name}", buttons=buttons)
                else:
                    await event.reply("❌ Failed to add contact")
            else:
                await event.reply("❌ Cannot extract user info from forwarded message")
        except Exception as e:
            logger.error(f"Forwarded contact error: {e}")
            await event.reply("❌ Error processing forwarded message")
    async def _process_add_contact(self, event, user_id: int, text: str, action: dict):
        """Process add contact input"""
        account = await self._get_user_account(user_id)
        try:
            # Parse user input
            if text.startswith('@'):
                username = text[1:]
                # Try to get user info from username
                try:
                    client = self._get_user_client(user_id)
                    if client:
                        user_entity = await client.get_entity(username)
                        contact_user_id = user_entity.id
                        first_name = user_entity.first_name or username
                        last_name = user_entity.last_name
                    else:
                        await event.reply("❌ No active client found")
                        return
                except Exception:
                    await event.reply("❌ User not found")
                    return
            elif text.startswith('+') or (text.replace(' ', '').replace('-', '').isdigit() and len(text.replace(' ', '').replace('-', '')) > 7):
                phone = text.replace(' ', '').replace('-', '')
                try:
                    client = self._get_user_client(user_id)
                    if client:
                        # Try to resolve phone number to user
                        from telethon.tl.functions.contacts import ResolvePhoneRequest
                        try:
                            result = await client(ResolvePhoneRequest(phone=phone))
                            if result.users:
                                user_entity = result.users[0]
                                contact_user_id = user_entity.id
                                first_name = user_entity.first_name or f"Contact_{phone}"
                                last_name = user_entity.last_name
                                username = user_entity.username
                            else:
                                await event.reply("❌ Phone number not found in Telegram")
                                return
                        except Exception:
                            # If phone resolution fails, try importing the contact first
                            from telethon.tl.functions.contacts import ImportContactsRequest
                            from telethon.tl.types import InputPhoneContact
                            contact_to_add = InputPhoneContact(
                                client_id=0,
                                phone=phone,
                                first_name=f"Contact_{phone[-4:]}",
                                last_name=""
                            )
                            try:
                                import_result = await client(ImportContactsRequest([contact_to_add]))
                                if import_result.users:
                                    user_entity = import_result.users[0]
                                    contact_user_id = user_entity.id
                                    first_name = user_entity.first_name or f"Contact_{phone}"
                                    last_name = user_entity.last_name
                                    username = user_entity.username
                                else:
                                    await event.reply("❌ Could not add contact with this phone number")
                                    return
                            except Exception as e:
                                await event.reply(f"❌ Failed to import contact: Phone number may not be registered on Telegram")
                                return
                    else:
                        await event.reply("❌ No active client found")
                        return
                except Exception as e:
                    await event.reply("❌ Error processing phone number")
                    return
            else:
                try:
                    contact_user_id = int(text)
                    first_name = f"User_{contact_user_id}"
                    last_name = None
                    username = None
                except ValueError:
                    await event.reply("❌ Invalid input. Send a user ID, @username, or phone number (+1234567890)")
                    return
            existing = await ContactDB.get_contact(contact_user_id, account)
            if existing:
                await event.reply("⚠️ Contact already exists!")
                return
            contact = Contact(
                user_id=contact_user_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                managed_by_account=account
            )
            success = await ContactDB.add_contact(contact)
            if success:
                del self.pending_actions[user_id]
                buttons = [
                    [Button.inline("👤 View Contact", f"contact:view:{contact_user_id}")],
                    [Button.inline("🔙 Back", "contacts:main")]
                ]
                await event.reply(f"✅ Contact added: {first_name}", buttons=buttons)
            else:
                await event.reply("❌ Failed to add contact")
        except Exception as e:
            logger.error(f"Add contact error: {e}")
            await event.reply("❌ Error adding contact")
    async def _view_contact(self, event, user_id: int, contact_id: int):
        """View contact details"""
        account = await self._get_user_account(user_id)
        contact = await ContactDB.get_contact(contact_id, account)
        if not contact:
            await event.answer("Contact not found")
            return
        name = f"{contact.first_name} {contact.last_name or ''}".strip()
        text = f"👤 **{name}**\n\n"
        text += f"🆔 ID: `{contact.user_id}`\n"
        if contact.username:
            text += f"👤 Username: @{contact.username}\n"
        if contact.phone:
            text += f"📞 Phone: {contact.phone}\n"
        if contact.tags:
            text += f"🏷️ Tags: {', '.join(contact.tags)}\n"
        if contact.notes:
            text += f"📝 Notes: {contact.notes}\n"
        status = []
        if contact.is_blacklisted:
            status.append("🚫 Blacklisted")
        if contact.is_whitelisted:
            status.append("✅ Whitelisted")
        if status:
            text += f"\n🔒 Status: {', '.join(status)}"
        buttons = [
            [Button.inline("✏️ Edit", f"contact:edit:{contact_id}"), Button.inline("🗑️ Delete", f"contact:delete:{contact_id}")],
            [Button.inline("🚫 Blacklist", f"contact:blacklist:{contact_id}"), Button.inline("✅ Whitelist", f"contact:whitelist:{contact_id}")],
            [Button.inline("🔙 Back", "contacts:list")]
        ]
        await event.edit(text, buttons=buttons)
    async def _start_search(self, event, user_id: int):
        """Start contact search"""
        self.pending_actions[user_id] = {'type': 'search'}
        await event.edit(
            "🔍 **Search Contacts**\n\n"
            "Send a name or username to search:\n\n"
            "Type 'cancel' to abort",
            buttons=[[Button.inline("❌ Cancel", "contacts:main")]]
        )
    async def _process_search(self, event, user_id: int, query: str):
        """Process search query"""
        account = await self._get_user_account(user_id)
        contacts = await ContactDB.search_contacts(account, query)
        del self.pending_actions[user_id]
        if not contacts:
            await event.reply("🔍 No contacts found", buttons=[[Button.inline("🔙 Back", "contacts:main")]])
            return
        text = f"🔍 **Search Results for '{query}'**\n\n"
        buttons = []
        for contact in contacts[:5]:
            name = f"{contact.first_name} {contact.last_name or ''}".strip()
            text += f"👤 {name} (@{contact.username or 'N/A'})\n"
            buttons.append([Button.inline(f"👤 {name}", f"contact:view:{contact.user_id}")])
        buttons.append([Button.inline("🔙 Back", "contacts:main")])
        await event.reply(text, buttons=buttons)
    async def _export_contacts(self, event, user_id: int):
        """Export contacts to CSV from Telegram"""
        from ..core.mongo_database import mongodb
        from telethon.tl.functions.contacts import GetContactsRequest
        from telethon.tl.types import User
        from datetime import datetime
        
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
        if not accounts:
            await event.edit("❌ No accounts found", buttons=[[Button.inline("🔙 Back", "contacts:main")]])
            return
        
        buttons = []
        for i, account in enumerate(accounts[:8]):
            status = "🟢" if account.get("is_active", False) else "🔴"
            buttons.append([Button.inline(f"{status} {account['name']}", f"export_acc:{i}")])
        buttons.append([Button.inline("🔙 Back", "contacts:main")])
        
        self.pending_actions[user_id] = {'type': 'export_select', 'accounts': accounts}
        await event.edit("📤 **Export Contacts**\n\nSelect account:", buttons=buttons)
    async def _toggle_blacklist(self, event, user_id: int, contact_id: int):
        """Toggle contact blacklist status"""
        account = await self._get_user_account(user_id)
        contact = await ContactDB.get_contact(contact_id, account)
        if not contact:
            await event.answer("Contact not found")
            return
        new_status = not contact.is_blacklisted
        success = await ContactDB.set_contact_blacklist_status(contact_id, account, new_status)
        if success:
            status = "blacklisted" if new_status else "removed from blacklist"
            await event.answer(f"✅ Contact {status}")
            await self._view_contact(event, user_id, contact_id)
        else:
            await event.answer("❌ Failed to update status")
    async def _toggle_whitelist(self, event, user_id: int, contact_id: int):
        """Toggle contact whitelist status"""
        account = await self._get_user_account(user_id)
        contact = await ContactDB.get_contact(contact_id, account)
        if not contact:
            await event.answer("Contact not found")
            return
        new_status = not contact.is_whitelisted
        success = await ContactDB.set_contact_whitelist_status(contact_id, account, new_status)
        if success:
            status = "whitelisted" if new_status else "removed from whitelist"
            await event.answer(f"✅ Contact {status}")
            await self._view_contact(event, user_id, contact_id)
        else:
            await event.answer("❌ Failed to update status")
    async def _show_sync_menu(self, event, user_id: int):
        """Show sync options"""
        buttons = [
            [Button.inline("📥 From Telegram", "sync:from_telegram")],
            [Button.inline("📤 To Telegram", "sync:to_telegram")],
            [Button.inline("🔄 Two-way Sync", "sync:both")],
            [Button.inline("🔙 Back", "contacts:main")]
        ]
        await event.edit(
            "🔄 **Contact Sync**\n\n"
            "📥 **From Telegram**: Import contacts from your Telegram account\n"
            "📤 **To Telegram**: Export local contacts to Telegram\n"
            "🔄 **Two-way**: Sync both directions\n\n"
            "Choose sync direction:",
            buttons=buttons
        )
    async def _handle_sync(self, event, user_id: int, sync_type: str):
        """Handle contact synchronization"""
        from ..core.contact_sync import ContactSync
        account = await self._get_user_account(user_id)
        client = self._get_user_client(user_id)
        if not client:
            await event.edit("❌ No active client found", buttons=[[Button.inline("🔙 Back", "contacts:main")]])
            return
        await event.edit("🔄 **Synchronizing...**\n\nPlease wait...")
        try:
            if sync_type == "from_telegram":
                result = await ContactSync.sync_from_telegram(client, account)
            elif sync_type == "to_telegram":
                result = await ContactSync.sync_to_telegram(client, account)
            elif sync_type == "both":
                result = await ContactSync.two_way_sync(client, account)
            else:
                await event.edit("❌ Invalid sync type")
                return
