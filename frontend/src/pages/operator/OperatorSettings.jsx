import { useState } from "react";
import Layout from "../../components/Layout";

import SettingsLayout, {
  SettingsCard,
  SettingsField,
  SettingsToggle,
  SettingsSelect,
  SettingsSaveButton,
} from "../../components/common/SettingsLayout";

import "../../components/common/SettingsLayout.css";
import "./OperatorSettings.css";

const TABS = [
  { id: "profile",  icon: "👤", label: "Profile" },
  { id: "system",   icon: "⚙️", label: "System" },
  { id: "prefs",    icon: "🎨", label: "Preferences" },
  { id: "security", icon: "🔒", label: "Security" },
];

export default function OperatorSettings() {
  const [tab, setTab] = useState("profile");

  const handleSave = () => {
    alert("Settings saved (demo).");
  };

  return (
    <Layout role="operator">
      <div className="opSettingsPage">
        <SettingsLayout
          title="Operator Settings"
          subtitle="Manage your profile, system preferences, and security."
          avatarLabel="O"
          tabs={TABS}
          activeTab={tab}
          onTabChange={setTab}
        >
          {tab === "profile" && (
            <>
              <SettingsCard icon="👤" title="Account Information">
                <SettingsField
                  label="Full Name"
                  placeholder="Enter your name"
                />
                <SettingsField
                  label="Email"
                  type="email"
                  placeholder="name@innovacx.com"
                />
                <SettingsField
                  label="Role"
                  defaultValue="Operator"
                />
              </SettingsCard>

              <div className="settingsFooterRow">
                <SettingsSaveButton onClick={handleSave} label="Save Changes" />
              </div>
            </>
          )}

          {tab === "system" && (
            <>
              <SettingsCard icon="⚙️" title="System Preferences">
                <SettingsToggle
                  label="Show advanced diagnostics"
                  description="Display detailed system metrics on the dashboard."
                  defaultChecked={true}
                />
                <SettingsToggle
                  label="Enable audit logging"
                  description="Record all operator actions for compliance review."
                  defaultChecked={true}
                />
                <SettingsToggle
                  label="Auto-refresh dashboard"
                  description="Automatically refresh dashboard data every 30 seconds."
                  defaultChecked={false}
                />
              </SettingsCard>

              <div className="settingsFooterRow">
                <SettingsSaveButton onClick={handleSave} label="Save Changes" />
              </div>
            </>
          )}

          {tab === "prefs" && (
            <>
              <SettingsCard icon="🎨" title="Preferences">
                <SettingsSelect
                  label="Language"
                  defaultValue="English"
                  options={[
                    { label: "English", value: "English" },
                    { label: "Arabic",  value: "Arabic" },
                  ]}
                />
                <SettingsSelect
                  label="Data export format"
                  defaultValue="CSV"
                  options={[
                    { label: "CSV",  value: "CSV" },
                    { label: "JSON", value: "JSON" },
                    { label: "PDF",  value: "PDF" },
                  ]}
                />
              </SettingsCard>

              <div className="settingsFooterRow">
                <SettingsSaveButton onClick={handleSave} label="Save Changes" />
              </div>
            </>
          )}

          {tab === "security" && (
            <>
              <SettingsCard icon="🔒" title="Security">
                <SettingsField
                  label="New Password"
                  type="password"
                  placeholder="Enter new password"
                  hint="At least 8 characters."
                />
                <SettingsField
                  label="Confirm Password"
                  type="password"
                  placeholder="Re-enter new password"
                />
              </SettingsCard>

              <div className="settingsFooterRow">
                <SettingsSaveButton onClick={handleSave} label="Update Password" />
              </div>
            </>
          )}
        </SettingsLayout>
      </div>
    </Layout>
  );
}
