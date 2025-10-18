"""
SessionMaster Operations - Merged into TeleGuard
Complete session operations, analytics, and automation functionality
"""
import asyncio
import io
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.types import User, Channel, Chat
from telethon.errors import FloodWaitError
from ..core.config import config

logger = logging.getLogger(__name__)

async def get_comprehensive_session_info(session_string: str) -> Dict[str, Any]:
    """Get comprehensive session information with analytics"""
    try:
        client = TelegramClient(StringSession(session_string), config.telegram.api_id, config.telegram.api_hash)
        await client.connect()
        
        me = await client.get_me()
        dialogs = await client.get_dialogs()
        
        stats = {"contacts": 0, "channels": 0, "bots": 0, "groups": 0, "private_chats": 0}
        
        for dialog in dialogs:
            entity = dialog.entity
            if isinstance(entity, User):
                if getattr(entity, "bot", False):
                    stats["bots"] += 1
                else:
                    stats["private_chats"] += 1
            elif isinstance(entity, Channel):
                if getattr(entity, "broadcast", False):
                    stats["channels"] += 1
                else:
                    stats["groups"] += 1
            elif isinstance(entity, Chat):
                stats["groups"] += 1
        
        info = {
            "name": f"{me.first_name or ''} {me.last_name or ''}".strip(),
            "premium": getattr(me, "premium", False),
            "verified": getattr(me, "verified", False),
            "id": me.id,
            "username": me.username,
            "phone": me.phone,
            "dialogs": len(dialogs),
            **stats
        }
        
        await client.disconnect()
        return info
        
    except Exception as e:
        logger.error(f"Error getting session info: {e}")
        raise Exception(f"Failed to get session info: {e}")

async def bulk_subscribe_channels(session_string: str, channels: List[str], delay_range: Tuple[int, int] = (1, 3)) -> Dict[str, Any]:
    """Subscribe to multiple channels with rate limiting"""
    try:
        client = TelegramClient(StringSession(session_string), config.telegram.api_id, config.telegram.api_hash)
        await client.connect()
        
        results = {"success": [], "failed": []}
        
        for channel in channels:
            try:
                await client(JoinChannelRequest(channel))
                results["success"].append(channel)
                await asyncio.sleep(delay_range[0] + (delay_range[1] - delay_range[0]) * 0.5)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                try:
                    await client(JoinChannelRequest(channel))
                    results["success"].append(channel)
                except Exception:
                    results["failed"].append(channel)
            except Exception as e:
                results["failed"].append(channel)
                logger.error(f"Failed to subscribe to {channel}: {e}")
        
        await client.disconnect()
        return results
        
    except Exception as e:
        logger.error(f"Bulk subscribe error: {e}")
        return {"success": [], "failed": channels}

async def extract_channel_members(session_string: str, channel_username: str, limit: int = 1000) -> List[Dict[str, Any]]:
    """Extract members from a channel/group"""
    try:
        client = TelegramClient(StringSession(session_string), config.telegram.api_id, config.telegram.api_hash)
        await client.connect()
        
        channel = await client.get_entity(channel_username)
        members = []
        
        async for user in client.iter_participants(channel, limit=limit):
            if isinstance(user, User):
                member_info = {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                    "phone": user.phone,
                    "is_bot": user.bot,
                    "is_premium": getattr(user, "premium", False)
                }
                members.append(member_info)
        
        await client.disconnect()
        return members
        
    except Exception as e:
        logger.error(f"Error extracting members: {e}")
        return []

async def scrape_channel_messages(session_string: str, channel_username: str, limit: int = 1000) -> List[Dict[str, Any]]:
    """Scrape messages from a channel"""
    try:
        client = TelegramClient(StringSession(session_string), config.telegram.api_id, config.telegram.api_hash)
        await client.connect()
        
        channel = await client.get_entity(channel_username)
        messages = []
        
        async for message in client.iter_messages(channel, limit=limit):
            if message.message:
                msg_info = {
                    "id": message.id,
                    "date": message.date.isoformat(),
                    "message": message.message,
                    "sender_id": message.sender_id,
                    "views": getattr(message, "views", 0),
                    "forwards": getattr(message, "forwards", 0)
                }
                messages.append(msg_info)
        
        await client.disconnect()
        return messages
        
    except Exception as e:
        logger.error(f"Error scraping messages: {e}")
        return []

async def analyze_account_activity(session_string: str, days: int = 30) -> Dict[str, Any]:
    """Analyze account activity patterns"""
    try:
        client = TelegramClient(StringSession(session_string), config.telegram.api_id, config.telegram.api_hash)
        await client.connect()
        
        me = await client.get_me()
        dialogs = await client.get_dialogs()
        
        activity_stats = {
            "total_chats": len(dialogs),
            "active_chats": 0,
            "peak_hours": defaultdict(int),
            "chat_types": {"users": 0, "groups": 0, "channels": 0, "bots": 0},
            "engagement_score": 0
        }
        
        cutoff_date = datetime.now() - timedelta(days=days)
        total_messages = 0
        
        for dialog in dialogs[:50]:  # Limit to avoid rate limits
            try:
                entity = dialog.entity
                
                if isinstance(entity, User):
                    if getattr(entity, "bot", False):
                        activity_stats["chat_types"]["bots"] += 1
                    else:
                        activity_stats["chat_types"]["users"] += 1
                elif isinstance(entity, Channel):
                    if getattr(entity, "broadcast", False):
                        activity_stats["chat_types"]["channels"] += 1
                    else:
                        activity_stats["chat_types"]["groups"] += 1
                elif isinstance(entity, Chat):
                    activity_stats["chat_types"]["groups"] += 1
                
                messages = await client.get_messages(entity, limit=100)
                recent_messages = [msg for msg in messages if msg.date > cutoff_date and msg.sender_id == me.id]
                
                if recent_messages:
                    activity_stats["active_chats"] += 1
                    total_messages += len(recent_messages)
                    
                    for msg in recent_messages:
                        hour = msg.date.hour
                        activity_stats["peak_hours"][hour] += 1
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.debug(f"Error analyzing dialog: {e}")
                continue
        
        if activity_stats["total_chats"] > 0:
            activity_stats["engagement_score"] = (activity_stats["active_chats"] / activity_stats["total_chats"]) * 100
        
        activity_stats["total_messages_sent"] = total_messages
        activity_stats["daily_average"] = total_messages / days if days > 0 else 0
        
        await client.disconnect()
        return activity_stats
        
    except Exception as e:
        logger.error(f"Error analyzing activity: {e}")
        return {"error": str(e)}

async def perform_account_warming(session_string: str, duration: int = 3600) -> Dict[str, Any]:
    """Perform account warming activities"""
    try:
        client = TelegramClient(StringSession(session_string), config.telegram.api_id, config.telegram.api_hash)
        await client.connect()
        
        start_time = datetime.now()
        activities_performed = []
        
        while (datetime.now() - start_time).seconds < duration:
            # Random activity selection
            activity = ["online", "typing", "read_messages"][datetime.now().second % 3]
            
            if activity == "online":
                await asyncio.sleep(60)
                activities_performed.append("stayed_online")
            
            elif activity == "typing":
                dialogs = await client.get_dialogs(limit=10)
                if dialogs:
                    chat = dialogs[0].entity
                    async with client.action(chat, "typing"):
                        await asyncio.sleep(3)
                    activities_performed.append("typing_simulation")
            
            elif activity == "read_messages":
                dialogs = await client.get_dialogs(limit=5)
                for dialog in dialogs[:2]:
                    if dialog.unread_count > 0:
                        await client.send_read_acknowledge(dialog.entity)
                        activities_performed.append("read_messages")
                        await asyncio.sleep(2)
            
            await asyncio.sleep(120)  # 2 minute intervals
        
        await client.disconnect()
        
        return {
            "duration": (datetime.now() - start_time).seconds,
            "activities": len(activities_performed),
            "activity_types": list(set(activities_performed))
        }
        
    except Exception as e:
        logger.error(f"Account warming error: {e}")
        return {"error": str(e)}

async def check_account_restrictions(session_string: str) -> Dict[str, Any]:
    """Check account for restrictions and spam blocks"""
    try:
        client = TelegramClient(StringSession(session_string), config.telegram.api_id, config.telegram.api_hash)
        await client.connect()
        
        restrictions = {
            "spam_blocked": False,
            "restricted": False,
            "can_send_messages": True,
            "can_join_groups": True
        }
        
        # Check spam block via spambot
        try:
            test_bot = await client.get_entity("spambot")
            await client.send_message(test_bot, "/start")
            await asyncio.sleep(2)
            messages = await client.get_messages(test_bot, limit=1)
            
            if messages and messages[0].message:
                message_text = messages[0].message.lower()
                if "ограничен" in message_text or "limited" in message_text:
                    restrictions["spam_blocked"] = True
        except Exception:
            pass
        
        await client.disconnect()
        return restrictions
        
    except Exception as e:
        logger.error(f"Restriction check error: {e}")
        return {"error": str(e)}