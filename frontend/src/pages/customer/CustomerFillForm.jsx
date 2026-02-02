import { useMemo, useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";
import "./CustomerFillForm.css";

export default function CustomerFillForm({ embedded = false, onCancel }) {
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
  const [assetType, setAssetType] = useState("Office");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const t = params.get("type");
    // eslint-disable-next-line react-hooks/set-state-in-effect -- TODO: review - setState in useEffect, consider deriving from URL
    if (t === "Complaint" || t === "Inquiry") setType(t);
  }, [location.search]);

  const submit = (e) => {
    e.preventDefault();

    const payload = {
      name: nameFromEmail,
      email,
      type,
      asset_type: assetType,
      subject,
      details: message,
    };

    console.log("FORM SUBMIT (demo):", payload);
    alert("Submitted (demo). Your request has been recorded.");

    setSubject("");
    setMessage("");
    setAssetType("Office");
    setType("Complaint");
    setMode("Text");
  };

  const handleMicClick = async () => {
    if (!isRecording) {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      chunksRef.current = [];
      const recorder = new MediaRecorder(stream, {
        mimeType: "audio/mp4",
      });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        setIsTranscribing(true);

        const blob = new Blob(chunksRef.current, { type: "audio/mp4" });
        const formData = new FormData();
        formData.append("audio", blob, "mic.mp4");

        const res = await fetch("http://localhost:3001/transcribe", {
          method: "POST",
          body: formData,
        });

        const data = await res.json();
        setMessage(data.transcript);
        setIsTranscribing(false);
      };

      recorder.start();
      setIsRecording(true);
      return;
    }

    mediaRecorderRef.current.stop();
    setIsRecording(false);
  };

  const handleCancel = () => {
    if (embedded) {
      if (typeof onCancel === "function") onCancel();
      return;
    }
    window.history.back();
  };

  const content = (
    <div className={`custFormPage ${embedded ? "custFormPage--embedded" : ""}`}>
      <PageHeader
        title="Fill a Form"
        subtitle="Submit a complaint or inquiry using text or audio."
      />

      <form className="custFormCard" onSubmit={submit}>
        <div className="custFormAutoGrid">
          <div className="custField">
            <label className="custLabel">User</label>
            <input className="custInput" value={nameFromEmail} disabled />
          </div>

          <div className="custField">
            <label className="custLabel">Email</label>
            <input className="custInput" value={email || "—"} disabled />
          </div>
        </div>

        <div className="custFormSpacer" />

        <div className="custFormGrid">
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
                className={mode === "Text" ? "custModeBtn custModeBtn--active" : "custModeBtn"}
                onClick={() => setMode("Text")}
              >
                Text
              </button>
              <button
                type="button"
                className={mode === "Audio" ? "custModeBtn custModeBtn--active" : "custModeBtn"}
                onClick={() => setMode("Audio")}
              >
                Audio
              </button>
            </div>
          </div>

          <div className="custField custField--span2">
            <label className="custLabel">Details</label>

            {mode === "Audio" && (
              <button
                type="button"
                className={`custMicBtn ${isRecording ? "recording" : ""}`}
                onClick={handleMicClick}
                disabled={isTranscribing}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  />
                  <path
                    d="M19 11a7 7 0 0 1-14 0"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  />
                  <path d="M12 18v3" stroke="currentColor" strokeWidth="1.8" />
                  <path d="M8 21h8" stroke="currentColor" strokeWidth="1.8" />
                </svg>
              </button>
            )}

            {isTranscribing && <div className="custHint">Transcribing audio…</div>}

            <textarea
              className="custTextarea"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Describe what happened. Include time/location if possible."
              rows={7}
              required
            />
          </div>
        </div>

        <div className="custFormActions">
          <button type="button" className="softPillBtn" onClick={handleCancel}>
            Cancel
          </button>

          <button type="submit" className="primaryPillBtn" disabled={isTranscribing}>
            Submit
          </button>
        </div>
      </form>
    </div>
  );

  if (embedded) return content;
  return <Layout role="customer">{content}</Layout>;
}
