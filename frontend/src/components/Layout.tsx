import type { ReactNode } from "react";
import { setToken, type User } from "../api/client";

interface LayoutProps {
  user: User;
  active: string;
  onNavigate: (page: string) => void;
  onLogout: () => void;
  children: ReactNode;
}

export function Layout({ user, active, onNavigate, onLogout, children }: LayoutProps) {
  const items = [
    ["kb", "Knowledge Bases"],
    ["search", "Search"],
    ["chat", "Chat"],
    ["assistants", "Assistants"],
    ["maintenanceKnowledge", "Maintenance"],
    ["indexJobs", "Index Jobs"],
    ...(user.role === "admin"
      ? [
          ["evaluationDashboard", "Eval Dashboard"],
          ["evaluationFailureTriage", "Failure Triage"],
          ["evaluation", "Evaluation"],
          ["annotations", "Annotations"],
          ["auditLogs", "Audit Logs"],
          ["alerts", "Alerts"],
          ["backups", "Backups"],
          ["metadataDictionary", "Metadata Dictionary"],
          ["metadataPrecheck", "Metadata Precheck"],
          ["users", "Users"],
          ["system", "System"],
        ]
      : []),
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <strong>CoreKB</strong>
          <span>{"\u77e5\u6838"}</span>
        </div>
        <nav>
          {items.map(([key, label]) => (
            <button key={key} className={active === key ? "active" : ""} onClick={() => onNavigate(key)}>
              {label}
            </button>
          ))}
        </nav>
        <div className="session">
          <span>{user.username}</span>
          <small>{user.role}</small>
          <button
            onClick={() => {
              setToken(null);
              onLogout();
            }}
          >
            Logout
          </button>
        </div>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
