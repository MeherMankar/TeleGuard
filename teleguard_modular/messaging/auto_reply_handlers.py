"""Split from auto_reply.py - auto_reply_handlers"""
                    del self.pending_actions[user_id]
                    buttons = [[Button.inline("🔙 Back to Keywords", "auto_reply:keywords")]]
                    message_preview = text[:50] + "..." if len(text) > 50 else text
                    await event.reply(f"✅ **Keyword Added Successfully!**\n\n🔑 Keyword: `{keyword}`\n💬 Reply: {message_preview}", buttons=buttons)
    async def _refresh_main_menu(self, event, user_id):
        """Refresh the main auto-reply menu"""
        try:
            encrypted_accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(100)
            accounts = [DataEncryption.decrypt_account_data(acc) for acc in encrypted_accounts]
            enabled_count = sum(1 for acc in accounts if acc.get('auto_reply_enabled', False))
            total_count = len(accounts)
            settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
            keyword_status = "🟢 On" if settings.get('keyword_replies_enabled', False) else "🔴 Off"
            time_status = "🟢 On" if settings.get('time_based_replies_enabled', False) else "🔴 Off"
            text = f"🤖 **Auto-Reply Settings**\n\n"
            text += f"📱 Accounts: {enabled_count}/{total_count} enabled\n"
            text += f"🔑 Keyword Replies: {keyword_status}\n"
            text += f"⏰ Time-based Replies: {time_status}\n\n"
            text += "Configure your automatic responses:"
            buttons = [
                [Button.inline("📱 Toggle Per Account", "auto_reply:toggle")],
                [Button.inline("🔑 Keyword Settings", "auto_reply:keyword_settings")],
                [Button.inline("⏰ Time Settings", "auto_reply:time_settings")],
                [Button.inline("📊 View Stats", "auto_reply:analytics")],
                [Button.inline("🗑️ Reset All", "auto_reply:reset")]
            ]
            await event.edit(text, buttons=buttons)
        except Exception as e:
            if "MessageNotModifiedError" not in str(e):
                logger.error(f"Error refreshing main menu: {e}")
    async def _refresh_keyword_settings(self, event, user_id):
        """Refresh the keyword settings menu"""
        try:
            settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
            status = "🟢 Enabled" if settings.get('keyword_replies_enabled', False) else "🔴 Disabled"
            toggle_text = "🔴 Disable" if settings.get('keyword_replies_enabled', False) else "🟢 Enable"
            buttons = [
                [Button.inline(f"{toggle_text} Keyword Replies", "auto_reply:toggle_keywords")],
                [Button.inline("⚙️ Configure Keywords", "auto_reply:keywords")],
                [Button.inline("🔙 Back", "auto_reply:main")]
            ]
            await event.edit(f"🔑 **Keyword Replies**\n\nStatus: {status}\n\nKeyword-based auto-replies respond to specific words in messages.", buttons=buttons)
        except Exception as e:
            if "MessageNotModifiedError" not in str(e):
                logger.error(f"Error refreshing keyword settings: {e}")
    async def _refresh_time_settings(self, event, user_id):
        """Refresh the time settings menu"""
        try:
            settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
            status = "🟢 Enabled" if settings.get('time_based_replies_enabled', False) else "🔴 Disabled"
            toggle_text = "🔴 Disable" if settings.get('time_based_replies_enabled', False) else "🟢 Enable"
            buttons = [
                [Button.inline(f"{toggle_text} Time-based Replies", "auto_reply:toggle_time")],
                [Button.inline("🕒 View Hours", "auto_reply:hours")],
                [Button.inline("🔙 Back", "auto_reply:main")]
            ]
            await event.edit(f"⏰ **Time-based Replies**\n\nStatus: {status}\n\nTime-based replies respond based on business hours when no keywords match.", buttons=buttons)
        except Exception as e:
            if "MessageNotModifiedError" not in str(e):
                logger.error(f"Error refreshing time settings: {e}")
    def setup_auto_reply_menu(self):
        """Setup auto-reply menu handlers"""
        @self.bot.on(events.CallbackQuery(pattern=r"^auto_reply:"))
        async def handle_auto_reply_menu(event):
            user_id = event.sender_id
            data = event.data.decode("utf-8")
            try:
                if data == "auto_reply:main":
                    await self._refresh_main_menu(event, user_id)
                elif data == "auto_reply:toggle":
                    # Show account selection for per-account control
                    encrypted_accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
                    if encrypted_accounts:
                        accounts = [DataEncryption.decrypt_account_data(acc) for acc in encrypted_accounts]
                        buttons = []
                        for account in accounts:
                            status = "🟢" if account.get('auto_reply_enabled', False) else "🔴"
                            buttons.append([Button.inline(f"{status} {account['name']}", f"auto_reply:toggle_account:{account['name']}")])
                        buttons.append([Button.inline("🔙 Back", "auto_reply:main")])
                        await event.edit("📱 **Select Account to Toggle Auto-Reply:**", buttons=buttons)
                    else:
                        await event.answer("No accounts found!")
                elif data == "auto_reply:keyword_settings":
                    await self._refresh_keyword_settings(event, user_id)
                elif data == "auto_reply:time_settings":
                    await self._refresh_time_settings(event, user_id)
                elif data == "auto_reply:toggle_keywords":
                    settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
                    new_status = not settings.get('keyword_replies_enabled', False)
                    await mongodb.db.auto_reply_settings.update_one(
                        {"user_id": user_id},
                        {"$set": {"keyword_replies_enabled": new_status}},
                        upsert=True
                    )
                    status_text = "enabled" if new_status else "disabled"
                    await event.answer(f"Keyword replies {status_text}!")
                    await self._refresh_keyword_settings(event, user_id)
                elif data == "auto_reply:toggle_time":
                    settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
                    new_status = not settings.get('time_based_replies_enabled', False)
                    await mongodb.db.auto_reply_settings.update_one(
                        {"user_id": user_id},
                        {"$set": {"time_based_replies_enabled": new_status}},
                        upsert=True
                    )
                    status_text = "enabled" if new_status else "disabled"
                    await event.answer(f"Time-based replies {status_text}!")
                    await self._refresh_time_settings(event, user_id)
                elif data == "auto_reply:keywords":
                    user_keywords = await self._get_user_keywords(user_id)
                    if user_keywords:
                        keyword_list = "\n".join([f"• {k}: {v[:50]}..." for k, v in user_keywords.items()])
                    else:
                        keyword_list = "No keywords configured."
                    buttons = [
                        [Button.inline("➕ Add Keyword", "auto_reply:add_keyword")],
                        [Button.inline("➖ Remove Keyword", "auto_reply:remove_keyword")],
                        [Button.inline("🔙 Back", "auto_reply:main")]
                    ]
                    await event.edit(f"🔑 **Active Keywords:**\n\n{keyword_list}", buttons=buttons)
                elif data == "auto_reply:add_keyword":
                    self.pending_actions[user_id] = {'action': 'add_keyword', 'step': 'keyword'}
                    buttons = [[Button.inline("❌ Cancel", "auto_reply:keywords")]]
                    await event.edit("➕ **Add New Keyword**\n\nSend the keyword you want to detect (e.g., 'busy', 'vacation'):\n\n📝 Type 'cancel' to abort", buttons=buttons)
                elif data == "auto_reply:remove_keyword":
                    user_keywords = await self._get_user_keywords(user_id)
                    if user_keywords:
                        buttons = [[Button.inline(f"❌ {k}", f"auto_reply:delete:{k}")] for k in user_keywords.keys()]
                        buttons.append([Button.inline("🔙 Back", "auto_reply:keywords")])
                        await event.edit("➖ **Remove Keyword**\n\nSelect keyword to delete:", buttons=buttons)
                    else:
                        await event.edit("⚠️ No keywords to remove.", buttons=[[Button.inline("🔙 Back", "auto_reply:keywords")]])
                elif data.startswith("auto_reply:delete:"):
                    keyword = data.split(":", 2)[2]
                    user_keywords = await self._get_user_keywords(user_id)
                    if keyword in user_keywords:
                        await self._remove_user_keyword(user_id, keyword)
                        await event.edit(f"✅ Keyword '{keyword}' removed!", buttons=[[Button.inline("🔙 Back", "auto_reply:keywords")]])
                    else:
                        await event.edit("❌ Keyword not found.", buttons=[[Button.inline("🔙 Back", "auto_reply:keywords")]])
                elif data == "auto_reply:analytics":
                    stats = f"📊 **Auto-Reply Analytics**\n\n"
                    stats += f"📨 Total Messages: {self.analytics['total_messages']}\n"
                    stats += f"🤖 Auto-Replies Sent: {self.analytics['auto_replies_sent']}\n"
                    stats += f"❓ Unmatched Queries: {self.analytics['unmatched_queries']}\n\n"
                    stats += f"🔑 **Keyword Hits:**\n"
                    for keyword, count in self.analytics['keyword_hits'].items():
                        stats += f"• {keyword}: {count}\n"
                    buttons = [[Button.inline("🔙 Back", "auto_reply:main")]]
                    await event.edit(stats, buttons=buttons)
                elif data == "auto_reply:hours":
                    current_hours = f"{self.business_hours['start'].strftime('%H:%M')} - {self.business_hours['end'].strftime('%H:%M')}"
                    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                    active_days = ', '.join([days[i] for i in self.business_hours['days']])
                    text = f"🕒 **Availability Hours**\n\n"
                    text += f"⏰ Hours: {current_hours}\n"
                    text += f"📅 Days: {active_days}\n\n"
                    text += f"During these hours, responses will indicate availability."
                    buttons = [[Button.inline("🔙 Back", "auto_reply:main")]]
                    await event.edit(text, buttons=buttons)
                elif data.startswith("auto_reply:toggle_account:"):
                    account_name = data.replace("auto_reply:toggle_account:", "", 1)
                    # Prevent rapid clicks (debouncing)
                    current_time = time_module.time()
                    toggle_key = f"{user_id}:{account_name}"
                    if toggle_key in self.last_toggle_time:
                        if current_time - self.last_toggle_time[toggle_key] < 2:  # 2 second cooldown
                            await event.answer("⏳ Please wait before toggling again...")
                            return
                    self.last_toggle_time[toggle_key] = current_time
                    try:
                        # Try to find account by encrypted name first, then by plain name
                        account_doc = None
                        try:
                            account_doc = await mongodb.db.accounts.find_one({"user_id": user_id, "name_enc": DataEncryption.encrypt_field(account_name)})
                        except:
                            pass
                        # If not found with encrypted name, try plain name
                        if not account_doc:
                            account_doc = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                        if account_doc:
                            # Decrypt account data if encrypted
                            account = DataEncryption.decrypt_account_data(account_doc)
                            current_status = account.get('auto_reply_enabled', False)
                            new_status = not current_status
                            update_query = {"user_id": user_id}
                            if "name_enc" in account_doc:
                                update_query["name_enc"] = account_doc["name_enc"]
                                update_data = {"$set": {"auto_reply_enabled_enc": DataEncryption.encrypt_field(new_status)}}
                            else:
                                update_query["name"] = account_name
                                update_data = {"$set": {"auto_reply_enabled": new_status}}
                            result = await mongodb.db.accounts.update_one(update_query, update_data)
                            if result.modified_count > 0:
                                logger.info(f"Auto-reply toggle for {account_name}: {current_status} -> {new_status}")
                                status_text = "🟢 enabled" if new_status else "🔴 disabled"
                                await event.answer(f"Auto-reply {status_text} for {account_name}!")
                                # Refresh account list with current data
                                encrypted_accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(100)
                                accounts = [DataEncryption.decrypt_account_data(acc) for acc in encrypted_accounts]
                                buttons = []
                                for acc in accounts:
                                    acc_status = acc.get('auto_reply_enabled', False)
                                    status_icon = "🟢" if acc_status else "🔴"
                                    buttons.append([Button.inline(f"{status_icon} {acc['name']}", f"auto_reply:toggle_account:{acc['name']}")])
                                buttons.append([Button.inline("🔙 Back", "auto_reply:main")])
                                try:
                                    await event.edit("📱 **Select Account to Toggle Auto-Reply:**", buttons=buttons)
                                except Exception as edit_error:
                                    if "MessageNotModifiedError" not in str(edit_error) and "Content of the message was not modified" not in str(edit_error):
                                        logger.error(f"Error refreshing account list: {edit_error}")
                            else:
                                await event.answer("❌ Failed to update account status")
                                logger.error(f"Database update failed for account {account_name}")
                        else:
                            await event.answer("❌ Account not found!")
                            logger.warning(f"Account {account_name} not found for user {user_id}")
                    except Exception as toggle_error:
                        logger.error(f"Error toggling auto-reply for {account_name}: {toggle_error}")
                        await event.answer("❌ Error toggling auto-reply")
                elif data == "auto_reply:reset":
                    try:
                        # Clear database settings
                        await mongodb.db.auto_reply_settings.delete_one({"user_id": user_id})
                        # Clear account auto-reply flags (handle both encrypted and unencrypted)
                        await mongodb.db.accounts.update_many(
                            {"user_id": user_id},
                            {"$unset": {"auto_reply_enabled_enc": "", "auto_reply_enabled": ""}}
                        )
                        # Force cleanup all handlers
                        await self.force_cleanup_user_handlers(user_id)
                        await event.edit("✅ **Complete Auto-Reply Reset**\n\nAll settings, keywords, and handlers cleared. Duplicate replies should stop now.", 
                                       buttons=[[Button.inline("🔙 Back", "auto_reply:main")]])
                    except Exception as reset_error:
                        logger.error(f"Error during auto-reply reset for user {user_id}: {reset_error}")
                        await event.answer("❌ Error during reset")
            except Exception as e:
                if "MessageNotModifiedError" not in str(e) and "Content of the message was not modified" not in str(e):
                    logger.error(f"Error in auto-reply menu handler: {e}")
                    # Show error to user for debugging
                    try:
                        await event.answer(f"❌ Error: {str(e)[:100]}")
                    except Exception as answer_error:
                        logger.error(f"Failed to send error message: {answer_error}")
    async def load_user_keywords(self, user_id: int):
        """Load user's custom keywords from database"""
        try:
            settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id})
            if settings and 'keywords' in settings:
                self.user_keywords[user_id] = settings['keywords']
        except Exception as e:
            logger.error(f"Error loading keywords for user {user_id}: {e}")
    def _is_business_hours(self, current_time: datetime = None) -> bool:
        """Check if currently in business hours"""
        if current_time is None:
            current_time = datetime.now()
        return (
            current_time.weekday() in self.business_hours['days'] and
            self.business_hours['start'] <= current_time.time() <= self.business_hours['end']
        )
