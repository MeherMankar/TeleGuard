"""Split from view_contacts.py - contacts_operations"""
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
    
    async def _edit_contact_menu(self, event, user_id: int, contact_id: int):
        """Show edit contact menu"""
        account = await self._get_user_account(user_id)
        contact = await ContactDB.get_contact(contact_id, account)
        if not contact:
            await event.answer("Contact not found")
            return
        name = f"{contact.first_name} {contact.last_name or ''}".strip()
        buttons = [
            [Button.inline("✏️ Edit Name", f"contact:edit_name:{contact_id}")],
            [Button.inline("📝 Add Notes", f"contact:add_notes:{contact_id}")],
            [Button.inline("🏷️ Add Tags", f"contact:add_tags:{contact_id}")],
            [Button.inline("🔙 Back", f"contact:view:{contact_id}")]
        ]
        await event.edit(f"✏️ **Edit Contact: {name}**\n\nChoose what to edit:", buttons=buttons)
    
    async def _delete_contact(self, event, user_id: int, contact_id: int):
        """Delete contact with confirmation"""
        account = await self._get_user_account(user_id)
        contact = await ContactDB.get_contact(contact_id, account)
        if not contact:
            await event.answer("Contact not found")
            return
        name = f"{contact.first_name} {contact.last_name or ''}".strip()
        buttons = [
            [Button.inline("✅ Confirm Delete", f"contact:delete_confirm:{contact_id}")],
            [Button.inline("❌ Cancel", f"contact:view:{contact_id}")]
        ]
        await event.edit(f"🗑️ **Delete Contact**\n\nAre you sure you want to delete {name}?", buttons=buttons)
    
    async def _process_add_notes(self, event, user_id: int, text: str, action: dict):
        """Process adding notes to contact"""
        account = await self._get_user_account(user_id)
        contact_id = action.get('contact_id')
        if not contact_id:
            await event.reply("❌ Invalid contact")
            return
        success = await ContactDB.update_contact(contact_id, account, {"notes": text})
        del self.pending_actions[user_id]
        if success:
            await event.reply("✅ Notes added", buttons=[[Button.inline("👤 View Contact", f"contact:view:{contact_id}")]])
        else:
            await event.reply("❌ Failed to add notes")
    
    async def _process_add_tags(self, event, user_id: int, text: str, action: dict):
        """Process adding tags to contact"""
        account = await self._get_user_account(user_id)
        contact_id = action.get('contact_id')
        if not contact_id:
            await event.reply("❌ Invalid contact")
            return
        tags = [tag.strip() for tag in text.split(',') if tag.strip()]
        contact = await ContactDB.get_contact(contact_id, account)
        if contact:
            existing_tags = set(contact.tags)
            existing_tags.update(tags)
            success = await ContactDB.update_contact(contact_id, account, {"tags": list(existing_tags)})
            del self.pending_actions[user_id]
            if success:
                await event.reply(f"✅ Tags added: {', '.join(tags)}", buttons=[[Button.inline("👤 View Contact", f"contact:view:{contact_id}")]])
            else:
                await event.reply("❌ Failed to add tags")
        else:
            await event.reply("❌ Contact not found")
    async def _start_import(self, event, user_id: int):
        """Start contact import process"""
        await event.edit(
            "📥 **Import Contacts**\n\n"
            "Send a CSV file with contacts. Supported formats:\n\n"
            "**Format 1 (TeleGuard):**\n"
            "`user_id, first_name, last_name, username, phone, tags, is_blacklisted, is_whitelisted, notes`\n\n"
            "**Format 2 (Export):**\n"
            "`ID, First Name, Last Name, Username, Phone, Is Bot, Is Verified, Is Premium, ...`\n\n"
            "The file should have headers in the first row.",
            buttons=[[Button.inline("❌ Cancel", "contacts:main")]]
        )
        self.pending_actions[user_id] = {'type': 'import'}
    async def _process_import_file(self, event, user_id: int):
        """Process uploaded CSV file for contact import"""
        try:
            if not event.message.document:
                await event.reply("❌ Please send a CSV file")
                return
            
            file_name = event.message.document.attributes[0].file_name if event.message.document.attributes else "file"
            if not file_name.endswith('.csv'):
                await event.reply("❌ Please send a CSV file")
                return
            
            await event.reply("📥 **Importing...**\n\n⏳ Processing file...")
            
            file_path = await event.download_media()
            if not file_path:
                await event.reply("❌ Failed to download file")
                return
            account = await self._get_user_account(user_id)
            if not account:
                await event.reply("❌ No active account found")
                return
            imported_count = 0
            skipped_count = 0
            error_count = 0
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                # Detect CSV format by reading first line
                first_line = csvfile.readline().strip()
                csvfile.seek(0)
                reader = csv.DictReader(csvfile)
                if 'ID' in reader.fieldnames and 'First Name' in reader.fieldnames:
                    for row in reader:
                        try:
                            user_id_val = int(row['ID'])
                            first_name = row.get('First Name', '').strip()
                            last_name = row.get('Last Name', '').strip()
                            username = row.get('Username', '').strip()
                            phone = row.get('Phone', '').strip()
                            # Skip bots
                            if row.get('Is Bot', 'False').lower() == 'true':
                                skipped_count += 1
                                continue
                            existing = await ContactDB.get_contact(user_id_val, account)
                            if existing:
                                skipped_count += 1
                                continue
                            contact = Contact(
                                user_id=user_id_val,
                                first_name=first_name or f"User_{user_id_val}",
                                last_name=last_name or None,
                                username=username or None,
                                phone=phone or None,
                                managed_by_account=account
                            )
                            success = await ContactDB.add_contact(contact)
                            if success:
                                imported_count += 1
                            else:
                                error_count += 1
                        except Exception as e:
                            logger.error(f"Error importing contact: {e}")
                            error_count += 1
                            continue
                elif 'user_id' in reader.fieldnames:
                    # TeleGuard format
                    for row in reader:
                        try:
                            user_id_val = int(row['user_id'])
                            first_name = row.get('first_name', '').strip()
                            last_name = row.get('last_name', '').strip()
                            username = row.get('username', '').strip()
                            phone = row.get('phone', '').strip()
                            tags = row.get('tags', '').strip().split(',') if row.get('tags') else []
                            is_blacklisted = row.get('is_blacklisted', 'False').lower() == 'true'
                            is_whitelisted = row.get('is_whitelisted', 'False').lower() == 'true'
                            notes = row.get('notes', '').strip()
                            existing = await ContactDB.get_contact(user_id_val, account)
                            if existing:
                                skipped_count += 1
                                continue
                            contact = Contact(
                                user_id=user_id_val,
                                first_name=first_name or f"User_{user_id_val}",
                                last_name=last_name or None,
                                username=username or None,
                                phone=phone or None,
                                tags=tags,
                                is_blacklisted=is_blacklisted,
                                is_whitelisted=is_whitelisted,
                                notes=notes,
                                managed_by_account=account
                            )
                            success = await ContactDB.add_contact(contact)
                            if success:
                                imported_count += 1
                            else:
                                error_count += 1
                        except Exception as e:
                            logger.error(f"Error importing contact: {e}")
                            error_count += 1
                            continue
                else:
                    await event.reply("❌ Unsupported CSV format. Please check the file headers.")
                    import os
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return
            
            import os
            if os.path.exists(file_path):
                os.remove(file_path)
            
            del self.pending_actions[user_id]
            
            text = (
                f"📥 **Import Complete**\n\n"
                f"✅ Imported: {imported_count}\n"
                f"⏭️ Skipped: {skipped_count}\n"
                f"❌ Errors: {error_count}\n\n"
                f"Total processed: {imported_count + skipped_count + error_count}"
            )
            buttons = [[Button.inline("🔙 Back to Contacts", "contacts:main")]]
            await event.reply(text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Import file error: {e}")
            await event.reply(f"❌ Error processing file: {str(e)}")
            if user_id in self.pending_actions:
                del self.pending_actions[user_id]
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
    
    async def _confirm_delete_contact(self, event, user_id: int, contact_id: int):
        """Confirm and delete contact"""
        account = await self._get_user_account(user_id)
        success = await ContactDB.delete_contact(contact_id, account)
        if success:
            await event.edit("✅ Contact deleted", buttons=[[Button.inline("🔙 Back", "contacts:main")]])
        else:
            await event.answer("❌ Failed to delete contact")
    
    async def _start_add_notes(self, event, user_id: int, contact_id: int):
        """Start adding notes to contact"""
        self.pending_actions[user_id] = {'type': 'add_notes', 'contact_id': contact_id}
        await event.edit(
            "📝 **Add Notes**\n\nSend the notes for this contact:\n\nType 'cancel' to abort",
            buttons=[[Button.inline("❌ Cancel", f"contact:view:{contact_id}")]]
        )
    
    async def _start_add_tags(self, event, user_id: int, contact_id: int):
        """Start adding tags to contact"""
        self.pending_actions[user_id] = {'type': 'add_tags', 'contact_id': contact_id}
        await event.edit(
            "🏷️ **Add Tags**\n\nSend tags separated by commas:\n\nExample: `friend, work, important`\n\nType 'cancel' to abort",
            buttons=[[Button.inline("❌ Cancel", f"contact:view:{contact_id}")]]
        )
    
    async def _view_tag_contacts(self, event, user_id: int, tag: str):
        """View contacts with specific tag"""
        account = await self._get_user_account(user_id)
        contacts = await ContactDB.get_contacts_by_tag(account, tag)
        if not contacts:
            await event.edit(f"🏷️ No contacts with tag '{tag}'", buttons=[[Button.inline("🔙 Back", "contacts:tags")]])
            return
        text = f"🏷️ **Tag: {tag}** ({len(contacts)} contacts)\n\n"
        buttons = []
        for contact in contacts[:8]:
            name = f"{contact.first_name} {contact.last_name or ''}".strip()
            text += f"👤 {name}\n"
            buttons.append([Button.inline(f"👤 {name}", f"contact:view:{contact.user_id}")])
        buttons.append([Button.inline("🔙 Back", "contacts:tags")])
        await event.edit(text, buttons=buttons)
    
    async def _view_group(self, event, user_id: int, group_name: str):
        """View group details"""
        account = await self._get_user_account(user_id)
        group = await ContactDB.get_group(group_name, account)
        if not group:
            await event.answer("Group not found")
            return
        text = f"📁 **{group.name}**\n\n"
        if group.description:
            text += f"{group.description}\n\n"
        text += f"👥 Members: {len(group.contact_ids)}\n\n"
        buttons = [
            [Button.inline("➕ Add Contact", f"group:add_contact:{group_name}")],
            [Button.inline("🗑️ Delete Group", f"group:delete:{group_name}")],
            [Button.inline("🔙 Back", "contacts:groups")]
        ]
        await event.edit(text, buttons=buttons)
    
    async def _start_create_group(self, event, user_id: int):
        """Start creating a new group"""
        self.pending_actions[user_id] = {'type': 'create_group'}
        await event.edit(
            "📁 **Create Group**\n\nSend the group name:\n\nType 'cancel' to abort",
            buttons=[[Button.inline("❌ Cancel", "contacts:groups")]]
        )
    
    async def _show_main_menu(self, event, user_id: int):
        """Show main contacts menu"""
        account = await self._get_user_account(user_id)
        if not account:
            await event.edit("❌ No active account found.", buttons=[])
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
        await event.edit(
            f"📱 **Contact Management**\n\n"
            f"📊 Total Contacts: {count}\n"
            f"🔧 Account: {account}\n\n"
            f"Choose an option:",
            buttons=buttons
        )
    
    async def _process_export(self, event, user_id: int, account_idx: int):
        """Process contact export for selected account"""
        from telethon.tl.functions.contacts import GetContactsRequest
        from telethon.tl.types import User
        from datetime import datetime
        
        action = self.pending_actions.get(user_id)
        if not action or action.get('type') != 'export_select':
            await event.answer("❌ Invalid export request")
            return
        
        accounts = action.get('accounts', [])
        if account_idx >= len(accounts):
            await event.edit("❌ Account not found", buttons=[[Button.inline("🔙 Back", "contacts:main")]])
            return
        
        account = accounts[account_idx]
        account_name = account['name']
        
        client = self._get_user_client(user_id)
        if not client:
            await event.edit("❌ Account not connected", buttons=[[Button.inline("🔙 Back", "contacts:main")]])
            return
        
        await event.edit("📤 **Exporting...**\n\n⏳ Fetching contacts...")
        
        try:
            result = await client(GetContactsRequest(hash=0))
            contacts_data = []
            
            for user in result.users:
                if isinstance(user, User):
                    contacts_data.append({
                        'id': user.id,
                        'first_name': user.first_name or '',
                        'last_name': user.last_name or '',
                        'username': user.username or '',
                        'phone': user.phone or '',
                        'is_bot': user.bot,
                        'is_verified': user.verified,
                        'is_premium': getattr(user, 'premium', False),
                        'is_mutual': user.mutual_contact,
                        'is_deleted': user.deleted
                    })
            
            if not contacts_data:
                await event.edit("📤 No contacts found", buttons=[[Button.inline("🔙 Back", "contacts:main")]])
                return
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'First Name', 'Last Name', 'Username', 'Phone', 'Is Bot', 'Is Verified', 'Is Premium', 'Is Mutual Contact', 'Is Deleted'])
            
            for contact in contacts_data:
                writer.writerow([
                    contact['id'], contact['first_name'], contact['last_name'],
                    contact['username'], contact['phone'], contact['is_bot'],
                    contact['is_verified'], contact['is_premium'],
                    contact['is_mutual'], contact['is_deleted']
                ])
            
            csv_data = output.getvalue().encode('utf-8')
            output.close()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"contacts_{account_name}_{timestamp}.csv"
            
            await self.bot.send_file(
                user_id,
                csv_data,
                attributes=[],
                file_name=filename,
                caption=f"📤 **Export Complete**\n\n📱 Account: {account_name}\n📊 Total: {len(contacts_data)} contacts\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            del self.pending_actions[user_id]
            await event.edit("✅ Export complete!", buttons=[[Button.inline("🔙 Back", "contacts:main")]])
            
        except Exception as e:
            logger.error(f"Export error: {e}")
            await event.edit(f"❌ Export failed: {str(e)[:100]}", buttons=[[Button.inline("🔙 Back", "contacts:main")]])
