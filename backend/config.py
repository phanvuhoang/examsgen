import os


# AI — Primary (Claudible, OpenAI-compatible)
CLAUDIBLE_BASE_URL = os.getenv("CLAUDIBLE_BASE_URL", "https://claudible.io/v1")
CLAUDIBLE_API_KEY = os.getenv("CLAUDIBLE_API_KEY", "")
CLAUDIBLE_MODEL_STRONG = os.getenv("CLAUDIBLE_MODEL_STRONG", "claude-opus-4.6")
CLAUDIBLE_MODEL_FAST = os.getenv("CLAUDIBLE_MODEL_FAST", "claude-sonnet-4.6")

# AI — Fallback (Anthropic direct, OpenAI-compatible endpoint)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL_STRONG = os.getenv("ANTHROPIC_MODEL_STRONG", "claude-opus-4-5")
ANTHROPIC_MODEL_FAST = os.getenv("ANTHROPIC_MODEL_FAST", "claude-sonnet-4-5")

# AI — Secondary fallback (OpenAI)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
OPENAI_FAST_MODEL = os.getenv("OPENAI_FAST_MODEL", "gpt-4o-mini")
OPENAI_STRONG_MODEL = os.getenv("OPENAI_STRONG_MODEL", "gpt-4o")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://legaldb_user:password@10.0.1.11:5432/examsgen")

# App
APP_PASSWORD = os.getenv("APP_PASSWORD", "admin")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")

# Paths
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
REGULATIONS_DIR = os.path.join(DATA_DIR, "regulations")
SYLLABUS_DIR = os.path.join(DATA_DIR, "syllabus")
SAMPLES_DIR = os.path.join(DATA_DIR, "samples")

# Context limits
MAX_CONTEXT_CHARS = 150_000
MAX_REGULATION_CHARS = 40_000

# Question number to sac_thue mapping
QUESTION_SAC_THUE = {
    "Q1": "CIT",
    "Q2": "PIT",
    "Q3": "FCT",
    "Q4": "VAT",
    "Q5": "CIT",
    "Q6": "PIT",
}

SAC_THUE_SYLLABUS = {
    "CIT": "CIT_Syllabus.docx",
    "VAT": "VAT_Syllabus.docx",
    "PIT": "PIT_Syllabus.docx",
    "FCT": "FCT_Syllabus.docx",
    "TP": "TaxAdmin_TP_Syllabus.docx",
    "ADMIN": "TaxAdmin_TP_Syllabus.docx",
}
