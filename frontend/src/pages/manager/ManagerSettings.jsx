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
import "./ManagerSettings.css";

const TABS = [
  { id: "profile",  icon: "👤", label: "Profile" },
  { id: "notifs",   icon: "🔔", label: "Notifications" },
  { id: "prefs",    icon: "🎨", label: "Preferences" },
  { id: "security", icon: "🔒", label: "Security" },
];

export default function ManagerSettings() {
  const [tab, setTab] = useState("profile");

  const handleSave = () => {
    alert("Settings saved (demo).");
  };

  return (
    <Layout role="manager">
      <div className="mgrSettingsPage">
        <SettingsLayout
          title="Manager Settings"
          subtitle="Manage your profile, notifications, and preferences."
          avatarLabel="M"
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
                  defaultValue="Manager"
                />
              </SettingsCard>

              <div className="settingsFooterRow">
                <SettingsSaveButton onClick={handleSave} label="Save Changes" />
              </div>
            </>
          )}

          {tab === "notifs" && (
            <>
              <SettingsCard icon="🔔" title="Notification Preferences">
                <SettingsToggle
                  label="Email Notifications"
                  description="Get approval and escalation alerts by email."
                  defaultChecked={true}
                />
                <SettingsToggle
                  label="In-app Notifications"
                  description="Show alerts inside the portal."
                  defaultChecked={true}
                />
                <SettingsToggle
                  label="Auto-approve weekly summary"
                  description="Receive a weekly digest of pending approvals."
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
                <SettingsToggle
                  label="Auto-approve low risk requests"
                  description="Automatically approve requests below the risk threshold."
                  defaultChecked={false}
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
