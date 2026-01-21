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

  const [type, setType] = useState("Complaint");
  const [mode, setMode] = useState("Text");
  const [category, setCategory] = useState("General");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const t = params.get("type");

    if (t === "Complaint" || t === "Inquiry") {
      setType(t);
    }
  }, [location.search]);

  const submit = (e) => {
    e.preventDefault();

    const payload = {
      name: nameFromEmail,
      email,
      type,
      mode,
      category,
      subject,
      message: mode === "Text" ? message : "(audio demo)",
      createdAt: new Date().toISOString(),
    };

    console.log("FORM SUBMIT (demo):", payload);
    alert("Submitted (demo). Your request has been recorded.");

    setSubject("");
    setMessage("");
    setCategory("General");
    setType("Complaint");
    setMode("Text");
  };

  return (
    <Layout role="customer">
      <div className="custFormPage">
        <PageHeader
          title="Fill a Form"
          subtitle="Submit a complaint or inquiry using text or audio. Your details are auto-filled."
        />

        <form className="custFormCard" onSubmit={submit}>
          <div className="custFormTopGrid">
            <div className="custField">
              <label className="custLabel">Name</label>
              <input className="custInput" value={nameFromEmail} disabled />
            </div>

            <div className="custField">
              <label className="custLabel">Email</label>
              <input className="custInput" value={email || "—"} disabled />
            </div>

            <div className="custField">
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

            <div className="custField">
              <label className="custLabel">Input Mode</label>
              <div className="custModeRow">
                <button
                  type="button"
                  className={
                    mode === "Text"
                      ? "custModeBtn custModeBtn--active"
                      : "custModeBtn"
                  }
                  onClick={() => setMode("Text")}
                >
                  Text
                </button>
                <button
                  type="button"
                  className={
                    mode === "Audio"
                      ? "custModeBtn custModeBtn--active"
                      : "custModeBtn"
                  }
                  onClick={() => setMode("Audio")}
                >
                  Audio
                </button>
              </div>
            </div>
          </div>

          <div className="custFormGrid">
            <div className="custField">
              <label className="custLabel">Category</label>
              <div className="custPillHolder">
                <PillSelect
                  value={category}
                  onChange={setCategory}
                  ariaLabel="Select category"
                  options={[
                    { value: "General", label: "General" },
                    { value: "Billing", label: "Billing" },
                    { value: "Facilities", label: "Facilities" },
                    { value: "Security", label: "Security" },
                    { value: "Technical", label: "Technical" },
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
                placeholder="Short summary (e.g., Air conditioning not working)"
                required
              />
            </div>

            {mode === "Text" ? (
              <div className="custField custField--span2">
                <label className="custLabel">Details</label>
                <textarea
                  className="custTextarea"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Describe what happened. Include time/location if possible."
                  rows={6}
                  required
                />
                <div className="custHint">
                  Tip: If this is urgent, include any safety risk or business impact.
                </div>
              </div>
            ) : (
              <div className="custField custField--span2">
                <label className="custLabel">Audio</label>

                <div className="custAudioBox">
                  <div className="custAudioTitle">Record audio (demo)</div>
                  <div className="custAudioSub">
                    This will use the mic + transcript confirmation next step (X / ✓ like ChatGPT).
                  </div>

                  <button
                    type="button"
                    className="custRecordBtn"
                    onClick={() =>
                      alert("Audio recording + transcript UI is next step (demo).")
                    }
                  >
                    Start recording
                  </button>
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
