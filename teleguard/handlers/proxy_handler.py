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
        
        text = (
            f"🌐 **Proxy Management**\n\n"
            f"📊 **Statistics:**\n"
            f"• Total Proxies: {len(proxies)}\n"
            f"• Accounts with Proxy: {accounts_with_proxy}/{len(accounts)}\n\n"
            f"**Supported Formats:**\n"
            f"• Telegram proxy links (t.me/proxy)\n"
            f"• MTProto proxies\n"
            f"• SOCKS5 proxies\n"
            f"• HTTP proxies\n\n"
            f"Select an option below:"
        )
        
        buttons = [
            [Button.inline("➕ Add Proxy", "proxy:add")],
            [Button.inline("📋 View Proxies", "proxy:list")],
            [Button.inline("🔗 Assign to Account", "proxy:assign")],
            [Button.inline("👥 View Accounts", "proxy:view_accounts")],
            [Button.inline("🔙 Back to Main Menu", "menu:main")]
        ]
        
        await event.edit(text, buttons=buttons)
    
    async def _show_proxy_list(self, event, user_id):
        """Show list of proxies"""
        proxies = await proxy_manager.get_user_proxies(user_id)
        
        if not proxies:
            text = "📋 **Your Proxies**\n\n❌ No proxies added yet.\n\nAdd a proxy to get started!"
            buttons = [
                [Button.inline("➕ Add Proxy", "proxy:add")],
                [Button.inline("🔙 Back", "proxy:menu")]
            ]
            await event.edit(text, buttons=buttons)
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
        
        await event.edit(text, buttons=buttons)
    
    async def _start_add_proxy(self, event, user_id):
        """Start adding proxy"""
        self.bot_manager.pending_actions[user_id] = {'action': 'add_proxy'}
        
        text = (
            "➕ **Add New Proxy**\n\n"
            "Send me a proxy in any of these formats:\n\n"
            "**Telegram Links:**\n"
            "• `t.me/proxy?server=1.2.3.4&port=443&secret=abc123`\n"
            "• `t.me/socks?server=1.2.3.4&port=1080&user=admin&pass=123`\n"
            "• `tg://proxy?server=1.2.3.4&port=443&secret=abc123`\n\n"
            "**Manual Format:**\n"
            "• `socks5://user:pass@1.2.3.4:1080`\n"
            "• `http://user:pass@1.2.3.4:8080`\n"
            "• `mtproto://1.2.3.4:443:secret`\n\n"
            "Or send /cancel to cancel"
        )
        
        await event.edit(text, buttons=[[Button.inline("❌ Cancel", "proxy:menu")]])
    
    async def process_proxy_input(self, event, user_id, text):
        """Process proxy input from user"""
        try:
            logger.info(f"Processing proxy input from user {user_id}: {text[:100]}...")
            
            # Parse proxy
            proxy_data = await proxy_manager.parse_telegram_proxy_link(text)
            logger.info(f"Parsed proxy data: {proxy_data}")
            
            if not proxy_data:
                logger.warning(f"Failed to parse proxy link: {text[:100]}")
                await event.reply(
                    "❌ Invalid proxy format. Please try again or send /cancel\n\n"
                    "Example: `t.me/proxy?server=1.2.3.4&port=443&secret=abc123`"
                )
                return
            
            # Add proxy
            success, result = await proxy_manager.add_proxy(user_id, proxy_data)
            
            if success:
                proxy_id = result
                await event.reply(
                    f"✅ **Proxy Added Successfully!**\n\n"
                    f"**Server:** {proxy_data['server']}\n"
                    f"**Port:** {proxy_data['port']}\n"
                    f"**Type:** {proxy_data['type']}\n\n"
                    f"Testing proxy...",
                    buttons=[[Button.inline("📋 View Proxies", "proxy:list")]]
                )
                
                # Test proxy
                test_success, test_msg, response_time = await proxy_manager.test_proxy(proxy_id)
                
                if test_success:
                    await self.bot.send_message(
                        user_id,
                        f"✅ **Proxy Test Successful!**\n\n"
                        f"Response time: {response_time:.2f}s\n"
                        f"Status: Working\n\n"
                        f"You can now assign this proxy to your accounts.",
                        buttons=[[Button.inline("🔗 Assign to Account", "proxy:assign")]]
                    )
                else:
                    await self.bot.send_message(
                        user_id,
                        f"⚠️ **Proxy Test Failed**\n\n"
                        f"Error: {test_msg}\n\n"
                        f"The proxy was added but may not work. You can test it again later.",
                        buttons=[[Button.inline("📋 View Proxies", "proxy:list")]]
                    )
            else:
                await event.reply(f"❌ Failed to add proxy: {result}")
            
            # Clear pending action
            self.bot_manager.pending_actions.pop(user_id, None)
        except Exception as e:
            logger.error(f"Process proxy input error: {e}")
            await event.reply(f"❌ Error: {str(e)}")
            self.bot_manager.pending_actions.pop(user_id, None)
    
    async def _test_proxy(self, event, user_id, proxy_id):
        """Test proxy connection"""
        try:
            await event.answer("🧪 Testing proxy...", alert=False)
        except:
            pass
        
        success, message, response_time = await proxy_manager.test_proxy(proxy_id)
        
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
            await event.edit(
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
        
        await event.edit(text, buttons=buttons)
    
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
            await event.edit(
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
        
        await event.edit(text, buttons=buttons)
    
    async def _assign_proxy(self, event, user_id, account_id, proxy_id):
        """Assign proxy to account"""
        success, message = await proxy_manager.assign_proxy_to_account(user_id, account_id, proxy_id)
        
        try:
            if success:
                await event.answer("✅ Proxy assigned! Restart account to apply.", alert=True)
            else:
                await event.answer(f"❌ {message}", alert=True)
        except:
            pass
        
        # Refresh selection
        await self._show_proxy_selection_for_account(event, user_id, account_id)
    
    async def _remove_proxy(self, event, user_id, account_id):
        """Remove proxy from account"""
        success, message = await proxy_manager.remove_proxy_from_account(user_id, account_id)
        
        try:
            if success:
                await event.answer("✅ Proxy removed", alert=True)
            else:
                await event.answer(f"❌ {message}", alert=True)
        except:
            pass
        
        # Refresh selection
        await self._show_proxy_selection_for_account(event, user_id, account_id)
    
    async def _show_accounts_with_proxies(self, event, user_id):
        """Show all accounts and their proxy status"""
        accounts = await mongodb.db.accounts.find({'user_id': user_id}).to_list(length=None)
        
        if not accounts:
            await event.edit(
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
        
        await event.edit(text, buttons=buttons)
