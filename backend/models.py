from pydantic import BaseModel
from typing import Optional, List


class LoginRequest(BaseModel):
    password: str


class MCQGenerateRequest(BaseModel):
    sac_thue: str
    count: int = 3
    topics: Optional[List[str]] = None
    exam_session: str = "Jun2026"
    difficulty: str = "standard"       # standard | hard
    model_tier: str = "haiku"          # haiku=default, fast=sonnet, strong=opus
    provider: Optional[str] = None     # None=auto, "claudible", "anthropic", "openai"
    session_id: Optional[int] = None
    user_id: int = 1
    syllabus_codes: Optional[List[str]] = None   # e.g. ["C2d", "C2n"]
    custom_instructions: Optional[str] = None
    reference_question_id: Optional[int] = None
    assumed_date: Optional[str] = None  # e.g. "1 February 2026"


class ScenarioGenerateRequest(BaseModel):
    question_number: str               # Q1 | Q2 | Q3 | Q4
    sac_thue: str
    marks: int = 10
    exam_session: str = "Jun2026"
    scenario_industry: Optional[str] = None
    topics: Optional[List[str]] = None
    difficulty: str = "standard"
    model_tier: str = "fast"
    provider: Optional[str] = None
    session_id: Optional[int] = None
    user_id: int = 1
    syllabus_codes: Optional[List[str]] = None
    custom_instructions: Optional[str] = None
    reference_question_id: Optional[int] = None
    assumed_date: Optional[str] = None


class LongformGenerateRequest(BaseModel):
    question_number: str               # Q5 | Q6
    sac_thue: str
    marks: int = 15
    exam_session: str = "Jun2026"
    topics: Optional[List[str]] = None
    difficulty: str = "standard"
    model_tier: str = "fast"
    provider: Optional[str] = None
    session_id: Optional[int] = None
    user_id: int = 1
    syllabus_codes: Optional[List[str]] = None
    custom_instructions: Optional[str] = None
    reference_question_id: Optional[int] = None
    assumed_date: Optional[str] = None


class RefineRequest(BaseModel):
    current_content: dict
    conversation_history: List[dict]
    user_message: str
    model_tier: str = "fast"
    provider: Optional[str] = None
    sac_thue: str
    question_type: str


class ExportRequest(BaseModel):
    question_ids: list[int]


class StarRequest(BaseModel):
    is_starred: bool
