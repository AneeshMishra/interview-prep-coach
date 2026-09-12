"""
Fetch a Google Doc as .docx via its public export link, so it can flow
through the exact same parse -> structure -> persist -> embed pipeline as a
manually uploaded file (see app/ingestion/pipeline.py and the /upload and
/import/google-doc routes in app/api/routers/documents.py).

This only works for documents shared as "Anyone with the link can view" —
there is no OAuth/Drive API integration here, so a private document will
fail with GoogleDocNotAccessible rather than silently returning nothing.
"""
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote

import httpx

DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB
GOOGLE_DOC_ID_PATTERN = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")


class GoogleDocNotAccessible(Exception):
    """The doc couldn't be fetched as .docx — bad link, private doc, or network failure."""


class GoogleDocTooLarge(Exception):
    """The export exceeded the configured max upload size."""


def extract_google_doc_id(url: str) -> str | None:
    match = GOOGLE_DOC_ID_PATTERN.search(url)
    return match.group(1) if match else None


def export_url_for(doc_id: str) -> str:
    return f"https://docs.google.com/document/d/{doc_id}/export?format=docx"


def sanitize_docx_filename(filename: str | None) -> str | None:
    """Reduce to a safe basename ending in .docx, or None if there's nothing usable."""
    if not filename:
        return None
    safe = Path(filename).name
    if not safe:
        return None
    if not safe.lower().endswith(".docx"):
        safe = f"{safe}.docx"
    return safe


def _filename_from_content_disposition(header: str | None) -> str | None:
    if not header:
        return None
    star_match = re.search(r"filename\*=UTF-8''([^;]+)", header)
    if star_match:
        return unquote(star_match.group(1))
    quoted_match = re.search(r'filename="([^"]+)"', header)
    if quoted_match:
        return quoted_match.group(1)
    return None


async def download_google_doc_as_docx(
    doc_id: str,
    max_bytes: int,
    client: httpx.AsyncClient | None = None,
) -> tuple[Path, str | None]:
    """Download the doc's public .docx export to a temp file.

    Returns (temp_file_path, filename_from_export). The caller owns the temp
    file and is responsible for deleting it, same contract as the regular
    upload endpoint's temp file.

    Raises GoogleDocNotAccessible if the doc isn't publicly link-viewable or
    the request otherwise fails, or GoogleDocTooLarge if the export exceeds
    max_bytes.
    """
    owns_client = client is None
    client = client or httpx.AsyncClient(follow_redirects=True, timeout=30.0)
    try:
        try:
            async with client.stream("GET", export_url_for(doc_id)) as response:
                content_type = response.headers.get("content-type", "")
                if response.status_code != 200 or "html" in content_type.lower():
                    raise GoogleDocNotAccessible(
                        "Google Docs did not return a .docx file for this link."
                    )

                filename = _filename_from_content_disposition(
                    response.headers.get("content-disposition")
                )

                fd, tmp_name = tempfile.mkstemp(suffix=".docx")
                os.close(fd)
                tmp_path = Path(tmp_name)
                total = 0
                with tmp_path.open("wb") as tmp:
                    async for chunk in response.aiter_bytes(DOWNLOAD_CHUNK_SIZE):
                        total += len(chunk)
                        if total > max_bytes:
                            tmp_path.unlink(missing_ok=True)
                            raise GoogleDocTooLarge(
                                f"Export exceeds maximum upload size of {max_bytes} bytes."
                            )
                        tmp.write(chunk)
        except httpx.HTTPError as exc:
            raise GoogleDocNotAccessible(f"Could not reach Google Docs: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()

    return tmp_path, filename
