// Centered card shell for the login / register screens.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { ThemeToggle } from "../app/ThemeToggle";

export function AuthShell({
  title, subtitle, children, footer,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <div className="auth-page">
      <div className="auth-top">
        <Link to="/" className="brand"><span className="brand-mark" aria-hidden /> Quanta</Link>
        <ThemeToggle />
      </div>
      <div className="auth-card card">
        <h1 className="auth-title">{title}</h1>
        <p className="auth-sub">{subtitle}</p>
        {children}
        <div className="auth-foot">{footer}</div>
      </div>
    </div>
  );
}
