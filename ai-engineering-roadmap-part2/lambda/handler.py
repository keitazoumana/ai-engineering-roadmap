"""Lambda behind the REST API: POST /audits runs the audit on AgentCore Runtime.

Synchronous on purpose: the request stays open while the agents work (usually one
to two minutes) and the report comes back in the response. No queue, no storage,
no polling.

Request body:  {"filename": "statement.pdf", "pdf_base64": "<base64 of the PDF>"}
Response:      {"status": "succeeded", "report_markdown": "...", "transactions_csv": "..."}

Environment variables:
  RUNTIME_ARN     ARN of the AgentCore Runtime agent
  ALLOWED_ORIGIN  origin of the web UI, for CORS (for example http://localhost:8000)
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import uuid

import boto3
from botocore.config import Config

RUNTIME_ARN = os.environ["RUNTIME_ARN"]
# CORS origin, set per environment. No origin is hardcoded: when unset, the browser
# simply refuses cross-origin reads, while the function itself keeps working.
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "")
MAX_PDF_BYTES = 4 * 1024 * 1024

# Timeouts, from the inside out: wait 170 s for the agents, the function stops at
# 180 s, API Gateway at 190 s. The innermost one fires first, so the user always
# gets a clear message instead of a bare timeout.
# No automatic retries: a retry would run the whole crew again and bill the model twice.
agentcore = boto3.client(
    "bedrock-agentcore",
    config=Config(read_timeout=170, connect_timeout=10, retries={"max_attempts": 1, "mode": "standard"}),
)


def response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            # With Lambda proxy integration, CORS headers must come from the function.
            "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "OPTIONS,POST",
        },
        "body": json.dumps(body),
    }


def method_of(event: dict) -> str:
    # REST API (payload 1.0) uses httpMethod; HTTP API and function URLs (2.0) use requestContext.http.
    return event.get("httpMethod") or (event.get("requestContext") or {}).get("http", {}).get("method", "")


def handler(event, context):
    method = method_of(event)
    if method == "OPTIONS":  # CORS preflight
        return response(204, {})
    if method != "POST":
        return response(405, {"error": "Use POST /audits."})

    try:
        raw = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode()
        body = json.loads(raw)
        pdf = base64.b64decode(body.get("pdf_base64", ""), validate=True)
    except (ValueError, binascii.Error):
        return response(400, {"error": "Send JSON with 'pdf_base64' (the PDF, base64-encoded)."})
    if not pdf.startswith(b"%PDF"):
        return response(400, {"error": "The file is not a PDF."})
    if len(pdf) > MAX_PDF_BYTES:
        return response(413, {"error": "The PDF is larger than 4 MB."})

    filename = os.path.basename(str(body.get("filename") or "statement.pdf"))[:200]
    try:
        reply = agentcore.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            # A new session per audit = a fresh, isolated microVM (33+ characters).
            runtimeSessionId=f"audit-{uuid.uuid4().hex}-{context.aws_request_id}",
            payload=json.dumps({"filename": filename, "pdf_base64": base64.b64encode(pdf).decode()}),
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(reply["response"].read())
    except Exception as error:  # details stay in CloudWatch, the user gets a clear message
        print(f"AgentCore invocation failed: {error!r}")
        return response(502, {"status": "failed", "error": "The agent could not be reached. Try again in a minute."})

    if result.get("status") != "succeeded":
        message = (result.get("error") or {}).get("message", "The audit failed.")
        return response(502, {"status": "failed", "error": message})
    return response(200, result)
