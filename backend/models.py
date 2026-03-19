from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    password: str


class MCQGenerateRequest(BaseModel):
    sac_thue: str
    count: int = 5
    topics: Optional[list[str]] = None
    exam_session: str = "Jun2026"
    difficulty: str = "standard"


class ScenarioGenerateRequest(BaseModel):
    question_number: str  # Q1, Q2, Q3, Q4
    sac_thue: str
    marks: int = 10
    exam_session: str = "Jun2026"
    scenario_industry: Optional[str] = None


class LongformGenerateRequest(BaseModel):
    question_number: str  # Q5, Q6
    sac_thue: str
    marks: int = 15
    exam_session: str = "Jun2026"


class RegulationUpload(BaseModel):
    sac_thue: str
    ten_van_ban: Optional[str] = None
    loai: str = "LAW"
    ngon_ngu: str = "ENG"


class ExportRequest(BaseModel):
    question_ids: list[int]


class StarRequest(BaseModel):
    is_starred: bool
