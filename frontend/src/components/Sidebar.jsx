import { NavLink, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import "./Sidebar.css";
import logo from "../assets/nova-logo.png";
import ConfirmDialog from "./common/ConfirmDialog";
import { clearAllAuth } from "../utils/auth";

/* SVG icon set */
const Icon = {
  bell: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M12 22a2.5 2.5 0 0 0 2.45-2H9.55A2.5 2.5 0 0 0 12 22ZM19 17H5c1.6-1.2 2-2.6 2-5.2V10a5 5 0 0 1 10 0v1.8c0 2.6.4 4 2 5.2Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  dashboard: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  ),
  tickets: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <rect x="9" y="3" width="6" height="4" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <path d="M9 12h6M9 16h4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
  reports: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M14 2v6h6M8 13h8M8 17h5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
  complaints: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  employees: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <circle cx="9" cy="7" r="4" stroke="currentColor" strokeWidth="1.8" />
      <path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M19 8v6M16 11h6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
  approvals: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M9 12l2 2 4-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  ),
  trends: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <polyline points="16 7 22 7 22 13" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  model: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M12 2L2 7l10 5 10-5-10-5Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  chatbot: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <rect x="3" y="11" width="18" height="11" rx="2" stroke="currentColor" strokeWidth="1.8" />
      <path d="M9 11V7a3 3 0 0 1 6 0v4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="9" cy="16" r="1" fill="currentColor" />
      <circle cx="15" cy="16" r="1" fill="currentColor" />
    </svg>
  ),
  form: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  settings: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  ),
  logout: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <polyline points="16 17 21 12 16 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <line x1="21" y1="12" x2="9" y2="12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
  /* Lock closed — shown when pinned (click to unpin) */
  lockClosed: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
      <rect x="5" y="11" width="14" height="11" rx="2" stroke="currentColor" strokeWidth="2.5" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  ),
  /* Lock open — shown when unpinned (click to pin) */
  lockOpen: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
      <rect x="5" y="11" width="14" height="11" rx="2" stroke="currentColor" strokeWidth="2.5" />
      <path d="M8 11V7a4 4 0 0 1 8 0" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  ),
  users: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <circle cx="9" cy="7" r="4" stroke="currentColor" strokeWidth="1.8" />
      <path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M17 11h4M19 9v4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
};

/* Menu definitions */
const menus = {
  customer: [
    { label: "Notifications", to: "/customer/notifications", icon: "bell" },
    { label: "My Tickets",    to: "/customer/mytickets",      icon: "tickets" },
    { label: "Fill a Form",   to: "/customer/fill-form",      icon: "form" },
  ],
  employee: [
    { label: "Notifications", to: "/employee/notifications", icon: "bell" },
    { label: "Dashboard",     to: "/employee",  end: true,   icon: "dashboard" },
    { label: "My Tickets",    to: "/employee/complaints",    icon: "tickets" },
    { label: "Reports",       to: "/employee/reports",       icon: "reports" },
  ],
  manager: [
    { label: "Notifications",       to: "/manager/notifications", icon: "bell" },
    { label: "Dashboard",           to: "/manager", end: true,    icon: "dashboard" },
    { label: "View All Complaints", to: "/manager/complaints",    icon: "complaints" },
    { label: "View All Employees",  to: "/manager/employees",     icon: "employees" },
    { label: "Approvals",           to: "/manager/approvals",     icon: "approvals" },
    { label: "Complaint Trends",    to: "/manager/trends",        icon: "trends" },
  ],
  operator: [
    { label: "Notifications",    to: "/operator/notifications",    icon: "bell" },
    { label: "Dashboard",        to: "/operator", end: true,       icon: "dashboard" },
    { label: "Model Health",   to: "/operator/model-health",   icon: "model" },
    { label: "Quality Control", to: "/operator/quality-control", icon: "chatbot" },
    { label: "Manage Users",     to: "/operator/users",            icon: "users" },
  ],
};

export default function Sidebar({ role, unreadCount = 0 }) {
  const navigate = useNavigate();

  /* Pinned = stays open without hover */
  const [pinned, setPinned] = useState(
    () => localStorage.getItem("sidebar-pinned") === "true"
  );
  const [hovered, setHovered] = useState(false);
  const [logoutOpen, setLogoutOpen] = useState(false);

  const isExpanded = pinned || hovered;

  useEffect(() => {
    localStorage.setItem("sidebar-pinned", String(pinned));
  }, [pinned]);

  /* Push page content as sidebar resizes */
  useEffect(() => {
    document.documentElement.style.setProperty(
      "--sidebar-current-width",
      isExpanded ? "210px" : "var(--sidebar-collapsed)"
    );
  }, [isExpanded]);

  const menu = menus[role] || [];

  /* Open logout confirmation */
  const handleLogout = () => setLogoutOpen(true);

  /* Actually perform the logout */
  const doLogout = () => {
    clearAllAuth();
    navigate("/login");
  };

  return (
    <aside
      className={`sidebar${isExpanded ? " sidebar--expanded" : ""}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Brand */}
      <div className="sidebar__brand">
        <img src={logo} alt="InnovaCX Logo" className="sidebar__logo" />
        <span className="sidebar__title">InnovaCX</span>
      </div>

      {/* Navigation */}
      <nav className="sidebar__nav" aria-label="Main navigation">
        {menu.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            title={item.label}
            aria-label={item.label}
            className={({ isActive }) =>
              isActive ? "sidebar__link sidebar__link--active" : "sidebar__link"
            }
          >
            <div className="sidebar__pill">
              <span className="sidebar__icon" aria-hidden="true">
                {Icon[item.icon]}
              </span>
              <span className="sidebar__label">{item.label}</span>
              {item.icon === "bell" && unreadCount > 0 && (
                <span className="sidebar__badge" aria-label={`${unreadCount} unread`}>
                  {unreadCount > 99 ? "99+" : unreadCount}
                </span>
              )}
            </div>
          </NavLink>
        ))}
      </nav>

      {/* Bottom controls */}
      <div className="sidebar__bottom">
        <NavLink
          to={`/${role}/settings`}
          title="Settings"
          aria-label="Settings"
          className={({ isActive }) =>
            isActive
              ? "sidebar__bottomBtn sidebar__bottomBtn--active"
              : "sidebar__bottomBtn"
          }
        >
          <span className="sidebar__icon" aria-hidden="true">{Icon.settings}</span>
          <span className="sidebar__label">Settings</span>
        </NavLink>

        <button
          onClick={handleLogout}
          type="button"
          title="Logout"
          aria-label="Logout"
          className="sidebar__bottomBtn sidebar__logoutBtn"
        >
          <span className="sidebar__icon" aria-hidden="true">{Icon.logout}</span>
          <span className="sidebar__label">Logout</span>
        </button>

        {/* Pin toggle — lock icon */}
        <button
          className={`sidebar__pinBtn${pinned ? " sidebar__pinBtn--active" : ""}`}
          type="button"
          onClick={() => setPinned((p) => !p)}
          aria-label={pinned ? "Unpin sidebar" : "Pin sidebar open"}
          title={pinned ? "Unpin sidebar" : "Pin sidebar open"}
        >
          <span aria-hidden="true">
            {pinned ? Icon.lockClosed : Icon.lockOpen}
          </span>
        </button>
      </div>

      {/* Logout confirm dialog */}
      <ConfirmDialog
        open={logoutOpen}
        variant="info"  
        icon="🔓"
        title="Log Out"
        message="Are you sure you want to log out of InnovaCX?"
        confirmLabel="Log Out"
        cancelLabel="Cancel"
        onCancel={() => setLogoutOpen(false)}
        onConfirm={() => {
          setLogoutOpen(false);
          doLogout();
        }}
      />
    </aside>
  );
}