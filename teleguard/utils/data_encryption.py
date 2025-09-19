"""Comprehensive data encryption system for all user data

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

from ..core.config import FERNET

logger = logging.getLogger(__name__)


class DataEncryption:
    """Handles encryption/decryption of all user data"""
    
    @staticmethod
    def encrypt_field(data: Any) -> str:
        """Encrypt any data field to encrypted string"""
        if data is None:
            return None
        
        # If encryption is disabled, return data as-is
        if FERNET is None:
            return data
        
        try:
            # Convert to JSON string first
            json_str = json.dumps(data, default=str)
            # Encrypt the JSON string
            encrypted_bytes = FERNET.encrypt(json_str.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Failed to encrypt field: {e}")
            raise
    
    @staticmethod
    def decrypt_field(encrypted_data: str) -> Any:
        """Decrypt encrypted string back to original data"""
        if encrypted_data is None:
            return None
        
        # If encryption is disabled, return data as-is
        if FERNET is None:
            return encrypted_data
        
        try:
            # Decrypt to bytes then to string
            decrypted_bytes = FERNET.decrypt(encrypted_data.encode())
            json_str = decrypted_bytes.decode()
            # Parse JSON back to original data
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to decrypt field: {e}")
            # Return None for corrupted data instead of raising
            return None
    
    @staticmethod
    def encrypt_user_data(user_data: Dict) -> Dict:
        """Encrypt sensitive user data fields"""
        # If encryption is disabled, return data as-is
        if FERNET is None:
            return user_data.copy()
        
        encrypted_data = user_data.copy()
        
        # Fields to encrypt
        sensitive_fields = [
            'developer_mode', 'settings', 'preferences', 
            'auto_reply_settings', 'otp_settings'
        ]
        
        for field in sensitive_fields:
            if field in encrypted_data:
                encrypted_data[f"{field}_enc"] = DataEncryption.encrypt_field(encrypted_data[field])
                del encrypted_data[field]
        
        return encrypted_data
    
    @staticmethod
    def decrypt_user_data(encrypted_data: Dict) -> Dict:
        """Decrypt user data fields"""
        if not encrypted_data:
            return {}
        
        decrypted_data = encrypted_data.copy()
        
        # Find encrypted fields and decrypt them
        encrypted_fields = [key for key in decrypted_data.keys() if key.endswith('_enc')]
        
        for enc_field in encrypted_fields:
            original_field = enc_field[:-4]  # Remove '_enc' suffix
            try:
                decrypted_value = DataEncryption.decrypt_field(decrypted_data[enc_field])
                if decrypted_value is not None:
                    decrypted_data[original_field] = decrypted_value
                del decrypted_data[enc_field]
            except Exception as e:
                logger.error(f"Failed to decrypt field {enc_field}: {e}")
                # Remove corrupted encrypted field
                del decrypted_data[enc_field]
        
        return decrypted_data
    
    @staticmethod
    def encrypt_account_data(account_data: Dict) -> Dict:
        """Encrypt sensitive account data fields"""
        # If encryption is disabled, return data as-is
        if FERNET is None:
            return account_data.copy()
        
        encrypted_data = account_data.copy()
        
        # Fields to encrypt
        sensitive_fields = [
            'session_string', 'name', 'username', 'bio', 'phone',
            'two_fa_password', 'otp_destroyer_enabled', 'is_active',
            'auto_reply_enabled', 'auto_reply_message', 'auto_reply_keywords',
            'business_hours', 'available_message', 'unavailable_message',
            'audit_log', 'last_activity', 'profile_data'
        ]
        
        for field in sensitive_fields:
            if field in encrypted_data:
                encrypted_data[f"{field}_enc"] = DataEncryption.encrypt_field(encrypted_data[field])
                del encrypted_data[field]
        
        return encrypted_data
    
    @staticmethod
    def decrypt_account_data(encrypted_data: Dict) -> Dict:
        """Decrypt account data fields"""
        if not encrypted_data:
            return {}
        
        decrypted_data = encrypted_data.copy()
        
        # Find encrypted fields and decrypt them
        encrypted_fields = [key for key in decrypted_data.keys() if key.endswith('_enc')]
        
        for enc_field in encrypted_fields:
            original_field = enc_field[:-4]  # Remove '_enc' suffix
            try:
                decrypted_value = DataEncryption.decrypt_field(decrypted_data[enc_field])
                if decrypted_value is not None:
                    decrypted_data[original_field] = decrypted_value
                del decrypted_data[enc_field]
            except Exception as e:
                logger.error(f"Failed to decrypt field {enc_field}: {e}")
                # Remove corrupted encrypted field
                del decrypted_data[enc_field]
        
        return decrypted_data
    
    @staticmethod
    def encrypt_settings_data(settings_data: Dict) -> Dict:
        """Encrypt settings data"""
        encrypted_data = settings_data.copy()
        
        # Fields to encrypt
        sensitive_fields = [
            'auto_reply_global', 'otp_destroyer_global', 'rate_limits',
            'security_settings', 'backup_settings', 'notification_settings'
        ]
        
        for field in sensitive_fields:
            if field in encrypted_data:
                encrypted_data[f"{field}_enc"] = DataEncryption.encrypt_field(encrypted_data[field])
                del encrypted_data[field]
        
        return encrypted_data
    
    @staticmethod
    def decrypt_settings_data(encrypted_data: Dict) -> Dict:
        """Decrypt settings data"""
        if not encrypted_data:
            return {}
        
        decrypted_data = encrypted_data.copy()
        
        # Find encrypted fields and decrypt them
        encrypted_fields = [key for key in decrypted_data.keys() if key.endswith('_enc')]
        
        for enc_field in encrypted_fields:
            original_field = enc_field[:-4]  # Remove '_enc' suffix
            decrypted_data[original_field] = DataEncryption.decrypt_field(decrypted_data[enc_field])
            del decrypted_data[enc_field]
        
        return decrypted_data