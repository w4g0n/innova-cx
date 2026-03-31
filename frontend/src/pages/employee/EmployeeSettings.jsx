import { useEffect, useMemo, useState } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";

import {
  SettingsCard,
  SettingsField,
  SettingsSaveButton,
  ChangePasswordModal,
} from "../../components/common/SettingsLayout";

import "../../components/common/SettingsLayout.css";
import "./EmployeeSettings.css";
import { getUser } from "../../utils/auth";
import { sanitizeText } from "./EmpSanitize";

export default function EmployeeSettings() {
  const [showPwModal, setShowPwModal] = useState(false);

  useEffect(() => { document.documentElement.removeAttribute("data-theme"); }, []);

  const user = useMemo(() => getUser() || {}, []);

  // Sanitize display values derived from localStorage before rendering
  const displayName = sanitizeText(
    user.name || user.full_name || user.fullName || user.username || "Employee",
    100
  );
  const displayEmail = sanitizeText(
    user.email || "employee@innova.cx",
    254
  );

  return (
    <Layout role="employee">
      <div className="empSettingsPage">
        <PageHeader
          title="Settings"
          subtitle="Manage your account preferences and basic configuration."
        />

        <div className="empSettingsContent">
          {/* Profile */}
          <div className="empFadeIn" style={{ animationDelay: "40ms" }}>
            <SettingsCard
              icon="👤"
              title="Profile"
              description="Your name and email are part of your account details."
            >
              <div className="empCardBody">
                {/* displayName and displayEmail are sanitized above */}
                <SettingsField label="Name"  value={displayName}  readOnly />
                <SettingsField label="Email" type="email" value={displayEmail} readOnly />
              </div>
            </SettingsCard>
          </div>

          {/* Security */}
          <div className="empFadeIn" style={{ animationDelay: "90ms" }}>
            <SettingsCard
              icon="🔒"
              title="Security"
              description="Keep your account protected with a strong password."
            >
              <div className="empCardBody">
                <div className="empPasswordRow">
                  <div className="empPasswordText">
                    <p className="empPasswordLabel">Password</p>
                    <p className="empPasswordSub">
                      Change your password anytime to keep your account secure.
                    </p>
                  </div>

                  <SettingsSaveButton
                    label="Change Password"
                    onClick={() => setShowPwModal(true)}
                  />
                </div>
              </div>
            </SettingsCard>
          </div>
        </div>
      </div>

      {showPwModal && (
        <ChangePasswordModal onClose={() => setShowPwModal(false)} />
      )}
    </Layout>
  );
}