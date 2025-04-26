from dataclasses import dataclass
from typing import List, Optional
import uuid

@dataclass
class StreamResponse:
    agent_name: str
    instructions: str
    steps: List[str]
    status_code: int
    output: str
    live_url: Optional[str] = None
    message_id: str = ""  # Unique identifier for each message
