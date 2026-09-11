import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { UploadPage } from "../pages/UploadPage";
import type { DocumentRecord } from "../api/types";

const { listDocumentsMock, uploadDocumentMock } = vi.hoisted(() => ({
  listDocumentsMock: vi.fn(),
  uploadDocumentMock: vi.fn(),
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, listDocuments: listDocumentsMock, uploadDocument: uploadDocumentMock };
});

function makeDocument(overrides: Partial<DocumentRecord> = {}): DocumentRecord {
  return {
    id: "doc1",
    filename: "sample.docx",
    content_hash: "hash",
    status: "done",
    error_message: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <UploadPage />
    </MemoryRouter>
  );
}

describe("UploadPage", () => {
  afterEach(() => {
    listDocumentsMock.mockReset();
    uploadDocumentMock.mockReset();
  });

  it("shows an empty state when there are no documents yet", async () => {
    listDocumentsMock.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText(/no documents uploaded yet/i)).toBeInTheDocument();
  });

  it("lists documents with their status, and surfaces the error detail for failed ones", async () => {
    listDocumentsMock.mockResolvedValue([
      makeDocument({ status: "failed", error_message: "LLM unreachable" }),
    ]);
    renderPage();

    expect(await screen.findByText("sample.docx")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("LLM unreachable")).toBeInTheDocument();
  });

  it("uploads the selected file and refreshes the document list", async () => {
    listDocumentsMock.mockResolvedValue([]);
    uploadDocumentMock.mockResolvedValue({ document_id: "doc1", status: "pending" });
    const user = userEvent.setup();
    renderPage();

    await screen.findByText(/no documents uploaded yet/i);
    listDocumentsMock.mockResolvedValue([makeDocument({ status: "pending" })]);

    const file = new File(["dummy"], "sample.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    await user.upload(screen.getByLabelText(/select a .docx file/i), file);
    await user.click(screen.getByRole("button", { name: /upload/i }));

    await waitFor(() => expect(uploadDocumentMock).toHaveBeenCalledWith(file));
    expect(await screen.findByText("Pending")).toBeInTheDocument();
  });

  it("shows an error message when the upload fails", async () => {
    listDocumentsMock.mockResolvedValue([]);
    uploadDocumentMock.mockRejectedValue(new Error("Only .docx files are supported in v1."));
    const user = userEvent.setup();
    renderPage();

    await screen.findByText(/no documents uploaded yet/i);
    // Rejected server-side (e.g. corrupt content); the input's own accept=".docx"
    // filter is a client-side hint, not the thing under test here.
    const file = new File(["dummy"], "sample.docx");
    await user.upload(screen.getByLabelText(/select a .docx file/i), file);
    await user.click(screen.getByRole("button", { name: /upload/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
