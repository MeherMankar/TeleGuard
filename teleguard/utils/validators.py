"""Input validation utilities"""

import re
from typing import Optional

from ..core.exceptions import ValidationError


class Validators:
    PHONE_REGEX = re.compile(r"^\+?[1-9]\d{1,14}$")
    USERNAME_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$")
    INVITE_HASH_REGEX = re.compile(r"^[A-Za-z0-9_-]{22}$")

    @staticmethod
    def validate_phone(phone: str) -> str:
        """Validate and normalize phone number"""
        if phone is None or not phone or not phone.strip():
            raise ValidationError("Phone number is required")

        phone = re.sub(r"[^\d+]", "", phone.strip())
        if not phone or not Validators.PHONE_REGEX.match(phone):
            raise ValidationError("Invalid phone number format")

        return phone if phone.startswith("+") else f"+{phone}"

    @staticmethod
    def validate_username(username: str) -> str:
        """Validate Telegram username"""
        if not username:
            raise ValidationError("Username is required")

        username = username.strip().lstrip("@")
        if not Validators.USERNAME_REGEX.match(username):
            raise ValidationError("Invalid username format")

        return username

    @staticmethod
    def validate_channel_link(link: str) -> str:
        """Validate and normalize channel link"""
        if not link:
            raise ValidationError("Channel link is required")

        link = link.strip()

        # Valid formats
        patterns = [
            r"^https://t\.me/[a-zA-Z][a-zA-Z0-9_]{4,31}$",
            r"^https://t\.me/\+[A-Za-z0-9_-]{22}$",
            r"^@[a-zA-Z][a-zA-Z0-9_]{4,31}$",
            r"^\+[A-Za-z0-9_-]{22}$",
            r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$",
        ]

        if not any(re.match(pattern, link) for pattern in patterns):
            raise ValidationError("Invalid channel link format")

        return link

    @staticmethod
    def sanitize_text(text: str, max_length: int = 1000) -> str:
        """Sanitize text input"""
        if not text:
            return ""

        text = text.strip()[:max_length]
        # Remove potentially dangerous characters
        text = re.sub(r"[<>]", "", text)
        text = re.sub(r'["\']', "", text)
        return text
