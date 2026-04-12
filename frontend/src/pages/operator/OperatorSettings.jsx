import { useEffect, useMemo, useState } from "react";
import Layout from "../../components/Layout";

import {
  SettingsCard,
  SettingsField,
  SettingsSaveButton,
  ChangePasswordModal,
} from "../../components/common/SettingsLayout";

import "../../components/common/SettingsLayout.css";
import "./OperatorSettings.css";
import { getUser } from "../../utils/auth";
import { sanitizeText } from "./Operatorsanitize";

export default function OperatorSettings() {
  const [showPwModal, setShowPwModal] = useState(false);

  useEffect(() => { document.documentElement.removeAttribute("data-theme"); }, []);

  const user = useMemo(() => getUser() || {}, []);
  const displayName  = sanitizeText(user.name || user.full_name || user.fullName || user.username || "Operator", 100);
  const displayEmail = sanitizeText(user.email || "operator@innova.cx", 254);

  return (
    <Layout role="operator">
      <div className="opSettingsPage">
        <div className="opSettingsHero">
          <h1 className="opSettingsHero__title">Settings</h1>
        </div>

        <div className="opSettingsContent">
          {/* Profile */}
          <div className="opFadeIn" style={{ animationDelay: "40ms" }}>
            <SettingsCard
              icon="👤"
              title="Profile"
              description="Your name and email are part of your account details."
            >
              <div className="opCardBody">
                <SettingsField label="Name" value={displayName} readOnly />
                <SettingsField
                  label="Email"
                  type="email"
                  value={displayEmail}
                  readOnly
                />
              </div>
            </SettingsCard>
          </div>

          {/* Security */}
          <div className="opFadeIn" style={{ animationDelay: "90ms" }}>
            <SettingsCard
              icon="🔒"
              title="Security"
              description="Keep your account protected with a strong password."
            >
              <div className="opCardBody">
                <div className="opPasswordRow">
                  <div className="opPasswordText">
                    <p className="opPasswordLabel">Password</p>
                    <p className="opPasswordSub">
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
