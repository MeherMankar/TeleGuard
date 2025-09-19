"""Input sanitization utilities"""

import html
import re
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class InputSanitizer:
    """Comprehensive input sanitization"""
    
    @staticmethod
    def sanitize_html(text: str) -> str:
        """Sanitize HTML content to prevent XSS"""
        if not isinstance(text, str):
            text = str(text)
        return html.escape(text)
    
    @staticmethod
    def sanitize_regex(pattern: str) -> str:
        """Sanitize regex pattern to prevent ReDoS attacks"""
        if not isinstance(pattern, str):
            pattern = str(pattern)
        return re.escape(pattern)
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format"""
        try:
            if not isinstance(url, str):
                return False
            
            parsed = urlparse(url)
            return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
        except Exception:
            return False
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal"""
        if not isinstance(filename, str):
            filename = str(filename)
        
        # Remove path separators and dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = filename.replace('..', '')
        filename = filename.strip('. ')
        
        # Limit length
        if len(filename) > 255:
            filename = filename[:255]
        
        return filename or 'unnamed'
    
    @staticmethod
    def validate_mongodb_query(query: Dict[str, Any]) -> bool:
        """Validate MongoDB query to prevent injection"""
        try:
            # Check for dangerous operators
            dangerous_ops = ['$where', '$eval', '$function']
            
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
        """General user input sanitization"""
        if not isinstance(text, str):
            text = str(text)
        
        # Remove null bytes and control characters
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Limit length
        if len(text) > max_length:
            text = text[:max_length]
        
        return text.strip()
    
    @staticmethod
    def validate_integer(value: Any, min_val: Optional[int] = None, max_val: Optional[int] = None) -> Optional[int]:
        """Validate and convert to integer"""
        try:
            int_val = int(value)
            
            if min_val is not None and int_val < min_val:
                return None
            if max_val is not None and int_val > max_val:
                return None
                
            return int_val
        except (ValueError, TypeError):
            return None

# Global instance
sanitizer = InputSanitizer()