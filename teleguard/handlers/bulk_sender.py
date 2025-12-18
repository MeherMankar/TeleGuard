"""Bulk Message Sender - Send messages to multiple users at once"""
import asyncio
import logging
import re
from typing import List, Dict
from telethon import events
from ..core.mongo_database import mongodb
from ..core.config import ADMIN_IDS
from ..core.rate_limiter import rate_limiter
from ..core.session_health import session_health
logger = logging.getLogger(__name__)
class BulkSender:
    """Handles bulk message sending operations"""
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.user_clients = bot_manager.user_clients
        self.active_jobs = {}
    def register_handlers(self):
        """Register bulk sender command handlers"""
        @self.bot.on(events.NewMessage(pattern=r'^/bulk_send$'))
        async def bulk_send_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            await event.reply(
                "📤 **Bulk Message Sender**\n\n"
                "Send messages to multiple users at once.\n\n"
                "**Commands:**\n"
                "• `/bulk_send_list` - Send to a list of usernames/IDs\n"
                "• `/bulk_send_contacts` - Send to all contacts\n"
                "• `/bulk_send_all` - Send from ALL accounts\n"
                "• `/bulk_jobs` - View active jobs\n"
                "• `/bulk_stop <job_id>` - Stop a job\n\n"
                "**Format for list:**\n"
                "`/bulk_send_list account_name\n"
                "username1,username2,user_id3\n"
                "Your message here`\n\n"
                "**Button Format:**\n"
                "Add buttons using: `[Button Text](url)` or `[Button Text](callback_data)`\n"
                "Example: `Check this out [Visit Site](https://example.com) [More Info](info_callback)`"
            )
        @self.bot.on(events.NewMessage(pattern=r'^/bulk_send_list\s+(.+)'))
        async def bulk_send_list_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            try:
                lines = event.text.split('\n', 2)
                if len(lines) < 3:
                    await event.reply("❌ Invalid format. Use:\n`/bulk_send_list account_name\nuser1,user2\nMessage`")
                    return
                account_name = lines[0].split()[1]
                targets = [t.strip() for t in lines[1].split(',')]
                message = lines[2]
                # Parse message and buttons
                message_text, buttons = self._parse_message_buttons(message)
                job_id = await self._start_bulk_job(event.sender_id, account_name, targets, message_text, event, buttons=buttons)
                if job_id:
                    await event.reply(f"✅ Bulk send job started: `{job_id}`\nSending to {len(targets)} targets...")
            except Exception as e:
                await event.reply(f"❌ Error: {str(e)}")
        @self.bot.on(events.NewMessage(pattern=r'^/bulk_send_contacts\s+(\S+)\s+(.+)'))
        async def bulk_send_contacts_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            try:
                parts = event.text.split(' ', 2)
                account_name = parts[1]
                message = parts[2]
                # Parse message and buttons
                message_text, buttons = self._parse_message_buttons(message)
                targets = await self._get_account_contacts(event.sender_id, account_name)
                if not targets:
                    await event.reply("❌ No contacts found for this account")
                    return
                job_id = await self._start_bulk_job(event.sender_id, account_name, targets, message_text, event, buttons=buttons)
                if job_id:
                    await event.reply(f"✅ Bulk send job started: `{job_id}`\nSending to {len(targets)} contacts...")
            except Exception as e:
                await event.reply(f"❌ Error: {str(e)}")
        @self.bot.on(events.NewMessage(pattern=r'^/bulk_send_all\s+(.+)'))
        async def bulk_send_all_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            try:
                lines = event.text.split('\n', 1)
                if len(lines) < 2:
                    await event.reply("❌ Invalid format. Use:\n`/bulk_send_all\nuser1,user2\nMessage`")
                    return
                targets = [t.strip() for t in lines[0].split('\n')[0].split(',')]
                message = lines[1]
                user_accounts = list(self.user_clients.get(event.sender_id, {}).keys())
                if not user_accounts:
                    await event.reply("❌ No accounts found")
                    return
                await event.reply(f"🚀 Starting bulk send from {len(user_accounts)} accounts to {len(targets)} targets...")
                jobs = []
                for account_name in user_accounts:
                    job_id = await self._start_bulk_job(event.sender_id, account_name, targets, message, event, multi_account=True)
                    if job_id:
                        jobs.append(job_id)
                if jobs:
                    await event.reply(f"✅ Started {len(jobs)} bulk jobs from all accounts")
            except Exception as e:
                await event.reply(f"❌ Error: {str(e)}")
        @self.bot.on(events.NewMessage(pattern=r'^/bulk_jobs$'))
        async def bulk_jobs_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            user_jobs = [job for job in self.active_jobs.values() if job['user_id'] == event.sender_id]
            if not user_jobs:
                await event.reply("📭 No active bulk jobs")
                return
            status_text = "📊 **Active Bulk Jobs:**\n\n"
            for job in user_jobs:
                progress = f"{job['sent']}/{job['total']}"
                account_info = f" [{job['account_name']}]" if job.get('multi_account') else ""
                status_text += f"🔹 `{job['id'][:8]}` - {progress} ({job['status']}){account_info}\n"
            await event.reply(status_text)
        @self.bot.on(events.NewMessage(pattern=r'^/bulk_stop\s+(\S+)$'))
        async def bulk_stop_command(event):
            if not event.is_private or event.sender_id not in ADMIN_IDS:
                return
            job_id = event.pattern_match.group(1)
            # Find job by partial ID
            full_job_id = None
            for jid in self.active_jobs:
                if jid.startswith(job_id):
                    full_job_id = jid
                    break
            if not full_job_id or self.active_jobs[full_job_id]['user_id'] != event.sender_id:
                await event.reply("❌ Job not found")
                return
            self.active_jobs[full_job_id]['status'] = 'stopped'
            await event.reply(f"⏹️ Job `{job_id}` stopped")
    async def _start_bulk_job(self, user_id: int, account_name: str, targets: List[str], message: str, event, multi_account: bool = False, buttons: List = None) -> str:
        """Start a bulk sending job"""
        try:
            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client:
                await event.reply(f"❌ Account `{account_name}` not found")
                return None
            
            # Get account phone for rate limiting
            account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
            account_phone = account.get('phone') if account else account_name
            
            # Check rate limit
            can_perform, error_msg = rate_limiter.can_perform(account_phone, 'bulk_send')
            if not can_perform:
                await event.reply(error_msg)
                return None
            
            # Check session health
            is_healthy, health_msg = await session_health.check_session(client, account_phone)
            if not is_healthy:
                await event.reply(f"⚠️ Session health check failed: {health_msg}\nProceed with caution.")
            
            # Record operation
            rate_limiter.record_operation(account_phone, 'bulk_send')
            rate_limiter.record_operation(account_phone, 'message', len(targets))
            import time
            job_id = f"bulk_{account_name}_{int(time.time())}"
            job = {
                'id': job_id,
                'user_id': user_id,
                'account_name': account_name,
                'targets': targets,
                'message': message,
                'buttons': buttons or [],
                'total': len(targets),
                'sent': 0,
                'failed': 0,
                'status': 'running',
                'event': event,
                'multi_account': multi_account
            }
            self.active_jobs[job_id] = job
            asyncio.create_task(self._execute_bulk_job(job_id, client))
            return job_id
        except Exception as e:
            logger.error(f"Failed to start bulk job: {e}")
            return None
    async def _execute_bulk_job(self, job_id: str, client):
        """Execute bulk sending job"""
        job = self.active_jobs.get(job_id)
        if not job:
            return
        
        status_msg = None
        try:
            # Send initial status
            status_msg = await job['event'].reply(
                f"🚀 **Campaign Started**\n\n"
                f"Account: {job['account_name']}\n"
                f"Total Users: {job['total']}\n"
                f"Sent: 0/{job['total']}\n"
                f"Progress: ░░░░░░░░░░ 0%"
            )
            
            for i, target in enumerate(job['targets']):
                if job['status'] != 'running':
                    break
                
                try:
                    # Resolve target with access_hash from source account
                    entity = None
                    try:
                        if target.startswith('@'):
                            entity = await client.get_entity(target)
                        elif target.isdigit():
                            user_id = int(target)
                            
                            # Try direct resolution first
                            try:
                                entity = await client.get_entity(user_id)
                            except:
                                # Get access_hash from any account that has this user
                                access_hash = await self._get_access_hash_from_any_account(
                                    job['user_id'], user_id
                                )
                                
                                if access_hash:
                                    # Use InputPeerUser with access_hash
                                    from telethon.tl.types import InputPeerUser
                                    entity = InputPeerUser(user_id, access_hash)
                                    logger.info(f"Using access_hash for user {user_id}")
                                else:
                                    logger.warning(f"No access_hash found for {user_id}")
                                    job['failed'] += 1
                                    continue
                        else:
                            entity = await client.get_entity(target)
                    except Exception as e:
                        logger.error(f"Failed to resolve {target}: {e}")
                        job['failed'] += 1
                        continue
                    
                    if not entity:
                        job['failed'] += 1
                        continue
                    
                    # Send message
                    if job['buttons']:
                        from telethon.tl.types import KeyboardButtonUrl, KeyboardButtonCallback
                        from telethon.tl.types import ReplyInlineMarkup
                        keyboard_rows = []
                        current_row = []
                        for btn in job['buttons']:
                            if btn['type'] == 'url':
                                button = KeyboardButtonUrl(btn['text'], btn['data'])
                            else:
                                button = KeyboardButtonCallback(btn['text'], btn['data'].encode())
                            current_row.append(button)
                            if len(current_row) >= 2:
                                keyboard_rows.append(current_row)
                                current_row = []
                        if current_row:
                            keyboard_rows.append(current_row)
                        markup = ReplyInlineMarkup(keyboard_rows) if keyboard_rows else None
                        await client.send_message(entity, job['message'], buttons=markup)
                    else:
                        await client.send_message(entity, job['message'])
                    
                    job['sent'] += 1
                    logger.info(f"✅ Sent to {target} ({job['sent']}/{job['total']})")
                    
                    # Record message operation for rate limiting
                    account = await mongodb.db.accounts.find_one({"user_id": job['user_id'], "name": job['account_name']})
                    if account:
                        rate_limiter.record_operation(account.get('phone', job['account_name']), 'message')
                    
                    # Update progress every 5 messages or at milestones
                    if (i + 1) % 5 == 0 or (i + 1) == job['total']:
                        progress_pct = int((job['sent'] / job['total']) * 100)
                        progress_bar = '■' * (progress_pct // 10) + '░' * (10 - progress_pct // 10)
                        
                        if status_msg:
                            try:
                                await status_msg.edit(
                                    f"📤 **Campaign Running**\n\n"
                                    f"Account: {job['account_name']}\n"
                                    f"Total Users: {job['total']}\n"
                                    f"Sent: {job['sent']}/{job['total']}\n"
                                    f"Failed: {job['failed']}\n"
                                    f"Progress: {progress_bar} {progress_pct}%"
                                )
                            except:
                                pass
                    
                    # Rate limiting - 8-15 seconds between messages (human-like)
                    import random
                    await asyncio.sleep(random.uniform(8, 15))
                    
                except Exception as e:
                    job['failed'] += 1
                    error_msg = str(e)
                    logger.error(f"❌ Failed to send to {target}: {error_msg}")
                    
                    # Check for flood wait
                    if 'FloodWaitError' in error_msg or 'FLOOD_WAIT' in error_msg:
                        import re
                        wait_match = re.search(r'(\d+)', error_msg)
                        if wait_match:
                            wait_time = int(wait_match.group(1))
                            if status_msg:
                                await status_msg.edit(
                                    f"⏸️ **Rate Limited**\n\n"
                                    f"Waiting {wait_time} seconds...\n"
                                    f"Sent: {job['sent']}/{job['total']}"
                                )
                            await asyncio.sleep(wait_time)
            
            # Job completed
            job['status'] = 'completed'
            
            if status_msg:
                await status_msg.edit(
                    f"✅ **Campaign Completed**\n\n"
                    f"Account: {job['account_name']}\n"
                    f"Total Users: {job['total']}\n"
                    f"Sent: {job['sent']}/{job['total']}\n"
                    f"Failed: {job['failed']}\n"
                    f"Progress: ■■■■■■■■■■ 100%"
                )
            
        except Exception as e:
            job['status'] = 'error'
            logger.error(f"Bulk job error: {e}")
            if status_msg:
                await status_msg.edit(
                    f"❌ **Campaign Failed**\n\n"
                    f"Error: {str(e)}\n"
                    f"Sent: {job['sent']}/{job['total']}"
                )
        finally:
            # Clean up after 1 hour
            await asyncio.sleep(3600)
            self.active_jobs.pop(job_id, None)
    async def _update_job_progress(self, job: Dict, final: bool = False):
        """Update job progress"""
        try:
            progress = f"{job['sent']}/{job['total']}"
            failed_text = f", {job['failed']} failed" if job['failed'] > 0 else ""
            if final:
                status_emoji = "✅" if job['status'] == 'completed' else "⏹️"
                text = f"{status_emoji} **Bulk job completed**\n\n📊 **Results:**\n• Sent: {job['sent']}\n• Failed: {job['failed']}\n• Total: {job['total']}"
            else:
                text = f"📤 **Bulk sending progress:** {progress}{failed_text}"
            await job['event'].reply(text)
        except Exception as e:
            logger.error(f"Failed to update job progress: {e}")
    async def _get_account_contacts(self, user_id: int, account_name: str) -> List[str]:
        """Get all contacts for an account"""
        try:
            client = self.user_clients.get(user_id, {}).get(account_name)
            if not client:
                return []
            contacts = []
            async for dialog in client.iter_dialogs():
                if dialog.is_user and not dialog.entity.bot:
                    if dialog.entity.username:
                        contacts.append(dialog.entity.username)
                    else:
                        contacts.append(str(dialog.entity.id))
            return contacts
        except Exception as e:
            logger.error(f"Failed to get contacts: {e}")
            return []
    async def _get_access_hash_from_any_account(self, user_id: int, target_user_id: int):
        """Get access_hash for a user from any account that has them"""
        try:
            # Try all user's accounts
            for account_name, client in self.user_clients.get(user_id, {}).items():
                if not client or not client.is_connected():
                    continue
                
                try:
                    # Try to get entity from this account
                    entity = await client.get_entity(target_user_id)
                    if hasattr(entity, 'access_hash') and entity.access_hash:
                        logger.info(f"Found access_hash from {account_name}")
                        return entity.access_hash
                except:
                    continue
            
            return None
        except Exception as e:
            logger.error(f"Failed to get access_hash: {e}")
            return None
    
    def _parse_message_buttons(self, message: str) -> tuple:
        """Parse message text and extract buttons"""
        import re
        # Find all button patterns: [Text](url_or_callback)
        button_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        buttons = []
        for match in re.finditer(button_pattern, message):
            text = match.group(1)
            data = match.group(2)
            # Determine if it's URL or callback
            if data.startswith('http://') or data.startswith('https://'):
                button_type = 'url'
            else:
                button_type = 'callback'
            buttons.append({
                'text': text,
                'data': data,
                'type': button_type
            })
        clean_message = re.sub(button_pattern, '', message).strip()
        return clean_message, buttons
