import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";
import { getToken } from "../../utils/auth"; // your token helper
import { apiUrl } from "../../config/apiBase"; // optional centralized API URL

import "./CustomerSettings.css";


export default function CustomerSettings() {
  const navigate = useNavigate();

  const [language, setLanguage] = useState("English");

  const [emailNotifs, setEmailNotifs] = useState(true);
  const [inAppNotifs, setInAppNotifs] = useState(true);
  const [statusAlerts, setStatusAlerts] = useState(true);

  const [darkMode, setDarkMode] = useState(false);
  const [defaultComplaintType, setDefaultComplaintType] = useState("General");

  const [account, setAccount] = useState({
    name: "",
    email: "",
    phone: "",
    role: "Customer",
  });

  // 🔹 Load settings from backend
  useEffect(() => {
    async function fetchCustomerSettings() {
      try {
        const token = getToken();
        const res = await fetch(apiUrl("api/customer/setting"), {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          console.error("Failed to fetch settings", res.status);
          return;
        }

        const data = await res.json();
        if (!data) return;

        // Account info
        if (data.account) {
          setAccount({
            name: data.account.name || "",
            email: data.account.email || "",
            phone: data.account.phone || "",
            role: data.account.role || "Customer",
          });
        }

        // Preferences
        if (data.preferences) {
          setLanguage(data.preferences.language || "English");
          setDarkMode(!!data.preferences.darkMode);
          setDefaultComplaintType(
            data.preferences.defaultComplaintType || "General"
          );
          setEmailNotifs(!!data.preferences.emailNotifications);
          setInAppNotifs(!!data.preferences.inAppNotifications);
          setStatusAlerts(!!data.preferences.statusAlerts);
        }
      } catch (err) {
        console.error("Error fetching customer settings", err);
      }
    }

    fetchCustomerSettings();
  }, []);

  // 🔹 Save settings to backend
  const saveSettings = async () => {
    try {
      const token = getToken();
      const res = await fetch(apiUrl("api/customer/setting"), {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          language,
          darkMode,
          defaultComplaintType,
          emailNotifications: emailNotifs,
          inAppNotifications: inAppNotifs,
          statusAlerts,
        }),
      });

      if (res.ok) {
        alert("Settings saved successfully");
      } else {
        alert("Failed to save settings");
      }
    } catch (err) {
      console.error("Error saving settings", err);
      alert("Failed to save settings");
    }
  };

  return (
    <Layout role="customer">
      <div className="customerSettingsPage">
        <PageHeader
          title="Settings"
          subtitle="Manage your preferences for this demo customer portal."
        />

        <div className="customerSettingsTopRow">
          <button type="button" className="customerSettingsBackBtn" onClick={() => navigate("/customer")}>
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
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
          <button type="button" className="customerSettingsActionBtn" onClick={saveSettings}>
              Save Changes
          </button>
        </div>

        <div className="customerSettingsGrid">
          {/* ACCOUNT CARD */}
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
                <div className="customerSettingsValue">{account.name}</div>
              </div>

              <div className="customerSettingsRow">
                <div className="customerSettingsLabel">Email</div>
                <div className="customerSettingsValue">{account.email}</div>
              </div>

              <div className="customerSettingsRow">
                <div className="customerSettingsLabel">Phone</div>
                <div className="customerSettingsValue">{account.phone}</div>
              </div>

              <div className="customerSettingsRow">
                <div className="customerSettingsLabel">Role</div>
                <div className="customerSettingsValue">{account.role}</div>
              </div>
            </div>
          </div>
 
          {/* NOTIFICATIONS CARD */}
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
                  <div className="customerSettingsToggleTitle">
                    In-app notifications
                  </div>
                  <div className="customerSettingsMuted">
                    Show notifications inside the portal.
                  </div>
                </div>

                <button
                  type="button"
                  className={
                    "customerToggle " + (inAppNotifs ? "customerToggle--on" : "")
                  }
                  aria-pressed={inAppNotifs}
                  onClick={() => setInAppNotifs((v) => !v)}
                >
                  <span className="customerToggleKnob" />
                </button>
              </div>

              <div className="customerSettingsToggleRow">
                <div className="customerSettingsToggleText">
                  <div className="customerSettingsToggleTitle">
                    Email notifications
                  </div>
                  <div className="customerSettingsMuted">
                    Send updates to your email.
                  </div>
                </div>

                <button
                  type="button"
                  className={
                    "customerToggle " + (emailNotifs ? "customerToggle--on" : "")
                  }
                  aria-pressed={emailNotifs}
                  onClick={() => setEmailNotifs((v) => !v)}
                >
                  <span className="customerToggleKnob" />
                </button>
              </div>

              <div className="customerSettingsToggleRow">
                <div className="customerSettingsToggleText">
                  <div className="customerSettingsToggleTitle">
                    Ticket status alerts
                  </div>
                  <div className="customerSettingsMuted">
                    Notify me when my complaint changes status.
                  </div>
                </div>

                <button
                  type="button"
                  className={
                    "customerToggle " + (statusAlerts ? "customerToggle--on" : "")
                  }
                  aria-pressed={statusAlerts}
                  onClick={() => setStatusAlerts((v) => !v)}
                >
                  <span className="customerToggleKnob" />
                </button>
              </div>
            </div>

            <div className="customerSettingsNote">
              Your notification preferences will now be saved to the backend.
            </div>
          </div>

          {/* PREFERENCES CARD */}
          <div className="customerSettingsCard">
            <div className="customerSettingsCardHeader">
              <div className="customerSettingsCardTitle">Preferences</div>
              <div className="customerSettingsCardSub">
                Customize your experience in the portal.
              </div>
            </div>

            <div className="customerSettingsForm">
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
                <div className="customerSettingsFieldLabel">
                  Default complaint type
                </div>
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
                    This toggle now updates backend preference.
                  </div>
                </div>

                <button
                  type="button"
                  className={
                    "customerToggle " + (darkMode ? "customerToggle--on" : "")
                  }
                  aria-pressed={darkMode}
                  onClick={() => setDarkMode((v) => !v)}
                >
                  <span className="customerToggleKnob" />
                </button>
              </div>
            </div>

            <div className="customerSettingsNote">
              Preferences are now connected to the backend.
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
