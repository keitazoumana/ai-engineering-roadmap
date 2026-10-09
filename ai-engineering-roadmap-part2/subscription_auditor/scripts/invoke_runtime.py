"""Invoke the deployed AgentCore Runtime with the sample statement.

Run from the subscription_auditor/ folder, with an AWS profile that may call
bedrock-agentcore:InvokeAgentRuntime (for example auditor-admin):

    AWS_PROFILE=auditor-admin uv run python scripts/invoke_runtime.py <RUNTIME_ARN>

Saves report.md and transactions.csv next to where you run it; compare report.md
with data/answer_key.md.
"""
import base64
import json
import sys
import uuid
from pathlib import Path

import boto3

SAMPLE_PDF = Path("data/bluepine_statement_2026Q3.pdf")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/invoke_runtime.py <RUNTIME_ARN>")
    runtime_arn = sys.argv[1]

    # arn:aws:bedrock-agentcore:<region>:<account>:runtime/<id>
    arn_parts = runtime_arn.split(":")
    if len(arn_parts) < 6 or arn_parts[2] != "bedrock-agentcore":
        sys.exit(f"Not a valid AgentCore runtime ARN: {runtime_arn}")
    region = arn_parts[3]

    if not SAMPLE_PDF.exists():
        sys.exit(f"Sample statement not found: {SAMPLE_PDF.resolve()}")

    payload = {
        "filename": SAMPLE_PDF.name,
        "pdf_base64": base64.b64encode(SAMPLE_PDF.read_bytes()).decode("ascii"),
    }

    client = boto3.client("bedrock-agentcore", region_name=region)
    print(f"Invoking {runtime_arn} (this takes a few minutes)...")
    reply = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=f"local-test-{uuid.uuid4().hex}",  # 33+ characters
        payload=json.dumps(payload),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(reply["response"].read())

    status = result.get("status")
    print(f"Status: {status}")
    if status != "succeeded":
        sys.exit(json.dumps(result, indent=2))

    Path("report.md").write_text(result.get("report_markdown", ""), encoding="utf-8")
    Path("transactions.csv").write_text(result.get("transactions_csv", ""), encoding="utf-8")
    print(f"Done in {result.get('duration_seconds')}s. Wrote report.md and transactions.csv.")


if __name__ == "__main__":
    main()
