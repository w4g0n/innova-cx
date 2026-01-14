import Sidebar from "./Sidebar";
import "./Layout.css";

export default function Layout({ role, children }) {
  return (
    <div className="appShell">
      <Sidebar role={role} />
      <main className="appContent">{children}</main>
    </div>
  );
}
