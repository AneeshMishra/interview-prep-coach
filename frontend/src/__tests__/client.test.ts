import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getQuestion, listQuestions, uploadDocument } from "../api/client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("builds query params from provided filters only", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await listQuestions({ company: "Amazon", difficulty: undefined, needs_review: true });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain("/questions?");
    expect(calledUrl).toContain("company=Amazon");
    expect(calledUrl).toContain("needs_review=true");
    expect(calledUrl).not.toContain("difficulty");
  });

  it("posts the file as multipart form data on upload", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ document_id: "doc-1", status: "pending" }));
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["dummy"], "sample.docx");
    const result = await uploadDocument(file);

    expect(result).toEqual({ document_id: "doc-1", status: "pending" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/documents/upload");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("raises ApiError with the backend's detail message on failure", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: "Question not found." }, 404));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getQuestion("missing-id")).rejects.toMatchObject(
      new ApiError(404, "Question not found.")
    );
  });

  it("raises a reachability ApiError when fetch itself throws", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch"))
    );

    await expect(listQuestions()).rejects.toMatchObject({ status: 0 });
  });
});
