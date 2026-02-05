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

  const fullName = (user?.name || user?.fullName || user?.username || "").trim();
  const email = (user?.email || "").trim();
  const phone = (user?.phone || user?.mobile || "").trim();

  const [language, setLanguage] = useState("English");
  const [notifPref, setNotifPref] = useState("Enabled");

  const [emailNotifs, setEmailNotifs] = useState(true);
  const [inAppNotifs, setInAppNotifs] = useState(true);
  const [statusAlerts, setStatusAlerts] = useState(true);

  const [darkMode, setDarkMode] = useState(false);
  const [defaultComplaintType, setDefaultComplaintType] = useState("General");

  const onDownloadData = () => {
    alert("Demo: This would download your data once the backend is connected.");
  };

  const onDeleteAccount = () => {
    const ok = window.confirm(
      "Demo only: This would request account deletion once the backend is connected. Continue?"
    );
    if (ok) alert("Demo: Delete request created (UI only).");
  };

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
          
          <div className="customerSettingsCard">
            <div className="customerSettingsCardHeader">
              <div className="customerSettingsCardTitle">Account</div>
              <div className="customerSettingsCardSub">
                Basic information for this demo session.
              </div>
            </div>

            <div className="customerSettingsRows">
              <div className="customerSettingsRow">
                <div className="customerSettingsLabel">Name</div>
                <div className="customerSettingsValue">{fullName || "—"}</div>
              </div>

              <div className="customerSettingsRow">
                <div className="customerSettingsLabel">Email</div>
                <div className="customerSettingsValue">{email || "—"}</div>
              </div>

              <div className="customerSettingsRow">
                <div className="customerSettingsLabel">Phone</div>
                <div className="customerSettingsValue">{phone || "—"}</div>
              </div>

              <div className="customerSettingsRow">
                <div className="customerSettingsLabel">Role</div>
                <div className="customerSettingsValue">Customer</div>
              </div>

              <div className="customerSettingsRow customerSettingsRow--actions">
                <div>
                  <div className="customerSettingsLabel">Password</div>
                  <div className="customerSettingsMuted">
                    Demo only — change password will be connected later.
                  </div>
                </div>

                <button
                  type="button"
                  className="customerSettingsActionBtn"
                  onClick={() =>
                    alert("Demo: Change password will be available once the backend is connected.")
                  }
                >
                  Change Password
                </button>
              </div>
            </div>
          </div>

          
          <div className="customerSettingsCard">
            <div className="customerSettingsCardHeader">
              <div className="customerSettingsCardTitle">Notifications</div>
              <div className="customerSettingsCardSub">
                Control how you receive updates about your complaints.
              </div>
            </div>

            <div className="customerSettingsToggleList">
              <div className="customerSettingsToggleRow">
                <div className="customerSettingsToggleText">
                  <div className="customerSettingsToggleTitle">In-app notifications</div>
                  <div className="customerSettingsMuted">Show notifications inside the portal.</div>
                </div>

                <button
                  type="button"
                  className={"customerToggle " + (inAppNotifs ? "customerToggle--on" : "")}
                  aria-pressed={inAppNotifs}
                  onClick={() => setInAppNotifs((v) => !v)}
                >
                  <span className="customerToggleKnob" />
                </button>
              </div>

              <div className="customerSettingsToggleRow">
                <div className="customerSettingsToggleText">
                  <div className="customerSettingsToggleTitle">Email notifications</div>
                  <div className="customerSettingsMuted">Send updates to your email.</div>
                </div>

                <button
                  type="button"
                  className={"customerToggle " + (emailNotifs ? "customerToggle--on" : "")}
                  aria-pressed={emailNotifs}
                  onClick={() => setEmailNotifs((v) => !v)}
                >
                  <span className="customerToggleKnob" />
                </button>
              </div>

              <div className="customerSettingsToggleRow">
                <div className="customerSettingsToggleText">
                  <div className="customerSettingsToggleTitle">Ticket status alerts</div>
                  <div className="customerSettingsMuted">
                    Notify me when my complaint changes status.
                  </div>
                </div>

                <button
                  type="button"
                  className={"customerToggle " + (statusAlerts ? "customerToggle--on" : "")}
                  aria-pressed={statusAlerts}
                  onClick={() => setStatusAlerts((v) => !v)}
                >
                  <span className="customerToggleKnob" />
                </button>
              </div>
            </div>

            <div className="customerSettingsNote">
              These toggles are UI-only for now. Your selection won’t be saved after refresh until we
              link the backend.
            </div>
          </div>

          
          <div className="customerSettingsCard">
            <div className="customerSettingsCardHeader">
              <div className="customerSettingsCardTitle">Preferences</div>
              <div className="customerSettingsCardSub">
                Customize your experience in the portal.
              </div>
            </div>

            <div className="customerSettingsForm">
              <div className="customerSettingsField">
                <div className="customerSettingsFieldLabel">Notifications (quick)</div>
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

              <div className="customerSettingsField">
                <div className="customerSettingsFieldLabel">Default complaint type</div>
                <div className="customerSettingsPillWrap">
                  <PillSelect
                    value={defaultComplaintType}
                    onChange={setDefaultComplaintType}
                    ariaLabel="Default complaint type"
                    options={[
                      { value: "General", label: "General" },
                      { value: "Service", label: "Service" },
                      { value: "Billing", label: "Billing" },
                      { value: "Technical", label: "Technical" },
                    ]}
                  />
                </div>
              </div>

              <div className="customerSettingsInlineToggle">
                <div className="customerSettingsInlineToggleText">
                  <div className="customerSettingsToggleTitle">Dark mode</div>
                  <div className="customerSettingsMuted">
                    Demo only — UI theme toggle will be wired later.
                  </div>
                </div>

                <button
                  type="button"
                  className={"customerToggle " + (darkMode ? "customerToggle--on" : "")}
                  aria-pressed={darkMode}
                  onClick={() => setDarkMode((v) => !v)}
                >
                  <span className="customerToggleKnob" />
                </button>
              </div>
            </div>

            <div className="customerSettingsNote">
              These options are UI-only for now. Your selection won’t be saved after refresh until we
              link the backend.
            </div>
          </div>

          
          <div className="customerSettingsCard">
            <div className="customerSettingsCardHeader">
              <div className="customerSettingsCardTitle">Privacy</div>
              <div className="customerSettingsCardSub">
                Manage your data and account for this demo.
              </div>
            </div>

            <div className="customerSettingsPrivacyActions">
              <button type="button" className="customerSettingsActionBtn" onClick={onDownloadData}>
                Download My Data
              </button>

              <button
                type="button"
                className="customerSettingsDangerBtn"
                onClick={onDeleteAccount}
              >
                Delete Account
              </button>
            </div>

            <div className="customerSettingsNote">
              These actions are placeholders. No real data will be downloaded or deleted until we
              connect the backend.
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}