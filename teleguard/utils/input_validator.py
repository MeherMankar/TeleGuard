"""
Input Validation Utilities for TeleGuard
Provides secure input validation and sanitization
"""

import re
import os
from pathlib import Path
from typing import Any, Optional, Union
from bson import ObjectId
from bson.errors import InvalidId

class InputValidator:
    """Secure input validation utilities"""
    
    @staticmethod
    def validate_user_id(user_id: Any) -> Optional[int]:
        """Validate and sanitize user ID"""
        try:
            uid = int(user_id)
            if uid > 0:
                return uid
        except (ValueError, TypeError):
            pass
        return None
    
    @staticmethod
    def validate_object_id(obj_id: Any) -> Optional[str]:
        """Validate MongoDB ObjectId"""
        try:
            if isinstance(obj_id, str) and ObjectId.is_valid(obj_id):
                return str(ObjectId(obj_id))
        except InvalidId:
            pass
        return None
    
    @staticmethod
    def validate_phone_number(phone: str) -> Optional[str]:
        """Validate phone number format"""
        if not isinstance(phone, str):
            return None
        
        # Remove all non-digit characters except +
        clean_phone = re.sub(r'[^\d+]', '', phone)
        
        # Check if it matches international format
        if re.match(r'^\+\d{10,15}$', clean_phone):
            return clean_phone
        
        return None
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal"""
        if not isinstance(filename, str):
            return "unknown"
        
        # Remove path separators and dangerous characters
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
        safe_name = re.sub(r'\.\.', '_', safe_name)  # Remove ..
        safe_name = safe_name.strip('. ')  # Remove leading/trailing dots and spaces
        
        return safe_name[:255] if safe_name else "unknown"
    
    @staticmethod
    def validate_file_path(base_path: str, file_path: str) -> Optional[str]:
        """Validate file path to prevent traversal attacks"""
        try:
            base = Path(base_path).resolve()
            target = (base / file_path).resolve()
            
            # Ensure target is within base directory
            if base in target.parents or base == target:
                return str(target)
        except (OSError, ValueError):
            pass
        
        return None
    
    @staticmethod
    def sanitize_text_input(text: str, max_length: int = 1000) -> str:
        """Sanitize text input for database storage"""
        if not isinstance(text, str):
            return ""
        
        # Remove null bytes and control characters
        clean_text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Limit length
        return clean_text[:max_length].strip()
    
    @staticmethod
    def validate_database_field(field_name: str) -> bool:
        """Validate database field names to prevent injection"""
        if not isinstance(field_name, str):
            return False
        
        # Only allow alphanumeric, underscore, and dot
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', field_name))
    
    @staticmethod
    def sanitize_command_arg(arg: str) -> str:
        """Sanitize command line arguments"""
        if not isinstance(arg, str):
            return ""
        
        # Remove dangerous characters
        safe_arg = re.sub(r'[;&|`$(){}[\]<>]', '', arg)
        return safe_arg.strip()