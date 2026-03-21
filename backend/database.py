import os
import psycopg2
import psycopg2.extras
import json
import logging
from contextlib import contextmanager

from backend.config import DATABASE_URL, DATA_DIR

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

            -- Add folder_path to exam_sessions
            ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS folder_path VARCHAR(500);

            -- Add doc_type and session_id to regulations
            ALTER TABLE regulations ADD COLUMN IF NOT EXISTS doc_type VARCHAR(50) DEFAULT 'regulation';
            ALTER TABLE regulations ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES exam_sessions(id);

            -- Seed default sessions
            INSERT INTO exam_sessions (name, exam_window_start, exam_window_end, regulations_cutoff, fiscal_year_end, tax_year, is_default, folder_path)
            VALUES ('June 2026', '2026-06-01', '2026-06-30', '2025-12-31', '2025-12-31', 2025, TRUE, 'sessions/june_2026')
            ON CONFLICT (name) DO UPDATE SET folder_path = EXCLUDED.folder_path WHERE exam_sessions.folder_path IS NULL;

            INSERT INTO exam_sessions (name, exam_window_start, exam_window_end, regulations_cutoff, fiscal_year_end, tax_year, is_default, folder_path)
            VALUES ('December 2026', '2026-12-01', '2026-12-31', '2025-12-31', '2025-12-31', 2025, FALSE, 'sessions/december_2026')
            ON CONFLICT (name) DO UPDATE SET folder_path = EXCLUDED.folder_path WHERE exam_sessions.folder_path IS NULL;

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
            UPDATE regulations SET session_id = (SELECT id FROM exam_sessions WHERE is_default = TRUE) WHERE session_id IS NULL;

            -- v2: exam_sessions — session settings columns
            ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS parameters JSONB DEFAULT '[]';
            ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS tax_types JSONB DEFAULT '[]';
            ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS question_types JSONB DEFAULT '[]';

            -- v2: kb_syllabus — new structured fields
            ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS tax_type VARCHAR(30);
            ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS syllabus_code VARCHAR(50);
            ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS topic VARCHAR(300);
            ALTER TABLE kb_syllabus ADD COLUMN IF NOT EXISTS detailed_syllabus TEXT;
        """)
        # v2: new tables
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_kb_syllabus_session_code
              ON kb_syllabus(session_id, tax_type, syllabus_code)
              WHERE syllabus_code IS NOT NULL;

            CREATE TABLE IF NOT EXISTS kb_regulation_parsed (
                id SERIAL PRIMARY KEY,
                session_id INTEGER REFERENCES exam_sessions(id),
                tax_type VARCHAR(30) NOT NULL,
                reg_code VARCHAR(100),
                doc_ref VARCHAR(200),
                article_no VARCHAR(50),
                paragraph_no INTEGER,
                paragraph_text TEXT NOT NULL,
                syllabus_codes TEXT[],
                tags VARCHAR(500),
                source_file VARCHAR(300),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS kb_tax_rates (
                id SERIAL PRIMARY KEY,
                session_id INTEGER REFERENCES exam_sessions(id),
                tax_type VARCHAR(30) NOT NULL,
                table_name VARCHAR(200) NOT NULL,
                content TEXT NOT NULL,
                source_file VARCHAR(300),
                display_order INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS sample_questions (
                id SERIAL PRIMARY KEY,
                question_type VARCHAR(20) NOT NULL,
                question_subtype VARCHAR(30),
                tax_type VARCHAR(30) NOT NULL,
                title VARCHAR(300),
                content TEXT NOT NULL,
                answer TEXT,
                marks INTEGER,
                exam_ref VARCHAR(200),
                syllabus_codes TEXT[],
                reg_codes TEXT[],
                tags VARCHAR(500),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            );

            -- v2: questions table — tagging fields
            ALTER TABLE questions ADD COLUMN IF NOT EXISTS mcq_subtype VARCHAR(30);
            ALTER TABLE questions ADD COLUMN IF NOT EXISTS syllabus_codes TEXT[];
            ALTER TABLE questions ADD COLUMN IF NOT EXISTS reg_codes TEXT[];
        """)

        # v2: seed default settings for existing sessions
        cur.execute("""
            UPDATE exam_sessions SET
                parameters = '[{"key":"USD Exchange Rate","value":"26500","unit":"VND"},{"key":"Monthly Base Salary (SHUI)","value":"46800000","unit":"VND"}]'::jsonb,
                tax_types = '[{"code":"CIT","name":"Corporate Income Tax"},{"code":"PIT","name":"Personal Income Tax"},{"code":"FCT","name":"Foreign Contractor Tax"},{"code":"VAT","name":"Value Added Tax"},{"code":"TAX-ADMIN","name":"Tax Administration"},{"code":"TP","name":"Transfer Pricing"}]'::jsonb,
                question_types = '[{"code":"MCQ","name":"Multiple Choice","subtypes":[{"code":"MCQ-1","name":"Single correct answer","description":"One correct answer out of 4 options","sample":""},{"code":"MCQ-N","name":"Multiple correct answers","description":"Two or more correct options. Candidates select all that apply.","sample":""},{"code":"MCQ-FIB","name":"Fill in the blank (words)","description":"Candidate fills missing word(s). Provide word bank.","sample":""}]},{"code":"SCENARIO","name":"Scenario Question (10-15 marks)","subtypes":[]},{"code":"LONGFORM","name":"Long-form Question (15-25 marks)","subtypes":[]}]'::jsonb
            WHERE parameters = '[]'::jsonb OR parameters IS NULL
        """)

        # Create session folders on disk
        cur.execute("SELECT folder_path FROM exam_sessions WHERE folder_path IS NOT NULL")
        for (fp,) in cur.fetchall():
            for sub in ['regulations', 'syllabus', 'samples']:
                os.makedirs(os.path.join(DATA_DIR, fp, sub), exist_ok=True)
        logger.info("Database tables initialized")
