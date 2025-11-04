"""Split from buttons.py - cleanup_buttons_helpers"""
            logger.error(f"Cleanup error for account {account_id}: {e}")
            
            error_text = (
                f"❌ **Cleanup error!**\n\n"
                f"🚫 Error: {str(e)}\n\n"
                f"💡 Try again in a few minutes"
            )
            
            buttons = [[Button.inline("🔙 Back to Main Menu", "menu:main")]]
            
            try:
                await self.bot.edit_message(user_id, event.message_id, error_text, buttons=buttons)
            except Exception as edit_error:
                if "Content of the message was not modified" in str(edit_error):
                    # Message content is the same, just answer callback if available
                    try:
                        await event.answer("❌ Cleanup failed")
                    except:
                        pass
                else:
                    # Send new message if edit fails for other reasons
                    await self.bot.send_message(user_id, error_text, buttons=buttons)
    
    async def _handle_cleanup_selection_callback(self, event, user_id: int, data: str):
        """Handle cleanup selection text input"""
        try:
            # Check if this is a text message (not callback)
            if hasattr(event, 'text'):
                # This is a text message response
                if not hasattr(self.account_manager, 'pending_actions') or user_id not in self.account_manager.pending_actions:
                    await event.reply("❌ No pending cleanup action found.")
                    return
                
                action_data = self.account_manager.pending_actions[user_id]
                if action_data.get('action') != 'cleanup_selection':
                    await event.reply("❌ Invalid action state.")
                    return
                
                account_id = action_data.get('account_id')
                cleanup_types = event.text.strip().lower()
                
                # Clear pending action
                del self.account_manager.pending_actions[user_id]
                
                # Send confirmation as new message to avoid edit conflicts
                await self._send_cleanup_confirmation_new(user_id, account_id, cleanup_types)
            else:
                # This is a callback query - handle differently
                parts = data.split(":")
                if len(parts) >= 3:
                    account_id = parts[2]
                    cleanup_types = parts[3] if len(parts) > 3 else "all"
                    await self._send_cleanup_confirmation_new(user_id, account_id, cleanup_types)
            
        except Exception as e:
            logger.error(f"Error in cleanup selection callback: {e}")
            await event.reply("❌ Error processing cleanup selection.")
    
    async def _send_cleanup_confirmation_new(self, user_id: int, account_id: str, cleanup_types: str):
        """Send cleanup confirmation as new message to avoid edit conflicts"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await self.bot.send_message(user_id, "❌ Account not found")
                return
            
            display_name = format_display_name(account)
            
            # Parse cleanup types
            cleanup_list = [t.strip().lower() for t in cleanup_types.split(',')]
            if 'all' in cleanup_list:
                cleanup_list = ['personal', 'bots', 'telegram', 'spambot', 'channels', 'groups', 'owned_groups', 'owned_channels']
            
            # Create display text for selected options
            selected_options = []
            if 'personal' in cleanup_list:
                selected_options.append("✅ 💬 Personal chats")
            if 'bots' in cleanup_list:
                selected_options.append("✅ 🤖 Bot chats")
            if 'telegram' in cleanup_list:
                selected_options.append("✅ 📢 Telegram official chats")
            if 'spambot' in cleanup_list:
                selected_options.append("✅ 🚫 Spambot chats")
            if 'channels' in cleanup_list:
                selected_options.append("✅ 🚪 Exit from channels")
            if 'groups' in cleanup_list:
                selected_options.append("✅ 👥 Exit from groups")
            if 'owned_groups' in cleanup_list:
                selected_options.append("✅ 🗑️ Delete owned groups")
            if 'owned_channels' in cleanup_list:
                selected_options.append("✅ 📺 Delete owned channels")
            
            if not selected_options:
                await self.bot.send_message(user_id, "❌ No valid cleanup options selected. Please try again with valid options: personal, bots, telegram, spambot, channels, groups, owned_groups, owned_channels, all")
                return
            
            text = (
                f"🧹 **Final Cleanup Confirmation**\n\n"
                f"📱 Account: {display_name}\n\n"
                f"**Selected cleanup actions:**\n"
                + "\n".join(selected_options) + "\n\n"
                f"⚠️ **FINAL WARNING**: This action cannot be undone!\n"
                f"All selected chats and data will be permanently deleted.\n\n"
                f"Are you absolutely sure you want to proceed?"
            )
            
            buttons = [
                [Button.inline("🚀 YES, Start Cleanup", f"cleanup:confirm:{account_id}:{cleanup_types}")],
                [Button.inline("❌ Cancel", "cleanup:menu")]
            ]
            
            await self.bot.send_message(user_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in cleanup confirmation: {e}")
            await self.bot.send_message(user_id, "❌ Error loading cleanup confirmation")
    
    async def _send_cleanup_confirmation(self, user_id: int, message_id: int, account_id: str, cleanup_types: str):
        """Send cleanup confirmation with selected options (legacy method for edit)"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                if message_id:
                    await self.bot.edit_message(user_id, message_id, "❌ Account not found", buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
                else:
                    await self.bot.send_message(user_id, "❌ Account not found")
                return
            
            display_name = format_display_name(account)
            
            # Parse cleanup types
            cleanup_list = [t.strip().lower() for t in cleanup_types.split(',')]
            if 'all' in cleanup_list:
                cleanup_list = ['personal', 'bots', 'telegram', 'spambot', 'channels', 'groups', 'owned_groups', 'owned_channels']
            
            # Create display text for selected options
            selected_options = []
            if 'personal' in cleanup_list:
                selected_options.append("✅ 💬 Personal chats")
            if 'bots' in cleanup_list:
                selected_options.append("✅ 🤖 Bot chats")
            if 'telegram' in cleanup_list:
                selected_options.append("✅ 📢 Telegram official chats")
            if 'spambot' in cleanup_list:
                selected_options.append("✅ 🚫 Spambot chats")
            if 'channels' in cleanup_list:
                selected_options.append("✅ 🚪 Exit from channels")
            if 'groups' in cleanup_list:
                selected_options.append("✅ 👥 Exit from groups")
            if 'owned_groups' in cleanup_list:
                selected_options.append("✅ 🗑️ Delete owned groups")
            if 'owned_channels' in cleanup_list:
                selected_options.append("✅ 📺 Delete owned channels")
            
            if not selected_options:
                error_msg = "❌ No valid cleanup options selected. Please try again with valid options: personal, bots, telegram, spambot, channels, groups, owned_groups, owned_channels, all"
                if message_id:
                    await self.bot.edit_message(user_id, message_id, error_msg, buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
                else:
                    await self.bot.send_message(user_id, error_msg)
                return
            
            text = (
                f"🧹 **Final Cleanup Confirmation**\n\n"
                f"📱 Account: {display_name}\n\n"
                f"**Selected cleanup actions:**\n"
                + "\n".join(selected_options) + "\n\n"
                f"⚠️ **FINAL WARNING**: This action cannot be undone!\n"
                f"All selected chats and data will be permanently deleted.\n\n"
                f"Are you absolutely sure you want to proceed?"
            )
            
            buttons = [
                [Button.inline("🚀 YES, Start Cleanup", f"cleanup:confirm:{account_id}:{cleanup_types}")],
                [Button.inline("❌ Cancel", "cleanup:menu")]
            ]
            
            if message_id:
                await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
            else:
                await self.bot.send_message(user_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in cleanup confirmation: {e}")
            error_msg = "❌ Error loading cleanup confirmation"
            if message_id:
                try:
                    await self.bot.edit_message(user_id, message_id, error_msg, buttons=[[Button.inline("🔙 Back", "cleanup:menu")]])
                except:
                    await self.bot.send_message(user_id, error_msg)
            else:
                await self.bot.send_message(user_id, error_msg)
    
    async def _handle_spam_appeal_select(self, event, user_id: int):
        """Handle spam appeal account selection"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
            if not accounts:
                text = "📞 **Spam Appeal**\n\n❌ No accounts found."
                buttons = [[Button.inline("🔙 Back", "cleanup:menu")]]
                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
                return
            
            text = (
                "📞 **Spam Appeal**\n\n"
                "Select account to submit spam appeal:"
            )
            buttons = []
            for account in accounts:
                status = "🟢" if account.get("is_active", False) else "🔴"
                display_name = format_display_name(account)
                button_text = f"{status} {display_name}"
                buttons.append([Button.inline(button_text, f"appeal_account_id:{account['_id']}")])
            
            buttons.append([Button.inline("🔙 Back", "cleanup:menu")])
            await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Error in spam appeal select: {e}")
            await event.answer("❌ Error loading spam appeal")
    
    async def _handle_spam_appeal(self, event, user_id: int, account_id: str):
        """Handle spam appeal for account before cleanup"""
        try:
            from bson import ObjectId
            account = await mongodb.db.accounts.find_one({"_id": ObjectId(account_id), "user_id": user_id})
            if not account:
                await event.answer("❌ Account not found")
                return
            
            display_name = format_display_name(account)
            
            # Check if spam appeal handler is available
            if hasattr(self.account_manager, 'spam_appeal_handler'):
                text = (
                    f"📞 **Spam Appeal - {display_name}**\n\n"
                    f"🤖 **Smart Appeal System**\n\n"
                    f"Before cleaning your account, you can try appealing any spam restrictions.\n\n"
                    f"**Features:**\n"
                    f"• AI-powered message selection\n"
                    f"• Automatic @spambot interaction\n"
                    f"• Manual captcha verification\n"
                    f"• Smart detection of restriction types\n\n"
                    f"Would you like to start the appeal process?"
                )
                
                buttons = [
                    [Button.inline("🚀 Start Appeal", f"appeal_account_id:{account_id}")],
                    [Button.inline("🧹 Skip to Cleanup", f"cleanup:select:{account_id}")],
                    [Button.inline("🔙 Back to Menu", "cleanup:menu")]
                ]
                
                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            else:
                text = (
                    f"📞 **Manual Spam Appeal - {display_name}**\n\n"
                    f"Spam appeal system is not available.\n\n"
                    f"**Manual steps:**\n"
                    f"1. Go to @spambot\n"
                    f"2. Send /start\n"
                    f"3. Follow the appeal process\n"
                    f"4. Complete any captcha verification\n\n"
                    f"After appealing, you can return to cleanup if needed."
                )
                
                buttons = [
                    [Button.inline("🧹 Continue to Cleanup", f"cleanup:select:{account_id}")],
                    [Button.inline("🔙 Back to Menu", "cleanup:menu")]
                ]
                
                await self.bot.edit_message(user_id, event.message_id, text, buttons=buttons)
            
