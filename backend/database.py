import psycopg2
import psycopg2.extras
import json
import logging
from contextlib import contextmanager

from backend.config import DATABASE_URL

logger = logging.getLogger(__name__)

psycopg2.extras.register_default_jsonb(globally=True, loads=json.loads)


def get_connection():
    return psycopg2.connect(DATABASE_URL)


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS regulations (
                id SERIAL PRIMARY KEY,
                sac_thue VARCHAR(20) NOT NULL,
                ten_van_ban VARCHAR(500),
                loai VARCHAR(50),
                ngon_ngu VARCHAR(5) DEFAULT 'ENG',
                file_path VARCHAR(500),
                file_name VARCHAR(500),
                is_active BOOLEAN DEFAULT TRUE,
                uploaded_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                question_type VARCHAR(20) NOT NULL,
                sac_thue VARCHAR(20) NOT NULL,
                question_part INTEGER,
                question_number VARCHAR(10),
                content_json JSONB NOT NULL,
                content_html TEXT,
                model_used VARCHAR(100),
                provider_used VARCHAR(50),
                exam_session VARCHAR(20) DEFAULT 'Jun2026',
                created_at TIMESTAMP DEFAULT NOW(),
                is_starred BOOLEAN DEFAULT FALSE,
                notes TEXT,
                user_id INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS kb_syllabus (
                id SERIAL PRIMARY KEY,
                sac_thue VARCHAR(20) NOT NULL,
                section_code VARCHAR(50),
                section_title VARCHAR(500),
                content TEXT NOT NULL,
                tags VARCHAR(500),
                source_file VARCHAR(200),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS kb_regulation (
                id SERIAL PRIMARY KEY,
                sac_thue VARCHAR(20) NOT NULL,
                regulation_ref VARCHAR(200),
                content TEXT NOT NULL,
                tags VARCHAR(500),
                syllabus_ids INTEGER[] DEFAULT '{}',
                source_file VARCHAR(200),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS kb_sample (
                id SERIAL PRIMARY KEY,
                question_type VARCHAR(20) NOT NULL,
                sac_thue VARCHAR(20) NOT NULL,
                title VARCHAR(300),
                content TEXT NOT NULL,
                exam_tricks TEXT,
                syllabus_ids INTEGER[] DEFAULT '{}',
                regulation_ids INTEGER[] DEFAULT '{}',
                source VARCHAR(100) DEFAULT 'manual',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS exam_sessions (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                exam_window_start DATE,
                exam_window_end DATE,
                regulations_cutoff DATE NOT NULL,
                fiscal_year_end DATE,
                tax_year INTEGER,
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                is_default BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS generation_log (
                id SERIAL PRIMARY KEY,
                question_id INTEGER REFERENCES questions(id),
                question_type VARCHAR(20),
                sac_thue VARCHAR(20),
                model_used VARCHAR(100),
                provider_used VARCHAR(50),
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                duration_ms INTEGER,
                status VARCHAR(20),
                error TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );

            -- Seed default sessions
            INSERT INTO exam_sessions (name, exam_window_start, exam_window_end, regulations_cutoff, fiscal_year_end, tax_year, is_default)
            VALUES ('June 2026', '2026-06-01', '2026-06-30', '2025-12-31', '2025-12-31', 2025, TRUE)
            ON CONFLICT (name) DO NOTHING;

            INSERT INTO exam_sessions (name, exam_window_start, exam_window_end, regulations_cutoff, fiscal_year_end, tax_year, is_default)
            VALUES ('December 2026', '2026-12-01', '2026-12-31', '2025-12-31', '2025-12-31', 2025, FALSE)
            ON CONFLICT (name) DO NOTHING;

            -- Add session_id columns to KB and questions tables
            ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES exam_sessions(id);
            ALTER TABLE kb_regulation ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES exam_sessions(id);
            ALTER TABLE kb_sample ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES exam_sessions(id);
            ALTER TABLE questions ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES exam_sessions(id);

            -- Assign existing rows to default session
            UPDATE kb_syllabus SET session_id = (SELECT id FROM exam_sessions WHERE is_default = TRUE) WHERE session_id IS NULL;
            UPDATE kb_regulation SET session_id = (SELECT id FROM exam_sessions WHERE is_default = TRUE) WHERE session_id IS NULL;
            UPDATE kb_sample SET session_id = (SELECT id FROM exam_sessions WHERE is_default = TRUE) WHERE session_id IS NULL;
            UPDATE questions SET session_id = (SELECT id FROM exam_sessions WHERE is_default = TRUE) WHERE session_id IS NULL;
        """)
        logger.info("Database tables initialized")
