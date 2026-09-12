import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { AuthProvider, useAuth } from "../context/AuthContext";
import { LoginPage } from "../pages/LoginPage";
import { ApiError } from "../api/client";
import type { UserProfile } from "../api/types";

const { getCurrentUserMock, logoutMock } = vi.hoisted(() => ({
  getCurrentUserMock: vi.fn(),
  logoutMock: vi.fn(),
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, getCurrentUser: getCurrentUserMock, logout: logoutMock };
});

const USER: UserProfile = { id: "u1", email: "a@example.com", display_name: "Alice", avatar_url: null };

function Protected() {
  return <div>Protected content</div>;
}

function AuthConsumer() {
  const { user, loading } = useAuth();
  if (loading) return <div>loading</div>;
  return <div>{user ? `Signed in as ${user.email}` : "Signed out"}</div>;
}

function renderWithAuth(children: React.ReactNode, initialEntries = ["/"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <AuthProvider>{children}</AuthProvider>
    </MemoryRouter>
  );
}

describe("AuthContext", () => {
  afterEach(() => {
    getCurrentUserMock.mockReset();
    logoutMock.mockReset();
  });

  it("loads the current user on mount", async () => {
    getCurrentUserMock.mockResolvedValue(USER);
    renderWithAuth(<AuthConsumer />);

    expect(await screen.findByText("Signed in as a@example.com")).toBeInTheDocument();
  });

  it("treats a failed lookup as signed-out", async () => {
    getCurrentUserMock.mockRejectedValue(new ApiError(401, "Not signed in."));
    renderWithAuth(<AuthConsumer />);

    expect(await screen.findByText("Signed out")).toBeInTheDocument();
  });
});

describe("ProtectedRoute", () => {
  afterEach(() => {
    getCurrentUserMock.mockReset();
  });

  it("redirects to /login when signed out", async () => {
    getCurrentUserMock.mockRejectedValue(new ApiError(401, "Not signed in."));
    renderWithAuth(
      <Routes>
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Protected />
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    );

    expect(await screen.findByRole("heading", { name: /sign in/i })).toBeInTheDocument();
  });

  it("renders the protected content once signed in", async () => {
    getCurrentUserMock.mockResolvedValue(USER);
    renderWithAuth(
      <Routes>
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Protected />
            </ProtectedRoute>
          }
        />
      </Routes>
    );

    expect(await screen.findByText("Protected content")).toBeInTheDocument();
  });
});

describe("LoginPage", () => {
  // LoginPage itself doesn't read auth state, so it's rendered standalone
  // here rather than through AuthProvider (which would otherwise kick off
  // an unrelated, unawaited getCurrentUser() call in these tests).
  it("only enables the Google sign-in button", () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByRole("button", { name: /continue with google/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /continue with facebook/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /continue with linkedin/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /azure ad sso/i })).toBeDisabled();
  });

  it("navigates the browser to the backend's Google login endpoint", async () => {
    const user = userEvent.setup();
    // jsdom doesn't implement real navigation; capture the attempted URL instead.
    delete (window as unknown as { location?: unknown }).location;
    (window as unknown as { location: { href: string } }).location = { href: "" };

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );
    await user.click(screen.getByRole("button", { name: /continue with google/i }));

    expect(window.location.href).toContain("/auth/google/login");
  });
});
