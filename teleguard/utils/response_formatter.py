"""
Response Formatting Utilities
Professional response formatting for consistent API responses,
user messages, and error handling across the application.
Authors: @Meher_Mankar, @Gutkesh
Repository: https://github.com/mehermankar/teleguard
"""
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum
from ..core.constants import StatusCodes, Emojis, MessageTemplates
logger = logging.getLogger(__name__)
class ResponseType(Enum):
    """Response type enumeration"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
class APIResponseFormatter:
    """Professional API response formatter"""
    @staticmethod
    def success(data: Any = None, message: str = "Operation successful", 
                status_code: int = StatusCodes.OK, meta: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Format successful API response.
        Args:
            data: Response data
            message: Success message
            status_code: HTTP status code
            meta: Additional metadata
        Returns:
            Formatted success response
        """
        response = {
            "success": True,
            "message": message,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
            "status_code": status_code
        }
        if meta:
            response["meta"] = meta
        return response
    @staticmethod
    def error(message: str, error_code: Optional[str] = None, 
              status_code: int = StatusCodes.BAD_REQUEST, 
              details: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Format error API response.
        Args:
            message: Error message
            error_code: Specific error code
            status_code: HTTP status code
            details: Additional error details
        Returns:
            Formatted error response
        """
        response = {
            "success": False,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "status_code": status_code
        }
        if error_code:
            response["error_code"] = error_code
        if details:
            response["details"] = details
        return response
    @staticmethod
    def paginated(data: List[Any], page: int, limit: int, total: int, 
                  message: str = "Data retrieved successfully") -> Dict[str, Any]:
        """
        Format paginated API response.
        Args:
            data: List of items
            page: Current page number
            limit: Items per page
            total: Total number of items
            message: Response message
        Returns:
            Formatted paginated response
        """
        total_pages = (total + limit - 1) // limit  # Ceiling division
        return APIResponseFormatter.success(
            data=data,
            message=message,
            meta={
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
        )
class TelegramMessageFormatter:
    """Telegram message formatting utilities"""
    @staticmethod
    def format_account_info(account: Dict[str, Any]) -> str:
        """
        Format account information for display.
        Args:
            account: Account data dictionary
        Returns:
            Formatted account information string
        """
        name = account.get('name', 'Unknown')
        phone = account.get('phone', 'Unknown')
        status = "🟢 Active" if account.get('is_active', False) else "🔴 Inactive"
        otp_status = "🛡️ Enabled" if account.get('otp_destroyer_enabled', False) else "❌ Disabled"
        online_status = "🟢 Enabled" if account.get('online_maker_enabled', False) else "❌ Disabled"
        return (
            f"📱 **Account: {name}**\n\n"
            f"📞 **Phone:** {phone}\n"
            f"📊 **Status:** {status}\n"
            f"🛡️ **OTP Protection:** {otp_status}\n"
            f"🌐 **Online Maker:** {online_status}\n"
        )
    @staticmethod
    def format_success_message(title: str, details: str, 
                             emoji: str = Emojis.SUCCESS) -> str:
        """
        Format success message for Telegram.
        Args:
            title: Message title
            details: Message details
            emoji: Emoji to use
        Returns:
            Formatted success message
        """
        return f"{emoji} **{title}**\n\n{details}"
    @staticmethod
    def format_error_message(title: str, details: str, 
                           emoji: str = Emojis.ERROR) -> str:
        """
        Format error message for Telegram.
        Args:
            title: Error title
            details: Error details
            emoji: Emoji to use
        Returns:
            Formatted error message
        """
        return f"{emoji} **{title}**\n\n{details}"
    @staticmethod
    def format_info_message(title: str, details: str, 
                          emoji: str = Emojis.INFO) -> str:
        """
        Format info message for Telegram.
        Args:
            title: Info title
            details: Info details
            emoji: Emoji to use
        Returns:
            Formatted info message
        """
        return f"{emoji} **{title}**\n\n{details}"
    @staticmethod
    def format_list_items(items: List[Dict[str, Any]], 
                         title: str = "Items", 
                         key_field: str = "name") -> str:
        """
        Format list of items for display.
        Args:
            items: List of items to format
            title: List title
            key_field: Field to use as item identifier
        Returns:
            Formatted list string
        """
        if not items:
            return f"📋 **{title}**\n\nNo items found."
        formatted_items = []
        for i, item in enumerate(items, 1):
            item_name = item.get(key_field, f"Item {i}")
            formatted_items.append(f"{i}. {item_name}")
        items_text = "\n".join(formatted_items)
        return f"📋 **{title}** ({len(items)})\n\n{items_text}"
    @staticmethod
    def format_status_report(data: Dict[str, Any], title: str = "Status Report") -> str:
        """
        Format status report for display.
        Args:
            data: Status data dictionary
            title: Report title
        Returns:
            Formatted status report
        """
        lines = [f"📊 **{title}**\n"]
        for key, value in data.items():
            # Format key (convert snake_case to Title Case)
            formatted_key = key.replace('_', ' ').title()
            # Format value based on type
            if isinstance(value, bool):
                formatted_value = "✅ Yes" if value else "❌ No"
            elif isinstance(value, (int, float)):
                formatted_value = f"{value:,}"
            elif isinstance(value, datetime):
                formatted_value = value.strftime("%Y-%m-%d %H:%M:%S")
            else:
                formatted_value = str(value)
            lines.append(f"• **{formatted_key}:** {formatted_value}")
        return "\n".join(lines)
class LogFormatter:
    """Logging message formatter"""
    @staticmethod
    def format_user_action(user_id: int, action: str, details: Optional[Dict] = None) -> str:
        """
        Format user action log message.
        Args:
            user_id: User's Telegram ID
            action: Action performed
            details: Additional details
        Returns:
            Formatted log message
        """
        message = f"User {user_id} performed action: {action}"
        if details:
            detail_parts = []
            for key, value in details.items():
                detail_parts.append(f"{key}={value}")
            message += f" | Details: {', '.join(detail_parts)}"
        return message
    @staticmethod
    def format_error_log(error: Exception, context: Optional[str] = None) -> str:
        """
        Format error log message.
        Args:
            error: Exception object
            context: Additional context
        Returns:
            Formatted error log message
        """
        message = f"Error: {type(error).__name__}: {str(error)}"
        if context:
            message = f"{context} | {message}"
        return message
    @staticmethod
    def format_security_event(user_id: int, event_type: str, 
                            details: Optional[Dict] = None) -> str:
        """
        Format security event log message.
        Args:
            user_id: User's Telegram ID
            event_type: Type of security event
            details: Event details
        Returns:
            Formatted security log message
        """
        message = f"SECURITY EVENT | User {user_id} | Event: {event_type}"
        if details:
            detail_parts = []
            for key, value in details.items():
                detail_parts.append(f"{key}={value}")
            message += f" | Details: {', '.join(detail_parts)}"
        return message
class DataFormatter:
    """Data formatting utilities"""
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        Format file size in human-readable format.
        Args:
            size_bytes: Size in bytes
        Returns:
            Formatted size string
        """
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        return f"{size:.1f} {size_names[i]}"
    @staticmethod
    def format_duration(seconds: int) -> str:
        """
        Format duration in human-readable format.
        Args:
            seconds: Duration in seconds
        Returns:
            Formatted duration string
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds}s" if remaining_seconds else f"{minutes}m"
        else:
            hours = seconds // 3600
            remaining_minutes = (seconds % 3600) // 60
            return f"{hours}h {remaining_minutes}m" if remaining_minutes else f"{hours}h"
    @staticmethod
    def format_phone_number(phone: str) -> str:
        """
        Format phone number for display.
        Args:
            phone: Phone number string
        Returns:
            Formatted phone number
        """
        cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        # Format based on length
        if len(cleaned) >= 12:  # International format
            return f"{cleaned[:3]} {cleaned[3:6]} {cleaned[6:9]} {cleaned[9:]}"
        else:
            return cleaned
    @staticmethod
    def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
        """
        Truncate text to specified length.
        Args:
            text: Text to truncate
            max_length: Maximum length
            suffix: Suffix to add when truncated
        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
