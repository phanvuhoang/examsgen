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


def fix_default_session():
    """If the current default session has no files, promote the session with most files to default."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            # Find session with most active files
            cur.execute("""
                SELECT session_id, COUNT(*) AS file_count
                FROM session_files
                WHERE is_active = TRUE
                GROUP BY session_id
                ORDER BY file_count DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if not row:
                return  # no files anywhere — nothing to do
            best_session_id, file_count = row

            # Check if the current default already has files
            cur.execute("SELECT id FROM exam_sessions WHERE is_default = TRUE LIMIT 1")
            default_row = cur.fetchone()
            if default_row:
                cur.execute(
                    "SELECT COUNT(*) FROM session_files WHERE session_id = %s AND is_active = TRUE",
                    (default_row[0],)
                )
                if cur.fetchone()[0] > 0:
                    return  # default session already has files — no fix needed

            # Promote the session with most files to default
            cur.execute("UPDATE exam_sessions SET is_default = FALSE WHERE is_default = TRUE")
            cur.execute("UPDATE exam_sessions SET is_default = TRUE WHERE id = %s", (best_session_id,))
            logger.info(f"fix_default_session: set session {best_session_id} as default ({file_count} files)")
    except Exception as e:
        logger.warning(f"fix_default_session failed (non-critical): {e}")
