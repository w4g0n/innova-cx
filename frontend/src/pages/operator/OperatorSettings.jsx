import Layout from "../../components/Layout";
import "./OperatorSettings.css";

export default function OperatorSettings() {
  return (
    <Layout role="operator">
      <div className="settingsPage">
        <div className="settingsHeader">
          <h1>Settings</h1>
          <p>Operator preferences for monitoring and management.</p>
        </div>

        <div className="settingsGrid">
          <section className="settingsCard">
            <h2>System</h2>
            <label className="toggleRow">
              <span>Show advanced diagnostics</span>
              <input type="checkbox" defaultChecked />
            </label>
            <label className="toggleRow">
              <span>Enable audit logging</span>
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