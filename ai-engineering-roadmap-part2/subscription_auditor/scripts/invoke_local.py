"""Send the sample statement to the locally running AgentCore container.

Run from the subscription_auditor/ folder, with the container listening on
port 8080 (docker run ... -p 8080:8080). Saves report.md and transactions.csv
next to where you run it; compare report.md with data/answer_key.md.
"""
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "http://localhost:8080/invocations"
SAMPLE_PDF = Path("data/bluepine_statement_2026Q3.pdf")
REQUEST_TIMEOUT_SECONDS = 600


def main() -> None:
    if not SAMPLE_PDF.exists():
        sys.exit(f"Sample statement not found: {SAMPLE_PDF.resolve()}")

    payload = {
        "filename": SAMPLE_PDF.name,
        "pdf_base64": base64.b64encode(SAMPLE_PDF.read_bytes()).decode("ascii"),
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    print(f"Sending {SAMPLE_PDF.name} to {ENDPOINT} (this takes a few minutes)...")
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        sys.exit(f"Request failed ({error.code}): {error.read().decode('utf-8', 'replace')}")
    except urllib.error.URLError as error:
        sys.exit(f"Could not reach {ENDPOINT}: {error.reason}")

    if body.get("status") != "succeeded":
        sys.exit(f"Audit failed: {json.dumps(body, indent=2)}")

    Path("report.md").write_text(body.get("report_markdown", ""), encoding="utf-8")
    Path("transactions.csv").write_text(body.get("transactions_csv", ""), encoding="utf-8")
    print(f"Done in {body.get('duration_seconds')}s. Wrote report.md and transactions.csv.")


if __name__ == "__main__":
    main()
