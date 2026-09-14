import { useEffect, useState } from "react";
import { Link, NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";
import { LogOut, Menu, Settings, X } from "lucide-react";

import { api, post } from "../api";
import type { Session } from "../types";
import { PlayerBar } from "./PlayerBar";

function Wordmark() {
  return (
    <Link className="wordmark" to="/" aria-label="Locher songs home">
      <span><em>Locher</em> songs</span>
      <small>Made at home · played everywhere</small>
    </Link>
  );
}

function Nav() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="nav-toggle" aria-label="Toggle navigation" onClick={() => setOpen(!open)}>
        {open ? <X /> : <Menu />}
      </button>
      <nav className={open ? "main-nav open" : "main-nav"} onClick={() => setOpen(false)}>
        <NavLink to="/">Listen</NavLink>
        <NavLink to="/about">About</NavLink>
        <span className="nav-rule" />
        <NavLink className="studio-link" to="/studio">
          Family studio <span aria-hidden>↗</span>
        </NavLink>
      </nav>
    </>
  );
}

export function PublicLayout() {
  return (
    <div className="site-shell public-shell">
      <header className="site-header">
        <Wordmark />
        <Nav />
      </header>
      <main>
        <Outlet />
      </main>
      <PlayerBar />
    </div>
  );
}

export function StudioLayout() {
  const [session, setSession] = useState<Session | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    void api<Session>("/api/auth/session/").then(setSession).catch(() => setSession({ authenticated: false, is_admin: false, name: "" }));
  }, []);

  if (!session) return <div className="loading-screen">Opening the studio…</div>;
  if (!session.authenticated || !session.is_admin) return <Navigate to="/studio/login" replace />;

  const signOut = async () => {
    await post<void>("/api/auth/logout/", {});
    navigate("/");
  };

  return (
    <div className="site-shell studio-shell">
      <header className="site-header studio-header">
        <Wordmark />
        <Nav />
      </header>
      <div className="studio-utility">
        <span>Our behind-the-scenes music desk</span>
        <NavLink to="/studio/integrations"><Settings size={16} /> Integrations</NavLink>
        <button onClick={signOut}><LogOut size={16} /> Sign out</button>
      </div>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
