from pathlib import Path
from typing import Type

import pdfplumber
import pymupdf
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# A page with fewer characters than this is treated as scanned (image-only).
SCANNED_PAGE_TEXT_THRESHOLD = 20

# Bundled statements live in <package>/data, regardless of the working directory.
PACKAGE_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def resolve_statement_path(statement_path: str) -> Path | None:
    """Find the statement whether the path is absolute, relative to the cwd, or a
    name/relative path under the package's data folder."""
    candidates = [
        Path(statement_path),
        PACKAGE_DATA_DIR / statement_path,
        PACKAGE_DATA_DIR / Path(statement_path).name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class StatementReaderInput(BaseModel):
    """Input schema for StatementReaderTool."""
    statement_path: str = Field(..., description="Path to the bank statement PDF file to read.")


class StatementReaderTool(BaseTool):
    name: str = "Statement Reader"
    description: str = (
        "Reads a bank statement PDF and returns its full text content, including "
        "tables of transactions, so it can be parsed into individual transactions "
        "with dates, merchants and amounts. Any page that has no extractable text "
        "(a scanned page) is rendered to a PNG image whose path is listed at the "
        "end, so the OCR tool can read it."
    )
    args_schema: Type[BaseModel] = StatementReaderInput

    def _run(self, statement_path: str) -> str:
        path = resolve_statement_path(statement_path)
        if path is None:
            return (
                f"Error: no statement file found at '{statement_path}' "
                f"(also looked in {PACKAGE_DATA_DIR})."
            )
        if path.suffix.lower() != ".pdf":
            return f"Error: expected a PDF statement but got '{path.suffix}'."

        pages_text: list[str] = []
        scanned_pages: list[int] = []
        try:
            with pdfplumber.open(path) as pdf:
                for page_number, page in enumerate(pdf.pages, start=1):
                    text = (page.extract_text() or "").strip()
                    if len(text) < SCANNED_PAGE_TEXT_THRESHOLD:
                        scanned_pages.append(page_number)
                        pages_text.append(
                            f"--- Page {page_number} (scanned, see OCR image) ---"
                        )
                    else:
                        pages_text.append(f"--- Page {page_number} ---\n{text}")
        except Exception as error:
            return f"Error: could not read the PDF statement: {error}"

        image_notes = self._render_scanned_pages(path, scanned_pages)

        content = "\n\n".join(pages_text).strip()
        if not content and not image_notes:
            return "Error: the PDF statement contained no extractable text."
        if image_notes:
            content = f"{content}\n\n{image_notes}"
        return content

    def _render_scanned_pages(self, path: Path, scanned_pages: list[int]) -> str:
        """Render text-less pages to PNGs and return their paths for the OCR tool."""
        if not scanned_pages:
            return ""

        image_paths: list[str] = []
        try:
            document = pymupdf.open(path)
            for page_number in scanned_pages:
                page = document.load_page(page_number - 1)
                pixmap = page.get_pixmap(dpi=200)
                image_path = path.with_name(f"{path.stem}_page{page_number}.png")
                pixmap.save(image_path)
                image_paths.append(str(image_path))
            document.close()
        except Exception as error:
            return f"Note: found scanned pages but could not render them for OCR: {error}"

        listed = "\n".join(f"- Page {n}: {p}" for n, p in zip(scanned_pages, image_paths))
        return (
            "Scanned pages could not be read as text. Use the OCR tool on these "
            f"images to recover their transactions:\n{listed}"
        )

