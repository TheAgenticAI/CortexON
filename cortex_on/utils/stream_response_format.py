from dataclasses import dataclass
from typing import List, Optional

@dataclass
class StreamResponse:
    agent_name: str
    instructions: str
    steps: List[str]
    status_code: int
    output: str
    live_url: Optional[str] = None
    metadata: Optional[dict] = None
