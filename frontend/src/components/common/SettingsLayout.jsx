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
export function SettingsCard({ icon, title, children }) {
  return (
    <div className="sc-card">
      <div className="sc-card-header">
        <span className="sc-card-icon">{icon}</span>
        <h2 className="sc-card-title">{title}</h2>
      </div>
      <div className="sc-card-body">{children}</div>
    </div>
  );
}

/** Labelled text/email/password input */
export function SettingsField({ label, type = "text", placeholder, defaultValue, hint }) {
  return (
    <div className="sf-field">
      <label className="sf-label">{label}</label>
      <input
        className="sf-input"
        type={type}
        placeholder={placeholder}
        defaultValue={defaultValue}
      />
      {hint && <p className="sf-hint">{hint}</p>}
    </div>
  );
}

/** Toggle switch row */
export function SettingsToggle({ label, description, defaultChecked = false }) {
  const [on, setOn] = useState(defaultChecked);
  return (
    <div className="st-row">
      <div className="st-text">
        <span className="st-label">{label}</span>
        {description && <span className="st-desc">{description}</span>}
      </div>
      <button
        role="switch"
        aria-checked={on}
        className={`st-toggle ${on ? "st-toggle--on" : ""}`}
        onClick={() => setOn(!on)}
      >
        <span className="st-thumb" />
      </button>
    </div>
  );
}

/** Select dropdown row */
export function SettingsSelect({ label, options = [], defaultValue }) {
  return (
    <div className="sf-field">
      <label className="sf-label">{label}</label>
      <select className="sf-input sf-select" defaultValue={defaultValue}>
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
export function DangerZone({ actions = [] }) {
  return (
    <div className="dz-root">
      <p className="dz-title">⚠ Danger Zone</p>
      <div className="dz-actions">
        {actions.map((a, i) => (
          <div key={i} className="dz-row">
            <div>
              <p className="dz-label">{a.label}</p>
              <p className="dz-desc">{a.description}</p>
            </div>
            <button className="dz-btn">{a.buttonText}</button>
          </div>
        ))}
      </div>
    </div>
  );
}
