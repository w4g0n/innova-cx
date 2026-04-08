import { useState, useRef } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import AudioReplyPlayer from "../../components/common/AudioReplyPlayer";
import { submitCustomerTicket, transcribeAudio, uploadCustomerAttachments } from "../../services/api";
import {
  sanitizeText,
  sanitizeFilename,
  sanitizeId,
  sanitizeTicketType,
  countWords,
  limitWords,
  sanitizeTextByWords,
  MAX_DESCRIPTION_LEN,
  MAX_TEXT_WORDS,
} from "./sanitize";
import "./CustomerFillForm.css";

// File upload constraints
const MAX_ATTACHMENT_COUNT  = 10;
const MAX_ATTACHMENT_BYTES  = 10 * 1024 * 1024; // 10 MB per file
const ALLOWED_MIME_PREFIXES = ["image/", "application/pdf"];
const ALLOWED_EXTENSIONS    = [".doc", ".docx", ".xls", ".xlsx", ".txt"];

function isAllowedFile(file) {
  const name = (file.name || "").toLowerCase();
  const ext  = name.substring(name.lastIndexOf("."));
  return (
    ALLOWED_MIME_PREFIXES.some((p) => (file.type || "").startsWith(p)) ||
    ALLOWED_EXTENSIONS.includes(ext)
  );
}

export default function CustomerFillForm({ embedded = false, onCancel, onSubmitted, initialType }) {
  // Sanitize and validate the initialType prop against an allowlist
  const safeInitialType = sanitizeTicketType(initialType);

  const [mode, setMode] = useState("Text");
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState([]);
  const fileInputRef = useRef(null);

  // Voice recording state
  const mediaRecorderRef    = useRef(null);
  const streamRef           = useRef(null);
  const chunksRef           = useRef([]);
  const cancelRecordingRef  = useRef(false);

  const [isRecording,    setIsRecording]    = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceStage,     setVoiceStage]     = useState("idle");
  const [draftTranscript,    setDraftTranscript]    = useState("");
  const [draftAudioFeatures, setDraftAudioFeatures] = useState(null);

  // Validation + submission state
  const [errors,      setErrors]      = useState({});
  const [submitted,   setSubmitted]   = useState(null);
  const [showConfirm, setShowConfirm] = useState(false);

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

    const fileErrors = [];
    setAttachments((prev) => {
      const next = [...prev];
      for (const f of files) {
        // Enforce attachment count cap
        if (next.length >= MAX_ATTACHMENT_COUNT) {
          fileErrors.push(`Maximum ${MAX_ATTACHMENT_COUNT} attachments allowed.`);
          break;
        }
        // Enforce per-file size cap
        if (f.size > MAX_ATTACHMENT_BYTES) {
          fileErrors.push(`"${sanitizeFilename(f.name, 40)}" exceeds the 10 MB limit.`);
          continue;
        }
        // Enforce MIME / extension allowlist
        if (!isAllowedFile(f)) {
          fileErrors.push(`"${sanitizeFilename(f.name, 40)}" is not an allowed file type.`);
          continue;
        }
        // Deduplicate by name + size + lastModified
        const exists = next.some(
          (x) =>
            x.name === f.name &&
            x.size === f.size &&
            x.lastModified === f.lastModified
        );
        if (!exists) next.push(f);
      }
      return next;
    });

    if (fileErrors.length) {
      setErrors((prev) => ({ ...prev, files: fileErrors[0] }));
    }

    e.target.value = "";
  };

  const removeAttachment = (fileToRemove) => {
    setAttachments((prev) =>
      prev.filter(
        (f) =>
          !(
            f.name === fileToRemove.name &&
            f.size === fileToRemove.size &&
            f.lastModified === fileToRemove.lastModified
          )
      )
    );
    setErrors((prev) => ({ ...prev, files: undefined }));
  };

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
    setDraftAudioFeatures(null);
    setErrors({});
    cleanupStream();
  };

  const validate = () => {
    const newErrors = {};
    const details = (message || "").trim();

    if (!details) {
      newErrors.message = "Please describe your issue before submitting.";
    } else if (details.length < 10) {
      newErrors.message = "Please provide more detail (at least 10 characters).";
    } else if (countWords(details) > MAX_TEXT_WORDS) {
      newErrors.message = `Description must be ${MAX_TEXT_WORDS.toLocaleString()} words or fewer.`;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmitClick = (e) => {
    e.preventDefault();
    if (!validate()) return;
    setShowConfirm(true);
  };

  const doActualSubmit = async () => {
    setShowConfirm(false);

    // Final sanitize before sending — trim + hard cap
    const details  = sanitizeTextByWords(message);
    const wasAudio = mode === "Audio";

    try {
      const result = await submitCustomerTicket({
        type:           safeInitialType,
        details,
        subject:        "",
        asset_type:     "General",
        has_audio:      wasAudio,
        audio_features: wasAudio ? draftAudioFeatures : null,
        // Sanitize file metadata before sending — never send raw File objects
        attachments: attachments.map((f) => ({
          name:         sanitizeFilename(f.name, 255),
          type:         sanitizeText(f.type || "", 100) || null,
          size:         typeof f.size === "number" ? f.size : null,
          lastModified: typeof f.lastModified === "number" ? f.lastModified : null,
        })),
      });

      const ticketId  = result?.ticket?.ticketId
        ? sanitizeId(String(result.ticket.ticketId), 48)
        : null;

      // Upload actual file bytes now that we have the ticket code.
      // Non-fatal: a failed upload won't block the success screen.
      if (ticketId && attachments.length > 0) {
        try {
          await uploadCustomerAttachments(ticketId, attachments);
        } catch (uploadErr) {
          console.warn("Attachment upload failed:", uploadErr);
        }
      }

      const replyText = `Your request has been successfully submitted. Ticket ID: ${ticketId ?? "N/A"}. Our team will review and respond as soon as possible.`;

      resetForm();
      setSubmitted({ ticketId, isInquiry: false, replyText, wasAudio });

      if (typeof onSubmitted === "function") {
        onSubmitted(result?.ticket || null);
      }
    } catch (err) {
      console.error("Ticket creation failed:", err);
      setErrors({
        submit: "We could not submit your request right now. Please try again in a moment.",
      });
    }
  };

  const [voiceError, setVoiceError] = useState("");

  const startRecording = async () => {
    setVoiceError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      cancelRecordingRef.current = false;

      const preferredTypes = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
      const supportedType =
        typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported
          ? preferredTypes.find((t) => MediaRecorder.isTypeSupported(t))
          : null;

      const recorder = supportedType
        ? new MediaRecorder(stream, { mimeType: supportedType })
        : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        const wasCancelled = cancelRecordingRef.current;
        setIsRecording(false);
        cleanupStream();
        if (wasCancelled) {
          setIsTranscribing(false);
          setVoiceStage("idle");
          return;
        }
        setIsTranscribing(true);
        try {
          const mimeType  = recorder.mimeType || supportedType || "audio/webm";
          const blob      = new Blob(chunksRef.current, { type: mimeType });
          const filename  = mimeType.includes("mp4") ? "mic.mp4" : "mic.webm";
          const data      = await transcribeAudio(blob, filename);

          // Sanitize transcript text returned by the transcription service
          const transcript = sanitizeTextByWords(data?.transcript || "");
          setDraftTranscript(transcript);
          setDraftAudioFeatures(data?.audio_features || null);
          setVoiceStage("review");
        } catch (err) {
          console.error("Transcription failed:", err);
          // State-based error replaces alert() — keeps error messaging inside the UI
          setVoiceError("Transcription failed. Please try again.");
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
      // State-based error replaces alert()
      setVoiceError("Microphone access is required for voice input. Please allow it in your browser settings.");
    }
  };

  const cancelRecording = () => {
    if (!mediaRecorderRef.current) return;
    cancelRecordingRef.current = true;
    try {
      if (mediaRecorderRef.current.state !== "inactive") mediaRecorderRef.current.stop();
    } catch {
      setIsRecording(false);
      cleanupStream();
      setVoiceStage("idle");
    }
  };

  const stopAndTranscribe = () => {
    if (!mediaRecorderRef.current) return;
    cancelRecordingRef.current = false;
    try {
      if (mediaRecorderRef.current.state !== "inactive") mediaRecorderRef.current.stop();
    } catch {
      setIsRecording(false);
      cleanupStream();
      setVoiceStage("idle");
    }
  };

  const discardTranscript = () => {
    setDraftTranscript("");
    setDraftAudioFeatures(null);
    setVoiceStage("idle");
    setVoiceError("");
  };

  const insertTranscript = () => {
    const t = (draftTranscript || "").trim();
    if (!t) {
      setDraftAudioFeatures(null);
      setVoiceStage("idle");
      return;
    }
    setMessage((prev) => {
      const combined = prev ? `${prev}\n${t}` : t;
      // Enforce the max word cap when appending a transcript.
      return limitWords(combined, MAX_TEXT_WORDS);
    });
    setDraftTranscript("");
    setVoiceStage("idle");
    setVoiceError("");
  };

  const handleCancel = () => {
    if (embedded) {
      if (typeof onCancel === "function") onCancel();
      return;
    }
    window.history.back();
  };

  if (submitted) {
    const successContent = (
      <div className="custFormPage">
        {!embedded && (
          <PageHeader title="Submission Confirmed" subtitle="Your request has been received." />
        )}
        <div className="custSuccessCard">
          <div className="custSuccessIcon" aria-hidden="true">
            <svg width="52" height="52" viewBox="0 0 52 52" fill="none">
              <circle cx="26" cy="26" r="26" fill="#dcfce7" />
              <path
                d="M15 26.5l8 8 14-16"
                stroke="#16a34a"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          {!submitted.isInquiry && (
            <div className="custSuccessTicketId">
              {/* ticketId is sanitizeId'd before being placed in submitted state */}
              Ticket ID: <strong>{submitted.ticketId ?? "N/A"}</strong>
            </div>
          )}
          <p className="custSuccessText">{submitted.replyText}</p>
          {submitted.wasAudio && (
            <AudioReplyPlayer
              ticketId={submitted.ticketId}
              isInquiry={submitted.isInquiry}
              replyText={submitted.replyText}
            />
          )}
          <button type="button" className="primaryPillBtn" onClick={() => setSubmitted(null)}>
            Submit Another
          </button>
        </div>
      </div>
    );
    if (embedded) return successContent;
    return <Layout role="customer">{successContent}</Layout>;
  }

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

          <div className="custField custField--span2">
            <label className="custLabel">Input Method</label>
            <div className="custModeRow">
              <button
                type="button"
                className={`custModeBtn${mode === "Text" ? " custModeBtn--active" : ""}`}
                onClick={() => setMode("Text")}
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ marginRight: 6 }}
                >
                  <path d="M4 7V4h16v3M9 20h6M12 4v16" />
                </svg>
                Text
              </button>
              <button
                type="button"
                className={`custModeBtn${mode === "Audio" ? " custModeBtn--active" : ""}`}
                onClick={() => setMode("Audio")}
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ marginRight: 6 }}
                >
                  <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z" />
                  <path d="M19 11a7 7 0 0 1-14 0" />
                  <path d="M12 18v3M8 21h8" />
                </svg>
                Audio
              </button>
            </div>
          </div>

          <div className="custField custField--span2">
            <label className="custLabel" htmlFor="cff-details">
              Description <span style={{ color: "#ef4444" }}>*</span>
            </label>

            {/* Voice error display — replaces alert() */}
            {voiceError && (
              <div className="custFieldError" role="alert" style={{ marginBottom: 8 }}>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  style={{ flexShrink: 0 }}
                >
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
                  <path
                    d="M12 8v4M12 16h.01"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
                {/* voiceError is set from a fixed internal string, never raw API content */}
                {voiceError}
              </div>
            )}

            {/* Voice input */}
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
                        <path
                          d="M12 18v3M8 21h8"
                          stroke="currentColor"
                          strokeWidth="1.8"
                        />
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
                      <span className="custWave" />
                      <span className="custWave" />
                      <span className="custWave" />
                      <span className="custWave" />
                      <span className="custWave" />
                    </div>
                    <div className="custVoiceBarText">
                      {isTranscribing ? "Transcribing..." : "Listening..."}
                    </div>
                    <div className="custVoiceActions">
                      <button
                        type="button"
                        className="custVoiceIconBtn custVoiceIconBtn--cancel"
                        onClick={cancelRecording}
                        disabled={isTranscribing || !isRecording}
                        aria-label="Cancel"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                          <path
                            d="M18 6 6 18M6 6l12 12"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                          />
                        </svg>
                      </button>
                      <button
                        type="button"
                        className="custVoiceIconBtn custVoiceIconBtn--confirm"
                        onClick={stopAndTranscribe}
                        disabled={isTranscribing || !isRecording}
                        aria-label="Stop and transcribe"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                          <path
                            d="M20 6 9 17l-5-5"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </button>
                    </div>
                  </div>
                )}

                {voiceStage === "review" && (
                  <div className="custVoiceReview">
                    <div className="custVoiceReviewTop">
                      <div className="custHint">
                        Review &amp; edit transcript, then confirm to insert.
                      </div>
                      <div className="custVoiceActions">
                        <button
                          type="button"
                          className="custVoiceIconBtn custVoiceIconBtn--cancel"
                          onClick={discardTranscript}
                          aria-label="Discard transcript"
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                            <path
                              d="M18 6 6 18M6 6l12 12"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                            />
                          </svg>
                        </button>
                        <button
                          type="button"
                          className="custVoiceIconBtn custVoiceIconBtn--confirm"
                          onClick={insertTranscript}
                          aria-label="Insert transcript"
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                            <path
                              d="M20 6 9 17l-5-5"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            />
                          </svg>
                        </button>
                      </div>
                    </div>
                    <textarea
                      id="cff-voice-draft"
                      name="voiceDraft"
                      className="custVoiceDraft"
                      value={draftTranscript}
                      onChange={(e) => {
                        // Cap transcript edits at the same description limit.
                        const v = e.target.value;
                        setDraftTranscript(limitWords(v, MAX_TEXT_WORDS));
                      }}
                      rows={3}
                      placeholder="Transcript will appear here..."
                    />
                  </div>
                )}
              </div>
            )}

            <textarea
              id="cff-details"
              name="details"
              className="custTextarea"
              value={message}
              onChange={(e) => {
                const v = e.target.value;
                // Enforce hard cap client-side — server also validates but this prevents
                // oversized payloads from being sent at all
                setMessage(limitWords(v, MAX_TEXT_WORDS));
                if (errors.message) setErrors((prev) => ({ ...prev, message: undefined }));
              }}
              placeholder="Describe what happened. Include time, location, or any relevant details."
              rows={embedded ? 6 : 8}
              style={
                errors.message
                  ? { borderColor: "rgba(239,68,68,.5)", boxShadow: "0 0 0 3px rgba(239,68,68,.1)" }
                  : {}
              }
            />

            {/* Word counter */}
            <div style={{ textAlign: "right", fontSize: "0.75rem", color: "var(--color-text-tertiary, #888)", marginTop: 2 }}>
              {countWords(message)} / {MAX_TEXT_WORDS.toLocaleString()} words
            </div>

            {errors.message && (
              <div className="custFieldError" role="alert">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
                  <path
                    d="M12 8v4M12 16h.01"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
                {errors.message}
              </div>
            )}

            <div className="custAttachSection">
              <div className="custAttachHeader">
                <div>
                  <div className="custAttachLabel">
                    Attachments <span className="custLabelOptional">(optional)</span>
                  </div>
                  <div className="custAttachHint">
                    Screenshots, PDFs, or other files to support your request.
                  </div>
                </div>
                <button
                  type="button"
                  className="custAttachBtn"
                  onClick={openFilePicker}
                  aria-label="Attach files"
                >
                  <span className="custAttachIcon" aria-hidden="true">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M21.44 11.05 12.95 19.54a6 6 0 0 1-8.49-8.49l9.19-9.19a4.5 4.5 0 0 1 6.36 6.36l-9.55 9.55a3 3 0 0 1-4.24-4.24l8.49-8.49"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </span>
                  Attach
                </button>
                <input
                  ref={fileInputRef}
                  id="cff-attachments"
                  name="attachments"
                  type="file"
                  className="custFileInput"
                  multiple
                  onChange={onFilesSelected}
                  accept="image/*,application/pdf,.doc,.docx,.xls,.xlsx,.txt"
                />
              </div>

              {errors.files && (
                <div className="custFieldError" role="alert" style={{ marginTop: 6 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
                    <path
                      d="M12 8v4M12 16h.01"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />
                  </svg>
                  {/* errors.files is set from a fixed internal template, never raw file data */}
                  {errors.files}
                </div>
              )}

              {attachments.length > 0 && (
                <div className="custFileChips" role="list" aria-label="Attached files">
                  {attachments.map((f) => (
                    <div
                      key={`${f.name}-${f.size}-${f.lastModified}`}
                      className="custFileChip"
                      role="listitem"
                      // title uses sanitized filename — no raw f.name
                      title={sanitizeFilename(f.name, 80)}
                    >
                      <span className="custFileName">
                        {/* Sanitize filename before rendering — prevents overlong/malformed names */}
                        {sanitizeFilename(f.name, 60)}
                      </span>
                      <span className="custFileMeta">{formatBytes(f.size)}</span>
                      <button
                        type="button"
                        className="custFileRemove"
                        onClick={() => removeAttachment(f)}
                        aria-label={`Remove ${sanitizeFilename(f.name, 40)}`}
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                          <path
                            d="M18 6 6 18M6 6l12 12"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                          />
                        </svg>
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
          <div
            className="custFieldError custFieldError--block"
            role="alert"
            style={{ marginTop: 8 }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
              <path
                d="M12 8v4M12 16h.01"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
            {errors.submit}
          </div>
        )}

        <div className="custFormActions">
          <button type="button" className="softPillBtn" onClick={handleCancel}>
            Cancel
          </button>
          <button type="submit" className="primaryPillBtn" disabled={isTranscribing}>
            Submit Request
          </button>
        </div>
      </form>

      {showConfirm && (
        <div
          className="custConfirmOverlay"
          onClick={() => setShowConfirm(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Confirm submission"
        >
          <div
            className="custConfirmModal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="custConfirmIconWrap" aria-hidden="true">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
                <circle
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  opacity=".25"
                />
                <path
                  d="M12 8v4M12 16h.01"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </div>
            <h3 className="custConfirmTitle">Submit your request?</h3>
            <p className="custConfirmBody">
              Once submitted, our agents will review and respond as soon as possible.
              This cannot be undone.
            </p>
            <div className="custConfirmActions">
              <button
                type="button"
                className="softPillBtn"
                onClick={() => setShowConfirm(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="primaryPillBtn"
                onClick={doActualSubmit}
              >
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
