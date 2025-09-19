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
                elif data.startswith("sync:"):
                    sync_type = data.split(":")[1]
                    await self._handle_sync(event, user_id, sync_type)
                    
            except Exception as e:
                logger.error(f"Contact callback error: {e}")
                await event.answer("❌ Error processing request")

        @self.bot.on(events.NewMessage(func=lambda e: e.sender_id in self.pending_actions and not e.message.text.startswith('/') and self.pending_actions.get(e.sender_id, {}).get('type') in ['add_contact', 'search', 'add_notes', 'add_tags']))
        async def handle_input(event):
            """Handle text input and forwarded messages for contact operations"""
            user_id = event.sender_id
            action = self.pending_actions.get(user_id)
            
            if not action or action.get('type') not in ['add_contact', 'search', 'add_notes', 'add_tags']:
                return
                
            # Handle forwarded messages
            if event.message.forward:
                if action['type'] == 'add_contact':
                    await self._process_forwarded_contact(event, user_id, action)
                    return
                    
            # Handle text input
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
                return list(user_clients.keys())[0]  # Return first account
            return ""
        except Exception:
            return ""

    async def _show_contacts_list(self, event, user_id: int):
        """Show paginated contacts list"""
        account = await self._get_user_account(user_id)
        contacts = await ContactDB.get_all_contacts(account, limit=10)
        
        if not contacts:
            await event.edit("📭 No contacts found", buttons=[[Button.inline("➕ Add Contact", "contacts:add")]])
            return
            
        text = "👥 **Your Contacts**\n\n"
        buttons = []
        
        for contact in contacts[:8]:  # Show max 8 contacts
            name = f"{contact.first_name} {contact.last_name or ''}".strip()
            status = ""
            if contact.is_blacklisted:
                status = "🚫"
            elif contact.is_whitelisted:
                status = "✅"
                
            text += f"{status} {name} (@{contact.username or 'N/A'})\n"
            buttons.append([Button.inline(f"👤 {name}", f"contact:view:{contact.user_id}")])
            
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
            # Get sender info from forwarded message
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
                    
                # Check if contact exists
                existing = await ContactDB.get_contact(contact_user_id, account)
                if existing:
                    await event.reply("⚠️ Contact already exists!")
                    return
                    
                # Create contact
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
                # Handle phone number
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
            
            # Check if contact exists
            existing = await ContactDB.get_contact(contact_user_id, account)
            if existing:
                await event.reply("⚠️ Contact already exists!")
                return
                
            # Create contact
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
        """Export contacts to CSV"""
        account = await self._get_user_account(user_id)
        contacts = await ContactDB.get_all_contacts(account, limit=1000)
        
        if not contacts:
            await event.answer("No contacts to export")
            return
            
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['user_id', 'first_name', 'last_name', 'username', 'phone', 'tags', 'is_blacklisted', 'is_whitelisted', 'notes'])
        
        for contact in contacts:
            writer.writerow([
                contact.user_id,
                contact.first_name,
                contact.last_name or '',
                contact.username or '',
                contact.phone or '',
                ','.join(contact.tags),
                contact.is_blacklisted,
                contact.is_whitelisted,
                contact.notes
            ])
        
        csv_data = output.getvalue().encode('utf-8')
        
        await event.edit("📤 **Exporting Contacts...**")
        await self.bot.send_file(
            user_id,
            csv_data,
            attributes=[],
            file_name=f"contacts_{account}.csv",
            caption=f"📤 **Contacts Export**\n\n📊 Total: {len(contacts)} contacts"
        )

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
                
            if result["success"]:
                if sync_type == "both":
                    text = f"✅ **Two-way Sync Complete**\n\n"
                    text += f"📥 From Telegram: {result['from_telegram']['added']} added, {result['from_telegram']['updated']} updated\n"
                    text += f"📤 To Telegram: {result['to_telegram']['added']} added\n"
                    if result['from_telegram']['errors'] or result['to_telegram']['errors']:
                        text += f"⚠️ Errors: {result['from_telegram']['errors'] + result['to_telegram']['errors']}"
                else:
                    text = f"✅ **Sync Complete**\n\n"
                    if 'added' in result:
                        text += f"➕ Added: {result['added']}\n"
                    if 'updated' in result:
                        text += f"🔄 Updated: {result['updated']}\n"
                    if 'errors' in result and result['errors']:
                        text += f"⚠️ Errors: {result['errors']}"
            else:
                text = f"❌ **Sync Failed**\n\nError: {result.get('error', 'Unknown error')}"
                
            buttons = [[Button.inline("🔙 Back", "contacts:main")]]
            await event.edit(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Sync error: {e}")
            await event.edit("❌ Sync failed", buttons=[[Button.inline("🔙 Back", "contacts:main")]])

    async def _show_groups(self, event, user_id: int):
        """Show contact groups"""
        account = await self._get_user_account(user_id)
        groups = await ContactDB.get_all_groups(account)
        
        if not groups:
            buttons = [[Button.inline("➕ Create Group", "group:create")], [Button.inline("🔙 Back", "contacts:main")]]
            await event.edit("📁 No groups found", buttons=buttons)
            return
            
        text = "📁 **Contact Groups**\n\n"
        buttons = []
        
        for group in groups[:5]:
            text += f"📁 {group.name} ({len(group.contact_ids)} contacts)\n"
            buttons.append([Button.inline(f"📁 {group.name}", f"group:view:{group.name}")])
            
        buttons.extend([
            [Button.inline("➕ Create Group", "group:create")],
            [Button.inline("🔙 Back", "contacts:main")]
        ])
        
        await event.edit(text, buttons=buttons)

    async def _show_tags(self, event, user_id: int):
        """Show contact tags"""
        account = await self._get_user_account(user_id)
        contacts = await ContactDB.get_all_contacts(account, limit=100)
        
        # Collect all tags
        all_tags = set()
        for contact in contacts:
            all_tags.update(contact.tags)
            
        if not all_tags:
            await event.edit("🏷️ No tags found", buttons=[[Button.inline("🔙 Back", "contacts:main")]])
            return
            
        text = "🏷️ **Contact Tags**\n\n"
        buttons = []
        
        for tag in sorted(all_tags)[:8]:
            tag_count = sum(1 for c in contacts if tag in c.tags)
            text += f"🏷️ {tag} ({tag_count} contacts)\n"
            buttons.append([Button.inline(f"🏷️ {tag}", f"tag:view:{tag}")])
            
        buttons.append([Button.inline("🔙 Back", "contacts:main")])
        await event.edit(text, buttons=buttons)

    async def _start_import(self, event, user_id: int):
        """Start contact import process"""
        await event.edit(
            "📥 **Import Contacts**\n\n"
            "Send a CSV file with the following columns:\n"
            "`user_id, first_name, last_name, username, phone, tags, is_blacklisted, is_whitelisted, notes`\n\n"
            "The file should have headers in the first row.",
            buttons=[[Button.inline("❌ Cancel", "contacts:main")]]
        )
        
        self.pending_actions[user_id] = {'type': 'import'}

    def _get_user_client(self, user_id: int):
        """Get user's first available client"""
        try:
            user_clients = self.bot_manager.user_clients.get(user_id, {})
            for client in user_clients.values():
                if client and client.is_connected():
                    return client
            return None
        except Exception:
            return None