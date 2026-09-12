import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { NavBar } from "../components/NavBar";
import { AuthProvider } from "../context/AuthContext";
import type { UserProfile } from "../api/types";

const { getCurrentUserMock, logoutMock } = vi.hoisted(() => ({
  getCurrentUserMock: vi.fn(),
  logoutMock: vi.fn(),
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, getCurrentUser: getCurrentUserMock, logout: logoutMock };
});

const USER: UserProfile = { id: "u1", email: "alice@example.com", display_name: "Alice", avatar_url: null };

function renderNavBar() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <NavBar />
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("NavBar", () => {
  afterEach(() => {
    getCurrentUserMock.mockReset();
    logoutMock.mockReset();
  });

  it("hides nav links and account info while signed out", async () => {
    getCurrentUserMock.mockRejectedValue(new ApiError(401, "Not signed in."));
    renderNavBar();

    await waitFor(() => expect(getCurrentUserMock).toHaveBeenCalled());
    expect(screen.queryByRole("link", { name: /upload/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /log out/i })).not.toBeInTheDocument();
  });

  it("shows nav links and the signed-in user's name once loaded", async () => {
    getCurrentUserMock.mockResolvedValue(USER);
    renderNavBar();

    expect(await screen.findByText("Alice")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /upload/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
  });

  it("logs out when the button is clicked", async () => {
    getCurrentUserMock.mockResolvedValue(USER);
    logoutMock.mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderNavBar();

    await screen.findByText("Alice");
    await user.click(screen.getByRole("button", { name: /log out/i }));

    expect(logoutMock).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByText("Alice")).not.toBeInTheDocument());
  });
});
