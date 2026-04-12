import { useMemo, useState, useRef, useEffect } from "react";
import Layout from "../../components/Layout";
import {
  SettingsCard,
  SettingsField,
  SettingsSaveButton,
} from "../../components/common/SettingsLayout";
import "../../components/common/SettingsLayout.css";
import "./ManagerSettings.css";
import { getUser } from "../../utils/auth";
import { sanitizeText } from "./ManagerSanitize";
import { apiUrl } from "../../config/apiBase";
import { getCsrfToken } from "../../services/api";

function getAuthToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken") ||
    ""
  );
}

// Calls POST /api/auth/change-password with { current_password, new_password }
function ChangePasswordModal({ onClose }) {
  const [currentPw, setCurrentPw] = useState("");
  const [newPw,     setNewPw]     = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [error,     setError]     = useState("");
  const [success,   setSuccess]   = useState(false);
  const [loading,   setLoading]   = useState(false);
  const firstInputRef             = useRef(null);

  useEffect(() => { firstInputRef.current?.focus(); }, []);

  useEffect(() => {
    const handler = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleSubmit = async () => {
    setError("");
    if (!currentPw) { setError("Please enter your current password."); return; }
    if (newPw.length < 8) { setError("New password must be at least 8 characters."); return; }
    if (newPw !== confirmPw) { setError("New passwords do not match."); return; }
    if (newPw === currentPw) { setError("New password must be different from your current password."); return; }

    const token = getAuthToken();
    if (!token) { setError("Session expired. Please log in again."); return; }

    setLoading(true);
    try {
      const csrf = await getCsrfToken();
      const res = await fetch(apiUrl("/api/auth/change-password"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          ...(csrf ? { "X-CSRF-Token": csrf } : {}),
        },
        body: JSON.stringify({
          current_password: currentPw,
          new_password:     newPw,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.detail || "Failed to change password. Please try again.");
        return;
      }
      setSuccess(true);
      setTimeout(onClose, 1600);
    } catch {
      setError("Network error. Please check your connection and try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="cpw-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      role="presentation"
    >
      <div className="cpw-modal" role="dialog" aria-modal="true" aria-labelledby="cpw-title">
        <div className="cpw-header">
          <h2 className="cpw-title" id="cpw-title">Change Password</h2>
          <button className="cpw-close" type="button" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {success ? (
          <div className="cpw-success">
            <span className="cpw-successIcon">✓</span>
            <p className="cpw-successText">Password changed successfully!</p>
          </div>
        ) : (
          <>
            <div className="cpw-body">
              <div className="cpw-field">
                <label className="cpw-label" htmlFor="cpw-current">Current Password</label>
                <input
                  id="cpw-current"
                  ref={firstInputRef}
                  type="password"
                  className="cpw-input"
                  value={currentPw}
                  onChange={(e) => setCurrentPw(e.target.value)}
                  placeholder="Enter current password"
                  autoComplete="current-password"
                />
              </div>
              <div className="cpw-field">
                <label className="cpw-label" htmlFor="cpw-new">New Password</label>
                <input
                  id="cpw-new"
                  type="password"
                  className="cpw-input"
                  value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                  placeholder="At least 8 characters"
                  autoComplete="new-password"
                />
              </div>
              <div className="cpw-field">
                <label className="cpw-label" htmlFor="cpw-confirm">Confirm New Password</label>
                <input
                  id="cpw-confirm"
                  type="password"
                  className="cpw-input"
                  value={confirmPw}
                  onChange={(e) => setConfirmPw(e.target.value)}
                  placeholder="Re-enter new password"
                  autoComplete="new-password"
                  onKeyDown={(e) => { if (e.key === "Enter") handleSubmit(); }}
                />
              </div>
              {error && <p className="cpw-error">{error}</p>}
            </div>

            <div className="cpw-actions">
              <button
                type="button"
                className="cpw-btnCancel"
                onClick={onClose}
                disabled={loading}
              >
                Cancel
              </button>
              <button
                type="button"
                className="cpw-btnSubmit"
                onClick={handleSubmit}
                disabled={loading || !currentPw || !newPw || !confirmPw}
              >
                {loading ? "Saving…" : "Change Password"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function ManagerSettings() {
  const [showPwModal, setShowPwModal] = useState(false);

  useEffect(() => { document.documentElement.removeAttribute("data-theme"); }, []);

  const user         = useMemo(() => getUser() || {}, []);
  const displayName  = sanitizeText(user.name || user.full_name || user.fullName || user.username || "Manager", 100);
  const displayEmail = sanitizeText(user.email || "manager@innova.cx", 254);

  return (
    <Layout role="manager">
      <div className="mgrSettingsPage">

        <div className="mgrSettingsHero">
          <h1 className="mgrSettingsHero__title">Settings</h1>
        </div>

        <div className="mgrSettingsContent">
          {/* Profile */}
          <div className="mgrFadeIn" style={{ animationDelay: "40ms" }}>
            <SettingsCard
              icon="👤"
              title="Profile"
              description="Your name and email are part of your account details."
            >
              <div className="mgrCardBody">
                <SettingsField label="Name"  value={displayName}  readOnly />
                <SettingsField label="Email" type="email" value={displayEmail} readOnly />
              </div>
            </SettingsCard>
          </div>

          {/* Security */}
          <div className="mgrFadeIn" style={{ animationDelay: "90ms" }}>
            <SettingsCard
              icon="🔒"
              title="Security"
              description="Keep your account protected with a strong password."
            >
              <div className="mgrCardBody">
                <div className="mgrPasswordRow">
                  <div className="mgrPasswordText">
                    <p className="mgrPasswordLabel">Password</p>
                    <p className="mgrPasswordSub">
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
