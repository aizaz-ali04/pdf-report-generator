"""
app.py — Stage 0, 4, 5: the API.

  GET  /health              -> { "status": "ok" }
  POST /reports              -> runs query -> render -> store, returns 201 + link
                                 (or 200 + existing link if one was already made today)
  GET  /reports/{id}         -> the report row + file link
  GET  /reports/{id}/file    -> serves the PDF bytes from disk

Idempotency: at most one report per calendar day, unless the caller
passes {"force": true} in the POST body.
"""
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from db import get_conn, init_db
from report import REPORTS_DIR, get_report_data, render_pdf, render_report_html

app = FastAPI(title="PDF report generator")


class GenerateReportBody(BaseModel):
    force: bool = False


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}

# Note: this endpoint blocks for a few seconds while Chromium renders — see README's Stage 4 note.
@app.post("/reports")
def create_report(body: GenerateReportBody = GenerateReportBody(), response: Response = None):
    """
    Runs the whole pipeline inside this one endpoint: query -> render -> store.
    No background job needed — the request just takes a few seconds.

    Idempotency: if a report was already generated today and force is not
    set, return that existing report (200) instead of making a new one (201).
    """
    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")

    if not body.force:
        existing = conn.execute(
            "SELECT id, path, created_at FROM reports WHERE date(created_at) = ? ORDER BY id DESC LIMIT 1",
            (today,),
        ).fetchone()
        if existing:
            conn.close()
            response.status_code = 200
            return {
                "id": existing["id"],
                "file": f"/reports/{existing['id']}/file",
            }

    # --- the pipeline: query -> render -> store ---
    data = get_report_data()
    html = render_report_html(data)

    # Insert first to get an id, then render to a path that uses that id.
    now_iso = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO reports (path, created_at) VALUES (?, ?)",
        ("", now_iso),
    )
    report_id = cur.lastrowid

    pdf_path = REPORTS_DIR / f"{report_id}.pdf"
    render_pdf(html, pdf_path)

    conn.execute("UPDATE reports SET path = ? WHERE id = ?", (str(pdf_path), report_id))
    conn.commit()
    conn.close()

    response.status_code = 201
    return {"id": report_id, "file": f"/reports/{report_id}/file"}


@app.get("/reports/{report_id}")
def get_report(report_id: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, path, created_at FROM reports WHERE id = ?", (report_id,)
    ).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="report not found")
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "file": f"/reports/{row['id']}/file",
    }


@app.get("/reports/{report_id}/file")
def get_report_file(report_id: int):
    conn = get_conn()
    row = conn.execute("SELECT path FROM reports WHERE id = ?", (report_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="report not found")

    pdf_path = Path(row["path"])
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="report file missing on disk")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"report-{report_id}.pdf",
    )
