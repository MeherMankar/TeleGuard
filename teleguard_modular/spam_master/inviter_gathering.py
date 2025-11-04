"""Split from mass_inviter.py - inviter_gathering"""
            user_id = event.sender_id
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "message_flood_all"},
                {"$set": {"phone": phone, "step": "message"}},
                upsert=True
            )
            
            await event.edit(
                f"🌊 **Message Flooder - All Groups**\n\n"
                f"Account: `{phone}`\n\n"
                f"Send the message to flood:"
            )
        
        # Raid Coordinator
        @self.bot.on(events.CallbackQuery(pattern=b"raid_coord"))
        async def raid_coord_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            if len(accounts) < 2:
                await event.answer("❌ Need at least 2 accounts", alert=True)
                return
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "raid_coord"},
                {"$set": {"step": "target", "accounts": len(accounts)}},
                upsert=True
            )
            
            await event.edit(
                f"⚔️ **Raid Coordinator Setup**\n\n"
                f"Using: {len(accounts)} accounts\n\n"
                f"Send target group username/link:"
            )
        
        # Stealth Raid
        @self.bot.on(events.CallbackQuery(pattern=b"stealth_raid"))
        async def stealth_raid_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            if len(accounts) < 2:
                await event.answer("❌ Need at least 2 accounts", alert=True)
                return
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "stealth_raid"},
                {"$set": {"step": "target", "accounts": len(accounts)}},
                upsert=True
            )
            
            await event.edit(
                f"🥷 **Stealth Raid Setup**\n\n"
                f"Using: {len(accounts)} accounts\n\n"
                f"Send target group username/link:"
            )
        
        # Multi-Target Raid
        @self.bot.on(events.CallbackQuery(pattern=b"multi_raid"))
        async def multi_raid_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            if len(accounts) < 3:
                await event.answer("❌ Need at least 3 accounts", alert=True)
                return
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "multi_raid"},
                {"$set": {"step": "targets", "accounts": len(accounts)}},
                upsert=True
            )
            
            await event.edit(
                f"🎯 **Multi-Target Raid Setup**\n\n"
                f"Using: {len(accounts)} accounts\n\n"
                f"Send target groups (one per line):"
            )
        
        # Send to All Groups
        @self.bot.on(events.CallbackQuery(pattern=b"send_all_groups"))
        async def send_all_groups_menu(event):
            await event.answer()
            user_id = event.sender_id
            accounts = await handler_self._get_accounts(user_id)
            
            if not accounts:
                await event.answer("❌ No accounts", alert=True)
                return
            
            buttons = [[Button.inline(f"📱 {acc['name']}", f"sag_acc:{acc['phone']}".encode())] for acc in accounts[:10]]
            buttons.append([Button.inline("🔙 Back", b"advanced_spam")])
            
            await event.edit("📢 **Send to All Groups**\n\nSelect account:", buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=rb"sag_acc:(.+)"))
        async def send_all_groups_setup(event):
            phone = event.data.decode().split(":", 1)[1]
            user_id = event.sender_id
            
            await mongodb.db.temp_data.update_one(
                {"user_id": user_id, "type": "send_all_groups"},
                {"$set": {"phone": phone, "step": "message"}},
                upsert=True
            )
            
            await event.edit(
                f"📢 **Send to All Groups Setup**\n\n"
                f"Account: `{phone}`\n\n"
                f"Send the message you want to broadcast to all groups:"
            )
        
        # Message handler for operations
        @self.bot.on(events.NewMessage(func=lambda e: e.is_private))
        async def operation_handler(event):
            user_id = event.sender_id
            temp_data = await mongodb.db.temp_data.find_one({"user_id": user_id})
            
            if not temp_data:
                return
            
            op_type = temp_data.get("type")
            
            if op_type == "mass_invite" and temp_data.get("step") == "target":
                await self._execute_mass_invite(event, temp_data)
            elif op_type == "contact_scrape" and temp_data.get("step") == "group":
                await self._execute_contact_scrape(event, temp_data)
            elif op_type == "username_check" and temp_data.get("step") == "base":
                await self._execute_username_check(event, temp_data)
            elif op_type == "forward_bomb" and temp_data.get("step") == "source":
                await self._handle_forward_bomb_source(event, temp_data)
            elif op_type == "forward_bomb" and temp_data.get("step") == "msgid":
                await self._execute_forward_bomb(event, temp_data)
            elif op_type == "message_flood" and temp_data.get("step") == "target":
                await self._execute_message_flood(event, temp_data)
            elif op_type == "raid_coord" and temp_data.get("step") == "target":
                await self._execute_raid_coord(event, temp_data)
            elif op_type == "stealth_raid" and temp_data.get("step") == "target":
                await self._execute_stealth_raid(event, temp_data)
            elif op_type == "multi_raid" and temp_data.get("step") == "targets":
                await self._execute_multi_raid(event, temp_data)
            elif op_type == "send_all_groups" and temp_data.get("step") == "message":
                await self._execute_send_all_groups(event, temp_data)
            elif op_type == "message_flood_all" and temp_data.get("step") == "message":
                await self._execute_message_flood_all(event, temp_data)
            elif op_type == "forward_bomb_all" and temp_data.get("step") == "source":
                await self._handle_forward_bomb_all_source(event, temp_data)
            elif op_type == "forward_bomb_all" and temp_data.get("step") == "msgid":
                await self._execute_forward_bomb_all(event, temp_data)
    
    async def _get_accounts(self, user_id):
        accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
        return [{"phone": acc["phone"], "name": acc.get("name", acc.get("first_name", acc["phone"]))} for acc in accounts]
    
    def _get_client(self, phone):
        phone = str(phone)
        if phone in self.user_clients:
            return self.user_clients[phone]
        phone_clean = phone.lstrip('+')
        if phone_clean in self.user_clients:
            return self.user_clients[phone_clean]
        phone_plus = f"+{phone_clean}"
        if phone_plus in self.user_clients:
            return self.user_clients[phone_plus]
        for key in self.user_clients:
            key_str = str(key).lstrip('+')
            if phone_clean in key_str or key_str in phone_clean:
                return self.user_clients[key]
        return None
    
    async def _execute_mass_invite(self, event, temp_data):
        phone = temp_data["phone"]
        target = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply(f"📤 Starting mass invite to {target}...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            group = await client.get_entity(target)
            users = await mongodb.db.spam_users.find({"owner_id": user_id}).limit(50).to_list(None)
            
            invited = 0
            failed = 0
            
            for user in users:
                try:
                    await client(InviteToChannelRequest(group, [user["user_id"]]))
                    invited += 1
                    await asyncio.sleep(random.randint(5, 15))
                except (FloodWaitError, UserPrivacyRestrictedError):
                    failed += 1
                except Exception as e:
                    logger.error(f"Invite error: {e}")
                    failed += 1
            
            await msg.edit(f"✅ Mass invite completed!\n\nInvited: {invited}\nFailed: {failed}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "mass_invite"})
    
    async def _execute_contact_scrape(self, event, temp_data):
        phone = temp_data["phone"]
        group = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply(f"📇 Scraping contacts from {group}...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            entity = await client.get_entity(group)
            contacts = []
            
            async for participant in client.iter_participants(entity, limit=5000):
                if not participant.bot:
                    contacts.append({
                        "user_id": participant.id,
                        "username": participant.username,
                        "first_name": participant.first_name,
                        "last_name": participant.last_name,
                        "phone": participant.phone
                    })
                    
                    if len(contacts) % 100 == 0:
                        await asyncio.sleep(1)
            
            # Export to CSV
            filename = f"contacts_{group.replace('@', '')}_{user_id}.csv"
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['user_id', 'username', 'first_name', 'last_name', 'phone'])
                writer.writeheader()
                writer.writerows(contacts)
            
            await self.bot.send_file(user_id, filename, caption=f"📇 Scraped {len(contacts)} contacts")
            await msg.edit(f"✅ Scraped {len(contacts)} contacts!\n\nFile sent above.")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "contact_scrape"})
    
    async def _execute_contact_scrape_all(self, event, phone, user_id):
        msg = await self.bot.send_message(user_id, "🌐 Scraping contacts from all groups...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            
            all_contacts = {}
            groups_scraped = 0
            
            for group in groups:
                try:
                    async for participant in client.iter_participants(group.entity, limit=5000):
                        if not participant.bot and participant.id not in all_contacts:
                            all_contacts[participant.id] = {
                                "user_id": participant.id,
                                "username": participant.username,
                                "first_name": participant.first_name,
                                "last_name": participant.last_name,
                                "phone": participant.phone
                            }
                    groups_scraped += 1
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Error scraping {group.name}: {e}")
            
            contacts = list(all_contacts.values())
            filename = f"contacts_all_groups_{user_id}.csv"
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['user_id', 'username', 'first_name', 'last_name', 'phone'])
                writer.writeheader()
                writer.writerows(contacts)
            
            await self.bot.send_file(user_id, filename, caption=f"🌐 Scraped {len(contacts)} unique contacts from {groups_scraped} groups")
            await msg.edit(f"✅ All groups scraped!\n\nGroups: {groups_scraped}\nContacts: {len(contacts)}\n\nFile sent above.")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
    
    async def _execute_username_check(self, event, temp_data):
        phone = temp_data["phone"]
        base = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply(f"🔍 Checking usernames for base: {base}...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            available = []
            checked = 0
            
            for i in range(100):
                username = f"{base}{random.randint(1, 9999)}"
                try:
                    await client.get_entity(username)
                except:
                    available.append(username)
                
                checked += 1
                if checked % 10 == 0:
                    await asyncio.sleep(1)
            
            result = f"✅ Username Check Complete!\n\nChecked: {checked}\nAvailable: {len(available)}\n\n"
            result += "\n".join([f"@{u}" for u in available[:20]])
            
            await msg.edit(result)
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "username_check"})
    
    async def _handle_forward_bomb_source(self, event, temp_data):
        source = event.text.strip()
        user_id = event.sender_id
        
        await mongodb.db.temp_data.update_one(
            {"user_id": user_id, "type": "forward_bomb"},
            {"$set": {"source": source, "step": "msgid"}}
        )
        
        await event.reply(f"💣 Source set: {source}\n\nNow send message ID to forward:")
    
    async def _execute_forward_bomb(self, event, temp_data):
        phone = temp_data["phone"]
        source = temp_data["source"]
        msg_id = int(event.text.strip())
        user_id = event.sender_id
        
        msg = await event.reply(f"💣 Starting forward bombing...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            users = await mongodb.db.spam_users.find({"owner_id": user_id}).limit(100).to_list(None)
            forwarded = 0
            
            for user in users:
                try:
                    await client.forward_messages(user["user_id"], msg_id, source)
                    forwarded += 1
                    await asyncio.sleep(random.randint(2, 8))
                except:
                    pass
            
            await msg.edit(f"✅ Forward bombing completed!\n\nForwarded: {forwarded}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "forward_bomb"})
    
    async def _execute_message_flood(self, event, temp_data):
        phone = temp_data["phone"]
        target = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply(f"🌊 Starting message flood to {target}...")
        
        flood_msgs = [
            "🔥🔥🔥 SPAM ATTACK 🔥🔥🔥",
            "💥 FLOODING IN PROGRESS 💥",
            "⚡ RAID MODE ACTIVATED ⚡",
            "🚨 SYSTEM OVERLOAD 🚨"
        ]
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            group = await client.get_entity(target)
            sent = 0
            
            for i in range(50):
                try:
                    await client.send_message(group, random.choice(flood_msgs))
