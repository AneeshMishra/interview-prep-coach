import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, listDocuments, uploadDocument } from "../api/client";
import type { DocumentRecord } from "../api/types";
import { DocumentStatusBadge } from "../components/DocumentStatusBadge";
import { EmptyState, ErrorMessage, Loading } from "../components/StatusStates";

const POLL_INTERVAL_MS = 3000;
const IN_FLIGHT_STATUSES = new Set(["pending", "processing"]);

export function UploadPage() {
  const [documents, setDocuments] = useState<DocumentRecord[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const pollHandle = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshDocuments = useCallback(async () => {
    try {
      const docs = await listDocuments();
      setDocuments(docs);
      setListError(null);
      return docs;
    } catch (err) {
      setListError(err instanceof ApiError ? err.message : "Failed to load documents.");
      return null;
    }
  }, []);

  useEffect(() => {
    void refreshDocuments();
  }, [refreshDocuments]);

  // Ingestion runs as a backend background task; poll while anything is
  // still pending/processing so status updates without a manual refresh.
  useEffect(() => {
    const hasInFlightDocument = documents?.some((doc) => IN_FLIGHT_STATUSES.has(doc.status));

    if (hasInFlightDocument && pollHandle.current === null) {
      pollHandle.current = setInterval(() => {
        void refreshDocuments();
      }, POLL_INTERVAL_MS);
    } else if (!hasInFlightDocument && pollHandle.current !== null) {
      clearInterval(pollHandle.current);
      pollHandle.current = null;
    }

    return () => {
      if (pollHandle.current !== null) {
        clearInterval(pollHandle.current);
        pollHandle.current = null;
      }
    };
  }, [documents, refreshDocuments]);

  async function handleUpload(event: React.FormEvent) {
    event.preventDefault();
    if (!selectedFile) {
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      await uploadDocument(selectedFile);
      setSelectedFile(null);
      await refreshDocuments();
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <section>
      <h1>Upload Interview Experience</h1>
      <p className="page-subtitle">
        Upload a .docx of past interview questions. It's parsed, structured by the configured
        LLM, and indexed for search — this can take a little while for a large document.
      </p>

      <form className="upload-form" onSubmit={handleUpload}>
        <input
          type="file"
          accept=".docx"
          aria-label="Select a .docx file to upload"
          onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
        />
        <button type="submit" disabled={!selectedFile || uploading}>
          {uploading ? "Uploading…" : "Upload"}
        </button>
      </form>
      {uploadError && <ErrorMessage message={uploadError} />}

      <h2>Documents</h2>
      {documents === null && listError === null && <Loading label="Loading documents…" />}
      {listError && <ErrorMessage message={listError} />}
      {documents !== null && documents.length === 0 && (
        <EmptyState message="No documents uploaded yet." />
      )}
      {documents !== null && documents.length > 0 && (
        <table className="documents-table">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Status</th>
              <th>Uploaded</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.id}>
                <td>{doc.filename}</td>
                <td>
                  <DocumentStatusBadge status={doc.status} />
                  {doc.status === "failed" && doc.error_message && (
                    <div className="doc-error-detail">{doc.error_message}</div>
                  )}
                </td>
                <td>{new Date(doc.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
