"""TeleGuard - Messaging Module"""
from .bulk_handlers import (
    send_bulk_sender_menu,
    start_bulk_list_flow,
    start_bulk_contacts_flow,
    start_bulk_all_flow,
    show_bulk_jobs,
    show_bulk_help
)
from .dm_reply_menu import handle_dm_reply_menu
from .messaging_menu import handle_messaging_menu

__all__ = [
    'send_bulk_sender_menu',
    'start_bulk_list_flow',
    'start_bulk_contacts_flow',
    'start_bulk_all_flow',
    'show_bulk_jobs',
    'show_bulk_help',
    'handle_dm_reply_menu',
    'handle_messaging_menu'
]

def register(bot_manager):
    """Register messaging handlers"""
    pass
