import { useMemo, useState } from "react";
import Layout from "../../components/Layout";

import SettingsLayout, {
  SettingsCard,
  SettingsField,
  SettingsToggle,
  SettingsSelect,
  SettingsSaveButton,
  DangerZone,
  ChangePasswordModal,
} from "../../components/common/SettingsLayout";

import "../../components/common/SettingsLayout.css";
import "./EmployeeSettings.css";

const TABS = [
  { id: "profile",  icon: "👤", label: "Profile" },
  { id: "security", icon: "🔒", label: "Security" },
  { id: "notifs",   icon: "🔔", label: "Notifications" },
  { id: "prefs",    icon: "🎨", label: "Preferences" },
];

export default function EmployeeSettings() {
  const [tab, setTab] = useState("profile");
  const [showPwModal, setShowPwModal] = useState(false);

  const [profile, setProfile] = useState({
    fullName: "Employee User",
    email: "employee@innovacx.com",
    phone: "+971 5X XXX XXXX",
    department: "Customer Support",
    location: "Dubai",
  });

  const [security, setSecurity] = useState({
    twoFA: false,
    sessionTimeout: "30",
  });

  const [notifs, setNotifs] = useState({
    emailNotifs: true,
    smsNotifs: false,
    weeklyDigest: true,
  });

  const [prefs, setPrefs] = useState({
    theme: "System",
    density: "Comfortable",
    language: "English",
  });

  const avatarLabel = useMemo(() => {
    const name = profile.fullName?.trim() || "Employee";
    const parts = name.split(/\s+/);
    const a = (parts[0]?.[0] || "E").toUpperCase();
    const b = (parts[1]?.[0] || "E").toUpperCase();
    return `${a}${b}`;
  }, [profile.fullName]);

  return (
    <Layout role="employee">
      <div className="employeeSettingsPage">
        <SettingsLayout
          title="Employee Settings"
          subtitle="Manage your profile, security, notifications, and preferences."
          avatarLabel={avatarLabel}
          tabs={TABS}
          activeTab={tab}
          onTabChange={setTab}
        >
          {/* ── Profile ── */}
          {tab === "profile" && (
            <>
              <SettingsCard
                icon="👤"
                title="Personal Information"
                description="Name and email are managed by your administrator."
              >
                <SettingsField
                  label="Full Name"
                  value={profile.fullName}
                  readOnly
                />
                <SettingsField
                  label="Email"
                  type="email"
                  value={profile.email}
                  readOnly
                />
                <SettingsField
                  label="Phone"
                  value={profile.phone}
                  onChange={(v) => setProfile((p) => ({ ...p, phone: v }))}
                  placeholder="+971..."
                />
              </SettingsCard>

              <SettingsCard
                icon="🏢"
                title="Work Details"
                description="Optional fields for internal context."
              >
                <SettingsField
                  label="Department"
                  value={profile.department}
                  onChange={(v) => setProfile((p) => ({ ...p, department: v }))}
                  placeholder="e.g., Customer Support"
                />
                <SettingsField
                  label="Location"
                  value={profile.location}
                  onChange={(v) => setProfile((p) => ({ ...p, location: v }))}
                  placeholder="e.g., Dubai"
                />
              </SettingsCard>

              <div className="settingsFooterRow">
                <SettingsSaveButton onClick={() => {}} label="Save Changes" />
              </div>
            </>
          )}

          {/* ── Security ── */}
          {tab === "security" && (
            <>
              <SettingsCard
                icon="🔑"
                title="Password"
                description="Keep your account secure with a strong, unique password."
              >
                <div className="settingsPasswordRow">
                  <div>
                    <p className="settingsPasswordLabel">Password</p>
                    <p className="settingsPasswordSub">
                      Update your password at any time to protect your account.
                    </p>
                  </div>
                  <SettingsSaveButton
                    label="Change Password"
                    onClick={() => setShowPwModal(true)}
                  />
                </div>
              </SettingsCard>

              <SettingsCard
                icon="🛡️"
                title="Account Security"
                description="Protect your account and control session behavior."
              >
                <SettingsToggle
                  label="Enable Two-Factor Authentication (2FA)"
                  description="Adds an extra layer of security to your account."
                  checked={security.twoFA}
                  onChange={(checked) => setSecurity((s) => ({ ...s, twoFA: checked }))}
                />
                <SettingsSelect
                  label="Session Timeout"
                  description="Automatically log out after inactivity."
                  value={security.sessionTimeout}
                  onChange={(v) => setSecurity((s) => ({ ...s, sessionTimeout: v }))}
                  options={[
                    { label: "15 minutes", value: "15" },
                    { label: "30 minutes", value: "30" },
                    { label: "60 minutes", value: "60" },
                    { label: "Never",      value: "0"  },
                  ]}
                />
              </SettingsCard>

              <DangerZone
                title="Danger Zone"
                description="Be careful — these actions cannot be undone."
                actions={[
                  {
                    label: "Log out from all devices",
                    kind: "warning",
                    onClick: () => {},
                  },
                  {
                    label: "Deactivate my account",
                    kind: "danger",
                    onClick: () => {},
                  },
                ]}
              />

              <div className="settingsFooterRow">
                <SettingsSaveButton onClick={() => {}} label="Save Changes" />
              </div>
            </>
          )}

          {/* ── Notifications ── */}
          {tab === "notifs" && (
            <>
              <SettingsCard
                icon="🔔"
                title="Notifications"
                description="Choose how you want to be notified."
              >
                <SettingsToggle
                  label="Email Notifications"
                  description="Get updates by email."
                  checked={notifs.emailNotifs}
                  onChange={(checked) => setNotifs((n) => ({ ...n, emailNotifs: checked }))}
                />
                <SettingsToggle
                  label="SMS Notifications"
                  description="Get urgent updates by SMS."
                  checked={notifs.smsNotifs}
                  onChange={(checked) => setNotifs((n) => ({ ...n, smsNotifs: checked }))}
                />
                <SettingsToggle
                  label="Weekly Digest"
                  description="A summary of your tickets and activity."
                  checked={notifs.weeklyDigest}
                  onChange={(checked) => setNotifs((n) => ({ ...n, weeklyDigest: checked }))}
                />
              </SettingsCard>

              <div className="settingsFooterRow">
                <SettingsSaveButton onClick={() => {}} label="Save Changes" />
              </div>
            </>
          )}

          {/* ── Preferences ── */}
          {tab === "prefs" && (
            <>
              <SettingsCard
                icon="🎨"
                title="Preferences"
                description="Personalise your experience."
              >
                <SettingsSelect
                  label="Theme"
                  description="Controls the app appearance."
                  value={prefs.theme}
                  onChange={(v) => setPrefs((p) => ({ ...p, theme: v }))}
                  options={[
                    { label: "System", value: "System" },
                    { label: "Light",  value: "Light"  },
                    { label: "Dark",   value: "Dark"   },
                  ]}
                />
                <SettingsSelect
                  label="Layout Density"
                  description="Adjust spacing to fit more or less content."
                  value={prefs.density}
                  onChange={(v) => setPrefs((p) => ({ ...p, density: v }))}
                  options={[
                    { label: "Comfortable", value: "Comfortable" },
                    { label: "Compact",     value: "Compact"     },
                  ]}
                />
                <SettingsSelect
                  label="Language"
                  description="Language for UI labels."
                  value={prefs.language}
                  onChange={(v) => setPrefs((p) => ({ ...p, language: v }))}
                  options={[
                    { label: "English", value: "English" },
                    { label: "Arabic",  value: "Arabic"  },
                  ]}
                />
              </SettingsCard>

              <div className="settingsFooterRow">
                <SettingsSaveButton onClick={() => {}} label="Save Changes" />
              </div>
            </>
          )}
        </SettingsLayout>

        {/* ── Change Password Modal ── */}
        {showPwModal && (
          <ChangePasswordModal onClose={() => setShowPwModal(false)} />
        )}
      </div>
    </Layout>
  );
}
