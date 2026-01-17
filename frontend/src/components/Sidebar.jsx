import { NavLink, useNavigate } from "react-router-dom";
import "./Sidebar.css";
import logo from "../assets/nova-logo.png";

export default function Sidebar({ role }) {
  const navigate = useNavigate();

  const menus = {
    customer: [
      { label: "Notifications", to: "/customer/notifications", icon: "bell" },
      { label: "Dashboard", to: "/customer", end: true },
      { label: "Chatbot", to: "/customer/chatbot" },
    ],
    employee: [
      { label: "Notifications", to: "/employee/notifications", icon: "bell" },
      { label: "Dashboard", to: "/employee", end: true },
      { label: "My Tickets", to: "/employee/complaints" },
      { label: "Reports", to: "/employee/reports" },
    ],
    manager: [
      { label: "Notifications", to: "/manager/notifications", icon: "bell" },
      { label: "Dashboard", to: "/manager", end: true },
      { label: "View All Complaints", to: "/manager/complaints" },
      { label: "View All Employees", to: "/manager/employees" },
      { label: "Approvals", to: "/manager/approvals" },
      { label: "Complaint Trends", to: "/manager/trends" },
    ],
    operator: [
      { label: "Notifications", to: "/operator/notifications", icon: "bell" },
      { label: "Dashboard", to: "/operator", end: true },
      { label: "Model Analysis", to: "/operator/model-analysis" },
      { label: "Chatbot Analysis", to: "/operator/chatbot-analysis" },
    ],
  };

  const menu = menus[role] || [];

  const handleLogout = () => {
    localStorage.removeItem("user");
    navigate("/");
  };

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <img className="sidebar__logo" src={logo} alt="InnovaCX Logo" />
        <span className="sidebar__title">InnovaCX</span>
      </div>

      <div className="sidebar__spacer" />

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
                  isActive
                    ? "sidebar__pill sidebar__pill--active"
                    : "sidebar__pill"
                }
              >
                {item.icon === "bell" && (
                  <span className="sidebar__icon">
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
                )}
                <span>{item.label}</span>
              </div>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar__bottom">
        <button className="sidebar__bottomBtn" type="button">
          <span className="sidebar__icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z"
                stroke="currentColor"
                strokeWidth="1.8"
              />
              <path
                d="M20 12a8.2 8.2 0 0 0-.1-1.2l1.8-1.3-1.8-3.1-2.1.8a8.1 8.1 0 0 0-2.1-1.2L13.5 3h-3L10 5.8A8.1 8.1 0 0 0 7.9 7l-2.1-.8L4 9.3l1.8 1.3A8.2 8.2 0 0 0 5.7 12c0 .4 0 .8.1 1.2L4 14.5l1.8 3.1 2.1-.8a8.1 8.1 0 0 0 2.1 1.2L10.5 21h3l.5-2.8a8.1 8.1 0 0 0 2.1-1.2l2.1.8 1.8-3.1-1.8-1.3c.1-.4.1-.8.1-1.2Z"
                stroke="currentColor"
                strokeWidth="1.4"
              />
            </svg>
          </span>
          <span>Settings</span>
        </button>

        <button className="sidebar__bottomBtn" onClick={handleLogout}>
          <span className="sidebar__icon">
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
              />
              <path
                d="M21 4v16"
                stroke="currentColor"
                strokeWidth="1.8"
              />
            </svg>
          </span>
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}
