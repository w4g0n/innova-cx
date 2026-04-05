import Sidebar from "./Sidebar";
import { useUnreadCount } from "../hooks/useUnreadCount";
import { usePendingApprovals } from "../hooks/usePendingApprovals";
import { useHeldCount } from "../hooks/useHeldCount";
import "./Layout.css";

export default function Layout({ role, children, hideSidebar = false }) {
  // Synchronously strip the customer data-theme so staff views are never affected.
  // Running this inline (not in useEffect) ensures zero flash — it executes before
  // the browser paints, so [data-theme="dark"] CSS rules never match staff pages.
  if (role !== "customer") {
    document.documentElement.removeAttribute("data-theme");
  }

  const shouldHideSidebar = hideSidebar || role === "customer";
  const [unreadCount] = useUnreadCount(shouldHideSidebar ? null : role);
  const pendingApprovals = usePendingApprovals(shouldHideSidebar ? null : role);
  const heldCount = useHeldCount(shouldHideSidebar ? null : role);

  return (
    <div className={`appShell ${shouldHideSidebar ? "appShell--noSidebar" : ""}`}>
      {!shouldHideSidebar && (
        <Sidebar role={role} unreadCount={unreadCount} pendingApprovals={pendingApprovals} heldCount={heldCount} />
      )}
      <main className={`appContent ${shouldHideSidebar ? "appContent--noSidebar" : ""}`}>
        {children}
      </main>
    </div>
  );
}
