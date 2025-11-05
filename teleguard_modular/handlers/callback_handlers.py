"""Callback handlers extracted from menu_system.py"""
import logging
from telethon import Button

logger = logging.getLogger(__name__)

async def handle_help_callback(menu_system, event, user_id: int, data: str):
    """Delegate to help callbacks"""
    await menu_system.help_callbacks.handle_help_callback(event, user_id, data)

async def handle_support_callback(menu_system, event, user_id: int, data: str):
    """Delegate to support callbacks"""
    from teleguard_modular.menu_delegation import handle_support_callback as support_cb
    await support_cb(menu_system.bot, user_id, event, data)

async def handle_developer_callback(menu_system, event, user_id: int, data: str):
    """Delegate to developer callbacks"""
    from teleguard_modular.menu_delegation import handle_developer_callback as dev_cb
    await dev_cb(menu_system.bot, user_id, event, data)

async def handle_menu_callback(menu_system, event, user_id: int, data: str):
    """Delegate to menu navigation"""
    from teleguard_modular.menu_delegation import handle_menu_callback as menu_cb
    await menu_cb(menu_system.bot, user_id, event, data, menu_system)

async def handle_dm_reply_callback(menu_system, event, user_id: int, data: str):
    """Delegate to DM reply callbacks"""
    from teleguard_modular.menu_delegation import handle_dm_reply_callback as dm_cb
    await dm_cb(menu_system.bot, user_id, event, data)

async def handle_channel_callback(menu_system, event, user_id: int, data: str):
    """Delegate to channel callbacks"""
    from teleguard_modular.menu_delegation import handle_channel_callback as ch_cb
    await ch_cb(menu_system.bot, user_id, event, data, menu_system.account_manager)
