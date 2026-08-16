# Invoice → SAF AOR Row Extractor

A deterministic local FastAPI app that extracts Google Sheets-ready SAF AOR rows from supported PDF invoices. It makes no network calls and uses no LLM. Text-layer PDFs use `pdfplumber`; image-only pages automatically fall back to local RapidOCR with bundled ONNX models.

## Run locally

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

Supported signatures: Tong Tar, Leisure Frontier, Atlantic Travel, Ridewell, and Jadia. Peak windows and AOR constants are at the top of `config.py`. Vendor-specific extraction stays isolated under `parsers/`.

The service exposes `POST /extract` as multipart form data:

- `files`: one or more PDFs
- `need_by_date`, `gr_date`: batch strings (preserved verbatim)
- `file_contexts`: JSON object keyed by filename, such as `{"invoice.pdf":{"po_number":"OA123"}}`

Rows keep upload order, followed by printed line order within each PDF. Missing external fields and ambiguous/non-bus content are marked for review rather than fabricated. OCR is enabled by default through `OCR_ENABLED` in `config.py` and runs entirely on the local CPU.
