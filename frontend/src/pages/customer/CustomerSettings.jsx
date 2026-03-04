import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";

import PageHeader from "../../components/common/PageHeader";

import {
  SettingsCard,
  SettingsField,
  SettingsSaveButton,
  ChangePasswordModal,
} from "../../components/common/SettingsLayout";
import "../../components/common/SettingsLayout.css";

import "./CustomerSettings.css";
import { getUser } from "../../utils/auth";

export default function CustomerSettings() {
  const navigate = useNavigate();
  const [showPwModal, setShowPwModal] = useState(false);

  const user = useMemo(() => getUser() || {}, []);
  const displayName =
    user.name || user.full_name || user.fullName || user.username || "Customer";
  const displayEmail = user.email || "customer1@innova.cx";

  return (
    <Layout role="customer">
      <div className="cs-page custSettings">
        <PageHeader
          title="Settings"
          subtitle="Manage your account preferences and basic configuration."
          actions={
            <button
              type="button"
              className="csBackBtn"
              onClick={() => navigate("/customer")}
              aria-label="Back to customer landing"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M15 6l-6 6 6 6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          }
        />

        {/* Content */}
        <div className="cs-grid">
          {/* Profile */}
          <div className="cs-animateIn" style={{ animationDelay: "40ms" }}>
            <SettingsCard
              icon="👤"
              title="Profile"
              description="Your name and email are part of your account details."
            >
              <div className="cs-cardBody">
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
          <div className="cs-animateIn" style={{ animationDelay: "90ms" }}>
            <SettingsCard
              icon="🔒"
              title="Security"
              description="Keep your account protected with a strong password."
            >
              <div className="cs-cardBody">
                <div className="cs-passwordRow">
                  <div className="cs-passwordText">
                    <p className="cs-passwordLabel">Password</p>
                    <p className="cs-passwordSub">
                      Change your password anytime to keep your account secure.
                    </p>
                  </div>

                  <div className="cs-passwordAction">
                    <SettingsSaveButton
                      label="Change Password"
                      onClick={() => setShowPwModal(true)}
                    />
                  </div>
                </div>
              </div>
            </SettingsCard>
          </div>
        </div>

        {/* Modal */}
        {showPwModal && (
          <ChangePasswordModal onClose={() => setShowPwModal(false)} />
        )}
      </div>
    </Layout>
  );
}