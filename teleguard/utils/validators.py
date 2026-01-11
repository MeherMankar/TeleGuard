"""
Unified Input Validation and Sanitization Utilities
Professional validation functions for user inputs, configurations,
and data integrity checks throughout the application.
Authors: @Meher_Mankar, @Gutkesh
Repository: https://github.com/mehermankar/teleguard
"""

import html
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union
from urllib.parse import urlparse

from bson import ObjectId
from bson.errors import InvalidId

from ..core.constants import AppConstants
from ..core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class InputSanitizer:
    """Comprehensive input sanitization"""

    @staticmethod
    def sanitize_html(text: str) -> str:
        if not isinstance(text, str):
            text = str(text)
        return html.escape(text)

    @staticmethod
    def sanitize_regex(pattern: str) -> str:
        if not isinstance(pattern, str):
            pattern = str(pattern)
        return re.escape(pattern)

    @staticmethod
    def validate_url(url: str) -> bool:
        try:
            if not isinstance(url, str):
                return False
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        if not isinstance(filename, str):
            filename = str(filename)
        filename = re.sub(r'[<>:"/\\|?*]', "", filename)
        filename = filename.replace("..", "")
        filename = filename.strip(". ")
        if len(filename) > 255:
            filename = filename[:255]
        return filename or "unnamed"

    @staticmethod
    def validate_mongodb_query(query: Dict[str, Any]) -> bool:
        try:
            dangerous_ops = ["$where", "$eval", "$function"]

            def check_dict(d):
                if not isinstance(d, dict):
                    return True
                for key, value in d.items():
                    if key in dangerous_ops:
                        return False
                    if isinstance(value, dict):
                        if not check_dict(value):
                            return False
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                if not check_dict(item):
                                    return False
                return True

            return check_dict(query)
        except Exception:
            return False

    @staticmethod
    def sanitize_user_input(text: str, max_length: int = 1000) -> str:
        if not isinstance(text, str):
            text = str(text)
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
        if len(text) > max_length:
            text = text[:max_length]
        return text.strip()

    @staticmethod
    def validate_integer(
        value: Any, min_val: Optional[int] = None, max_val: Optional[int] = None
    ) -> Optional[int]:
        try:
            int_val = int(value)
            if min_val is not None and int_val < min_val:
                return None
            if max_val is not None and int_val > max_val:
                return None
            return int_val
        except (ValueError, TypeError):
            return None


class InputValidator:
    """Secure input validation utilities"""

    @staticmethod
    def validate_user_id(user_id: Any) -> Optional[int]:
        if user_id is None:
            return None
        try:
            uid = int(user_id)
            return uid if uid > 0 else None
        except (ValueError, TypeError, OverflowError):
            return None

    @staticmethod
    def validate_object_id(obj_id: Any) -> Optional[str]:
        try:
            if isinstance(obj_id, str) and ObjectId.is_valid(obj_id):
                return str(ObjectId(obj_id))
        except InvalidId:
            pass
        return None

    @staticmethod
    def validate_phone_number(phone: str) -> Optional[str]:
        if not isinstance(phone, str) or not phone.strip():
            return None
        clean_phone = re.sub(r"[^\d+]", "", phone.strip())
        if re.match(r"^\+\d{10,15}$", clean_phone):
            return clean_phone
        return None

    @staticmethod
    def validate_file_path(base_path: str, file_path: str) -> Optional[str]:
        try:
            base = Path(base_path).resolve()
            target = (base / file_path).resolve()
            if base in target.parents or base == target:
                return str(target)
        except (OSError, ValueError):
            pass
        return None

    @staticmethod
    def sanitize_text_input(text: str, max_length: int = 1000) -> str:
        if not isinstance(text, str):
            return ""
        clean_text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
        clean_text = " ".join(clean_text.split())
        return clean_text[:max_length] if clean_text else ""

    @staticmethod
    def validate_database_field(field_name: str) -> bool:
        if not isinstance(field_name, str):
            return False
        return bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", field_name))

    @staticmethod
    def sanitize_command_arg(arg: str) -> str:
        if not isinstance(arg, str):
            return ""
        safe_arg = re.sub(r"[;&|`$(){}[\]<>]", "", arg)
        return safe_arg.strip()


class PhoneValidator:
    """Phone number validation utilities"""

    # International phone number pattern
    PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{1,14}$")

    @classmethod
    def validate_phone_number(cls, phone: str) -> str:
        """
        Validate and normalize phone number.
        Args:
            phone: Phone number string
        Returns:
            Normalized phone number
        Raises:
            ValidationError: If phone number is invalid
        """
        if not phone:
            raise ValidationError("Phone number is required")
        cleaned = re.sub(r"[^\d+]", "", phone.strip())
        if not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        if not cls.PHONE_PATTERN.match(cleaned):
            raise ValidationError(
                "Invalid phone number format. Use international format (+1234567890)",
                error_code="INVALID_PHONE_FORMAT",
            )
        if len(cleaned) < 8 or len(cleaned) > 16:
            raise ValidationError(
                "Phone number must be between 8 and 16 digits",
                error_code="INVALID_PHONE_LENGTH",
            )
        return cleaned


class PasswordValidator:
    """Password validation utilities"""

    @classmethod
    def validate_password(
        cls, password: str, min_length: int = AppConstants.PASSWORD_MIN_LENGTH
    ) -> bool:
        """
        Validate password strength.
        Args:
            password: Password string
            min_length: Minimum password length
        Returns:
            True if valid
        Raises:
            ValidationError: If password is invalid
        """
        if not password:
            raise ValidationError("Password is required")
        if len(password) < min_length:
            raise ValidationError(
                f"Password must be at least {min_length} characters long",
                error_code="PASSWORD_TOO_SHORT",
            )
        if len(password) > 128:
            raise ValidationError(
                "Password must be less than 128 characters",
                error_code="PASSWORD_TOO_LONG",
            )
        weak_passwords = ["password", "123456", "qwerty", "admin", "root"]
        if password.lower() in weak_passwords:
            raise ValidationError(
                "Password is too common. Please choose a stronger password",
                error_code="WEAK_PASSWORD",
            )
        return True


class UserInputValidator:
    """General user input validation"""

    @classmethod
    def validate_user_id(cls, user_id: Union[str, int]) -> int:
        """
        Validate Telegram user ID.
        Args:
            user_id: User ID to validate
        Returns:
            Validated user ID as integer
        Raises:
            ValidationError: If user ID is invalid
        """
        try:
            uid = int(user_id)
            if uid <= 0:
                raise ValidationError("User ID must be positive")
            if uid > 2**63 - 1:  # Max int64
                raise ValidationError("User ID is too large")
            return uid
        except (ValueError, TypeError):
            raise ValidationError("Invalid user ID format")

    @classmethod
    def validate_account_name(cls, name: str) -> str:
        """
        Validate account name.
        Args:
            name: Account name to validate
        Returns:
            Validated account name
        Raises:
            ValidationError: If name is invalid
        """
        if not name:
            raise ValidationError("Account name is required")
        name = name.strip()
        if len(name) < 2:
            raise ValidationError("Account name must be at least 2 characters")
        if len(name) > 50:
            raise ValidationError("Account name must be less than 50 characters")
        if not re.match(r"^[a-zA-Z0-9\s\-_.]+$", name):
            raise ValidationError(
                "Account name contains invalid characters",
                error_code="INVALID_ACCOUNT_NAME",
            )
        return name

    @classmethod
    def validate_otp_code(cls, code: str) -> str:
        """
        Validate OTP code format.
        Args:
            code: OTP code to validate
        Returns:
            Validated OTP code
        Raises:
            ValidationError: If code is invalid
        """
        if not code:
            raise ValidationError("OTP code is required")
        code = re.sub(r"\s", "", code.strip())
        if not code.isdigit():
            raise ValidationError("OTP code must contain only numbers")
        if len(code) != AppConstants.OTP_CODE_LENGTH:
            raise ValidationError(
                f"OTP code must be {AppConstants.OTP_CODE_LENGTH} digits"
            )
        return code

    @classmethod
    def validate_session_string(cls, session_string: str) -> str:
        """
        Validate Telethon session string format.
        Args:
            session_string: Session string to validate
        Returns:
            Validated session string
        Raises:
            ValidationError: If session string is invalid
        """
        if not session_string:
            raise ValidationError("Session string is required")
        session_string = session_string.strip()
        # Basic length check (Telethon session strings are typically 200+ chars)
        if len(session_string) < 100:
            raise ValidationError(
                "Session string appears to be too short",
                error_code="INVALID_SESSION_LENGTH",
            )
        if not re.match(r"^[A-Za-z0-9+/=]+$", session_string):
            raise ValidationError(
                "Session string contains invalid characters",
                error_code="INVALID_SESSION_FORMAT",
            )
        return session_string


class ConfigValidator:
    """Configuration validation utilities"""

    @classmethod
    def validate_api_credentials(cls, api_id: Union[str, int], api_hash: str) -> tuple:
        """
        Validate Telegram API credentials.
        Args:
            api_id: Telegram API ID
            api_hash: Telegram API hash
        Returns:
            Tuple of (validated_api_id, validated_api_hash)
        Raises:
            ValidationError: If credentials are invalid
        """
        try:
            api_id = int(api_id)
            if api_id <= 0:
                raise ValidationError("API ID must be positive")
        except (ValueError, TypeError):
            raise ValidationError("Invalid API ID format")
        if not api_hash:
            raise ValidationError("API hash is required")
        api_hash = api_hash.strip()
        if len(api_hash) != 32:
            raise ValidationError("API hash must be 32 characters long")
        if not re.match(r"^[a-f0-9]+$", api_hash.lower()):
            raise ValidationError("API hash must be hexadecimal")
        return api_id, api_hash

    @classmethod
    def validate_bot_token(cls, token: str) -> str:
        """
        Validate Telegram bot token format.
        Args:
            token: Bot token to validate
        Returns:
            Validated bot token
        Raises:
            ValidationError: If token is invalid
        """
        if not token:
            raise ValidationError("Bot token is required")
        token = token.strip()
        # Bot token format: 123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
        if not re.match(r"^\d+:[A-Za-z0-9_-]+$", token):
            raise ValidationError(
                "Invalid bot token format", error_code="INVALID_BOT_TOKEN"
            )
        parts = token.split(":")
        if len(parts) != 2:
            raise ValidationError("Bot token must contain exactly one colon")
        bot_id, token_part = parts
        if len(bot_id) < 8 or len(token_part) < 35:
            raise ValidationError("Bot token appears to be malformed")
        return token


class DataValidator:
    """Data structure validation utilities"""

    @classmethod
    def validate_account_data(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate account data structure.
        Args:
            data: Account data dictionary
        Returns:
            Validated account data
        Raises:
            ValidationError: If data is invalid
        """
        required_fields = ["user_id", "name", "phone"]
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing required field: {field}")
        validated_data = {
            "user_id": UserInputValidator.validate_user_id(data["user_id"]),
            "name": UserInputValidator.validate_account_name(data["name"]),
            "phone": PhoneValidator.validate_phone_number(data["phone"]),
        }
        # Optional fields
        if "session_string" in data:
            validated_data["session_string"] = (
                UserInputValidator.validate_session_string(data["session_string"])
            )
        # Boolean fields with defaults
        validated_data.update(
            {
                "is_active": data.get("is_active", True),
                "otp_destroyer_enabled": data.get("otp_destroyer_enabled", False),
                "online_maker_enabled": data.get("online_maker_enabled", False),
            }
        )
        return validated_data

    @classmethod
    def validate_pagination_params(
        cls, page: Union[str, int], limit: Union[str, int]
    ) -> tuple:
        """
        Validate pagination parameters.
        Args:
            page: Page number
            limit: Items per page
        Returns:
            Tuple of (validated_page, validated_limit)
        Raises:
            ValidationError: If parameters are invalid
        """
        try:
            page = int(page) if page else 1
            limit = int(limit) if limit else 10
        except (ValueError, TypeError):
            raise ValidationError("Page and limit must be integers")
        if page < 1:
            raise ValidationError("Page must be at least 1")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")
        return page, limit


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.
    Args:
        filename: Original filename
    Returns:
        Sanitized filename
    """
    if not filename:
        return "unnamed_file"
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)
    sanitized = re.sub(r"\.\.", "_", sanitized)
    sanitized = sanitized.strip(". ")
    if not sanitized:
        return "unnamed_file"
    # Limit length
    if len(sanitized) > 255:
        name, ext = sanitized.rsplit(".", 1) if "." in sanitized else (sanitized, "")
        max_name_length = 250 - len(ext)
        sanitized = name[:max_name_length] + ("." + ext if ext else "")
    return sanitized


def validate_json_data(data: str) -> Dict[str, Any]:
    """
    Validate and parse JSON data.
    Args:
        data: JSON string
    Returns:
        Parsed JSON data
    Raises:
        ValidationError: If JSON is invalid
    """
    import json

    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON format: {str(e)}")
    except Exception as e:
        raise ValidationError(f"JSON parsing error: {str(e)}")


class Validators:
    """Main validator class combining all validation utilities"""

    phone = PhoneValidator
    password = PasswordValidator
    user_input = UserInputValidator
    config = ConfigValidator
    data = DataValidator

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        return sanitize_filename(filename)

    @staticmethod
    def validate_json_data(data: str) -> Dict[str, Any]:
        return validate_json_data(data)

    @staticmethod
    def validate_channel_link(link: str) -> Optional[str]:
        """Validate and normalize channel/group link"""
        if not link or not isinstance(link, str):
            return None

        link = link.strip()

        # Handle different link formats
        if link.startswith("@"):
            username = link[1:]
        elif "t.me/" in link:
            username = link.split("t.me/")[-1].split("?")[0]
        elif "telegram.me/" in link:
            username = link.split("telegram.me/")[-1].split("?")[0]
        else:
            username = link

        # Validate username format
        if re.match(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$", username):
            return username

        return None
