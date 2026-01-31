import Sidebar from "./Sidebar";
import "./Layout.css";

export default function Layout({ role, children, hideSidebar = false }) {
  const shouldHideSidebar = hideSidebar || role === "customer";

  return (
    <div className={`appShell ${shouldHideSidebar ? "appShell--noSidebar" : ""}`}>
      {!shouldHideSidebar && <Sidebar role={role} />}
      <main className={`appContent ${shouldHideSidebar ? "appContent--noSidebar" : ""}`}>
        {children}
      </main>
    </div>
  );
}