from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from urllib.parse import urlparse

class StreamRequestModel(BaseModel):
    """Model for stream request"""
    cmd: str = Field(..., description="Command to execute")
    url: str = Field("https://google.com", description="URL to navigate to")
    critique_disabled: bool = Field(False, description="Whether to disable critique")
    model_preference: str = Field("Anthropic", description="Model provider preference (Anthropic or OpenAI)")

    @validator('url')
    def validate_and_format_url(cls, v):
        """Validate and format the URL to ensure it has a protocol"""
        if not v:
            return "https://google.com"
        
        # Add https:// if no protocol specified
        if not v.startswith(('http://', 'https://')):
            v = f"https://{v}"
        
        # Validate URL format
        try:
            result = urlparse(v)
            if not result.netloc:
                raise ValueError("Invalid URL format")
            return v
        except Exception as e:
            raise ValueError(f"Invalid URL: {str(e)}")

class StreamResponseModel(BaseModel):
    """Model for stream response"""
    type: str = Field(..., description="Type of response (meta, info, error, final)")
    message: str = Field(..., description="Message content")
    session_id: str = Field(..., description="Session ID")
    live_url: Optional[str] = Field(None, description="Live URL for debugging")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")