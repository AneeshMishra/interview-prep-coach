import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatHistoryPage } from "../pages/ChatHistoryPage";
import type { ChatHistoryEntry } from "../api/types";

const { listChatSessionsMock } = vi.hoisted(() => ({
  listChatSessionsMock: vi.fn(),
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, listChatSessions: listChatSessionsMock };
});

function makeEntry(overrides: Partial<ChatHistoryEntry> = {}): ChatHistoryEntry {
  return {
    id: "c1",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:05:00Z",
    message_count: 4,
    preview: "Nagarro asked about virtual threads.",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ChatHistoryPage />
    </MemoryRouter>
  );
}

describe("ChatHistoryPage", () => {
  afterEach(() => {
    listChatSessionsMock.mockReset();
  });

  it("shows an empty state when there are no past chats", async () => {
    listChatSessionsMock.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText(/no chats yet/i)).toBeInTheDocument();
  });

  it("lists past chats with preview and message count", async () => {
    listChatSessionsMock.mockResolvedValue([
      makeEntry(),
      makeEntry({ id: "c2", message_count: 0, preview: null }),
    ]);
    renderPage();

    expect(await screen.findByText("Nagarro asked about virtual threads.")).toBeInTheDocument();
    expect(screen.getByText(/4 messages/i)).toBeInTheDocument();
    expect(screen.getByText("No messages yet.")).toBeInTheDocument();

    const link = screen.getByRole("link", { name: /nagarro asked about virtual threads/i });
    expect(link).toHaveAttribute("href", "/chats/c1");
  });

  it("shows an error message when loading fails", async () => {
    listChatSessionsMock.mockRejectedValue(new Error("Could not reach the API."));
    renderPage();

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("links to the new-chat page", async () => {
    listChatSessionsMock.mockResolvedValue([]);
    renderPage();

    await screen.findByText(/no chats yet/i);
    expect(screen.getByRole("link", { name: /new chat/i })).toHaveAttribute("href", "/chat");
  });
});
