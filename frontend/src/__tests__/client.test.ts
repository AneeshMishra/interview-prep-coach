import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  getCurrentUser,
  getQuestion,
  listQuestions,
  logout,
  sendChatMessageStream,
  uploadDocument,
} from "../api/client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// Builds a Response whose body streams the given raw text chunks one at a
// time — lets tests control exactly how SSE frames are split across reads,
// including splitting mid-frame, to prove the client's buffering is correct.
function sseResponse(rawChunks: string[], status = 200): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of rawChunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, { status, headers: { "Content-Type": "text/event-stream" } });
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

  it("always sends credentials so the session cookie rides along cross-origin", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: "u1", email: "a@b.com" }));
    vi.stubGlobal("fetch", fetchMock);

    await getCurrentUser();

    const [, init] = fetchMock.mock.calls[0];
    expect(init.credentials).toBe("include");
  });

  it("handles a 204 No Content response without trying to parse a body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(logout()).resolves.toBeUndefined();
  });

  describe("sendChatMessageStream", () => {
    it("invokes onChunk for each chunk event and resolves with the final message", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          sseResponse([
            'event: chunk\ndata: {"text": "Nagarro asked "}\n\n',
            'event: chunk\ndata: {"text": "about virtual threads."}\n\n',
            'event: done\ndata: {"answer": "Nagarro asked about virtual threads.", "cited_question_ids": ["q1"]}\n\n',
            'event: message\ndata: {"id": "m2", "session_id": "s1", "role": "assistant", "content": "Nagarro asked about virtual threads.", "cited_question_ids": ["q1"], "created_at": "2026-01-01T00:00:00Z"}\n\n',
          ])
        )
      );

      const chunks: string[] = [];
      const message = await sendChatMessageStream("s1", "hi", (text) => chunks.push(text));

      expect(chunks).toEqual(["Nagarro asked ", "about virtual threads."]);
      expect(message).toEqual({
        id: "m2",
        session_id: "s1",
        role: "assistant",
        content: "Nagarro asked about virtual threads.",
        cited_question_ids: ["q1"],
        created_at: "2026-01-01T00:00:00Z",
      });
    });

    it("reassembles an SSE frame split across separate stream reads", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          sseResponse([
            'event: chunk\ndata: {"text": "Hel',
            'lo"}\n\n',
            'event: message\ndata: {"id": "m1", "session_id": "s1", "role": "assistant", "content": "Hello", "cited_question_ids": [], "created_at": "2026-01-01T00:00:00Z"}\n\n',
          ])
        )
      );

      const chunks: string[] = [];
      const message = await sendChatMessageStream("s1", "hi", (text) => chunks.push(text));

      expect(chunks).toEqual(["Hello"]);
      expect(message.content).toBe("Hello");
    });

    it("rejects with an ApiError when the stream emits an error event", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          sseResponse(['event: error\ndata: {"detail": "Could not generate an answer right now."}\n\n'])
        )
      );

      await expect(sendChatMessageStream("s1", "hi", () => {})).rejects.toMatchObject(
        new ApiError(0, "Could not generate an answer right now.")
      );
    });

    it("rejects with the backend's detail when the initial request itself fails", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "Chat session not found." }, 404)));

      await expect(sendChatMessageStream("missing", "hi", () => {})).rejects.toMatchObject(
        new ApiError(404, "Chat session not found.")
      );
    });
  });
});
