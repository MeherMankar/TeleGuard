"""Central delegation for menu handlers - reduces menu_system.py size"""
from .account_settings.profile_handlers import (
    send_profile_management,
    handle_profile_name_change,
    handle_profile_username_change,
    handle_profile_bio_change,
    handle_profile_photo_change
)
from .messaging.bulk_handlers import (
    send_bulk_sender_menu,
    start_bulk_list_flow,
    start_bulk_contacts_flow,
    start_bulk_all_flow,
    show_bulk_jobs,
    show_bulk_help
)
from .messaging.dm_reply_menu import handle_dm_reply_menu
from .messaging.messaging_menu import handle_messaging_menu
from .contacts.contacts_menu import handle_contacts_menu
from .channels.channels_menu import handle_channels_menu
from .cleanup.cleanup_menu import handle_cleanup_menu
from .help.help_menu import handle_help_menu
from .support.support_menu import handle_support_menu
from .dev_panel.dev_menu import handle_developer_menu
from .account_settings.account_handlers import handle_account_settings
from .otp_manager.otp_handlers import handle_otp_manager
from .utils.helpers import parse_callback, format_display_name

__all__ = [
    'send_profile_management',
    'handle_profile_name_change',
    'handle_profile_username_change',
    'handle_profile_bio_change',
    'handle_profile_photo_change',
    'send_bulk_sender_menu',
    'start_bulk_list_flow',
    'start_bulk_contacts_flow',
    'start_bulk_all_flow',
    'show_bulk_jobs',
    'show_bulk_help',
    'handle_dm_reply_menu',
    'handle_messaging_menu',
    'handle_contacts_menu',
    'handle_channels_menu',
    'handle_cleanup_menu',
    'handle_help_menu',
    'handle_support_menu',
    'handle_developer_menu',
    'handle_account_settings',
    'handle_otp_manager',
    'parse_callback',
    'format_display_name'
]
