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

    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(self._format_message("INFO", message, **kwargs))

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(self._format_message("WARNING", message, **kwargs))

    def error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(self._format_message("ERROR", message, **kwargs))

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(self._format_message("DEBUG", message, **kwargs))


def get_logger(name: str) -> StructuredLogger:
    """Get structured logger instance"""
    return StructuredLogger(name)
