"""Contact export handler for exporting Telegram contacts to CSV"""

import asyncio
import csv
import io
import logging
from datetime import datetime
from telethon import Button, events
from telethon.tl.types import User
from telethon.tl.functions.contacts import GetContactsRequest
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)

class ContactExportHandler:
    """Handle contact export functionality"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        self.pending_exports = {}
        self.export_cooldowns = {}  # Track export cooldowns
        
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup contact export handlers"""
        
        @self.bot.on(events.CallbackQuery(pattern=r"^contacts:export$"))
        async def handle_export_contacts(event):
            user_id = event.sender_id
            
            # Get user accounts
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            if not accounts:
                await event.edit("❌ No accounts found. Add accounts first to export contacts.")
                return
            
            # Show account selection
            buttons = []
            for i, account in enumerate(accounts[:8]):  # Limit to 8 accounts
                status = "🟢" if account.get("is_active", False) else "🔴"
                # Use index instead of full name to avoid callback data length limit
                buttons.append([Button.inline(f"{status} {account['name']}", f"export_contacts:{i}")])
            
            buttons.append([Button.inline("🔙 Back", "menu:main")])
            
            text = "📇 **Export Contacts**\n\nSelect account to export contacts from:"
            await event.edit(text, buttons=buttons)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^export_contacts:"))
        async def handle_account_selection(event):
            user_id = event.sender_id
            account_index_str = event.data.decode().replace("export_contacts:", "")
            
            try:
                account_index = int(account_index_str)
            except ValueError:
                await event.edit("❌ Invalid account selection.")
                return
            
            # Get accounts again to find the selected one
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(None)
            if account_index >= len(accounts) or account_index < 0:
                await event.edit("❌ Account not found.")
                return
            
            account = accounts[account_index]
            account_name = account['name']
            
            # Check cooldown to prevent rapid exports
            cooldown_key = f"{user_id}:{account_name}"
            current_time = asyncio.get_event_loop().time()
            
            if cooldown_key in self.export_cooldowns:
                if current_time - self.export_cooldowns[cooldown_key] < 3.0:  # 3 second cooldown
                    return  # Ignore rapid clicks
            
            self.export_cooldowns[cooldown_key] = current_time
            
            # Check if account exists and is active
            if user_id not in self.user_clients or account_name not in self.user_clients[user_id]:
                await event.edit("❌ Account not found or not connected.")
                return
            
            client = self.user_clients[user_id][account_name]
            if not client or not client.is_connected():
                await event.edit("❌ Account is not connected. Please reconnect the account.")
                return
            
            # Start export process
            try:
                await event.edit("📇 **Exporting Contacts...**\n\n⏳ Please wait while we fetch your contacts...")
            except Exception as e:
                logger.warning(f"Failed to edit message: {e}")
            
            try:
                contacts_data = await self.export_contacts(client, account_name)
                
                if not contacts_data:
                    await event.edit("📇 **No Contacts Found**\n\nThis account has no contacts to export.")
                    return
                
                # Create CSV file
                csv_content = self.create_csv(contacts_data)
                
                # Send CSV file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"contacts_{account_name}_{timestamp}.csv"
                
                # Create file-like object
                csv_file = io.BytesIO(csv_content)
                csv_file.name = filename
                
                await self.bot.send_file(
                    user_id,
                    csv_file,
                    caption=f"📇 **Contacts Export Complete**\n\n"
                           f"📱 Account: {account_name}\n"
                           f"📊 Total Contacts: {len(contacts_data)}\n"
                           f"📅 Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                
                try:
                    await event.edit("✅ **Export Complete!**\n\nContacts CSV file sent above.")
                except Exception:
                    pass  # Ignore edit errors
                
            except Exception as e:
                logger.error(f"Contact export error for {account_name}: {e}")
                try:
                    await event.edit(f"❌ **Export Failed**\n\nError: {str(e)[:100]}")
                except Exception:
                    pass  # Ignore edit errors
    
    async def export_contacts(self, client, account_name):
        """Export contacts from Telegram account"""
        try:
            contacts_data = []
            
            # Get all contacts using Telethon API
            result = await client(GetContactsRequest(hash=0))
            
            for user in result.users:
                if isinstance(user, User):
                    contact_info = {
                        'id': user.id,
                        'first_name': user.first_name or '',
                        'last_name': user.last_name or '',
                        'username': user.username or '',
                        'phone': user.phone or '',
                        'is_bot': user.bot,
                        'is_verified': user.verified,
                        'is_premium': getattr(user, 'premium', False),
                        'is_mutual_contact': user.mutual_contact,
                        'is_deleted': user.deleted,
                        'language_code': getattr(user, 'lang_code', ''),
                        'access_hash': user.access_hash,
                        'status': str(user.status) if user.status else '',
                        'exported_at': datetime.now().isoformat()
                    }
                    contacts_data.append(contact_info)
            
            logger.info(f"Exported {len(contacts_data)} contacts from {account_name}")
            return contacts_data
            
        except Exception as e:
            logger.error(f"Error exporting contacts from {account_name}: {e}")
            raise
    
    def create_csv(self, contacts_data):
        """Create CSV content from contacts data"""
        if not contacts_data:
            return None
        
        # CSV headers
        headers = [
            'ID', 'First Name', 'Last Name', 'Username', 'Phone', 
            'Is Bot', 'Is Verified', 'Is Premium', 'Is Mutual Contact',
            'Is Deleted', 'Language Code', 'Access Hash', 'Status', 'Exported At'
        ]
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(headers)
        
        # Write contact data
        for contact in contacts_data:
            row = [
                contact['id'],
                contact['first_name'],
                contact['last_name'],
                contact['username'],
                contact['phone'],
                contact['is_bot'],
                contact['is_verified'],
                contact['is_premium'],
                contact['is_mutual_contact'],
                contact['is_deleted'],
                contact['language_code'],
                contact['access_hash'],
                contact['status'],
                contact['exported_at']
            ]
            writer.writerow(row)
        
        # Get CSV content as bytes
        csv_content = output.getvalue().encode('utf-8')
        output.close()
        
        return csv_content