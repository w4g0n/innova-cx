import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";

import "./CustomerSettings.css";

export default function CustomerSettings() {
  const navigate = useNavigate();

  const user = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem("user") || "{}") || {};
    } catch {
      return {};
    }
  }, []);

  const email = (user?.email || "").trim();

  // ✅ Demo preferences (placeholder only — will connect to backend later)
  const [language, setLanguage] = useState("English");
  const [notifPref, setNotifPref] = useState("Enabled");

  return (
    <Layout role="customer">
      <div className="customerSettingsPage">
        <PageHeader
          title="Settings"
          subtitle="Manage your preferences for this demo customer portal."
        />

        <div className="customerSettingsTopRow">
          <button
            type="button"
            className="customerSettingsBackBtn"
            onClick={() => navigate("/customer")}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M15 18l-6-6 6-6"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Back
          </button>
        </div>

        <div className="customerSettingsGrid">
          {/* Account */}
          <div className="customerSettingsCard">
            <div className="customerSettingsCardHeader">
              <div className="customerSettingsCardTitle">Account</div>
              <div className="customerSettingsCardSub">
                Basic information for this demo session.
              </div>
            </div>

            <div className="customerSettingsRows">
              <div className="customerSettingsRow">
                <div className="customerSettingsLabel">Email</div>
                <div className="customerSettingsValue">{email || "—"}</div>
              </div>

              <div className="customerSettingsRow">
                <div className="customerSettingsLabel">Role</div>
                <div className="customerSettingsValue">Customer</div>
              </div>
            </div>
          </div>

          {/* Preferences */}
          <div className="customerSettingsCard">
            <div className="customerSettingsCardHeader">
              <div className="customerSettingsCardTitle">Preferences</div>
              <div className="customerSettingsCardSub">
                Placeholder settings — we’ll connect real preferences later.
              </div>
            </div>

            <div className="customerSettingsForm">
              <div className="customerSettingsField">
                <div className="customerSettingsFieldLabel">Notifications</div>
                <div className="customerSettingsPillWrap">
                  <PillSelect
                    value={notifPref}
                    onChange={setNotifPref}
                    ariaLabel="Notification preference"
                    options={[
                      { value: "Enabled", label: "Enabled" },
                      { value: "Disabled", label: "Disabled" },
                    ]}
                  />
                </div>
              </div>

              <div className="customerSettingsField">
                <div className="customerSettingsFieldLabel">Language</div>
                <div className="customerSettingsPillWrap">
                  <PillSelect
                    value={language}
                    onChange={setLanguage}
                    ariaLabel="Language preference"
                    options={[
                      { value: "English", label: "English" },
                      { value: "Arabic", label: "Arabic" },
                    ]}
                  />
                </div>
              </div>
            </div>

            <div className="customerSettingsNote">
              These options are UI-only for now. Your selection won’t be saved after refresh until we link the backend.
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
