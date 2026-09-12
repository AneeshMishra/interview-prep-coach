import httpx
import pytest

from app.ingestion.google_docs_import import (
    GoogleDocNotAccessible,
    GoogleDocTooLarge,
    download_google_doc_as_docx,
    export_url_for,
    extract_google_doc_id,
    sanitize_docx_filename,
)

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class TestExtractGoogleDocId:
    @pytest.mark.parametrize(
        "url",
        [
            "https://docs.google.com/document/d/1klKw9KYkzLO5L9z0PhnMGpkI2MbMo5wDq9FuzBBNb-E/edit?usp=drivesdk",
            "https://docs.google.com/document/d/1klKw9KYkzLO5L9z0PhnMGpkI2MbMo5wDq9FuzBBNb-E/edit#heading=h.abc",
            "https://docs.google.com/document/d/1klKw9KYkzLO5L9z0PhnMGpkI2MbMo5wDq9FuzBBNb-E",
            "https://docs.google.com/document/d/1klKw9KYkzLO5L9z0PhnMGpkI2MbMo5wDq9FuzBBNb-E/",
        ],
    )
    def test_extracts_id_from_various_url_shapes(self, url):
        assert extract_google_doc_id(url) == "1klKw9KYkzLO5L9z0PhnMGpkI2MbMo5wDq9FuzBBNb-E"

    def test_returns_none_for_non_google_docs_url(self):
        assert extract_google_doc_id("https://example.com/not-a-doc") is None
        assert extract_google_doc_id("https://docs.google.com/spreadsheets/d/abc123") is None

    def test_extracts_id_from_publish_to_web_url(self):
        # "Publish to the web" links use a distinct .../d/e/<token>/pub shape;
        # the "e/" prefix must be captured with the token, not dropped, or
        # export_url_for() builds a URL for a document that doesn't exist.
        url = (
            "https://docs.google.com/document/d/e/2PACX-1vREH7wBSxdAMEWhZpuXzzoWWRVFGnawMQ"
            "uSo4JTfPolgT7oWMwq6epoL96_SgtS0_Bw8sieqeQNLYUW/pub"
        )
        assert extract_google_doc_id(url) == (
            "e/2PACX-1vREH7wBSxdAMEWhZpuXzzoWWRVFGnawMQuSo4JTfPolgT7oWMwq6epoL96_SgtS0_Bw8sieqeQNLYUW"
        )


def test_export_url_uses_docx_format():
    assert export_url_for("abc123") == "https://docs.google.com/document/d/abc123/export?format=docx"


def test_export_url_preserves_publish_to_web_prefix():
    assert (
        export_url_for("e/2PACX-token")
        == "https://docs.google.com/document/d/e/2PACX-token/export?format=docx"
    )


class TestSanitizeDocxFilename:
    def test_appends_extension_if_missing(self):
        assert sanitize_docx_filename("My Interview Notes") == "My Interview Notes.docx"

    def test_keeps_existing_extension(self):
        assert sanitize_docx_filename("My Interview Notes.docx") == "My Interview Notes.docx"

    def test_strips_path_components(self):
        assert sanitize_docx_filename("../../etc/passwd.docx") == "passwd.docx"

    def test_none_for_empty_or_missing(self):
        assert sanitize_docx_filename(None) is None
        assert sanitize_docx_filename("") is None


class TestDownloadGoogleDocAsDocx:
    async def test_downloads_and_extracts_filename(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={
                    "content-type": DOCX_CONTENT_TYPE,
                    "content-disposition": 'attachment; filename="Amazon Interview.docx"',
                },
                content=b"fake docx bytes",
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            tmp_path, filename = await download_google_doc_as_docx("abc123", max_bytes=10_000, client=client)
            assert tmp_path.exists()
            assert tmp_path.read_bytes() == b"fake docx bytes"
            assert filename == "Amazon Interview.docx"
        finally:
            tmp_path.unlink(missing_ok=True)
            await client.aclose()

    async def test_url_encoded_filename_is_decoded(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={
                    "content-type": DOCX_CONTENT_TYPE,
                    "content-disposition": "attachment; filename*=UTF-8''Amazon%20Interview.docx",
                },
                content=b"x",
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            tmp_path, filename = await download_google_doc_as_docx("abc123", max_bytes=10_000, client=client)
            assert filename == "Amazon Interview.docx"
        finally:
            tmp_path.unlink(missing_ok=True)
            await client.aclose()

    async def test_html_response_raises_not_accessible(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>login</html>")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(GoogleDocNotAccessible):
                await download_google_doc_as_docx("abc123", max_bytes=10_000, client=client)
        finally:
            await client.aclose()

    async def test_non_200_raises_not_accessible(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, headers={"content-type": DOCX_CONTENT_TYPE}, content=b"")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(GoogleDocNotAccessible):
                await download_google_doc_as_docx("abc123", max_bytes=10_000, client=client)
        finally:
            await client.aclose()

    async def test_network_error_raises_not_accessible(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(GoogleDocNotAccessible):
                await download_google_doc_as_docx("abc123", max_bytes=10_000, client=client)
        finally:
            await client.aclose()

    async def test_exceeding_max_bytes_raises_too_large(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"content-type": DOCX_CONTENT_TYPE}, content=b"x" * 2000)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(GoogleDocTooLarge):
                await download_google_doc_as_docx("abc123", max_bytes=100, client=client)
        finally:
            await client.aclose()
