import { useState } from "react";
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
      <p className="dz-title">⚠ {title || "Danger Zone"}</p>
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

  const handleSubmit = (e) => {
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
    setSuccess(true);
    setTimeout(onClose, 1800);
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
          <h3 className="cpw-title">🔑 Change Password</h3>
          <button
            type="button"
            className="cpw-close"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {success ? (
          <div className="cpw-success">
            <div className="cpw-success-icon">✓</div>
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
              <button type="submit" className="ssb-btn ssb-btn--primary">
                Update Password
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
