from pydantic import BaseModel
from typing import Dict, Optional
from enum import Enum

class FactModel(BaseModel):
    facts: str

class PlanModel(BaseModel):
    plan: str

class LedgerAnswer(BaseModel):
    """Model for individual ledger answers"""

    answer: bool | str
    explanation: Optional[str] = None

class LedgerModel(BaseModel):
    """Main ledger state model"""

    is_request_satisfied: LedgerAnswer
    is_in_loop: LedgerAnswer
    is_progress_being_made: LedgerAnswer
    next_speaker: LedgerAnswer
    instruction_or_question: LedgerAnswer

class Action(str, Enum):
    enable = "enable"
    disable = "disable"
    
class MCPRequest(BaseModel):
    server_name: str
    action: Action
    server_secret: str
