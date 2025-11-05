"""Centralized callback routing"""
import logging
from telethon import Button

logger = logging.getLogger(__name__)

async def route_main_callback(bot, event, user_id, data, menu_system):
    """Route main callback queries"""
    if data.startswith("account:"):
        await _route_account_callbacks(bot, event, user_id, data, menu_system)
    elif data.startswith("otp_setting:"):
        await menu_system._handle_otp_setting_callback(event, user_id, data)
    elif data.startswith("otp:"):
        await menu_system._handle_otp_callback(event, user_id, data)
    elif data.startswith("menu:"):
        await menu_system._handle_menu_callback(event, user_id, data)
    elif data.startswith("cleanup:"):
        await menu_system._handle_cleanup_callback(event, user_id, data)
    elif data.startswith("help:"):
        await menu_system._handle_help_callback(event, user_id, data)
    elif data.startswith("support:"):
        await menu_system._handle_support_callback(event, user_id, data)
    elif data.startswith("dev:"):
        await menu_system._handle_developer_callback(event, user_id, data)
    else:
        await event.answer("Action processed", alert=False)

async def _route_account_callbacks(bot, event, user_id, data, menu_system):
    """Route account callbacks"""
    if data == "account:add":
        await menu_system._handle_add_account(event, user_id)
    elif data.startswith("account:manage:"):
        account_id = data.split(":")[2]
        await menu_system.send_account_management(user_id, account_id, event.message_id)
    elif data == "account:remove":
        await menu_system._handle_remove_account(event, user_id)

__all__ = ['route_main_callback']
