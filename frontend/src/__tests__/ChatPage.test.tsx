import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatPage } from "../pages/ChatPage";
import type { ChatMessageRecord } from "../api/types";

const { createChatSessionMock, listChatMessagesMock, sendChatMessageStreamMock } = vi.hoisted(() => ({
  createChatSessionMock: vi.fn(),
  listChatMessagesMock: vi.fn(),
  sendChatMessageStreamMock: vi.fn(),
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    createChatSession: createChatSessionMock,
    listChatMessages: listChatMessagesMock,
    sendChatMessageStream: sendChatMessageStreamMock,
  };
});

function makeMessage(overrides: Partial<ChatMessageRecord> = {}): ChatMessageRecord {
  return {
    id: "m1",
    session_id: "s1",
    role: "assistant",
    content: "Here's what I found.",
    cited_question_ids: [],
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ChatPage />
    </MemoryRouter>
  );
}

function renderResumedPage(sessionId: string) {
  return render(
    <MemoryRouter initialEntries={[`/chats/${sessionId}`]}>
      <Routes>
        <Route path="/chats/:sessionId" element={<ChatPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ChatPage", () => {
  afterEach(() => {
    createChatSessionMock.mockReset();
    listChatMessagesMock.mockReset();
    sendChatMessageStreamMock.mockReset();
  });

  it("starts a session and shows a starter prompt when there's no history", async () => {
    createChatSessionMock.mockResolvedValue({ id: "s1", created_at: "2026-01-01T00:00:00Z" });
    listChatMessagesMock.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText(/what system design questions came up/i)).toBeInTheDocument();
  });

  it("loads and renders existing conversation history", async () => {
    createChatSessionMock.mockResolvedValue({ id: "s1", created_at: "2026-01-01T00:00:00Z" });
    listChatMessagesMock.mockResolvedValue([
      makeMessage({ id: "m1", role: "user", content: "What Kafka questions came up?" }),
      makeMessage({ id: "m2", role: "assistant", content: "Nagarro asked about exactly-once delivery." }),
    ]);
    renderPage();

    expect(await screen.findByText("What Kafka questions came up?")).toBeInTheDocument();
    expect(screen.getByText("Nagarro asked about exactly-once delivery.")).toBeInTheDocument();
  });

  it("sends a message and renders the grounded reply with a source link", async () => {
    createChatSessionMock.mockResolvedValue({ id: "s1", created_at: "2026-01-01T00:00:00Z" });
    listChatMessagesMock.mockResolvedValue([]);
    sendChatMessageStreamMock.mockImplementation(async (_sessionId: string, _message: string, onChunk: (t: string) => void) => {
      onChunk("Nagarro asked ");
      onChunk("about virtual threads.");
      return makeMessage({
        id: "m2",
        role: "assistant",
        content: "Nagarro asked about virtual threads.",
        cited_question_ids: ["q1"],
      });
    });
    const user = userEvent.setup();
    renderPage();

    const input = await screen.findByLabelText(/chat message/i);
    await user.type(input, "What Java questions came up at Nagarro?");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(screen.getByText("What Java questions came up at Nagarro?")).toBeInTheDocument();
    expect(await screen.findByText("Nagarro asked about virtual threads.")).toBeInTheDocument();

    const sourceLink = screen.getByRole("link", { name: "#1" });
    expect(sourceLink).toHaveAttribute("href", "/questions/q1");
  });

  it("renders the answer bubble growing as chunks arrive, before the stream completes", async () => {
    createChatSessionMock.mockResolvedValue({ id: "s1", created_at: "2026-01-01T00:00:00Z" });
    listChatMessagesMock.mockResolvedValue([]);
    let resolveStream!: (message: ChatMessageRecord) => void;
    let onChunkCallback!: (text: string) => void;
    sendChatMessageStreamMock.mockImplementation(
      (_sessionId: string, _message: string, onChunk: (t: string) => void) =>
        new Promise<ChatMessageRecord>((resolve) => {
          onChunkCallback = onChunk;
          resolveStream = resolve;
        })
    );
    const user = userEvent.setup();
    renderPage();

    const input = await screen.findByLabelText(/chat message/i);
    await user.type(input, "anything");
    await user.click(screen.getByRole("button", { name: /send/i }));

    // Before any chunk arrives: a loading indicator, no partial bubble yet.
    expect(await screen.findByText(/thinking/i)).toBeInTheDocument();

    act(() => onChunkCallback("Partial answer"));
    expect(await screen.findByText("Partial answer")).toBeInTheDocument();
    expect(screen.queryByText(/thinking/i)).not.toBeInTheDocument();

    act(() => onChunkCallback(" continues here."));
    expect(await screen.findByText("Partial answer continues here.")).toBeInTheDocument();

    act(() => resolveStream(makeMessage({ id: "m2", content: "Partial answer continues here." })));
    await waitFor(() => expect(screen.queryByText(/thinking/i)).not.toBeInTheDocument());
    expect(await screen.findByText("Partial answer continues here.")).toBeInTheDocument();
  });

  it("shows an error message when sending fails, without losing the typed message", async () => {
    createChatSessionMock.mockResolvedValue({ id: "s1", created_at: "2026-01-01T00:00:00Z" });
    listChatMessagesMock.mockResolvedValue([]);
    sendChatMessageStreamMock.mockRejectedValue(new Error("Semantic search is unavailable."));
    const user = userEvent.setup();
    renderPage();

    const input = await screen.findByLabelText(/chat message/i);
    await user.type(input, "anything");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(screen.getByText("anything")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });

  it("shows an error state when the session fails to start", async () => {
    createChatSessionMock.mockRejectedValue(new Error("Could not reach the API."));
    renderPage();

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("disables the send button until a session exists and there is text to send", async () => {
    createChatSessionMock.mockResolvedValue({ id: "s1", created_at: "2026-01-01T00:00:00Z" });
    listChatMessagesMock.mockResolvedValue([]);
    renderPage();

    const sendButton = await screen.findByRole("button", { name: /send/i });
    expect(sendButton).toBeDisabled();
  });

  it("resumes an existing session from a /chats/:sessionId route instead of creating a new one", async () => {
    listChatMessagesMock.mockResolvedValue([
      makeMessage({ id: "m1", role: "user", content: "What Kafka questions came up?" }),
      makeMessage({ id: "m2", role: "assistant", content: "Nagarro asked about exactly-once delivery." }),
    ]);
    renderResumedPage("existing-session-1");

    expect(await screen.findByText("What Kafka questions came up?")).toBeInTheDocument();
    expect(screen.getByText("Nagarro asked about exactly-once delivery.")).toBeInTheDocument();
    expect(createChatSessionMock).not.toHaveBeenCalled();
    expect(listChatMessagesMock).toHaveBeenCalledWith("existing-session-1");
  });

  it("shows an error when resuming an unknown/inaccessible session", async () => {
    listChatMessagesMock.mockRejectedValue(new Error("Chat session not found."));
    renderResumedPage("missing-session");

    expect(await screen.findByText(/failed to load this chat/i)).toBeInTheDocument();
  });
});
