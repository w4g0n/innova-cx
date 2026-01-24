import { useMemo, useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";
import "./CustomerFillForm.css";

export default function CustomerFillForm() {
  const location = useLocation();

  const user = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem("user") || "{}");
    } catch {
      return {};
    }
  }, []);

  const email = (user?.email || "").trim();

  const nameFromEmail = useMemo(() => {
    if (!email.includes("@")) return "Customer";
    const raw = email.split("@")[0] || "";
    const cleaned = raw.replace(/[._-]+/g, " ").trim();
    if (!cleaned) return "Customer";
    return cleaned
      .split(" ")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  }, [email]);

  const [timestamp] = useState(() => {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
      d.getHours()
    )}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  });

  const tenantTier = useMemo(() => {
    const e = email.toLowerCase();
    const n = nameFromEmail.toLowerCase();
    if (e.includes("vip") || e.includes("premium") || n.includes("vip")) return "Gold";
    if (e.includes("standard") || e.includes("silver")) return "Silver";
    return "Bronze";
  }, [email, nameFromEmail]);

  // Provided
  const [type, setType] = useState("Complaint");
  const [mode, setMode] = useState("Text");
  const [category, setCategory] = useState("Tenant Support");
  const [assetType, setAssetType] = useState("Office");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [audioWeight, setAudioWeight] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const t = params.get("type");
    if (t === "Complaint" || t === "Inquiry") setType(t);
  }, [location.search]);

  const submit = (e) => {
    e.preventDefault();

    const payload = {
      // Auto
      name: nameFromEmail,
      email,
      timestamp,
      tenant_tier: tenantTier,

      // Provided
      type,
      category,
      asset_type: assetType,
      subject,
      details: mode === "Text" ? message : "(audio demo)",
      audio_weight: mode === "Audio" && audioWeight.trim() ? audioWeight.trim() : null,
    };

    console.log("FORM SUBMIT (demo):", payload);
    alert("Submitted (demo). Your request has been recorded.");

    setSubject("");
    setMessage("");
    setCategory("Tenant Support");
    setAssetType("Office");
    setType("Complaint");
    setMode("Text");
    setAudioWeight("");
  };

  return (
    <Layout role="customer">
      <div className="custFormPage">
        <PageHeader
          title="Fill a Form"
          subtitle="Submit a complaint or inquiry using text or audio. Your details are auto-filled."
        />

        <form className="custFormCard" onSubmit={submit}>
          {/* Auto fields */}
          <div className="custFormAutoGrid">
            <div className="custField">
              <label className="custLabel">User</label>
              <input className="custInput" value={nameFromEmail} disabled />
            </div>

            <div className="custField">
              <label className="custLabel">Email</label>
              <input className="custInput" value={email || "—"} disabled />
            </div>

            <div className="custField">
              <label className="custLabel">Timestamp</label>
              <input className="custInput" value={timestamp} disabled />
            </div>

            <div className="custField">
              <label className="custLabel">Tenant Tier</label>
              <input className="custInput" value={tenantTier} disabled />
            </div>
          </div>

          <div className="custFormSpacer" />

          {/* Provided fields */}
          <div className="custFormGrid">
            <div className="custFieldRow custField--span2">
              <div className="custField custField--inline">
                <label className="custLabel">Type</label>
                <div className="custPillHolder">
                  <PillSelect
                    value={type}
                    onChange={setType}
                    ariaLabel="Select request type"
                    options={[
                      { value: "Complaint", label: "Complaint" },
                      { value: "Inquiry", label: "Inquiry" },
                    ]}
                  />
                </div>
              </div>

              <div className="custField custField--inline">
                <label className="custLabel">Category</label>
                <div className="custPillHolder">
                  <PillSelect
                    value={category}
                    onChange={setCategory}
                    ariaLabel="Select category"
                    options={[
                      { value: "Tenant Support", label: "Tenant Support" },
                      { value: "Leasing Inquiry", label: "Leasing Inquiry" },
                    ]}
                  />
                </div>
              </div>
            </div>

            <div className="custField">
              <label className="custLabel">Asset Type</label>
              <div className="custPillHolder">
                <PillSelect
                  value={assetType}
                  onChange={setAssetType}
                  ariaLabel="Select asset type"
                  options={[
                    { value: "Office", label: "Office" },
                    { value: "Warehouse", label: "Warehouse" },
                    { value: "Retail Store", label: "Retail Store" },
                  ]}
                />
              </div>
            </div>

            <div className="custField custField--span2">
              <label className="custLabel">Subject</label>
              <input
                className="custInput"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Short summary (e.g., Access card not working)"
                required
              />
            </div>

            <div className="custField custField--span2">
              <label className="custLabel">Details input</label>
              <div className="custModeRow">
                <button
                  type="button"
                  className={
                    mode === "Text" ? "custModeBtn custModeBtn--active" : "custModeBtn"
                  }
                  onClick={() => setMode("Text")}
                >
                  Text
                </button>
                <button
                  type="button"
                  className={
                    mode === "Audio" ? "custModeBtn custModeBtn--active" : "custModeBtn"
                  }
                  onClick={() => setMode("Audio")}
                >
                  Audio
                </button>
              </div>
            </div>

            {mode === "Text" ? (
              <div className="custField custField--span2">
                <label className="custLabel">Details</label>
                <textarea
                  className="custTextarea"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Describe what happened. Include time/location if possible."
                  rows={7}
                  required
                />
                <div className="custHint">
                  Tip: If urgent, include safety risk or business impact.
                </div>
              </div>
            ) : (
              <div className="custField custField--span2">
                <label className="custLabel">Audio</label>

                <div className="custAudioBox">
                  <div className="custAudioTitle">Record audio</div>

                  <div className="custAudioRowCompact">
                    <button
                      type="button"
                      className="custRecordBtn"
                      onClick={() => alert("Audio recording + transcript UI is next step (demo).")}
                    >
                      Start recording
                    </button>

                    <div className="custAudioWeightCompact">
                      <label className="custLabel custLabel--small">
                        Audio weight (optional)
                      </label>
                      <input
                        className="custInput custInput--compact"
                        value={audioWeight}
                        onChange={(e) => setAudioWeight(e.target.value)}
                        placeholder="e.g., 0.7"
                      />
                    </div>
                  </div>

                  <div className="custHint">
                    If provided, audio weight helps prioritize audio-based details (demo field).
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="custFormActions">
            <button
              type="button"
              className="softPillBtn"
              onClick={() => window.history.back()}
            >
              Cancel
            </button>

            <button type="submit" className="primaryPillBtn">
              Submit
            </button>
          </div>
        </form>
      </div>
    </Layout>
  );
}
