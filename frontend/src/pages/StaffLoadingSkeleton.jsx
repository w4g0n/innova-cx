import React, { useEffect, useState } from "react";
import "./StaffLoadingSkeleton.css";
import novaLogo from "../assets/nova-logo.png"; // adjust path if needed

const PHASES = [
  "Initialising dashboard…",
  "Loading your workspace…",
  "Fetching your data…",
  "Almost ready…",
];

export default function StaffLoadingSkeleton() {
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    const duration = 3000;
    const interval = 30;
    const steps = duration / interval;
    let step = 0;

    const timer = setInterval(() => {
      step++;
      const raw = step / steps;
      const eased = 1 - Math.pow(1 - raw, 2.4);
      setProgress(Math.min(Math.round(eased * 100), 98));
      setPhase(Math.min(Math.floor(raw * PHASES.length), PHASES.length - 1));
      if (step >= steps) clearInterval(timer);
    }, interval);

    return () => clearInterval(timer);
  }, []);

  return (
    <div className="sls-root">
      {/* Subtle background pattern */}
      <div className="sls-bg" aria-hidden="true">
        <div className="sls-blob sls-blob1" />
        <div className="sls-blob sls-blob2" />
        <div className="sls-dots" />
      </div>

      <div className="sls-card">
        {/* Top accent bar */}
        <div className="sls-accent-bar" aria-hidden="true" />

        {/* Logo */}
        <div className="sls-logo-wrap" aria-label="InnovaAI">
          <div className="sls-logo-ring" aria-hidden="true" />
          <div className="sls-logo-glow"  aria-hidden="true" />
          <img
            src={novaLogo}
            alt="InnovaAI"
            className="sls-logo"
            draggable={false}
          />
        </div>

        {/* Brand */}
        <div className="sls-brand">InnovaAI</div>
        <div className="sls-sub">Staff Portal</div>

        {/* Phase label */}
        <div className="sls-phase-wrap">
          {PHASES.map((p, i) => (
            <span
              key={p}
              className={`sls-phase ${i === phase ? "sls-phase--active" : ""}`}
              aria-live={i === phase ? "polite" : undefined}
            >
              {p}
            </span>
          ))}
        </div>

        {/* Progress bar */}
        <div
          className="sls-bar-track"
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div className="sls-bar-fill" style={{ width: `${progress}%` }}>
            <div className="sls-bar-shimmer" />
          </div>
          <div className="sls-bar-tip" style={{ left: `${progress}%` }} />
        </div>

        <div className="sls-percent">{progress}%</div>

        {/* Ghost skeleton rows mimicking the dashboard layout */}
        <div className="sls-ghost" aria-hidden="true">
          {/* KPI row */}
          <div className="sls-ghost-kpis">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="sls-ghost-kpi" style={{ animationDelay: `${i * 0.08}s` }} />
            ))}
          </div>
          {/* Content rows */}
          <div className="sls-ghost-row" style={{ width: "80%", animationDelay: "0s" }} />
          <div className="sls-ghost-row" style={{ width: "60%", animationDelay: "0.1s" }} />
          <div className="sls-ghost-row" style={{ width: "70%", animationDelay: "0.2s" }} />
        </div>
      </div>

      <div className="sls-footer" aria-hidden="true">© 2026 InnovaAI</div>
    </div>
  );
}