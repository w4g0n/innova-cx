import Sidebar from "./Sidebar";
import { useUnreadCount } from "../hooks/useUnreadCount";
import "./Layout.css";

export default function Layout({ role, children, hideSidebar = false }) {
  const shouldHideSidebar = hideSidebar || role === "customer";
  const [unreadCount] = useUnreadCount(shouldHideSidebar ? null : role);

  return (
    <div className={`appShell ${shouldHideSidebar ? "appShell--noSidebar" : ""}`}>
      {!shouldHideSidebar && <Sidebar role={role} unreadCount={unreadCount} />}
      <main className={`appContent ${shouldHideSidebar ? "appContent--noSidebar" : ""}`}>
        {children}
      </main>
    </div>
  );
}