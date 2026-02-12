"""
Centralized error handling and logging for Liquidctl GUI.

Provides structured error messages with context for easier debugging and AI interaction.
"""

import logging
import sys
from typing import Optional, Dict, Any
from enum import Enum


class ErrorCategory(Enum):
    """Error categories for structured error handling."""
    DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
    DEVICE_INIT = "DEVICE_INIT"
    DEVICE_CONTROL = "DEVICE_CONTROL"
    PERMISSION = "PERMISSION"
    CONFIG = "CONFIG"
    PROFILE = "PROFILE"
    NETWORK = "NETWORK"
    INTERNAL = "INTERNAL"


class ErrorHandler:
    """Centralized error handling with structured logging."""
    
    def __init__(self, logger_name: str = __name__):
        self.logger = logging.getLogger(logger_name)
        self._operation_stack = []
    
    def format_error(self, 
                    category: ErrorCategory,
                    message: str,
                    device: Optional[str] = None,
                    channel: Optional[str] = None,
                    operation: Optional[str] = None,
                    context: Optional[Dict[str, Any]] = None) -> str:
        """
        Format error message with full context.
        
        Args:
            category: Error category
            message: Human-readable error message
            device: Device name (if applicable)
            channel: Channel name (if applicable)
            operation: Operation being performed
            context: Additional context dictionary
        
        Returns:
            Formatted error string with all context
        
        Example:
            >>> handler.format_error(
            ...     ErrorCategory.DEVICE_NOT_FOUND,
            ...     "Cannot find device",
            ...     device="NZXT Kraken",
            ...     operation="initialize",
            ...     context={"available_devices": ["x53", "amdgpu"]}
            ... )
            "[DEVICE_NOT_FOUND] Cannot find device 'NZXT Kraken' during initialize. Available: x53, amdgpu"
        """
        parts = [f"[{category.value}]", message]
        
        if device:
            parts.append(f"(device: {device}")
            if channel:
                parts[-1] += f", channel: {channel}"
            parts[-1] += ")"
        
        if operation:
            parts.append(f"[operation: {operation}]")
        
        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            parts.append(f"[{context_str}]")
        
        return " ".join(parts)
    
    def log_error(self,
                 category: ErrorCategory,
                 message: str,
                 device: Optional[str] = None,
                 channel: Optional[str] = None,
                 operation: Optional[str] = None,
                 context: Optional[Dict[str, Any]] = None,
                 exc_info: bool = False) -> None:
        """
        Log an error with full context.
        
        Args:
            category: Error category
            message: Error message
            device: Device name
            channel: Channel name
            operation: Operation name
            context: Additional context
            exc_info: Include exception traceback
        """
        error_msg = self.format_error(category, message, device, channel, operation, context)
        self.logger.error(error_msg, exc_info=exc_info)
    
    def log_warning(self,
                   message: str,
                   device: Optional[str] = None,
                   operation: Optional[str] = None,
                   context: Optional[Dict[str, Any]] = None) -> None:
        """Log a warning with context."""
        parts = [message]
        if device:
            parts.append(f"(device: {device})")
        if operation:
            parts.append(f"[{operation}]")
        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            parts.append(f"[{context_str}]")
        
        self.logger.warning(" ".join(parts))
    
    def log_operation(self,
                     operation: str,
                     device: Optional[str] = None,
                     channel: Optional[str] = None,
                     **params) -> None:
        """
        Log an operation with parameters for debugging.
        
        Args:
            operation: Operation name (e.g., "set_color", "initialize")
            device: Device name
            channel: Channel name
            **params: Operation parameters
        """
        parts = [f"[OP:{operation}]"]
        if device:
            parts.append(f"device={device}")
        if channel:
            parts.append(f"channel={channel}")
        if params:
            params_str = ", ".join(f"{k}={v}" for k, v in params.items())
            parts.append(params_str)
        
        self.logger.info(" ".join(parts))
    
    def is_device_not_found_error(self, error_message: str) -> bool:
        """
        Check if error message indicates device not found.
        
        Args:
            error_message: Error message to check
        
        Returns:
            True if device not found error
        """
        if not error_message:
            return False
        
        error_lower = error_message.lower()
        not_found_indicators = [
            "not found",
            "no device",
            "device unavailable",
            "cannot find device",
            "no such device"
        ]
        return any(indicator in error_lower for indicator in not_found_indicators)


def configure_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Configure logging for the entire application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for log output
    """
    # Create formatter with timestamp and context
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Reduce verbosity of external libraries
    logging.getLogger('liquidctl').setLevel(logging.WARNING)


# Global error handler instance
_global_handler = None


def get_error_handler(logger_name: str = __name__) -> ErrorHandler:
    """Get or create global error handler instance."""
    global _global_handler
    if _global_handler is None:
        _global_handler = ErrorHandler(logger_name)
    return _global_handler
