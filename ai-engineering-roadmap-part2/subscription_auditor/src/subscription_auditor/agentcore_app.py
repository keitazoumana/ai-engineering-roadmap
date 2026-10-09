"""AgentCore Runtime entrypoint for the SubscriptionAuditor crew.

Request payload:  {"filename": "statement.pdf", "pdf_base64": "<base64 of the PDF>"}
Response:         {"status": "succeeded", "report_markdown": "...", "transactions_csv": "..."}
                  {"status": "failed", "error": {"code": "...", "message": "..."}}
"""
import base64
import binascii
import logging
import shutil
import tempfile
import time
from pathlib import Path

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from subscription_auditor.crew import SubscriptionAuditor

MAX_PDF_BYTES = 4 * 1024 * 1024  # statements are small; reject anything unexpected

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("subscription_auditor")

app = BedrockAgentCoreApp()


def failed(code: str, message: str) -> dict:
    return {"status": "failed", "error": {"code": code, "message": message}}


def decode_pdf(payload: dict) -> bytes:
    """Validate the payload and return the PDF bytes, or raise ValueError."""
    if not isinstance(payload, dict) or not payload.get("pdf_base64"):
        raise ValueError("Payload must contain 'pdf_base64'.")
    try:
        pdf = base64.b64decode(payload["pdf_base64"], validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("'pdf_base64' is not valid base64.") from error
    if len(pdf) > MAX_PDF_BYTES:
        raise ValueError(f"PDF is larger than {MAX_PDF_BYTES // (1024 * 1024)} MB.")
    if not pdf.startswith(b"%PDF"):
        raise ValueError("The file is not a PDF.")
    return pdf


def run_audit(statement_path: Path) -> dict:
    """Run the crew and return its outputs."""
    result = SubscriptionAuditor().crew().kickoff(inputs={"statement_path": str(statement_path)})
    outputs = {task.name: task.raw for task in result.tasks_output}
    return {
        "transactions_csv": outputs.get("extract_task", ""),
        "report_markdown": outputs.get("review_task", result.raw),
    }


@app.entrypoint
def invoke(payload, context):
    session_id = getattr(context, "session_id", None)
    try:
        pdf = decode_pdf(payload)
    except ValueError as error:
        return failed("invalid_input", str(error))

    # Each invocation works in its own folder, deleted afterwards:
    # no statement is ever left on disk.
    work_dir = Path(tempfile.mkdtemp(prefix="audit_"))
    statement_path = work_dir / "statement.pdf"
    statement_path.write_bytes(pdf)
    started = time.time()
    logger.info("Audit started (session=%s, %d bytes)", session_id, len(pdf))
    try:
        outputs = run_audit(statement_path)
    except Exception:  # never leak internals to the caller; details go to CloudWatch
        logger.exception("Audit failed (session=%s)", session_id)
        return failed("audit_failed", "The agents could not complete the audit. Check the runtime logs.")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    duration = round(time.time() - started, 1)
    logger.info("Audit finished in %ss (session=%s)", duration, session_id)
    return {"status": "succeeded", "duration_seconds": duration, "filename": payload.get("filename"), **outputs}


if __name__ == "__main__":
    app.run()  # listens on port 8080 (0.0.0.0 inside a container)
