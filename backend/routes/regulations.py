import os
import shutil
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional

from backend.config import REGULATIONS_DIR
from backend.database import get_db
from backend.document_extractor import extract_text

router = APIRouter(prefix="/api/regulations", tags=["regulations"])


@router.get("")
def list_regulations(sac_thue: Optional[str] = None):
    with get_db() as conn:
        cur = conn.cursor()
        if sac_thue:
            cur.execute(
                "SELECT id, sac_thue, ten_van_ban, loai, ngon_ngu, file_name, is_active, uploaded_at "
                "FROM regulations WHERE sac_thue = %s ORDER BY uploaded_at DESC",
                (sac_thue,),
            )
        else:
            cur.execute(
                "SELECT id, sac_thue, ten_van_ban, loai, ngon_ngu, file_name, is_active, uploaded_at "
                "FROM regulations ORDER BY sac_thue, uploaded_at DESC"
            )
        rows = cur.fetchall()
    return [
        {
            "id": r[0], "sac_thue": r[1], "ten_van_ban": r[2], "loai": r[3],
            "ngon_ngu": r[4], "file_name": r[5], "is_active": r[6],
            "uploaded_at": r[7].isoformat() if r[7] else None,
        }
        for r in rows
    ]


@router.post("/upload")
async def upload_regulation(
    file: UploadFile = File(...),
    sac_thue: str = Form(...),
    ten_van_ban: Optional[str] = Form(None),
    loai: str = Form("LAW"),
    ngon_ngu: str = Form("ENG"),
):
    if not file.filename.endswith((".doc", ".docx")):
        raise HTTPException(status_code=400, detail="Only .doc and .docx files are supported")

    save_dir = os.path.join(REGULATIONS_DIR, sac_thue)
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, file.filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO regulations (sac_thue, ten_van_ban, loai, ngon_ngu, file_path, file_name) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (sac_thue, ten_van_ban or file.filename, loai, ngon_ngu, file_path, file.filename),
        )
        reg_id = cur.fetchone()[0]

    return {"id": reg_id, "message": "File uploaded successfully"}


@router.patch("/{reg_id}")
def toggle_regulation(reg_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE regulations SET is_active = NOT is_active WHERE id = %s RETURNING is_active",
            (reg_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Regulation not found")
    return {"id": reg_id, "is_active": row[0]}


@router.delete("/{reg_id}")
def delete_regulation(reg_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE regulations SET is_active = FALSE WHERE id = %s RETURNING id",
            (reg_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Regulation not found")
    return {"message": "Regulation deactivated"}


@router.get("/{reg_id}/text")
def get_regulation_text(reg_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_path, ten_van_ban FROM regulations WHERE id = %s", (reg_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Regulation not found")
    text = extract_text(row[0])
    return {"id": reg_id, "name": row[1], "text": text[:50000]}
