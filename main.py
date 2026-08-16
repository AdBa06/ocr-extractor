from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from extraction import read_pdf
from service import extract_rows


BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Invoice Extractor")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.middleware("http")
async def disable_browser_cache(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract")
async def extract(
    files: list[UploadFile] = File(...),
    need_by_date: str = Form(""),
    gr_date: str = Form(""),
    file_contexts: str = Form("{}"),
):
    try:
        contexts = json.loads(file_contexts)
        if not isinstance(contexts, dict):
            contexts = {}
    except json.JSONDecodeError:
        contexts = {}

    rows = []
    files_meta = []
    for uploaded in files:
        filename = Path(uploaded.filename or "unnamed.pdf").name
        po_number = str(contexts.get(filename, {}).get("po_number", ""))
        if (uploaded.content_type and uploaded.content_type != "application/pdf") or not filename.lower().endswith(".pdf"):
            rows.extend(extract_rows([], filename, need_by_date, gr_date, po_number))
            rows[-1]["notes"] = "Only PDF files are supported"
            rows[-1]["needs_review"] = True
            files_meta.append({"source_file": filename, "vendor": None})
            continue
        try:
            pages = read_pdf(await uploaded.read())
            file_rows = extract_rows(pages, filename, need_by_date, gr_date, po_number)
        except Exception as exc:
            file_rows = extract_rows([], filename, need_by_date, gr_date, po_number)
            file_rows[0]["notes"] = f"PDF could not be read: {type(exc).__name__}: {exc}"
            file_rows[0]["needs_review"] = True
        rows.extend(file_rows)
        files_meta.append({"source_file": filename, "row_count": len(file_rows)})
    return {"columns": config.OUTPUT_COLUMNS, "rows": rows, "files": files_meta}
