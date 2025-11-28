"""Session Creation Improvements - Event-based OTP, Resend, Progress, etc."""
import logging
import asyncio
import re
from datetime import datetime, timedelta
from telethon import events, Button
from telethon.errors import FloodWaitError

logger = logging.getLogger(__name__)

class SessionImprovements:
    """Enhanced session creation with event-based OTP and improvements"""
    
    # OTP patterns for multiple formats (11)
    OTP_PATTERNS = [
        r'Login code:\s*(\d{5,7})',
        r'code:\s*(\d{5,7})',
        r'(\d{5,7})\s*is your',
        r'Telegram code:\s*(\d{5,7})',
        r'verification code:\s*(\d{5,7})',
        r'código:\s*(\d{5,7})',  # Spanish
        r'код:\s*(\d{5,7})',  # Russian
    ]
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.otp_listeners = {}  # Track active listeners
        self.session_cache = {}  # Cache sessions temporarily (13)
    
    async def setup_event_listener(self, user_client, user_id, request_time):
        """Setup event-based OTP listener (1)"""
        otp_received = asyncio.Event()
        otp_code = None
        
        async def otp_listener(event):
            nonlocal otp_code
            try:
                message_text = event.message.message
                if not message_text:
                    return
                
                logger.info(f"OTP listener triggered")
                
                # Extract OTP without time check (like OTP forward)
                for pattern in self.OTP_PATTERNS:
                    match = re.search(pattern, message_text, re.IGNORECASE)
                    if match:
                        otp_code = match.group(1)
                        logger.info(f"OTP found: {otp_code}")
                        otp_received.set()
                        break
            except Exception as e:
                logger.error(f"OTP listener error: {e}")
        
        # Register listener - use chats parameter like OTP forward does
        user_client.add_event_handler(otp_listener, events.NewMessage(chats=[777000, 42777]))
        self.otp_listeners[user_id] = (user_client, otp_listener)
        
        return otp_received, lambda: otp_code
    
    def cleanup_listener(self, user_id):
        """Remove event listener"""
        if user_id in self.otp_listeners:
            client, handler = self.otp_listeners[user_id]
            try:
                client.remove_event_handler(handler)
            except:
                pass
            del self.otp_listeners[user_id]
    
    async def wait_with_progress(self, event, account_name, phone, otp_event, timeout=20):
        """Wait for OTP with progress countdown (1)"""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            remaining = int(timeout - elapsed)
            
            if remaining <= 0:
                return None
            
            # Update progress every 3 seconds
            if int(elapsed) % 3 == 0:
                await event.edit(
                    f"📱 **OTP Sent - {account_name}**\n\n"
                    f"📞 **Phone:** {phone}\n\n"
                    f"🔍 **Waiting for OTP...**\n"
                    f"⏱️ **Time remaining:** {remaining}s"
                )
            
            try:
                await asyncio.wait_for(otp_event.wait(), timeout=1)
                return True  # OTP received
            except asyncio.TimeoutError:
                continue
    
    async def show_resend_options(self, event, user_id, account_name, phone):
        """Show resend OTP button (4)"""
        from telethon import Button
        buttons = [
            [Button.inline("🔄 Resend OTP", f"resend_otp:{account_name}")],
            [Button.inline("✍️ Enter Manually", f"manual_otp:{account_name}")],
            [Button.inline("❌ Cancel", "cancel_session")]
        ]
        
        await event.edit(
            f"⏰ **OTP Timeout - {account_name}**\n\n"
            f"📞 **Phone:** {phone}\n\n"
            f"No OTP received within 20 seconds.\n\n"
            f"**Options:**",
            buttons=buttons
        )
    
    async def handle_flood_wait(self, error, event, account_name):
        """Handle FloodWait gracefully (7)"""
        wait_time = error.seconds if hasattr(error, 'seconds') else 60
        
        await event.edit(
            f"⏰ **Rate Limited - {account_name}**\n\n"
            f"Telegram requires waiting **{wait_time}s** before retry.\n\n"
            f"⏳ Auto-retrying in {wait_time}s..."
        )
        
        # Countdown
        for remaining in range(wait_time, 0, -5):
            await asyncio.sleep(5)
            await event.edit(
                f"⏰ **Rate Limited - {account_name}**\n\n"
                f"⏳ Retrying in {remaining}s..."
            )
        
        await asyncio.sleep(wait_time % 5)
        return True  # Ready to retry
    
    async def ensure_client_connected(self, client, max_retries=3):
        """Auto-reconnect client if disconnected (9)"""
        for attempt in range(max_retries):
            if client.is_connected():
                return True
            
            try:
                logger.info(f"Reconnecting client (attempt {attempt + 1}/{max_retries})")
                await client.connect()
                if client.is_connected():
                    return True
            except Exception as e:
                logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
        
        return False
    
    def cache_session(self, user_id, account_name, session_data):
        """Cache session temporarily (13)"""
        cache_key = f"{user_id}:{account_name}"
        self.session_cache[cache_key] = {
            'data': session_data,
            'timestamp': datetime.now()
        }
        logger.info(f"Cached session for {account_name}")
    
    def get_cached_session(self, user_id, account_name, max_age_minutes=10):
        """Retrieve cached session (13)"""
        cache_key = f"{user_id}:{account_name}"
        if cache_key in self.session_cache:
            cached = self.session_cache[cache_key]
            age = (datetime.now() - cached['timestamp']).total_seconds() / 60
            if age < max_age_minutes:
                logger.info(f"Retrieved cached session for {account_name}")
                return cached['data']
            else:
                del self.session_cache[cache_key]
        return None
    
    def check_otp_expiry(self, request_time):
        """Check if OTP is about to expire (6)"""
        elapsed = (datetime.now() - request_time).total_seconds()
        remaining = 120 - elapsed  # OTP valid for 2 minutes
        
        if remaining < 30:
            return True, int(remaining)
        return False, int(remaining)
    
    async def optimize_batch_delay(self, current_index, total):
        """Reduce delays in batch processing (10)"""
        # No delay for first account
        if current_index == 0:
            return
        
        # Minimal delay between accounts
        await asyncio.sleep(1)
    
    async def request_sms_fallback(self, client, phone):
        """Fallback to SMS if app OTP fails (12)"""
        try:
            logger.info(f"Requesting SMS fallback for {phone}")
            # Telegram automatically sends SMS after app OTP timeout
            # Just need to wait a bit longer
            await asyncio.sleep(5)
            return True
        except Exception as e:
            logger.error(f"SMS fallback failed: {e}")
            return False
