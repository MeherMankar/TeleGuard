"""
IP Change Handler for Koyeb Dynamic IPs
Handles session stability when IP addresses change frequently
"""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

class IPChangeHandler:
    """Handle IP changes for cloud platforms like Koyeb"""
    
    def __init__(self):
        self.current_ip: Optional[str] = None
        self.last_check = 0
        self.change_count = 0
    
    async def get_current_ip(self) -> Optional[str]:
        """Get current public IP address"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.ipify.org?format=json', timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('ip')
        except Exception as e:
            logger.warning(f"Failed to get IP: {e}")
        return None
    
    async def check_and_handle_change(self) -> bool:
        """Check for IP change and handle if needed"""
        current_time = time.time()
        
        # Check every 5 minutes
        if current_time - self.last_check < 300:
            return False
        
        self.last_check = current_time
        new_ip = await self.get_current_ip()
        
        if not new_ip:
            return False
        
        if self.current_ip and self.current_ip != new_ip:
            self.change_count += 1
            logger.info(f"IP changed: {self.current_ip} -> {new_ip} (#{self.change_count})")
            
            # Handle the change
            await self._handle_ip_change(self.current_ip, new_ip)
            self.current_ip = new_ip
            return True
        
        if not self.current_ip:
            self.current_ip = new_ip
            logger.info(f"Initial IP detected: {new_ip}")
        
        return False
    
    async def _handle_ip_change(self, old_ip: str, new_ip: str):
        """Handle IP change with session warmup"""
        logger.info(f"Handling IP change from {old_ip} to {new_ip}")
        
        # Wait a bit for network to stabilize
        await asyncio.sleep(10)
        
        # Perform gentle session warmup
        await self._session_warmup()
    
    async def _session_warmup(self):
        """Gentle session warmup after IP change"""
        try:
            from ..core.bot_manager import bot_manager
            
            if not bot_manager or not bot_manager.clients:
                return
            
            # Use first available client for warmup
            client = next(iter(bot_manager.clients.values()))
            
            # Gentle operations with delays
            operations = [
                ('ping', lambda: client.get_me()),
                ('check_dialogs', lambda: client.get_dialogs(limit=1)),
            ]
            
            for op_name, op_func in operations:
                try:
                    await asyncio.sleep(5)  # Wait between operations
                    await op_func()
                    logger.debug(f"Warmup {op_name} completed")
                except Exception as e:
                    logger.warning(f"Warmup {op_name} failed: {e}")
            
            logger.info("Session warmup completed")
            
        except Exception as e:
            logger.error(f"Session warmup failed: {e}")

# Global instance
ip_handler = IPChangeHandler()

async def monitor_ip_changes():
    """Background task to monitor IP changes"""
    while True:
        try:
            await ip_handler.check_and_handle_change()
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            logger.error(f"IP monitoring error: {e}")
            await asyncio.sleep(300)  # Wait 5 minutes on error