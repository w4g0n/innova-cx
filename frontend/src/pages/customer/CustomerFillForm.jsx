import { useState, useRef } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import AudioReplyPlayer from "../../components/common/AudioReplyPlayer";
import { submitTextComplaint, transcribeAudio } from "../../services/api";
import "./CustomerFillForm.css";

export default function CustomerFillForm({ embedded = false, onCancel, initialType }) {
  const [mode, setMode] = useState("Text");
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState([]);
  const fileInputRef = useRef(null);

  // Voice recording state
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const cancelRecordingRef = useRef(false);

  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceStage, setVoiceStage] = useState("idle");
  const [draftTranscript, setDraftTranscript] = useState("");
  const [latestAudioFeatures, setLatestAudioFeatures] = useState(null);

  // Validation state
  const [errors, setErrors] = useState({});
  const [submitted, setSubmitted] = useState(null);
  const [showConfirm, setShowConfirm] = useState(false);

  // ── File helpers ────────────────────────────────────────────────────────
  const BYTES_PER_KB = 1024;
  const BYTES_PER_MB = BYTES_PER_KB * BYTES_PER_KB;
  const formatBytes = (bytes) => {
    if (typeof bytes !== "number" || Number.isNaN(bytes)) return "";
    if (bytes < BYTES_PER_KB) return `${bytes} B`;
    const kb = bytes / BYTES_PER_KB;
    if (kb < BYTES_PER_KB) return `${kb.toFixed(1)} KB`;
    return `${(bytes / BYTES_PER_MB).toFixed(1)} MB`;
  };

  const openFilePicker = () => fileInputRef.current?.click();

  const onFilesSelected = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setAttachments((prev) => {
      const next = [...prev];
      for (const f of files) {
        const exists = next.some((x) => x.name === f.name && x.size === f.size && x.lastModified === f.lastModified);
        if (!exists) next.push(f);
      }
      return next;
    });
    e.target.value = "";
  };

  const removeAttachment = (fileToRemove) => {
    setAttachments((prev) =>
      prev.filter((f) => !(f.name === fileToRemove.name && f.size === fileToRemove.size && f.lastModified === fileToRemove.lastModified))
    );
  };

  // ── Stream cleanup ──────────────────────────────────────────────────────
  const cleanupStream = () => {
    try {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
    } catch (err) {
      console.debug("Failed to cleanup media stream:", err);
    }
  };

  const resetForm = () => {
    setMode("Text");
    setMessage("");
    setAttachments([]);
    setIsRecording(false);
    setIsTranscribing(false);
    setVoiceStage("idle");
    setDraftTranscript("");
    setLatestAudioFeatures(null);
    setErrors({});
    cleanupStream();
  };

  // ── Validation ──────────────────────────────────────────────────────────
  const validate = () => {
    const newErrors = {};
    const details = (message || "").trim();
    if (!details) {
      newErrors.message = "Please describe your issue before submitting.";
    } else if (details.length < 10) {
      newErrors.message = "Please provide more detail (at least 10 characters).";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // ── Submit ──────────────────────────────────────────────────────────────
  // Step 1: validate → show confirm dialog
  const handleSubmitClick = (e) => {
    e.preventDefault();
    if (!validate()) return;
    setShowConfirm(true);
  };

  // Step 2: user confirmed → actually call the API
  const doActualSubmit = async () => {
    setShowConfirm(false);
    const details = (message || "").trim();
    const wasAudio = mode === "Audio";
    try {
      const orchestratorResult = await submitTextComplaint(details, {
        ticket_type: initialType ? initialType.toLowerCase() : null,
        has_audio: wasAudio,
        audio_features: wasAudio ? latestAudioFeatures : null,
      });
      const isInquiry = !orchestratorResult?.ticket_id;
      const ticketId = orchestratorResult?.ticket_id ?? null;
      const replyText = isInquiry
        ? (orchestratorResult?.chatbot_response || "Your inquiry has been received. Our team will respond shortly.")
        : `Your request has been successfully submitted. Ticket ID: ${ticketId}. Our team will review and respond as soon as possible.`;
      resetForm();
      setSubmitted({ ticketId, isInquiry, replyText, wasAudio });
    } catch (err) {
      console.error("Ticket creation failed:", err);
      setErrors({ submit: `Submission failed: ${err.message}` });
    }
  };

  // ── Voice recording ─────────────────────────────────────────────────────
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      cancelRecordingRef.current = false;

      const preferredTypes = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
      const supportedType = typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported
        ? preferredTypes.find((t) => MediaRecorder.isTypeSupported(t))
        : null;

      const recorder = supportedType
        ? new MediaRecorder(stream, { mimeType: supportedType })
        : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => { chunksRef.current.push(e.data); };
      recorder.onstop = async () => {
        const wasCancelled = cancelRecordingRef.current;
        setIsRecording(false);
        cleanupStream();
        if (wasCancelled) { setIsTranscribing(false); setVoiceStage("idle"); return; }
        setIsTranscribing(true);
        try {
          const mimeType = recorder.mimeType || supportedType || "audio/webm";
          const blob = new Blob(chunksRef.current, { type: mimeType });
          const filename = mimeType.includes("mp4") ? "mic.mp4" : "mic.webm";
          const data = await transcribeAudio(blob, filename);
          setDraftTranscript(data?.transcript || "");
          setLatestAudioFeatures(data?.audio_features || null);
          setVoiceStage("review");
        } catch (err) {
          console.error("Transcription failed:", err);
          alert("Transcription failed. Please try again.");
          setVoiceStage("idle");
        } finally {
          setIsTranscribing(false);
        }
      };

      recorder.start();
      setIsRecording(true);
      setDraftTranscript("");
      setVoiceStage("recording");
    } catch (err) {
      console.error("Microphone access denied:", err);
      alert("Microphone access is required for voice input.");
    }
  };

  const cancelRecording = () => {
    if (!mediaRecorderRef.current) return;
    cancelRecordingRef.current = true;
    try {
      if (mediaRecorderRef.current.state !== "inactive") mediaRecorderRef.current.stop();
    } catch {
      setIsRecording(false); cleanupStream(); setVoiceStage("idle");
    }
  };

  const stopAndTranscribe = () => {
    if (!mediaRecorderRef.current) return;
    cancelRecordingRef.current = false;
    try {
      if (mediaRecorderRef.current.state !== "inactive") mediaRecorderRef.current.stop();
    } catch {
      setIsRecording(false); cleanupStream(); setVoiceStage("idle");
    }
  };

  const discardTranscript = () => { setDraftTranscript(""); setVoiceStage("idle"); };
  const insertTranscript = () => {
    const t = (draftTranscript || "").trim();
    if (!t) { setVoiceStage("idle"); return; }
    setMessage((prev) => (prev ? `${prev}\n${t}` : t));
    setDraftTranscript("");
    setVoiceStage("idle");
  };

  const handleCancel = () => {
    if (embedded) { if (typeof onCancel === "function") onCancel(); return; }
    window.history.back();
  };

  // ── Success screen ──────────────────────────────────────────────────────
  if (submitted) {
    const successContent = (
      <div className="custFormPage">
        {!embedded && (
          <PageHeader title="Submission Confirmed" subtitle="Your request has been received." />
        )}
        <div className="custSuccessCard">
          <div className="custSuccessIcon" aria-hidden="true">
            <svg width="52" height="52" viewBox="0 0 52 52" fill="none">
              <circle cx="26" cy="26" r="26" fill="#dcfce7"/>
              <path d="M15 26.5l8 8 14-16" stroke="#16a34a" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          {!submitted.isInquiry && (
            <div className="custSuccessTicketId">
              Ticket ID: <strong>{submitted.ticketId}</strong>
            </div>
          )}
          <p className="custSuccessText">{submitted.replyText}</p>
          <AudioReplyPlayer
            ticketId={submitted.ticketId}
            isInquiry={submitted.isInquiry}
            replyText={submitted.replyText}
          />
          <button type="button" className="primaryPillBtn" onClick={() => setSubmitted(null)}>
            Submit Another
          </button>
        </div>
      </div>
    );
    if (embedded) return successContent;
    return <Layout role="customer">{successContent}</Layout>;
  }

  // ── Form ────────────────────────────────────────────────────────────────
  const content = (
    <div className={`custFormPage ${embedded ? "custFormPage--embedded" : ""}`}>
      {!embedded && (
        <PageHeader
          title="Fill a Form"
          subtitle="Submit your request and our agents will respond promptly."
        />
      )}

      <form className="custFormCard" onSubmit={handleSubmitClick} noValidate>
        <div className="custFormGrid">

          {/* ── Input Method ───────────────────────────────────── */}
          <div className="custField custField--span2">
            <label className="custLabel">Input Method</label>
            <div className="custModeRow">
              <button
                type="button"
                className={`custModeBtn${mode === "Text" ? " custModeBtn--active" : ""}`}
                onClick={() => setMode("Text")}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
                  <path d="M4 7V4h16v3M9 20h6M12 4v16"/>
                </svg>
                Text
              </button>
              <button
                type="button"
                className={`custModeBtn${mode === "Audio" ? " custModeBtn--active" : ""}`}
                onClick={() => setMode("Audio")}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
                  <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z"/>
                  <path d="M19 11a7 7 0 0 1-14 0"/>
                  <path d="M12 18v3M8 21h8"/>
                </svg>
                Audio
              </button>
            </div>
          </div>

          {/* ── Description (required) ─────────────────────────── */}
          <div className="custField custField--span2">
            <label className="custLabel" htmlFor="cff-details">
              Description <span style={{ color: "#ef4444" }}>*</span>
            </label>

            {/* Voice input — shown when Audio mode selected */}
            {mode === "Audio" && (
              <div className="custVoiceWrap">
                {voiceStage === "idle" && (
                  <button
                    type="button"
                    className="custVoiceStart"
                    onClick={startRecording}
                    disabled={isTranscribing}
                    aria-label="Start recording"
                  >
                    <span className="custVoiceStartIcon" aria-hidden="true">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                        <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z" stroke="currentColor" strokeWidth="1.8"/>
                        <path d="M19 11a7 7 0 0 1-14 0" stroke="currentColor" strokeWidth="1.8"/>
                        <path d="M12 18v3M8 21h8" stroke="currentColor" strokeWidth="1.8"/>
                      </svg>
                    </span>
                    <span className="custVoiceStartText">Tap to record</span>
                  </button>
                )}

                {(voiceStage === "recording" || isTranscribing) && (
                  <div
                    className={`custVoiceBar${voiceStage === "recording" ? " custVoiceBar--recording" : ""}${isTranscribing ? " custVoiceBar--transcribing" : ""}`}
                    role="group"
                    aria-label="Voice recorder"
                  >
                    <div className="custWaves" aria-hidden="true">
                      <span className="custWave"/><span className="custWave"/><span className="custWave"/>
                      <span className="custWave"/><span className="custWave"/>
                    </div>
                    <div className="custVoiceBarText">{isTranscribing ? "Transcribing..." : "Listening..."}</div>
                    <div className="custVoiceActions">
                      <button type="button" className="custVoiceIconBtn custVoiceIconBtn--cancel" onClick={cancelRecording} disabled={isTranscribing || !isRecording} aria-label="Cancel">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M18 6 6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
                      </button>
                      <button type="button" className="custVoiceIconBtn custVoiceIconBtn--confirm" onClick={stopAndTranscribe} disabled={isTranscribing || !isRecording} aria-label="Stop and transcribe">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M20 6 9 17l-5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                      </button>
                    </div>
                  </div>
                )}

                {voiceStage === "review" && (
                  <div className="custVoiceReview">
                    <div className="custVoiceReviewTop">
                      <div className="custHint">Review & edit transcript, then confirm to insert.</div>
                      <div className="custVoiceActions">
                        <button type="button" className="custVoiceIconBtn custVoiceIconBtn--cancel" onClick={discardTranscript} aria-label="Discard transcript">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M18 6 6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
                        </button>
                        <button type="button" className="custVoiceIconBtn custVoiceIconBtn--confirm" onClick={insertTranscript} aria-label="Insert transcript">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M20 6 9 17l-5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                        </button>
                      </div>
                    </div>
                    <textarea
                      className="custVoiceDraft"
                      value={draftTranscript}
                      onChange={(e) => setDraftTranscript(e.target.value)}
                      rows={3}
                      placeholder="Transcript will appear here..."
                    />
                  </div>
                )}
              </div>
            )}

            <textarea
              id="cff-details"
              className="custTextarea"
              value={message}
              onChange={(e) => {
                setMessage(e.target.value);
                if (errors.message) setErrors((prev) => ({ ...prev, message: undefined }));
              }}
              placeholder="Describe what happened. Include time, location, or any relevant details."
              rows={embedded ? 6 : 8}
              style={errors.message ? { borderColor: "rgba(239,68,68,.5)", boxShadow: "0 0 0 3px rgba(239,68,68,.1)" } : {}}
            />
            {errors.message && (
              <div className="custFieldError" role="alert">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
                  <path d="M12 8v4M12 16h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                {errors.message}
              </div>
            )}

            {/* ── Attachments (optional) ─────────────────────── */}
            <div className="custAttachSection">
              <div className="custAttachHeader">
                <div>
                  <div className="custAttachLabel">
                    Attachments <span className="custLabelOptional">(optional)</span>
                  </div>
                  <div className="custAttachHint">Screenshots, PDFs, or other files to support your request.</div>
                </div>
                <button type="button" className="custAttachBtn" onClick={openFilePicker} aria-label="Attach files">
                  <span className="custAttachIcon" aria-hidden="true">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                      <path d="M21.44 11.05 12.95 19.54a6 6 0 0 1-8.49-8.49l9.19-9.19a4.5 4.5 0 0 1 6.36 6.36l-9.55 9.55a3 3 0 0 1-4.24-4.24l8.49-8.49" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </span>
                  Attach
                </button>
                <input ref={fileInputRef} type="file" className="custFileInput" multiple onChange={onFilesSelected} accept="image/*,application/pdf,.doc,.docx,.xls,.xlsx,.txt"/>
              </div>

              {attachments.length > 0 && (
                <div className="custFileChips" role="list" aria-label="Attached files">
                  {attachments.map((f) => (
                    <div key={`${f.name}-${f.size}-${f.lastModified}`} className="custFileChip" role="listitem" title={f.name}>
                      <span className="custFileName">{f.name}</span>
                      <span className="custFileMeta">{formatBytes(f.size)}</span>
                      <button type="button" className="custFileRemove" onClick={() => removeAttachment(f)} aria-label={`Remove ${f.name}`}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M18 6 6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Submit error */}
        {errors.submit && (
          <div className="custFieldError custFieldError--block" role="alert" style={{ marginTop: 8 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
              <path d="M12 8v4M12 16h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            {errors.submit}
          </div>
        )}

        <div className="custFormActions">
          <button type="button" className="softPillBtn" onClick={handleCancel}>Cancel</button>
          <button type="submit" className="primaryPillBtn" disabled={isTranscribing}>
            Submit Request
          </button>
        </div>
      </form>

      {/* ── Confirmation modal ─────────────────────────────────────────── */}
      {showConfirm && (
        <div className="custConfirmOverlay" onClick={() => setShowConfirm(false)} role="dialog" aria-modal="true" aria-label="Confirm submission">
          <div className="custConfirmModal" onClick={(e) => e.stopPropagation()}>
            <div className="custConfirmIconWrap" aria-hidden="true">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.8" opacity=".25"/>
                <path d="M12 8v4M12 16h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </div>
            <h3 className="custConfirmTitle">Submit your request?</h3>
            <p className="custConfirmBody">
              Once submitted, our agents will review and respond as soon as possible. This cannot be undone.
            </p>
            <div className="custConfirmActions">
              <button type="button" className="softPillBtn" onClick={() => setShowConfirm(false)}>
                Cancel
              </button>
              <button type="button" className="primaryPillBtn" onClick={doActualSubmit}>
                Yes, submit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  if (embedded) return content;
  return <Layout role="customer">{content}</Layout>;
}