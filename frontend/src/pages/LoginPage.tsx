import { oauthLoginUrl } from "../api/client";
import type { OAuthProviderName } from "../api/types";

const PROVIDERS: { id: OAuthProviderName; label: string; available: boolean }[] = [
  { id: "google", label: "Continue with Google", available: true },
  { id: "facebook", label: "Continue with Facebook", available: false },
  { id: "linkedin", label: "Continue with LinkedIn", available: false },
  { id: "azure", label: "Continue with Microsoft (Azure AD SSO)", available: false },
];

export function LoginPage() {
  function handleSignIn(provider: OAuthProviderName) {
    // A full-page redirect, not a fetch — the browser needs to actually
    // navigate to present the provider's own consent screen, then the
    // backend redirects it back here once sign-in completes.
    window.location.href = oauthLoginUrl(provider);
  }

  return (
    <section className="login-page">
      <h1>Sign in</h1>
      <p className="page-subtitle">
        Sign in to upload your own interview documents and keep your questions, chats and mock
        interviews private to your account.
      </p>

      <div className="login-provider-list">
        {PROVIDERS.map((provider) => (
          <button
            key={provider.id}
            type="button"
            className="login-provider-button"
            disabled={!provider.available}
            onClick={() => handleSignIn(provider.id)}
          >
            {provider.label}
            {!provider.available && <span className="login-provider-button__badge">Coming soon</span>}
          </button>
        ))}
      </div>
    </section>
  );
}
