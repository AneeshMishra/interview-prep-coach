import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function NavBar() {
  const { user, logout } = useAuth();

  async function handleLogout() {
    try {
      await logout();
    } catch (err) {
      console.error("Failed to log out:", err);
    }
  }

  return (
    <header className="app-header">
      <div className="app-header__title">Interview Prep Coach</div>
      {user && (
        <nav className="app-nav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
            Upload
          </NavLink>
          <NavLink to="/questions" className={({ isActive }) => (isActive ? "active" : "")}>
            Question Explorer
          </NavLink>
          <NavLink to="/chat" className={({ isActive }) => (isActive ? "active" : "")}>
            Chat
          </NavLink>
          <NavLink to="/interview" className={({ isActive }) => (isActive ? "active" : "")}>
            Mock Interview
          </NavLink>
        </nav>
      )}
      {user && (
        <div className="app-header__account">
          {user.avatar_url && <img className="app-header__avatar" src={user.avatar_url} alt="" />}
          <span className="app-header__account-name">{user.display_name || user.email}</span>
          <button type="button" className="app-header__logout" onClick={handleLogout}>
            Log out
          </button>
        </div>
      )}
    </header>
  );
}
