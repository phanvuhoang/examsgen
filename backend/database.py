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
        """)
        logger.info("Database tables initialized")
