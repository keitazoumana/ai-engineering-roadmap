"""Offline tests for the Part 2 Lambda handler. No AWS calls, no network.

Run from the project root:
    pip install pytest
    pytest tests -q
"""
import base64
import json
import os
import sys
from pathlib import Path

# The handler reads RUNTIME_ARN at import time and builds a boto3 client (no network).
os.environ.setdefault("RUNTIME_ARN", "arn:aws:bedrock-agentcore:us-east-1:000000000000:runtime/test-id")
os.environ.setdefault("ALLOWED_ORIGIN", "http://localhost:8000")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lambda"))

import handler  # noqa: E402


def _body(event):
    return json.loads(event["body"])


def test_options_preflight_returns_204():
    event = {"httpMethod": "OPTIONS"}
    result = handler.handler(event, None)
    assert result["statusCode"] == 204
    assert result["headers"]["Access-Control-Allow-Origin"] == "http://localhost:8000"


def test_non_post_returns_405():
    event = {"httpMethod": "GET"}
    result = handler.handler(event, None)
    assert result["statusCode"] == 405


def test_invalid_base64_returns_400():
    event = {"httpMethod": "POST", "body": json.dumps({"pdf_base64": "not valid base64!!"})}
    result = handler.handler(event, None)
    assert result["statusCode"] == 400


def test_non_pdf_returns_400():
    not_a_pdf = base64.b64encode(b"hello world").decode()
    event = {"httpMethod": "POST", "body": json.dumps({"pdf_base64": not_a_pdf})}
    result = handler.handler(event, None)
    assert result["statusCode"] == 400
    assert "not a PDF" in _body(result)["error"]


def test_oversized_pdf_returns_413():
    big = base64.b64encode(b"%PDF" + b"0" * (4 * 1024 * 1024 + 1)).decode()
    event = {"httpMethod": "POST", "body": json.dumps({"pdf_base64": big})}
    result = handler.handler(event, None)
    assert result["statusCode"] == 413
