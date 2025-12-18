"""Proxy Management Handler"""
import logging
from telethon import Button
from ..core.mongo_database import mongodb
from ..core.proxy_manager import proxy_manager
from ..utils.network_helpers import format_display_name

logger = logging.getLogger(__name__)


class ProxyHandler:
    """Handles proxy management UI and operations"""
    
    def __init__(self, bot_manager):
        self.bot = bot_manager.bot
        self.bot_manager = bot_manager
    
    async def _safe_edit(self, event, text, buttons=None):
        """Safely edit message, ignoring 'content not modified' errors"""
        try:
            await event.edit(text, buttons=buttons)
        except Exception as e:
            if "not modified" not in str(e).lower():
                logger.error(f"Edit error: {e}")
                raise
    
    def register_handlers(self):
        """Register proxy callback handlers"""
        from telethon import events
        
        @self.bot.on(events.CallbackQuery(pattern=r'^proxy:'))
        async def proxy_callback_handler(event):
            try:
                data = event.data.decode('utf-8')
                user_id = event.sender_id
                
                parts = data.split(':')
                action = parts[1] if len(parts) > 1 else None
                
                if action == 'menu':
                    await self._show_proxy_menu(event, user_id)
                elif action == 'list':
                    await self._show_proxy_list(event, user_id)
                elif action == 'add':
                    await self._start_add_proxy(event, user_id)
                elif action == 'test':
                    proxy_id = parts[2] if len(parts) > 2 else None
                    await self._test_proxy(event, user_id, proxy_id)
                elif action == 'delete':
                    proxy_id = parts[2] if len(parts) > 2 else None
                    await self._delete_proxy(event, user_id, proxy_id)
                elif action == 'assign':
                    await self._show_account_selection(event, user_id)
                elif action == 'assign_new':
                    proxy_id = parts[2] if len(parts) > 2 else None
                    await self._show_account_selection_for_proxy(event, user_id, proxy_id)
                elif action == 'set_default':
                    proxy_id = parts[2] if len(parts) > 2 else None
                    await self._set_default_proxy(event, user_id, proxy_id)
                elif action == 'assign_to':
                    account_id = parts[2] if len(parts) > 2 else None
                    await self._show_proxy_selection_for_account(event, user_id, account_id)
                elif action == 'set':
                    account_id = parts[2] if len(parts) > 2 else None
                    proxy_id = parts[3] if len(parts) > 3 else None
                    await self._assign_proxy(event, user_id, account_id, proxy_id)
                elif action == 'remove':
                    account_id = parts[2] if len(parts) > 2 else None
                    await self._remove_proxy(event, user_id, account_id)
                elif action == 'view_accounts':
                    await self._show_accounts_with_proxies(event, user_id)
                
                try:
                    await event.answer()
                except:
                    pass
            except Exception as e:
                logger.error(f"Proxy callback error: {e}")
                try:
                    await event.answer("❌ Error processing request")
                except:
                    pass
    
    async def _show_proxy_menu(self, event, user_id):
        """Show main proxy menu"""
        proxies = await proxy_manager.get_user_proxies(user_id)
        accounts = await mongodb.db.accounts.find({'user_id': user_id}).to_list(length=None)
        accounts_with_proxy = sum(1 for acc in accounts if acc.get('proxy_id'))
        
        # Get default proxy
        default_proxy = await proxy_manager.get_default_proxy(user_id)
        default_info = f"✅ {default_proxy['server']}:{default_proxy['port']}" if default_proxy else "❌ None"
        
        text = (
            f"🌐 **Proxy Management**\n\n"
            f"📊 **Statistics:**\n"
            f"• Total Proxies: {len(proxies)}\n"
            f"• Accounts with Proxy: {accounts_with_proxy}/{len(accounts)}\n"
            f"• Default for New Accounts: {default_info}\n\n"
            f"**Supported Formats:**\n"
            f"✅ SOCKS5 proxies (Recommended)\n"
            f"✅ HTTP proxies (Recommended)\n"
            f"⚠️ MTProto proxies (May not work on cloud)\n"
            f"• Telegram proxy links (t.me/proxy, t.me/socks)\n\n"
            f"Select an option below:"
        )
        
        buttons = [
            [Button.inline("➕ Add Proxy", "proxy:add")],
            [Button.inline("📋 View Proxies", "proxy:list")],
            [Button.inline("🔗 Assign to Account", "proxy:assign")],
            [Button.inline("👥 View Accounts", "proxy:view_accounts")],
            [Button.inline("🔙 Back to Main Menu", "menu:main")]
        ]
        
        await self._safe_edit(event, text, buttons=buttons)
    
    async def _show_proxy_list(self, event, user_id):
        """Show list of proxies"""
        proxies = await proxy_manager.get_user_proxies(user_id)
        
        if not proxies:
            text = "📋 **Your Proxies**\n\n❌ No proxies added yet.\n\nAdd a proxy to get started!"
            buttons = [
                [Button.inline("➕ Add Proxy", "proxy:add")],
                [Button.inline("🔙 Back", "proxy:menu")]
            ]
            await self._safe_edit(event, text, buttons=buttons)
            return
        
        text = f"📋 **Your Proxies** ({len(proxies)})\n\n"
        buttons = []
        
        for proxy in proxies[:10]:  # Show first 10
            status_emoji = {
                'working': '✅',
                'failed': '❌',
                'timeout': '⏱️',
                'untested': '❓'
            }.get(proxy.get('status', 'untested'), '❓')
            
            proxy_name = proxy.get('name', f"{proxy['server']}:{proxy['port']}")
            response_time = f" ({proxy['response_time']}s)" if proxy.get('response_time') else ""
            
            text += f"{status_emoji} **{proxy_name}**{response_time}\n"
            text += f"   Type: {proxy['type']} | {proxy['server']}:{proxy['port']}\n\n"
            
            proxy_id = str(proxy['_id'])
            buttons.append([
                Button.inline(f"🧪 Test", f"proxy:test:{proxy_id}"),
                Button.inline(f"🗑️ Delete", f"proxy:delete:{proxy_id}")
            ])
        
        if len(proxies) > 10:
            text += f"\n... and {len(proxies) - 10} more"
        
        buttons.append([Button.inline("➕ Add Proxy", "proxy:add")])
        buttons.append([Button.inline("🔙 Back", "proxy:menu")])
        
        await self._safe_edit(event, text, buttons=buttons)
    
    async def _start_add_proxy(self, event, user_id):
        """Start adding proxy"""
        self.bot_manager.pending_actions[user_id] = {'action': 'add_proxy'}
        
        text = (
            "➕ **Add New Proxy**\n\n"
            "⚠️ **RECOMMENDED: Use SOCKS5 or HTTP proxies**\n"
            "MTProto proxies may not work reliably on cloud platforms.\n\n"
            "Send me a proxy in any of these formats:\n\n"
            "**Telegram Links:**\n"
            "• `t.me/socks?server=1.2.3.4&port=1080&user=admin&pass=123` ✅\n"
            "• `t.me/proxy?server=1.2.3.4&port=443&secret=abc123` ⚠️\n"
            "• `tg://socks?server=1.2.3.4&port=1080&user=admin&pass=123` ✅\n\n"
            "**Manual Format:**\n"
            "• `socks5://user:pass@1.2.3.4:1080` ✅ Recommended\n"
            "• `http://user:pass@1.2.3.4:8080` ✅ Recommended\n"
            "• `mtproto://1.2.3.4:443:secret` ⚠️ May not work\n\n"
            "Or send /cancel to cancel"
        )
        
        await self._safe_edit(event, text, buttons=[[Button.inline("❌ Cancel", "proxy:menu")]])
    
    async def process_proxy_input(self, event, user_id, text):
        """Process proxy input from user"""
        try:
            logger.info(f"Processing proxy input from user {user_id}: {text[:100]}...")
            
            # Send immediate processing feedback
            processing_msg = await event.reply("🔄 Processing proxy...")
            
            # Parse proxy
            proxy_data = await proxy_manager.parse_telegram_proxy_link(text)
            logger.info(f"Parsed proxy data: {proxy_data}")
            
            if not proxy_data:
                logger.warning(f"Failed to parse proxy link: {text[:100]}")
                await processing_msg.edit(
                    "❌ **Invalid Proxy Format**\n\n"
                    "Could not parse the proxy link you provided.\n\n"
                    "**Supported Formats:**\n"
                    "• `t.me/proxy?server=1.2.3.4&port=443&secret=abc123`\n"
                    "• `t.me/socks?server=1.2.3.4&port=1080&user=admin&pass=123`\n"
                    "• `socks5://user:pass@1.2.3.4:1080`\n\n"
                    "Please try again or send /cancel"
                )
                return
            
            # Add proxy
            await processing_msg.edit(f"📥 Adding proxy {proxy_data['server']}:{proxy_data['port']}...")
            success, result = await proxy_manager.add_proxy(user_id, proxy_data)
            
            if success:
                proxy_id = result
                await processing_msg.edit(
                    f"✅ **Proxy Added Successfully!**\n\n"
                    f"**Server:** {proxy_data['server']}\n"
                    f"**Port:** {proxy_data['port']}\n"
                    f"**Type:** {proxy_data['type']}\n\n"
                    f"🧪 Testing connection...",
                    buttons=[[Button.inline("📋 View Proxies", "proxy:list")]]
                )
                
                # Test proxy
                test_success, test_msg, response_time = await proxy_manager.test_proxy(proxy_id, self.bot_manager)
                
                # Check if user has accounts
                accounts = await mongodb.db.accounts.find({'user_id': user_id}).to_list(length=None)
                
                if test_success:
                    if accounts:
                        await self.bot.send_message(
                            user_id,
                            f"✅ **Proxy Test Successful!**\n\n"
                            f"**Server:** {proxy_data['server']}:{proxy_data['port']}\n"
                            f"**Response Time:** {response_time:.2f}s\n"
                            f"**Status:** ✅ Working\n\n"
                            f"❓ What would you like to do?",
                            buttons=[
                                [Button.inline("🔗 Assign to Account", f"proxy:assign_new:{proxy_id}")],
                                [Button.inline("🤖 Set as Default for New Accounts", f"proxy:set_default:{proxy_id}")],
                                [Button.inline("📋 View Proxies", "proxy:list")]
                            ]
                        )
                    else:
                        await self.bot.send_message(
                            user_id,
                            f"✅ **Proxy Test Successful!**\n\n"
                            f"**Server:** {proxy_data['server']}:{proxy_data['port']}\n"
                            f"**Response Time:** {response_time:.2f}s\n"
                            f"**Status:** ✅ Working\n\n"
                            f"❓ Set as default for new accounts?",
                            buttons=[
                                [Button.inline("✅ Yes, Set as Default", f"proxy:set_default:{proxy_id}")],
                                [Button.inline("📋 View Proxies", "proxy:list")]
                            ]
                        )
                else:
                    await self.bot.send_message(
                        user_id,
                        f"⚠️ **Proxy Test Failed**\n\n"
                        f"**Server:** {proxy_data['server']}:{proxy_data['port']}\n"
                        f"**Error:** {test_msg}\n\n"
                        f"❌ The proxy was added but may not work properly.\n\n"
                        f"**Possible Issues:**\n"
                        f"• Proxy server is offline\n"
                        f"• Incorrect credentials\n"
                        f"• Network connectivity issues\n\n"
                        f"💡 You can test it again later from the proxy list.",
                        buttons=[[Button.inline("📋 View Proxies", "proxy:list")], [Button.inline("🧪 Test Again", f"proxy:test:{proxy_id}")]]
                    )
            else:
                await processing_msg.edit(
                    f"❌ **Failed to Add Proxy**\n\n"
                    f"Error: {result}\n\n"
                    f"Please check your proxy details and try again."
                )
            
            # Clear pending action
            self.bot_manager.pending_actions.pop(user_id, None)
        except Exception as e:
            logger.error(f"Process proxy input error: {e}")
            await event.reply(
                f"❌ **Error Processing Proxy**\n\n"
                f"An unexpected error occurred: {str(e)}\n\n"
                f"Please try again or contact support."
            )
            self.bot_manager.pending_actions.pop(user_id, None)
    
    async def _test_proxy(self, event, user_id, proxy_id):
        """Test proxy connection"""
        try:
            await event.answer("🧪 Testing proxy...", alert=False)
        except:
            pass
        
        success, message, response_time = await proxy_manager.test_proxy(proxy_id, self.bot_manager)
        
        try:
            if success:
                await event.answer(f"✅ Proxy working! ({response_time:.2f}s)", alert=True)
            else:
                await event.answer(f"❌ Proxy failed: {message}", alert=True)
        except:
            pass
        
        # Refresh list
        await self._show_proxy_list(event, user_id)
    
    async def _delete_proxy(self, event, user_id, proxy_id):
        """Delete proxy"""
        success, message = await proxy_manager.delete_proxy(user_id, proxy_id)
        
        try:
            if success:
                await event.answer("✅ Proxy deleted", alert=True)
            else:
                await event.answer(f"❌ {message}", alert=True)
        except:
            pass
        
        # Refresh list
        await self._show_proxy_list(event, user_id)
    
    async def _show_account_selection(self, event, user_id):
        """Show account selection for proxy assignment"""
        accounts = await mongodb.db.accounts.find({'user_id': user_id}).to_list(length=None)
        
        if not accounts:
            await self._safe_edit(
                event,
                "❌ No accounts found",
                buttons=[[Button.inline("🔙 Back", "proxy:menu")]]
            )
            return
        
        text = "🔗 **Assign Proxy to Account**\n\nSelect an account:"
        buttons = []
        
        for account in accounts:
            display_name = format_display_name(account)
            has_proxy = "🌐" if account.get('proxy_id') else "⚪"
            account_id = str(account['_id'])
            
            buttons.append([Button.inline(
                f"{has_proxy} {display_name}",
                f"proxy:assign_to:{account_id}"
            )])
        
        buttons.append([Button.inline("🔙 Back", "proxy:menu")])
        
        await self._safe_edit(event, text, buttons=buttons)
    
    async def _set_default_proxy(self, event, user_id, proxy_id):
        """Set default proxy for new accounts"""
        from bson import ObjectId
        
        proxy = await mongodb.db.proxies.find_one({'_id': ObjectId(proxy_id), 'user_id': user_id})
        if not proxy:
            try:
                await event.answer("❌ Proxy not found", alert=True)
            except:
                pass
            return
        
        success, message = await proxy_manager.set_default_proxy(user_id, proxy_id)
        
        try:
            if success:
                proxy_info = f"{proxy['server']}:{proxy['port']}"
                await event.answer(
                    f"✅ Default Proxy Set!\n\n"
                    f"Proxy: {proxy_info}\n\n"
                    f"All new accounts will automatically use this proxy.",
                    alert=True
                )
            else:
                await event.answer(f"❌ {message}", alert=True)
        except:
            pass
        
        await self._show_proxy_menu(event, user_id)
    
    async def _show_account_selection_for_proxy(self, event, user_id, proxy_id):
        """Show account selection for newly added proxy"""
        from bson import ObjectId
        
        accounts = await mongodb.db.accounts.find({'user_id': user_id}).to_list(length=None)
        proxy = await mongodb.db.proxies.find_one({'_id': ObjectId(proxy_id), 'user_id': user_id})
        
        if not accounts:
            await self._safe_edit(
                event,
                "❌ No accounts found",
                buttons=[[Button.inline("🔙 Back", "proxy:list")]]
            )
            return
        
        if not proxy:
            await self._safe_edit(
                event,
                "❌ Proxy not found",
                buttons=[[Button.inline("🔙 Back", "proxy:list")]]
            )
            return
        
        proxy_info = f"{proxy['server']}:{proxy['port']}"
        text = f"🔗 **Assign Proxy to Account**\n\n**Proxy:** {proxy_info}\n\nSelect an account:"
        buttons = []
        
        for account in accounts:
            display_name = format_display_name(account)
            has_proxy = "🌐" if account.get('proxy_id') else "⚪"
            account_id = str(account['_id'])
            
            buttons.append([Button.inline(
                f"{has_proxy} {display_name}",
                f"proxy:set:{account_id}:{proxy_id}"
            )])
        
        buttons.append([Button.inline("❌ Skip", "proxy:list")])
        
        await self._safe_edit(event, text, buttons=buttons)
    
    async def _show_proxy_selection_for_account(self, event, user_id, account_id):
        """Show proxy selection for specific account"""
        from bson import ObjectId
        
        account = await mongodb.db.accounts.find_one({'_id': ObjectId(account_id), 'user_id': user_id})
        if not account:
            try:
                await event.answer("❌ Account not found", alert=True)
            except:
                pass
            return
        
        proxies = await proxy_manager.get_user_proxies(user_id)
        
        if not proxies:
            await self._safe_edit(
                event,
                "❌ No proxies available. Add a proxy first!",
                buttons=[
                    [Button.inline("➕ Add Proxy", "proxy:add")],
                    [Button.inline("🔙 Back", "proxy:assign")]
                ]
            )
            return
        
        display_name = format_display_name(account)
        current_proxy_id = account.get('proxy_id')
        
        text = f"🔗 **Select Proxy for {display_name}**\n\n"
        buttons = []
        
        for proxy in proxies:
            status_emoji = {
                'working': '✅',
                'failed': '❌',
                'timeout': '⏱️',
                'untested': '❓'
            }.get(proxy.get('status', 'untested'), '❓')
            
            proxy_name = proxy.get('name', f"{proxy['server']}:{proxy['port']}")
            proxy_id = str(proxy['_id'])
            
            is_current = "✓ " if proxy_id == current_proxy_id else ""
            
            buttons.append([Button.inline(
                f"{is_current}{status_emoji} {proxy_name}",
                f"proxy:set:{account_id}:{proxy_id}"
            )])
        
        if current_proxy_id:
            buttons.append([Button.inline("🚫 Remove Proxy", f"proxy:remove:{account_id}")])
        
        buttons.append([Button.inline("🔙 Back", "proxy:assign")])
        
        await self._safe_edit(event, text, buttons=buttons)
    
    async def _assign_proxy(self, event, user_id, account_id, proxy_id):
        """Assign proxy to account"""
        from bson import ObjectId
        
        # Get account and proxy details for better feedback
        account = await mongodb.db.accounts.find_one({'_id': ObjectId(account_id), 'user_id': user_id})
        proxy = await proxy_manager.get_account_proxy(account_id) if account and account.get('proxy_id') else None
        new_proxy = await mongodb.db.proxies.find_one({'_id': ObjectId(proxy_id), 'user_id': user_id})
        
        success, message = await proxy_manager.assign_proxy_to_account(user_id, account_id, proxy_id)
        
        if success:
            # Restart account to apply proxy
            phone = account.get('phone')
            if phone and phone in self.bot_manager.user_clients:
                try:
                    await event.answer("🔄 Restarting account...", alert=False)
                    client = self.bot_manager.user_clients[phone]
                    await client.disconnect()
                    await self.bot_manager._start_user_client(account)
                    
                    if account and new_proxy:
                        account_name = account.get('name', 'Unknown')
                        proxy_info = f"{new_proxy['server']}:{new_proxy['port']}"
                        await event.answer(
                            f"✅ Proxy Applied!\n\n"
                            f"Account: {account_name}\n"
                            f"Proxy: {proxy_info}\n"
                            f"Status: ✅ Active",
                            alert=True
                        )
                    else:
                        await event.answer("✅ Proxy assigned and applied!", alert=True)
                except Exception as e:
                    logger.error(f"Restart error: {e}")
                    await event.answer("✅ Proxy assigned! Restart account manually.", alert=True)
            else:
                if account and new_proxy:
                    account_name = account.get('name', 'Unknown')
                    proxy_info = f"{new_proxy['server']}:{new_proxy['port']}"
                    await event.answer(
                        f"✅ Proxy Assigned!\n\n"
                        f"Account: {account_name}\n"
                        f"Proxy: {proxy_info}\n\n"
                        f"⚠️ Start account to apply",
                        alert=True
                    )
                else:
                    await event.answer("✅ Proxy assigned! Start account to apply.", alert=True)
        else:
            try:
                await event.answer(f"❌ {message}", alert=True)
            except:
                pass
        
        # Refresh selection
        await self._show_proxy_selection_for_account(event, user_id, account_id)
    
    async def _remove_proxy(self, event, user_id, account_id):
        """Remove proxy from account"""
        from bson import ObjectId
        
        # Get account details for better feedback
        account = await mongodb.db.accounts.find_one({'_id': ObjectId(account_id), 'user_id': user_id})
        
        success, message = await proxy_manager.remove_proxy_from_account(user_id, account_id)
        
        if success:
            # Restart account to remove proxy
            phone = account.get('phone')
            if phone and phone in self.bot_manager.user_clients:
                try:
                    await event.answer("🔄 Restarting account...", alert=False)
                    client = self.bot_manager.user_clients[phone]
                    await client.disconnect()
                    await self.bot_manager._start_user_client(account)
                    
                    if account:
                        account_name = account.get('name', 'Unknown')
                        await event.answer(
                            f"✅ Proxy Removed\n\n"
                            f"Account: {account_name}\n"
                            f"Status: ✅ Direct connection",
                            alert=True
                        )
                    else:
                        await event.answer("✅ Proxy removed and applied!", alert=True)
                except Exception as e:
                    logger.error(f"Restart error: {e}")
                    await event.answer("✅ Proxy removed! Restart account manually.", alert=True)
            else:
                if account:
                    account_name = account.get('name', 'Unknown')
                    await event.answer(
                        f"✅ Proxy Removed\n\n"
                        f"Account: {account_name}\n"
                        f"Status: Direct connection\n\n"
                        f"⚠️ Start account to apply",
                        alert=True
                    )
                else:
                    await event.answer("✅ Proxy removed! Start account to apply.", alert=True)
        else:
            try:
                await event.answer(f"❌ {message}", alert=True)
            except:
                pass
        
        # Refresh selection
        await self._show_proxy_selection_for_account(event, user_id, account_id)
    
    async def _show_accounts_with_proxies(self, event, user_id):
        """Show all accounts and their proxy status"""
        accounts = await mongodb.db.accounts.find({'user_id': user_id}).to_list(length=None)
        
        if not accounts:
            await self._safe_edit(
                event,
                "❌ No accounts found",
                buttons=[[Button.inline("🔙 Back", "proxy:menu")]]
            )
            return
        
        text = "👥 **Accounts & Proxies**\n\n"
        
        for account in accounts:
            display_name = format_display_name(account)
            
            if account.get('proxy_id'):
                proxy = await proxy_manager.get_account_proxy(str(account['_id']))
                if proxy:
                    status_emoji = {
                        'working': '✅',
                        'failed': '❌',
                        'timeout': '⏱️',
                        'untested': '❓'
                    }.get(proxy.get('status', 'untested'), '❓')
                    
                    proxy_info = f"{status_emoji} {proxy['server']}:{proxy['port']}"
                else:
                    proxy_info = "❌ Proxy not found"
            else:
                proxy_info = "⚪ No proxy"
            
            text += f"**{display_name}**\n{proxy_info}\n\n"
        
        buttons = [
            [Button.inline("🔗 Assign Proxies", "proxy:assign")],
            [Button.inline("🔙 Back", "proxy:menu")]
        ]
        
        await self._safe_edit(event, text, buttons=buttons)
