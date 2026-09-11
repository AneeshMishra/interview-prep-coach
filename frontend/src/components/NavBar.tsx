import { NavLink } from "react-router-dom";

export function NavBar() {
  return (
    <header className="app-header">
      <div className="app-header__title">Interview Prep Coach</div>
      <nav className="app-nav">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
          Upload
        </NavLink>
        <NavLink to="/questions" className={({ isActive }) => (isActive ? "active" : "")}>
          Question Explorer
        </NavLink>
      </nav>
    </header>
  );
}
