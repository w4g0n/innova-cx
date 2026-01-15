import { NavLink } from "react-router-dom";
import "./Sidebar.css";
import logo from "../assets/nova-logo.png";

export default function Sidebar({ role }) {
  const menus = {
    customer: [
      { label: "Dashboard", to: "/customer", end: true },
      { label: "Chatbot", to: "/customer" },
    ],
    employee: [
      { label: "Dashboard", to: "/employee", end: true },
      { label: "My Tickets", to: "/employee/complaints" },
      { label: "Reports", to: "/employee/reports" },
    ],
    manager: [
      { label: "Dashboard", to: "/manager", end: true },
      { label: "View All Complaints", to: "/manager/complaints" },
      { label: "View All Employees", to: "/manager/employees" },
      { label: "Approvals", to: "/manager/approvals" },
      { label: "Complaint Trends", to: "/manager/trends" },
    ],
    operator: [
      { label: "Dashboard", to: "/operator", end: true },
      { label: "Model Analysis", to: "/operator/model-analysis" },
      { label: "Chatbot Analysis", to: "/operator/chatbot-analysis" },
    ],
  };

  const menu = menus[role] || [];

  return (
    <aside className="sidebar">
      {/* Top brand */}
      <div className="sidebar__brand">
        <img className="sidebar__logo" src={logo} alt="InnovaCX Logo" />
        <span className="sidebar__title">InnovaCX</span>
      </div>

      {/* Notifications (NOT clickable for now) */}
      <div className="sidebar__notifications">
        <span className="sidebar__icon" aria-hidden="true">
          {/* bell icon */}
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 22a2.5 2.5 0 0 0 2.45-2H9.55A2.5 2.5 0 0 0 12 22ZM19 17H5c1.6-1.2 2-2.6 2-5.2V10a5 5 0 0 1 10 0v1.8c0 2.6.4 4 2 5.2Z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <span>Notifications</span>
      </div>

      {/* Menu links */}
      <nav className="sidebar__nav">
        {menu.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              isActive ? "sidebar__link sidebar__link--active" : "sidebar__link"
            }
          >
            {({ isActive }) => (
              <div
                className={
                  isActive ? "sidebar__pill sidebar__pill--active" : "sidebar__pill"
                }
              >
                {item.label}
              </div>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Bottom actions */}
      <div className="sidebar__bottom">
        <button className="sidebar__bottomBtn" type="button">
          <span className="sidebar__icon" aria-hidden="true">
            {/* settings gear */}
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z"
                stroke="currentColor"
                strokeWidth="1.8"
              />
              <path
                d="M19.4 15a7.8 7.8 0 0 0 .1-2l2-1.2-2-3.5-2.3.6a7.8 7.8 0 0 0-1.7-1L15 5h-6l-.6 2.9a7.8 7.8 0 0 0-1.7 1L4.4 8.3l-2 3.5 2 1.2a7.8 7.8 0 0 0 .1 2l-2 1.2 2 3.5 2.3-.6a7.8 7.8 0 0 0 1.7 1L9 23h6l.6-2.9a7.8 7.8 0 0 0 1.7-1l2.3.6 2-3.5-2-1.2Z"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <span>Settings</span>
        </button>

        <button className="sidebar__bottomBtn" type="button">
          <span className="sidebar__icon" aria-hidden="true">
            {/* logout icon */}
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path
                d="M10 17l5-5-5-5"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M15 12H3"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
              <path
                d="M21 4v16"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </span>
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}
