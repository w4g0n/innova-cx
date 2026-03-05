import { useMemo, useState } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";

import {
  SettingsCard,
  SettingsField,
  SettingsSaveButton,
  ChangePasswordModal,
} from "../../components/common/SettingsLayout";

import "../../components/common/SettingsLayout.css";
import "./OperatorSettings.css";
import { getUser } from "../../utils/auth";

export default function OperatorSettings() {
  const [showPwModal, setShowPwModal] = useState(false);

  const user = useMemo(() => getUser() || {}, []);
  const displayName =
    user.name || user.full_name || user.fullName || user.username || "Operator";
  const displayEmail = user.email || "operator@innova.cx";

  return (
    <Layout role="operator">
      <div className="opSettingsPage">
        <PageHeader
          title="Settings"
          subtitle="Manage your account preferences and basic configuration."
        />

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