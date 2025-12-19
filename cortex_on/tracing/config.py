"""
Tracing Configuration

Environment-based configuration for the tracing system.
Provides centralized configuration management with sensible defaults.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class TracingConfig:
    """
    Configuration for the tracing system.
    
    Attributes:
        enabled: Whether tracing is enabled (TRACING_ENABLED env var)
        log_format: Log format preference - "json" or "text" (LOG_FORMAT env var)
        include_sensitive: Whether to include potentially sensitive data in traces
        max_step_depth: Maximum nesting depth for steps (prevents infinite recursion)
    """
    enabled: bool = True
    log_format: str = "json"
    include_sensitive: bool = False
    max_step_depth: int = 10
    
    @classmethod
    def from_env(cls) -> "TracingConfig":
        """Create configuration from environment variables."""
        return cls(
            enabled=os.getenv("TRACING_ENABLED", "true").lower() == "true",
            log_format=os.getenv("LOG_FORMAT", "json").lower(),
            include_sensitive=os.getenv("TRACING_INCLUDE_SENSITIVE", "false").lower() == "true",
            max_step_depth=int(os.getenv("TRACING_MAX_STEP_DEPTH", "10"))
        )
    
    def is_json_format(self) -> bool:
        """Check if JSON log format is enabled."""
        return self.log_format == "json"
    
    def validate(self) -> None:
        """Validate configuration values."""
        if self.log_format not in ("json", "text"):
            raise ValueError(f"Invalid log format: {self.log_format}. Must be 'json' or 'text'")
        
        if self.max_step_depth < 1:
            raise ValueError(f"max_step_depth must be >= 1, got {self.max_step_depth}")


# Global configuration instance
_config: Optional[TracingConfig] = None


def get_config() -> TracingConfig:
    """Get the global tracing configuration, initializing from environment if needed."""
    global _config
    if _config is None:
        _config = TracingConfig.from_env()
        _config.validate()
    return _config


def set_config(config: TracingConfig) -> None:
    """Set the global tracing configuration."""
    global _config
    config.validate()
    _config = config


def is_tracing_enabled() -> bool:
    """Quick check if tracing is enabled."""
    return get_config().enabled


def get_log_format() -> str:
    """Get the configured log format."""
    return get_config().log_format



