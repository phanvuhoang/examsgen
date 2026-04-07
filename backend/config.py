import os


# AI — Primary (Claudible, OpenAI-compatible)
CLAUDIBLE_BASE_URL = os.getenv("CLAUDIBLE_BASE_URL", "https://claudible.io/v1")
CLAUDIBLE_API_KEY = os.getenv("CLAUDIBLE_API_KEY", "")
CLAUDIBLE_MODEL_HAIKU  = os.getenv("CLAUDIBLE_MODEL_HAIKU",  "claude-haiku-4.5")

# AI — Anthropic direct
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL_HAIKU  = os.getenv("ANTHROPIC_MODEL_HAIKU",  "claude-haiku-4-5")
ANTHROPIC_MODEL_FAST   = os.getenv("ANTHROPIC_MODEL_FAST",   "claude-sonnet-4-6")
ANTHROPIC_MODEL_STRONG = os.getenv("ANTHROPIC_MODEL_STRONG", "claude-opus-4-6")

# AI — OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL_FAST   = os.getenv("OPENAI_MODEL_FAST",   "gpt-4o-mini")
OPENAI_MODEL_STRONG = os.getenv("OPENAI_MODEL_STRONG", "gpt-4o")

# AI — DeepSeek direct
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL   = os.getenv("DEEPSEEK_MODEL",   "deepseek-reasoner")

# AI — OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL1  = os.getenv("OPENROUTER_MODEL1",  "")
OPENROUTER_MODEL2  = os.getenv("OPENROUTER_MODEL2",  "")
OPENROUTER_MODEL3  = os.getenv("OPENROUTER_MODEL3",  "")

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
