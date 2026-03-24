import logging
from backend.database import get_db

logger = logging.getLogger(__name__)


def seed_regulations():
    """Seed a default exam session if none exists."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM exam_sessions")
            if cur.fetchone()[0] == 0:
                cur.execute("""
                    INSERT INTO exam_sessions (name, exam_date, assumed_date, is_default)
                    VALUES ('June 2026', 'Jun2026', '1 June 2026', TRUE)
                """)
                logger.info("Seeded default exam session: June 2026")
    except Exception as e:
        logger.warning(f"Seed failed (non-critical): {e}")
