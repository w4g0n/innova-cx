import React, { useEffect, useState } from "react";
import "./CustomerLoadingSkeleton.css";
import novaLogo from "../../assets/nova-logo.png"; // ← your actual logo path

const PHASES = [
  "Initialising portal…",
  "Loading your profile…",
  "Fetching your tickets…",
  "Almost ready…",
];

export default function CustomerLoadingSkeleton() {
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    // Smooth animated progress bar
    const duration = 4000; // ms total
    const interval = 30;   // tick every 30ms
    const steps = duration / interval;
    let step = 0;

    const timer = setInterval(() => {
      step++;
      // Ease-out curve: fast at start, slows near end
      const raw = step / steps;
      const eased = 1 - Math.pow(1 - raw, 2.4);
      const pct = step >= steps ? 100 : Math.min(Math.round(eased * 100), 98);
      setProgress(pct);
      setPhase(Math.min(Math.floor(raw * PHASES.length), PHASES.length - 1));

      if (step >= steps) clearInterval(timer);
    }, interval);

    return () => clearInterval(timer);
  }, []);

  return (
    <div className="cls-root">
      {/* Ambient nebula background */}
      <div className="cls-bg" aria-hidden="true">
        <div className="cls-neb cls-neb1" />
        <div className="cls-neb cls-neb2" />
        <div className="cls-neb cls-neb3" />
        <div className="cls-grid" />
      </div>

      {/* Central card */}
      <div className="cls-card">
        {/* Shimmer border */}
        <div className="cls-card-border" aria-hidden="true" />

        {/* Floating logo */}
        <div className="cls-logo-wrap" aria-label="InnovaAI">
          <div className="cls-logo-glow" aria-hidden="true" />
          <div className="cls-logo-ring cls-logo-ring1" aria-hidden="true" />
          <div className="cls-logo-ring cls-logo-ring2" aria-hidden="true" />
          <img
            src={novaLogo}
            alt="InnovaAI"
            className="cls-logo"
            draggable={false}
          />
        </div>

        {/* Brand name */}
        <div className="cls-brand">InnovaAI</div>
        <div className="cls-sub">Customer Portal</div>

        {/* Phase label */}
        <div className="cls-phase-wrap">
          {PHASES.map((p, i) => (
            <span
              key={p}
              className={`cls-phase ${i === phase ? "cls-phase--active" : ""}`}
              aria-live={i === phase ? "polite" : undefined}
            >
              {p}
            </span>
          ))}
        </div>

        {/* Progress bar */}
        <div className="cls-bar-track" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
          <div className="cls-bar-fill" style={{ width: `${progress}%` }}>
            <div className="cls-bar-shimmer" />
          </div>
          <div className="cls-bar-glow" style={{ left: `${progress}%` }} />
        </div>

        <div className="cls-percent">{progress}%</div>

        {/* Skeleton rows — hint of the page behind */}
        <div className="cls-ghost-rows" aria-hidden="true">
          <div className="cls-ghost-row" style={{ width: "70%", animationDelay: "0s" }} />
          <div className="cls-ghost-row" style={{ width: "50%", animationDelay: ".1s" }} />
          <div className="cls-ghost-row" style={{ width: "60%", animationDelay: ".2s" }} />
        </div>
      </div>

      {/* Corner monospace label */}
      <div className="cls-corner-label" aria-hidden="true">© 2026 InnovaAI</div>
    </div>
  );
}