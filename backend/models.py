from pydantic import BaseModel
from typing import Optional, List


class LoginRequest(BaseModel):
    password: str


class MCQGenerateRequest(BaseModel):
    sac_thue: str
    count: int = 3
    topics: Optional[list[str]] = None
    exam_session: str = "Jun2026"
    difficulty: str = "standard"
    model_tier: str = "fast"   # fast=sonnet, strong=opus
    reference_question_id: Optional[int] = None
    custom_instructions: Optional[str] = None
    kb_syllabus_ids: Optional[List[int]] = None
    kb_regulation_ids: Optional[List[int]] = None
    kb_sample_ids: Optional[List[int]] = None


class ScenarioGenerateRequest(BaseModel):
    question_number: str  # Q1, Q2, Q3, Q4
    sac_thue: str
    marks: int = 10
    exam_session: str = "Jun2026"
    scenario_industry: Optional[str] = None
    model_tier: str = "strong"  # default opus for scenario
    reference_question_id: Optional[int] = None
    custom_instructions: Optional[str] = None
    kb_syllabus_ids: Optional[List[int]] = None
    kb_regulation_ids: Optional[List[int]] = None
    kb_sample_ids: Optional[List[int]] = None


class LongformGenerateRequest(BaseModel):
    question_number: str  # Q5, Q6
    sac_thue: str
    marks: int = 15
    exam_session: str = "Jun2026"
    model_tier: str = "strong"  # default opus for longform
    reference_question_id: Optional[int] = None
    custom_instructions: Optional[str] = None
    kb_syllabus_ids: Optional[List[int]] = None
    kb_regulation_ids: Optional[List[int]] = None
    kb_sample_ids: Optional[List[int]] = None


class RefineRequest(BaseModel):
    current_content: dict
    conversation_history: List[dict]  # [{role: "user"|"assistant", content: str}]
    user_message: str
    model_tier: str = "fast"
    sac_thue: str
    question_type: str


class RegulationUpload(BaseModel):
    sac_thue: str
    ten_van_ban: Optional[str] = None
    loai: str = "LAW"
    ngon_ngu: str = "ENG"


class ExportRequest(BaseModel):
    question_ids: list[int]


class StarRequest(BaseModel):
    is_starred: bool
