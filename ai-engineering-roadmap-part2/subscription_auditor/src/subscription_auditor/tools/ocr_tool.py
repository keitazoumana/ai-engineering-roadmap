"""OCR tool that reads a scanned page image with the same Bedrock model as the agents."""
import os
import tempfile
from pathlib import Path
from typing import Type

import boto3
from botocore.config import Config
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

FORMATS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg"}
MAX_IMAGE_BYTES = 3_750_000  # Bedrock Converse limit per image is 3.75 MB
PROMPT = (
    "This is one page of a bank statement. Transcribe every transaction line "
    "exactly as printed (date, description, amount), plus any printed totals. "
    "Do not summarize, guess or add anything that is not on the page."
)


class OCRInput(BaseModel):
    image_path: str = Field(..., description="Path of a page image listed by the Statement Reader.")


def bedrock_model_id() -> str:
    """MODEL is in CrewAI format (bedrock/<id>); Converse needs only <id>."""
    return os.getenv("MODEL", "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0").removeprefix("bedrock/")


def bedrock_region() -> str:
    return os.getenv("AWS_REGION_NAME") or os.getenv("AWS_REGION") or "us-east-1"


class BedrockOCRTool(BaseTool):
    name: str = "OCR tool"
    description: str = "Reads the text of a scanned statement page image, using the Bedrock model."
    args_schema: Type[BaseModel] = OCRInput

    def _run(self, image_path: str) -> str:
        path = Path(image_path).resolve()
        # Only read images the Statement Reader wrote to the temp folder.
        if Path(tempfile.gettempdir()).resolve() not in path.parents:
            return "Error: only page images listed by the Statement Reader can be read."
        if path.suffix.lower() not in FORMATS or not path.is_file():
            return f"Error: no PNG or JPEG image at {image_path}"
        image = path.read_bytes()
        if len(image) > MAX_IMAGE_BYTES:
            return "Error: page image is too large for the model."

        client = boto3.client("bedrock-runtime", region_name=bedrock_region(),
                              config=Config(read_timeout=120, retries={"max_attempts": 3, "mode": "adaptive"}))
        response = client.converse(
            modelId=bedrock_model_id(),
            messages=[{"role": "user", "content": [
                {"text": PROMPT},
                {"image": {"format": FORMATS[path.suffix.lower()], "source": {"bytes": image}}},
            ]}],
            inferenceConfig={"temperature": 0},
        )
        return response["output"]["message"]["content"][0]["text"]
