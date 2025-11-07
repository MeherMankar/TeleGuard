"""Session Protection - Prevent Telegram from forcibly ending sessions"""

import asyncio
import random
import logging
import time
from typing import Dict, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SessionProtection:
    """Comprehensive session protection to prevent forced session termination"""
    
    def __init__(self):
        self.activity_tracker: Dict[str, Dict] = {}  # Track activity per session
        self.rate_limits: Dict[str, Dict] = {}  # Rate limiting per session
        self.last_activity: Dict[str, float] = {}  # Last activity timestamp
        self.session_health: Dict[str, Dict] = {}  # Session health metrics
        
    def register_session(self, session_id: str, account_name: str):
        """Register a session for protection"""
        self.activity_tracker[session_id] = {
            'account_name': account_name,
            'messages_sent': 0,
            'joins_today': 0,
            'last_message_time': 0,
            'last_join_time': 0,
            'daily_reset': time.time(),
            'suspicious_activity': 0,
            'protection_level': 'normal'  # normal, high, maximum
        }
        
        self.rate_limits[session_id] = {
            'messages_per_hour': 0,
            'joins_per_day': 0,
            'hour_reset': time.time(),
            'day_reset': time.time()
        }
        
        self.session_health[session_id] = {
            'health_score': 100,
            'risk_level': 'low',
            'last_check': time.time(),
            'warnings': []
        }
        
        logger.info(f"Session protection enabled for {account_name}")
    
    async def check_message_safety(self, session_id: str, message_content: str = "", target: str = "") -> bool:
        """Check if sending a message is safe"""
        # Check if protection is bypassed for appeals
        if await self._is_protection_bypassed(session_id):
            return True
            
        if session_id not in self.activity_tracker:
            return False
            
        tracker = self.activity_tracker[session_id]
        limits = self.rate_limits[session_id]
        
        # Reset counters if needed
        current_time = time.time()
        if current_time - limits['hour_reset'] > 3600:  # 1 hour
            limits['messages_per_hour'] = 0
            limits['hour_reset'] = current_time
            
        if current_time - tracker['daily_reset'] > 86400:  # 24 hours
            tracker['joins_today'] = 0
            tracker['daily_reset'] = current_time
        
        # Check rate limits
        if limits['messages_per_hour'] >= self._get_message_limit(tracker['protection_level']):
            logger.warning(f"Message rate limit reached for {tracker['account_name']}")
            return False
            
        # Check message content for spam indicators
        if self._is_suspicious_message(message_content):
            tracker['suspicious_activity'] += 1
            logger.warning(f"Suspicious message detected for {tracker['account_name']}")
            return False
            
        # Check time between messages
        time_since_last = current_time - tracker['last_message_time']
        min_delay = self._get_min_message_delay(tracker['protection_level'])
        
        if time_since_last < min_delay:
            wait_time = min_delay - time_since_last
            logger.info(f"Rate limiting message for {tracker['account_name']}, waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
        
        return True
    
    async def record_message_sent(self, session_id: str):
        """Record that a message was sent"""
        if session_id not in self.activity_tracker:
            return
            
        tracker = self.activity_tracker[session_id]
        limits = self.rate_limits[session_id]
        
        tracker['messages_sent'] += 1
        tracker['last_message_time'] = time.time()
        limits['messages_per_hour'] += 1
        
        # Add human-like delay after sending
        delay = random.uniform(1.0, 3.0)
        await asyncio.sleep(delay)
    
    async def check_join_safety(self, session_id: str, chat_info: str = "") -> bool:
        """Check if joining a chat/channel is safe"""
        # Check if protection is bypassed for appeals
        if await self._is_protection_bypassed(session_id):
            return True
            
        if session_id not in self.activity_tracker:
            return False
            
        tracker = self.activity_tracker[session_id]
        limits = self.rate_limits[session_id]
        
        # Reset daily counter if needed
        current_time = time.time()
        if current_time - tracker['daily_reset'] > 86400:
            tracker['joins_today'] = 0
            limits['joins_per_day'] = 0
            tracker['daily_reset'] = current_time
        
        # Check daily join limit
        max_joins = self._get_join_limit(tracker['protection_level'])
        if limits['joins_per_day'] >= max_joins:
            logger.warning(f"Daily join limit reached for {tracker['account_name']}")
            return False
        
        # Check time between joins
        time_since_last = current_time - tracker['last_join_time']
        min_delay = self._get_min_join_delay(tracker['protection_level'])
        
        if time_since_last < min_delay:
            wait_time = min_delay - time_since_last
            logger.info(f"Rate limiting join for {tracker['account_name']}, waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
        
        return True
    
    async def record_join_action(self, session_id: str):
        """Record that a join action was performed"""
        if session_id not in self.activity_tracker:
            return
            
        tracker = self.activity_tracker[session_id]
        limits = self.rate_limits[session_id]
        
        tracker['joins_today'] += 1
        tracker['last_join_time'] = time.time()
        limits['joins_per_day'] += 1
        
        # Add human-like delay after joining
        delay = random.uniform(5.0, 15.0)  # Longer delay for joins
        await asyncio.sleep(delay)
    
    def increase_protection_level(self, session_id: str, reason: str = ""):
        """Increase protection level for a session"""
        if session_id not in self.activity_tracker:
            return
            
        tracker = self.activity_tracker[session_id]
        health = self.session_health[session_id]
        
        if tracker['protection_level'] == 'normal':
            tracker['protection_level'] = 'high'
        elif tracker['protection_level'] == 'high':
            tracker['protection_level'] = 'maximum'
            
        health['health_score'] -= 20
        health['warnings'].append(f"{datetime.now()}: {reason}")
        
        logger.warning(f"Increased protection level to {tracker['protection_level']} for {tracker['account_name']}: {reason}")
    
    def get_session_health(self, session_id: str) -> Dict:
        """Get session health information"""
        if session_id not in self.session_health:
            return {'health_score': 0, 'risk_level': 'unknown'}
            
        health = self.session_health[session_id]
        tracker = self.activity_tracker.get(session_id, {})
        
        # Calculate risk level
        if health['health_score'] > 80:
            health['risk_level'] = 'low'
        elif health['health_score'] > 60:
            health['risk_level'] = 'medium'
        elif health['health_score'] > 40:
            health['risk_level'] = 'high'
        else:
            health['risk_level'] = 'critical'
            
        return {
            'health_score': health['health_score'],
            'risk_level': health['risk_level'],
            'protection_level': tracker.get('protection_level', 'normal'),
            'messages_today': tracker.get('messages_sent', 0),
            'joins_today': tracker.get('joins_today', 0),
            'suspicious_activity': tracker.get('suspicious_activity', 0)
        }
    
    def _get_message_limit(self, protection_level: str) -> int:
        """Get message limit based on protection level"""
        limits = {
            'normal': 50,    # 50 messages per hour
            'high': 20,      # 20 messages per hour
            'maximum': 10    # 10 messages per hour
        }
        return limits.get(protection_level, 50)
    
    def _get_join_limit(self, protection_level: str) -> int:
        """Get join limit based on protection level"""
        limits = {
            'normal': 10,    # 10 joins per day
            'high': 5,       # 5 joins per day
            'maximum': 2     # 2 joins per day
        }
        return limits.get(protection_level, 10)
    
    def _get_min_message_delay(self, protection_level: str) -> float:
        """Get minimum delay between messages"""
        delays = {
            'normal': 2.0,     # 2 seconds
            'high': 5.0,       # 5 seconds
            'maximum': 10.0    # 10 seconds
        }
        return delays.get(protection_level, 2.0)
    
    def _get_min_join_delay(self, protection_level: str) -> float:
        """Get minimum delay between joins"""
        delays = {
            'normal': 300.0,    # 5 minutes
            'high': 900.0,      # 15 minutes
            'maximum': 1800.0   # 30 minutes
        }
        return delays.get(protection_level, 300.0)
    
    def _is_suspicious_message(self, content: str) -> bool:
        """Check if message content is suspicious"""
        if not content:
            return False
            
        suspicious_patterns = [
            'http://', 'https://', 't.me/', '@',  # Links and mentions
            'join', 'click', 'free', 'win', 'prize',  # Spam keywords
            '🎁', '💰', '🔥', '⚡'  # Spam emojis
        ]
        
        content_lower = content.lower()
        suspicious_count = sum(1 for pattern in suspicious_patterns if pattern in content_lower)
        
        # If more than 2 suspicious patterns, consider it risky
        return suspicious_count > 2
    
    async def _is_protection_bypassed(self, session_id: str) -> bool:
        """Check if session protection is bypassed (e.g., for appeals)"""
        try:
            # Extract user_id from session_id (format: user_id_account_name)
            parts = session_id.split('_')
            if len(parts) < 2:
                return False
            
            user_id = int(parts[0])
            
            # Check database for bypass flag
            from ..core.mongo_database import mongodb
            account = await mongodb.db.accounts.find_one({
                "user_id": user_id,
                "session_protection_disabled": True,
                "protection_bypass_until": {"$gt": time.time()}
            })
            
            return account is not None
        except Exception as e:
            logger.error(f"Error checking protection bypass: {e}")
            return False

# Global session protection instance
session_protection = SessionProtection()
