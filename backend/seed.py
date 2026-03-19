"""Seed existing data files into the regulations table on first startup."""
import os
import logging
from backend.config import REGULATIONS_DIR
from backend.database import get_db

logger = logging.getLogger(__name__)

REGULATION_META = {
    "CIT": [
        ("CIT_Law_67_2025_ENG.doc", "CIT Law 67/2025/QH15 (English)", "LAW"),
        ("CIT_Decree_320_2025_ENG.doc", "CIT Decree 320/2025/ND-CP (English)", "DECREE"),
    ],
    "VAT": [
        ("VAT_Law_48_2024_ENG.doc", "VAT Law 48/2024/QH15 (English)", "LAW"),
        ("VAT_Decree_181_2025_ENG.doc", "VAT Decree 181/2025/ND-CP (English)", "DECREE"),
        ("VAT_FCT_Circular_69_2025_ENG.doc", "VAT/FCT Circular 69/2025/TT-BTC (English)", "CIRCULAR"),
    ],
    "PIT": [
        ("PIT_VBHN_02_ENG.doc", "PIT Consolidated Law VBHN 02 (English)", "LAW"),
    ],
    "FCT": [
        ("FCT_Circular_103_2014_ENG.doc", "FCT Circular 103/2014/TT-BTC (English)", "CIRCULAR"),
    ],
    "TP": [
        ("TP_Decree_132_2020.doc", "TP Decree 132/2020/ND-CP", "DECREE"),
    ],
    "ADMIN": [
        ("TaxAdmin_VBHN_15_ENG.doc", "Tax Administration Consolidated Law VBHN 15 (English)", "LAW"),
        ("QLT_Decree_20_2025_ENG.doc", "Tax Admin Decree 20/2025/ND-CP (English)", "DECREE"),
        ("Invoice_VBHN_18_ENG.doc", "Invoice Consolidated Law VBHN 18 (English)", "LAW"),
    ],
    "SHARED": [
        ("Tax_Rates_Jun2026.docx", "Tax Rates — Jun 2026 Exam Session", "TAXRATES"),
        ("PIT_Rates_Jun2026.docx", "PIT Tax Rates — Jun 2026 Exam Session", "TAXRATES"),
    ],
}


def seed_regulations():
    """Insert regulation records for existing files if the table is empty."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM regulations")
            count = cur.fetchone()[0]
            if count > 0:
                logger.info(f"Regulations table has {count} records, skipping seed")
                return

            inserted = 0
            for sac_thue, files in REGULATION_META.items():
                for fname, name, loai in files:
                    file_path = os.path.join(REGULATIONS_DIR, sac_thue, fname)
                    if os.path.exists(file_path):
                        cur.execute(
                            "INSERT INTO regulations (sac_thue, ten_van_ban, loai, ngon_ngu, file_path, file_name) "
                            "VALUES (%s, %s, %s, 'ENG', %s, %s)",
                            (sac_thue, name, loai, file_path, fname),
                        )
                        inserted += 1
                    else:
                        logger.warning(f"Seed file not found: {file_path}")

            logger.info(f"Seeded {inserted} regulation records")
    except Exception as e:
        logger.error(f"Failed to seed regulations: {e}")
