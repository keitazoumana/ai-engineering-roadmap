"""FastAPI web UI for the SubscriptionAuditor crew.

Run from the project root:

    uv run python ui/server.py

Then open http://127.0.0.1:8000 in your browser.
"""
from __future__ import annotations

import json
import queue
import shutil
import threading
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from subscription_auditor.crew import SubscriptionAuditor

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
# crewai writes report.md / transactions.csv relative to the working directory.
PROJECT_ROOT = BASE_DIR.parent

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# The three sequential tasks, in order, shown as agent stages in the UI.
AGENT_STAGES = [
    {
        "key": "extract",
        "label": "Statement Extractor",
        "detail": "Reading the PDF and extracting every transaction",
    },
    {
        "key": "detect",
        "label": "Subscription Detective",
        "detail": "Finding recurring charges, price increases and duplicates",
    },
    {
        "key": "review",
        "label": "Savings Reviewer",
        "detail": "Verifying findings and writing your savings report",
    },
]

app = FastAPI(title="SubscriptionAuditor")

jobs: dict[str, dict] = {}


def _run_job(job_id: str, statement_path: Path) -> None:
    """Run the crew in a background thread, pushing progress onto the job queue."""
    job = jobs[job_id]
    events: "queue.Queue[dict]" = job["events"]
    completed = {"count": 0}

    def on_task_complete(_output: object) -> None:
        completed["count"] += 1
        done = completed["count"]
        events.put(
            {
                "type": "progress",
                "activeIndex": done,
                "percent": int(done / len(AGENT_STAGES) * 100),
            }
        )

    # The first agent starts working immediately.
    events.put({"type": "progress", "activeIndex": 0, "percent": 5})

    try:
        crew = SubscriptionAuditor().crew()
        crew.task_callback = on_task_complete
        crew.kickoff(inputs={"statement_path": str(statement_path)})

        job_output = OUTPUT_DIR / job_id
        job_output.mkdir(parents=True, exist_ok=True)

        report_text = ""
        report_src = PROJECT_ROOT / "report.md"
        if report_src.is_file():
            report_text = report_src.read_text(encoding="utf-8")
            shutil.copyfile(report_src, job_output / "report.md")

        csv_src = PROJECT_ROOT / "transactions.csv"
        has_csv = csv_src.is_file()
        if has_csv:
            shutil.copyfile(csv_src, job_output / "transactions.csv")

        job["report"] = report_text
        events.put(
            {"type": "done", "percent": 100, "report": report_text, "hasCsv": has_csv}
        )
    except Exception as error:  # surface any failure to the browser
        events.put({"type": "error", "message": str(error)})
    finally:
        events.put({"type": "end"})


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF statement.")

    job_id = uuid.uuid4().hex
    dest = UPLOAD_DIR / f"{job_id}_{Path(file.filename).name}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    jobs[job_id] = {"events": queue.Queue(), "report": None, "filename": file.filename}
    threading.Thread(target=_run_job, args=(job_id, dest), daemon=True).start()
    return {"jobId": job_id, "filename": file.filename, "stages": AGENT_STAGES}


@app.get("/api/progress/{job_id}")
def progress(job_id: str) -> StreamingResponse:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job.")
    events: "queue.Queue[dict]" = job["events"]

    def stream():
        while True:
            payload = events.get()
            yield f"data: {json.dumps(payload)}\n\n"
            if payload.get("type") == "end":
                break

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/report/{job_id}/download")
def download_report(job_id: str) -> FileResponse:
    path = OUTPUT_DIR / job_id / "report.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Report not ready.")
    return FileResponse(
        path, media_type="text/markdown", filename="subscription_report.md"
    )


@app.get("/api/transactions/{job_id}/download")
def download_transactions(job_id: str) -> FileResponse:
    path = OUTPUT_DIR / job_id / "transactions.csv"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Transactions not ready.")
    return FileResponse(path, media_type="text/csv", filename="transactions.csv")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
