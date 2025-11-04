"""Structured logging system with correlation IDs"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.correlation_id: Optional[str] = None
        self.name = name
    def set_correlation_id(self, correlation_id: str = None):
        """Set correlation ID for request tracking"""
        self.correlation_id = correlation_id or str(uuid.uuid4())[:8]
    def _format_message(self, level: str, message: str, **kwargs) -> str:
        """Format message with structured data"""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            "correlation_id": self.correlation_id,
            **kwargs,
        }
        return json.dumps(log_data, default=str)
    def info(self, message: str, *args, **kwargs):
        """Log info message with support for format args"""
        if args:
            formatted_message = message % args
        else:
            formatted_message = message
        self.logger.info(self._format_message("INFO", formatted_message, **kwargs))
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message with support for format args"""
        if args:
            formatted_message = message % args
        else:
            formatted_message = message
        self.logger.warning(self._format_message("WARNING", formatted_message, **kwargs))
    
    def error(self, message: str, *args, **kwargs):
        """Log error message with support for format args"""
        if args:
            formatted_message = message % args
        else:
            formatted_message = message
        self.logger.error(self._format_message("ERROR", formatted_message, **kwargs))
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message with support for format args"""
        if args:
            formatted_message = message % args
        else:
            formatted_message = message
        self.logger.debug(self._format_message("DEBUG", formatted_message, **kwargs))
def get_logger(name: str) -> StructuredLogger:
    """Get structured logger instance"""
    return StructuredLogger(name)
