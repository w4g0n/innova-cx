import { useState } from "react";
import { apiUrl } from "../../config/apiBase";
import "./SettingsLayout.css";


export default function SettingsLayout({
  title,
  subtitle,
  avatarLabel = "U",
  tabs = [],
  children,
  activeTab,
  onTabChange,
}) {
  return (
    <div className="sl-root">
      {/*  Header banner  */}
      <div className="sl-banner">
        <div className="sl-banner-orb sl-orb1" />
        <div className="sl-banner-orb sl-orb2" />
        <div className="sl-avatar">{avatarLabel}</div>
        <div className="sl-banner-text">
          <h1 className="sl-title">{title}</h1>
          <p className="sl-subtitle">{subtitle}</p>
        </div>
      </div>

      {/*  Tab rail  */}
      <div className="sl-tabs" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={activeTab === t.id}
            className={`sl-tab ${activeTab === t.id ? "sl-tab--active" : ""}`}
            onClick={() => onTabChange(t.id)}
          >
            <span className="sl-tab-icon">{t.icon}</span>
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {/*  Content panel  */}
      <div className="sl-panel">{children}</div>
    </div>
  );
}


/** A titled card section */
export function SettingsCard({ icon, title, description, children }) {
  return (
    <div className="sc-card">
      <div className="sc-card-header">
        <span className="sc-card-icon">{icon}</span>
        <div>
          <h2 className="sc-card-title">{title}</h2>
          {description && <p className="sc-card-desc">{description}</p>}
        </div>
      </div>
      <div className="sc-card-body">{children}</div>
    </div>
  );
}

/**
 * Labelled input field.
 * readOnly=true renders a non-editable display value (name/email etc.).
 * Supports controlled (value + onChange) and uncontrolled (defaultValue) modes.
 */
export function SettingsField({
  label,
  type = "text",
  placeholder,
  defaultValue,
  value,
  onChange,
  hint,
  readOnly,
}) {
  if (readOnly) {
    return (
      <div className="sf-field">
        <label className="sf-label">{label}</label>
        <div className="sf-readonly">{value || defaultValue || "—"}</div>
        {hint && <p className="sf-hint">{hint}</p>}
      </div>
    );
  }

  const isControlled = value !== undefined && onChange !== undefined;
  return (
    <div className="sf-field">
      <label className="sf-label">{label}</label>
      <input
        className="sf-input"
        type={type}
        placeholder={placeholder}
        {...(isControlled
          ? { value, onChange: (e) => onChange(e.target.value) }
          : { defaultValue })}
      />
      {hint && <p className="sf-hint">{hint}</p>}
    </div>
  );
}

/**
 * Toggle switch row.
 * Supports controlled (checked + onChange) and uncontrolled (defaultChecked) modes.
 */
export function SettingsToggle({
  label,
  description,
  defaultChecked = false,
  checked,
  onChange,
}) {
  const isControlled = checked !== undefined;
  const [on, setOn] = useState(defaultChecked);
  const isOn = isControlled ? checked : on;

  const handleToggle = () => {
    if (isControlled) {
      onChange?.(!checked);
    } else {
      setOn((prev) => !prev);
    }
  };

  return (
    <div className="st-row">
      <div className="st-text">
        <span className="st-label">{label}</span>
        {description && <span className="st-desc">{description}</span>}
      </div>
      <button
        role="switch"
        aria-checked={isOn}
        className={`st-toggle ${isOn ? "st-toggle--on" : ""}`}
        onClick={handleToggle}
      >
        <span className="st-thumb" />
      </button>
    </div>
  );
}

/**
 * Select dropdown.
 * Supports controlled (value + onChange) and uncontrolled (defaultValue) modes.
 */
export function SettingsSelect({
  label,
  options = [],
  defaultValue,
  value,
  onChange,
  description,
}) {
  const isControlled = value !== undefined && onChange !== undefined;
  return (
    <div className="sf-field">
      <label className="sf-label">{label}</label>
      {description && <p className="sf-hint">{description}</p>}
      <select
        className="sf-input sf-select"
        {...(isControlled
          ? { value, onChange: (e) => onChange(e.target.value) }
          : { defaultValue })}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/** Save / action button */
export function SettingsSaveButton({ label = "Save changes", onClick, variant = "primary" }) {
  return (
    <button className={`ssb-btn ssb-btn--${variant}`} onClick={onClick}>
      {label}
    </button>
  );
}

/** Danger zone section */
export function DangerZone({ title, description, actions = [] }) {
  return (
    <div className="dz-root">
      <p className="dz-title">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight:6,verticalAlign:"middle"}}>
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        {title || "Danger Zone"}
      </p>
      {description && <p className="dz-zone-desc">{description}</p>}
      <div className="dz-actions">
        {actions.map((a, i) => (
          <div key={i} className="dz-row">
            <div>
              <p className="dz-label">{a.label}</p>
              {a.description && <p className="dz-desc">{a.description}</p>}
            </div>
            <button className="dz-btn" onClick={a.onClick}>
              {a.buttonText || a.label}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Change Password Modal — overlay with animated entrance, form validation, and success state */
export function ChangePasswordModal({ onClose }) {
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!form.current) {
      setError("Please enter your current password.");
      return;
    }
    if (form.next.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (form.next !== form.confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (form.next === form.current) {
      setError("New password must differ from your current password.");
      return;
    }

    const token = localStorage.getItem("access_token");
    setLoading(true);
    try {
      const res = await fetch(apiUrl("/api/auth/change-password"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_password: form.current,
          new_password: form.next,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Failed to change password.");
        return;
      }
      setSuccess(true);
      setTimeout(onClose, 1800);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="cpw-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Change password"
    >
      <div className="cpw-modal" onClick={(e) => e.stopPropagation()}>
        <div className="cpw-header">
          <h3 className="cpw-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight:8,verticalAlign:"middle"}}>
              <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/>
            </svg>
            Change Password
          </h3>
          <button
            type="button"
            className="cpw-close"
            onClick={onClose}
            aria-label="Close"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
          </button>
        </div>

        {success ? (
          <div className="cpw-success">
            <div className="cpw-success-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 6 9 17l-5-5"/>
              </svg>
            </div>
            <p>Password updated successfully!</p>
          </div>
        ) : (
          <form className="cpw-body" onSubmit={handleSubmit}>
            {error && <div className="cpw-error">{error}</div>}

            <div className="sf-field">
              <label className="sf-label">Current Password</label>
              <input
                className="sf-input"
                type="password"
                placeholder="Enter current password"
                value={form.current}
                onChange={(e) => setForm((f) => ({ ...f, current: e.target.value }))}
                autoFocus
              />
            </div>

            <div className="sf-field">
              <label className="sf-label">New Password</label>
              <input
                className="sf-input"
                type="password"
                placeholder="At least 8 characters"
                value={form.next}
                onChange={(e) => setForm((f) => ({ ...f, next: e.target.value }))}
              />
            </div>

            <div className="sf-field">
              <label className="sf-label">Confirm New Password</label>
              <input
                className="sf-input"
                type="password"
                placeholder="Repeat new password"
                value={form.confirm}
                onChange={(e) => setForm((f) => ({ ...f, confirm: e.target.value }))}
              />
            </div>

            <div className="cpw-footer">
              <button
                type="button"
                className="ssb-btn ssb-btn--secondary"
                onClick={onClose}
              >
                Cancel
              </button>
              <button type="submit" className="ssb-btn ssb-btn--primary" disabled={loading}>
                {loading ? "Saving…" : "Update Password"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}