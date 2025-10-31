"""Contact Sharing Handler - Share contacts between accounts"""
import logging
from telethon import events
from ..core.config import ADMIN_IDS

logger = logging.getLogger(__name__)

class ContactShareHandler:
    """Share contacts between accounts for cross-account messaging"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
    
    def register_handlers(self):
        """Register contact sharing handlers"""
        
        @self.bot.on(events.NewMessage(pattern=r'^/share_contacts$'))
        async def share_contacts_command(event):
            if event.sender_id not in ADMIN_IDS:
                return
            
            await event.reply(
                "📇 **Contact Sharing**\n\n"
                "Share contacts from one account to another for cross-account messaging.\n\n"
                "**Usage:**\n"
                "`/share_contacts source_account target_account`\n\n"
                "**Example:**\n"
                "`/share_contacts Account1 Account2`\n\n"
                "This will import Account1's contacts into Account2."
            )
        
        @self.bot.on(events.NewMessage(pattern=r'^/share_contacts\s+(\S+)\s+(\S+)$'))
        async def share_contacts_execute(event):
            if event.sender_id not in ADMIN_IDS:
                return
            
            source_name = event.pattern_match.group(1)
            target_name = event.pattern_match.group(2)
            user_id = event.sender_id
            
            source_client = self.user_clients.get(user_id, {}).get(source_name)
            target_client = self.user_clients.get(user_id, {}).get(target_name)
            
            if not source_client:
                await event.reply(f"❌ Source account `{source_name}` not found")
                return
            
            if not target_client:
                await event.reply(f"❌ Target account `{target_name}` not found")
                return
            
            status_msg = await event.reply(
                f"🔄 **Sharing Contacts**\n\n"
                f"From: {source_name}\n"
                f"To: {target_name}\n\n"
                f"Collecting contacts..."
            )
            
            try:
                # Get contacts from source
                from telethon.tl.functions.contacts import GetContactsRequest
                result = await source_client(GetContactsRequest(hash=0))
                
                if not result.users:
                    await status_msg.edit("❌ No contacts found in source account")
                    return
                
                await status_msg.edit(
                    f"📥 Found {len(result.users)} contacts\n\n"
                    f"Importing to {target_name}..."
                )
                
                # Import contacts to target
                from telethon.tl.functions.contacts import ImportContactsRequest
                from telethon.tl.types import InputPhoneContact
                
                contacts_to_import = []
                for user in result.users:
                    if user.phone:
                        contact = InputPhoneContact(
                            client_id=user.id,
                            phone=user.phone,
                            first_name=user.first_name or "User",
                            last_name=user.last_name or ""
                        )
                        contacts_to_import.append(contact)
                
                if not contacts_to_import:
                    await status_msg.edit("❌ No phone numbers found in contacts")
                    return
                
                # Import in batches of 100
                imported = 0
                batch_size = 100
                for i in range(0, len(contacts_to_import), batch_size):
                    batch = contacts_to_import[i:i+batch_size]
                    try:
                        await target_client(ImportContactsRequest(batch))
                        imported += len(batch)
                        
                        await status_msg.edit(
                            f"📥 Importing contacts...\n\n"
                            f"Progress: {imported}/{len(contacts_to_import)}"
                        )
                    except Exception as e:
                        logger.error(f"Batch import error: {e}")
                
                await status_msg.edit(
                    f"✅ **Contact Sharing Complete**\n\n"
                    f"From: {source_name}\n"
                    f"To: {target_name}\n\n"
                    f"Imported: {imported}/{len(contacts_to_import)} contacts\n\n"
                    f"You can now send messages to these users from {target_name}!"
                )
                
                logger.info(f"Shared {imported} contacts from {source_name} to {target_name}")
                
            except Exception as e:
                await status_msg.edit(f"❌ Contact sharing failed: {str(e)}")
                logger.error(f"Contact sharing error: {e}")
