from dataclasses import dataclass
from typing import List, Optional, Dict

@dataclass
class StreamResponse:
    agent_name: str
    instructions: str
    steps: List[str]
    status_code: int
    output: str
    live_url: Optional[str] = None
    source_code: Optional[str] = None
    metadata: Optional[Dict] = None
