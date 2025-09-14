"""Chat Import Handler - Retroactively imports existing private chats into topic system"""

import asyncio
import logging
from telethon import events, types
from telethon.tl.types import User, Chat, Channel
from ..core.mongo_database import mongodb
from ..core.config import ADMIN_IDS

logger = logging.getLogger(__name__)


class ChatImportHandler:
    """Handles importing existing private chats into the topic system"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.unified_messaging = bot_manager.unified_messaging
        
    def register_handlers(self):
        """Register the import chats command handler"""
        
        @self.bot.on(events.NewMessage(pattern=r'^/import_chats$'))
        async def import_chats_command(event):
            if not event.is_private:
                return
                
            user_id = event.sender_id
            
            # Check if user is admin
            if user_id not in ADMIN_IDS:
                await event.reply("❌ This command is only available to administrators.")
                return
            
            # Check if user has configured admin group
            admin_group_id = await self.unified_messaging._get_user_admin_group(user_id)
            if not admin_group_id:
                await event.reply(
                    "❌ Please configure your admin group first using /set_dm_group before importing chats."
                )
                return
            
            await event.reply(
                "🚀 **Starting Chat Import**\n\n"
                "This will import all existing private conversations into your admin group as topics.\n\n"
                "⏳ This may take several minutes depending on the number of accounts and conversations..."
            )
            
            # Start the import process
            await self._import_all_chats(user_id, admin_group_id, event)
    
    async def _import_all_chats_silent(self, user_id: int, admin_group_id: int):
        """Import all existing private chats silently (no user feedback)"""
        try:
            total_accounts = 0
            total_topics_created = 0
            
            # Get all managed accounts for this user
            user_clients = self.bot_manager.user_clients.get(user_id, {})
            
            if not user_clients:
                return
            
            for account_name, client in user_clients.items():
                if not client or not client.is_connected():
                    continue
                
                total_accounts += 1
                
                try:
                    # Get account info
                    me = await client.get_me()
                    account_id = me.id
                    
                    # Process this account's chats
                    account_topics, _ = await self._process_account_chats(
                        client, account_id, admin_group_id, account_name
                    )
                    
                    total_topics_created += account_topics
                    
                    # Rate limiting between accounts
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error processing account {account_name}: {e}")
                    continue
            
            if total_topics_created > 0:
                logger.info(f"Auto-imported {total_topics_created} topics for user {user_id}")
            
        except Exception as e:
            logger.error(f"Silent chat import failed for user {user_id}: {e}")
        
        @self.bot.on(events.NewMessage(pattern=r'^/check_admin_group$'))
        async def check_admin_group_command(event):
            if not event.is_private:
                return
                
            user_id = event.sender_id
            
            if user_id not in ADMIN_IDS:
                await event.reply("❌ This command is only available to administrators.")
                return
            
            try:
                admin_group_id = await self.unified_messaging._get_user_admin_group(user_id)
                if not admin_group_id:
                    await event.reply("❌ No admin group configured. Use /set_dm_group first.")
                    return
                
                # Get group info
                chat_info = await self.bot.get_entity(admin_group_id)
                is_forum = getattr(chat_info, 'forum', False)
                
                # Check bot permissions
                try:
                    permissions = await self.bot.get_permissions(admin_group_id, 'me')
                    can_manage_topics = getattr(permissions, 'manage_topics', False)
                    is_admin = permissions.is_admin
                except Exception as perm_error:
                    can_manage_topics = False
                    is_admin = False
                
                status_text = (
                    f"🔍 **Admin Group Status**\n\n"
                    f"📱 **Group ID:** `{admin_group_id}`\n"
                    f"📝 **Group Name:** {getattr(chat_info, 'title', 'Unknown')}\n"
                    f"🏛️ **Is Forum:** {'✅ Yes' if is_forum else '❌ No'}\n"
                    f"👑 **Bot is Admin:** {'✅ Yes' if is_admin else '❌ No'}\n"
                    f"🎯 **Can Manage Topics:** {'✅ Yes' if can_manage_topics else '❌ No'}\n\n"
                )
                
                if not is_forum:
                    status_text += (
                        "⚠️ **Issue Found:**\n"
                        "Your admin group is not a Forum group. Topics cannot be created.\n\n"
                        "**To fix:**\n"
                        "1. Go to your group settings\n"
                        "2. Enable 'Topics' feature\n"
                        "3. Try importing chats again"
                    )
                elif not is_admin or not can_manage_topics:
                    status_text += (
                        "⚠️ **Issue Found:**\n"
                        "Bot doesn't have proper permissions.\n\n"
                        "**To fix:**\n"
                        "1. Make the bot an admin in your group\n"
                        "2. Give it 'Manage Topics' permission\n"
                        "3. Try importing chats again"
                    )
                else:
                    status_text += "✅ **All checks passed!** Your group is ready for topic creation."
                
                await event.reply(status_text)
                
            except Exception as e:
                await event.reply(f"❌ Error checking admin group: {str(e)}")
        
        @self.bot.on(events.NewMessage(pattern=r'^/import_help$'))
        async def import_help_command(event):
            if not event.is_private:
                return
                
            user_id = event.sender_id
            
            if user_id not in ADMIN_IDS:
                await event.reply("❌ This command is only available to administrators.")
                return
            
            help_text = (
                "📚 **Chat Import Help**\n\n"
                "**Commands:**\n"
                "• `/import_chats` - Import all existing chats\n"
                "• `/check_admin_group` - Check group configuration\n\n"
                "**What import does:**\n"
                "• Scans all your managed accounts\n"
                "• Finds existing private conversations\n"
                "• Creates topics for each conversation\n"
                "• Imports last 5 messages for context\n\n"
                "**Requirements:**\n"
                "• Admin group must be configured (`/set_dm_group`)\n"
                "• Group must have Topics enabled\n"
                "• Bot must have admin permissions\n\n"
                "**Troubleshooting:**\n"
                "1. Run `/check_admin_group` first\n"
                "2. Fix any issues it reports\n"
                "3. Then run `/import_chats`\n\n"
                "**Note:** This is a one-time setup command. New conversations will automatically create topics."
            )
            
            await event.reply(help_text)
    
    async def _import_all_chats(self, user_id: int, admin_group_id: int, event):
        """Import all existing private chats for the user"""
        try:
            total_accounts = 0
            total_topics_created = 0
            total_chats_processed = 0
            
            # Get all managed accounts for this user
            user_clients = self.bot_manager.user_clients.get(user_id, {})
            
            if not user_clients:
                await event.reply(
                    "❌ **No Managed Accounts Found**\n\n"
                    "Please add some accounts first using the Account Settings menu."
                )
                return
            
            # Send progress update
            progress_msg = await event.reply(
                f"🔄 **Processing {len(user_clients)} accounts...**\n\n"
                "This may take a while. Please wait..."
            )
            
            for account_name, client in user_clients.items():
                if not client or not client.is_connected():
                    logger.warning(f"Skipping disconnected client: {account_name}")
                    continue
                
                total_accounts += 1
                logger.info(f"Processing account: {account_name}")
                
                try:
                    # Get account info
                    me = await client.get_me()
                    account_id = me.id
                    
                    # Update progress
                    try:
                        await progress_msg.edit(
                            f"🔄 **Processing Account {total_accounts}/{len(user_clients)}**\n\n"
                            f"📱 Current: {account_name}\n"
                            f"📊 Progress: {total_chats_processed} chats, {total_topics_created} topics\n\n"
                            "Please wait..."
                        )
                    except Exception:
                        pass  # Continue if progress update fails
                    
                    # Process this account's chats
                    account_topics, account_chats = await self._process_account_chats(
                        client, account_id, admin_group_id, account_name
                    )
                    
                    total_topics_created += account_topics
                    total_chats_processed += account_chats
                    
                    # Rate limiting between accounts
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    logger.error(f"Error processing account {account_name}: {e}")
                    continue
            
            # Update progress message with final results
            try:
                await progress_msg.edit(
                    f"✅ **Chat Import Complete!**\n\n"
                    f"📊 **Final Summary:**\n"
                    f"• Accounts processed: {total_accounts}\n"
                    f"• Private chats found: {total_chats_processed}\n"
                    f"• New topics created: {total_topics_created}\n\n"
                    f"🎉 All existing conversations are now available in your admin group!\n\n"
                    f"📝 **Next Steps:**\n"
                    f"• Check your admin group for new topics\n"
                    f"• Reply in any topic to respond to users\n"
                    f"• New conversations will auto-create topics"
                )
            except Exception:
                # Fallback if edit fails
                await event.reply(
                    f"✅ **Import Complete:** {total_accounts} accounts, {total_chats_processed} chats, {total_topics_created} new topics created!"
                )
            
            logger.info(f"Chat import completed for user {user_id}: {total_accounts} accounts, {total_topics_created} topics created")
            
        except Exception as e:
            logger.error(f"Chat import failed for user {user_id}: {e}")
            try:
                await progress_msg.edit(
                    f"❌ **Import Failed**\n\n"
                    f"Error: {str(e)}\n\n"
                    f"Please try again or contact support if the issue persists."
                )
            except Exception:
                await event.reply(f"❌ Import failed: {str(e)}")
    
    async def _process_account_chats(self, client, account_id: int, admin_group_id: int, account_name: str):
        """Process all chats for a specific account"""
        topics_created = 0
        chats_processed = 0
        
        try:
            # Get all dialogs (conversations)
            dialogs = await client.get_dialogs()
            logger.info(f"Found {len(dialogs)} dialogs for {account_name}")
            
            for dialog in dialogs:
                try:
                    # Filter for private chats only
                    if not self._is_private_user_chat(dialog.entity):
                        continue
                    
                    chats_processed += 1
                    user_entity = dialog.entity
                    
                    # Check if topic already exists
                    existing_topic = await self.unified_messaging._find_existing_topic(
                        admin_group_id, user_entity.id, account_id
                    )
                    
                    if existing_topic:
                        logger.info(f"Topic {existing_topic} already exists for {user_entity.id} -> {account_id}")
                        continue
                    
                    # Create new topic with conversation history
                    topic_created = await self._create_topic_with_history(
                        client, admin_group_id, user_entity, account_id, dialog
                    )
                    
                    if topic_created:
                        topics_created += 1
                        logger.info(f"Created topic for {user_entity.id} -> {account_id}")
                    
                    # Rate limiting between chats
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing dialog with {getattr(dialog.entity, 'id', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Account {account_name}: {chats_processed} chats processed, {topics_created} topics created")
            return topics_created, chats_processed
            
        except Exception as e:
            logger.error(f"Error getting dialogs for {account_name}: {e}")
            return 0, 0
    
    def _is_private_user_chat(self, entity) -> bool:
        """Check if the entity is a private chat with a real user"""
        # Must be a User (not Channel or Chat)
        if not isinstance(entity, User):
            return False
        
        # Skip bots
        if getattr(entity, 'bot', False):
            return False
        
        # Skip deleted accounts
        if getattr(entity, 'deleted', False):
            return False
        
        # Skip self (shouldn't happen but just in case)
        if getattr(entity, 'is_self', False):
            return False
        
        return True
    
    async def _create_topic_with_history(self, client, admin_group_id: int, user_entity, account_id: int, dialog):
        """Create a new topic and import recent conversation history"""
        try:
            logger.info(f"Creating topic for {user_entity.id} -> {account_id} in group {admin_group_id}")
            
            # Create the topic using unified messaging system  
            topic_id = await self.unified_messaging._find_or_create_topic(
                admin_group_id, user_entity.id, account_id, user_entity, 0  # Use 0 as dummy user_id for import
            )
            
            if not topic_id:
                logger.error(f"Failed to create topic for {user_entity.id} -> {account_id}")
                return False
            
            # Fetch recent messages (last 5 messages)
            try:
                messages = await client.get_messages(user_entity, limit=5)
                
                if messages:
                    # Reverse to get chronological order (oldest first)
                    messages.reverse()
                    
                    # Import messages into the topic
                    await self._import_messages_to_topic(
                        admin_group_id, topic_id, messages, user_entity, account_id
                    )
                    
                    logger.info(f"Imported {len(messages)} messages for topic {topic_id}")
                
            except Exception as e:
                logger.warning(f"Could not fetch messages for {user_entity.id}: {e}")
                # Topic was created successfully even if we couldn't get messages
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create topic with history for {user_entity.id}: {e}")
            return False
    
    async def _import_messages_to_topic(self, admin_group_id: int, topic_id: int, messages, user_entity, account_id: int):
        """Import messages into the topic with proper formatting"""
        try:
            # Get account info for display
            account_info = await self._get_account_display_name(account_id)
            user_name = self.unified_messaging._get_topic_title(user_entity)
            
            # Send context header
            context_header = (
                f"📚 **Conversation History**\n"
                f"👤 **User:** {user_name}\n"
                f"📱 **Account:** {account_info}\n"
                f"📅 **Last {len(messages)} messages:**\n"
                f"{'─' * 30}"
            )
            
            await self.bot.send_message(
                admin_group_id,
                context_header,
                reply_to=topic_id,
                parse_mode='md'
            )
            
            # Import each message
            for i, message in enumerate(messages):
                try:
                    await self._format_and_send_message(
                        admin_group_id, topic_id, message, user_entity, account_info
                    )
                    
                    # Small delay between messages
                    if i < len(messages) - 1:
                        await asyncio.sleep(0.5)
                        
                except Exception as e:
                    logger.error(f"Error importing message {message.id}: {e}")
                    continue
            
            # Send footer
            footer = f"{'─' * 30}\n✅ **History import complete**"
            await self.bot.send_message(
                admin_group_id,
                footer,
                reply_to=topic_id,
                parse_mode='md'
            )
            
        except Exception as e:
            logger.error(f"Error importing messages to topic {topic_id}: {e}")
    
    async def _format_and_send_message(self, admin_group_id: int, topic_id: int, message, user_entity, account_info):
        """Format and send a single message to the topic"""
        try:
            # Determine sender
            if message.out:
                sender_name = f"📱 {account_info}"
                direction = "→"
            else:
                sender_name = f"👤 {self.unified_messaging._get_topic_title(user_entity)}"
                direction = "←"
            
            # Format timestamp
            timestamp = message.date.strftime("%m/%d %H:%M")
            
            # Handle different message types
            if message.text:
                content = message.text
                if len(content) > 200:
                    content = content[:200] + "..."
            elif message.media:
                content = "[Media/File]"
            else:
                content = "[Message]"
            
            # Format the message
            formatted_message = (
                f"{direction} **{sender_name}** `{timestamp}`\n"
                f"{content}"
            )
            
            await self.bot.send_message(
                admin_group_id,
                formatted_message,
                reply_to=topic_id,
                parse_mode='md'
            )
            
        except Exception as e:
            logger.error(f"Error formatting message: {e}")
    
    async def _get_account_display_name(self, account_id: int) -> str:
        """Get display name for account"""
        try:
            # Find account in database
            account = await mongodb.db.accounts.find_one({"user_id": {"$exists": True}})
            if account:
                return account.get("name", f"ID: {account_id}")
            return f"ID: {account_id}"
        except Exception:
            return f"ID: {account_id}"