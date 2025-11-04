"""Split from mass_inviter.py - inviter_campaigns"""
                    sent += 1
                    await asyncio.sleep(random.uniform(0.1, 0.5))
                except (FloodWaitError, SlowModeWaitError, ChatWriteForbiddenError):
                    break
            
            await msg.edit(f"✅ Message flood completed!\n\nSent: {sent}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "message_flood"})
    
    async def _execute_raid_coord(self, event, temp_data):
        target = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply(f"⚔️ Starting coordinated raid on {target}...")
        
        try:
            accounts = await self._get_accounts(user_id)
            clients = [self._get_client(acc["phone"]) for acc in accounts if self._get_client(acc["phone"])]
            
            if not clients:
                await msg.edit("❌ No clients available")
                return
            
            tasks = []
            for client in clients:
                task = asyncio.create_task(self._raid_worker(client, target, 60))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            total = sum(r for r in results if isinstance(r, int))
            
            await msg.edit(f"✅ Raid completed!\n\nTotal messages: {total}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "raid_coord"})
    
    async def _raid_worker(self, client, target, duration):
        sent = 0
        start = asyncio.get_event_loop().time()
        
        try:
            group = await client.get_entity(target)
            while (asyncio.get_event_loop().time() - start) < duration:
                try:
                    await client.send_message(group, "⚔️ RAID ATTACK ⚔️")
                    sent += 1
                    await asyncio.sleep(0.2)
                except:
                    break
        except:
            pass
        
        return sent
    
    async def _execute_stealth_raid(self, event, temp_data):
        target = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply(f"🥷 Starting stealth raid on {target}...")
        
        try:
            accounts = await self._get_accounts(user_id)
            clients = [self._get_client(acc["phone"]) for acc in accounts if self._get_client(acc["phone"])]
            
            if not clients:
                await msg.edit("❌ No clients available")
                return
            
            tasks = []
            for client in clients:
                task = asyncio.create_task(self._stealth_worker(client, target, 20))
                tasks.append(task)
                await asyncio.sleep(random.uniform(5, 20))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            total = sum(r for r in results if isinstance(r, int))
            
            await msg.edit(f"✅ Stealth raid completed!\n\nTotal messages: {total}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "stealth_raid"})
    
    async def _stealth_worker(self, client, target, count):
        sent = 0
        human_messages = [
            "Hey everyone!", "What's up?", "Anyone here?", "Good morning!",
            "How's it going?", "Nice group!", "Hello there", "Greetings!",
            "What's happening?", "Hey guys", "Sup", "Yo", "Hi all",
            "Good to be here", "Interesting discussion", "I agree",
            "That's cool", "Nice", "Awesome", "Great point",
            "Thanks for sharing", "Appreciate it", "Cool stuff", "Interesting",
            "Makes sense", "True that", "Exactly", "For sure", "Definitely",
            "I see", "Got it", "Understood", "Fair enough", "Good idea"
        ]
        
        try:
            group = await client.get_entity(target)
            for i in range(count):
                try:
                    # Random typing indicator (50% chance)
                    if random.random() > 0.5:
                        async with client.action(group, 'typing'):
                            await asyncio.sleep(random.uniform(1, 4))
                    
                    # Send varied message
                    message = random.choice(human_messages)
                    await client.send_message(group, message)
                    sent += 1
                    
                    # Human-like delays: shorter at start, longer as time goes
                    base_delay = random.uniform(15, 45)
                    fatigue_factor = 1 + (i * 0.1)  # Gets slower over time
                    delay = base_delay * fatigue_factor
                    
                    # Random "distraction" - longer pause (20% chance)
                    if random.random() > 0.8:
                        delay += random.uniform(30, 120)
                    
                    await asyncio.sleep(delay)
                except:
                    break
        except:
            pass
        return sent
    
    async def _execute_multi_raid(self, event, temp_data):
        targets = event.text.strip().split("\n")
        user_id = event.sender_id
        
        msg = await event.reply(f"🎯 Starting multi-target raid on {len(targets)} groups...")
        
        try:
            accounts = await self._get_accounts(user_id)
            clients = [self._get_client(acc["phone"]) for acc in accounts if self._get_client(acc["phone"])]
            
            if not clients:
                await msg.edit("❌ No clients available")
                return
            
            tasks = []
            for i, target in enumerate(targets):
                client = clients[i % len(clients)]
                task = asyncio.create_task(self._raid_worker(client, target, 30))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            total = sum(r for r in results if isinstance(r, int))
            
            await msg.edit(f"✅ Multi-target raid completed!\n\nTotal messages: {total}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "multi_raid"})
    
    async def _execute_send_all_groups(self, event, temp_data):
        phone = temp_data["phone"]
        message = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply(f"📢 Sending message to all groups...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            # Get all dialogs (groups and channels)
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            
            sent = 0
            failed = 0
            
            for group in groups:
                try:
                    await client.send_message(group.entity, message)
                    sent += 1
                    await asyncio.sleep(random.uniform(2, 5))
                except (FloodWaitError, ChatWriteForbiddenError) as e:
                    failed += 1
                    if isinstance(e, FloodWaitError):
                        await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.error(f"Send error: {e}")
                    failed += 1
            
            await msg.edit(f"✅ Broadcast completed!\n\nSent: {sent}\nFailed: {failed}\nTotal groups: {len(groups)}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "send_all_groups"})
    
    async def _execute_mass_invite_all(self, event, phone, user_id):
        msg = await self.bot.send_message(user_id, "🌐 Starting mass invite to all groups...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            users = await mongodb.db.spam_users.find({"owner_id": user_id}).limit(50).to_list(None)
            
            total_invited = 0
            total_failed = 0
            
            for group in groups:
                try:
                    for user in users:
                        try:
                            await client(InviteToChannelRequest(group.entity, [user["user_id"]]))
                            total_invited += 1
                            await asyncio.sleep(random.randint(5, 15))
                        except:
                            total_failed += 1
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Error inviting to {group.name}: {e}")
            
            await msg.edit(f"✅ Mass invite completed!\n\nGroups: {len(groups)}\nInvited: {total_invited}\nFailed: {total_failed}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
    
    async def _handle_forward_bomb_all_source(self, event, temp_data):
        source = event.text.strip()
        user_id = event.sender_id
        
        await mongodb.db.temp_data.update_one(
            {"user_id": user_id, "type": "forward_bomb_all"},
            {"$set": {"source": source, "step": "msgid"}}
        )
        
        await event.reply(f"💣 Source set: {source}\n\nNow send message ID to forward:")
    
    async def _execute_forward_bomb_all(self, event, temp_data):
        phone = temp_data["phone"]
        source = temp_data["source"]
        msg_id = int(event.text.strip())
        user_id = event.sender_id
        
        msg = await event.reply("💣 Starting forward bomb to all groups...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            
            forwarded = 0
            
            for group in groups:
                try:
                    await client.forward_messages(group.entity, msg_id, source)
                    forwarded += 1
                    await asyncio.sleep(random.randint(2, 8))
                except:
                    pass
            
            await msg.edit(f"✅ Forward bomb completed!\n\nGroups: {len(groups)}\nForwarded: {forwarded}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
        finally:
            await mongodb.db.temp_data.delete_one({"user_id": user_id, "type": "forward_bomb_all"})
    
    async def _execute_message_flood_all(self, event, temp_data):
        phone = temp_data["phone"]
        message = event.text.strip()
        user_id = event.sender_id
        
        msg = await event.reply("🌊 Starting flood to all groups...")
        
        try:
            client = self._get_client(phone)
            if not client:
                await msg.edit("❌ Client not found")
                return
            
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            
            total_sent = 0
            
            for group in groups:
                try:
                    for i in range(50):
                        try:
                            await client.send_message(group.entity, message)
                            total_sent += 1
                            await asyncio.sleep(random.uniform(0.1, 0.5))
                        except (FloodWaitError, SlowModeWaitError, ChatWriteForbiddenError):
                            break
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Flood error: {e}")
            
            await msg.edit(f"✅ Flood completed!\n\nGroups: {len(groups)}\nMessages sent: {total_sent}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")
