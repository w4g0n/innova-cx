import Layout from "../../components/Layout";
import "./ManagerSettings.css";

export default function ManagerSettings() {
  return (
    <Layout role="manager">
      <div className="settingsPage">
        <div className="settingsHeader">
          <h1>Settings</h1>
          <p>Manager preferences and account configuration.</p>
        </div>

        <div className="settingsGrid">
          <section className="settingsCard">
            <h2>Manager Controls</h2>
            <label className="toggleRow">
              <span>Auto-approve low risk requests</span>
              <input type="checkbox" />
            </label>
            <label className="toggleRow">
              <span>Weekly summary email</span>
              <input type="checkbox" defaultChecked />
            </label>
          </section>

          <section className="settingsCard">
            <h2>Security</h2>
            <p className="settingsHint">Connected later to backend.</p>
            <button className="settingsBtnPrimary">Change Password</button>
          </section>
        </div>
      </div>
    </Layout>
  );
}