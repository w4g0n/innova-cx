import { useState, useRef, useCallback, useEffect } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";
import { submitTextComplaint, transcribeAudio, getAudioReply } from "../../services/api";
import "./CustomerFillForm.css";

// ─── AudioReplyPlayer ──────────────────────────────────────────────────────────
//
// Fetches TTS audio from the backend after mount (non-blocking relative to the
// success screen appearing).  Falls back to browser SpeechSynthesis if the
// backend TTS service is unavailable (e.g. edge-tts not reachable on GCP).
//
function AudioReplyPlayer({ ticketId, isInquiry, replyText }) {
  // "loading" → "playing" → "ready"  (or "fallback" when using SpeechSynthesis)
  const [uiState, setUiState] = useState("loading");
  const audioUrlRef = useRef(null);   // object URL for the decoded MP3 blob
  const audioElemRef = useRef(null);  // current HTMLAudioElement

  // ── Stop any currently playing audio / speech ─────────────────────────────
  const stopAll = useCallback(() => {
    if (audioElemRef.current) {
      audioElemRef.current.pause();
      audioElemRef.current.onended = null;
      audioElemRef.current.onerror = null;
      audioElemRef.current = null;
    }
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  }, []);

  // ── Play a previously created blob URL ────────────────────────────────────
  const playBlobUrl = useCallback(
    (url) => {
      stopAll();
      const audio = new Audio(url);
      audioElemRef.current = audio;
      audio.onended = () => setUiState("ready");
      audio.onerror = () => setUiState("ready");
      // audio.play() returns a Promise; autoplay may be blocked by the browser
      // if the user gesture context has expired — handle silently.
      audio.play().catch(() => setUiState("ready"));
      setUiState("playing");
    },
    [stopAll],
  );

  // ── Browser SpeechSynthesis fallback ──────────────────────────────────────
  const playFallback = useCallback(
    (text) => {
      if (typeof window === "undefined" || !window.speechSynthesis) {
        setUiState("fallback");
        return;
      }
      stopAll();
      const utt = new SpeechSynthesisUtterance(text);
      utt.onend = () => setUiState("fallback");
      utt.onerror = () => setUiState("fallback");
      window.speechSynthesis.speak(utt);
      setUiState("playing");
    },
    [stopAll],
  );

  // ── Fetch TTS on mount, auto-play when ready ──────────────────────────────
  useEffect(() => {
    let cancelled = false;

    (async () => {
      const data = await getAudioReply({
        ticketId,
        messageType: isInquiry ? "inquiry_handled" : "ticket_logged",
        ticketType: "complaint",
      });

      if (cancelled) return;

      if (data?.audio_base64) {
        try {
          // Decode base64 → Uint8Array → Blob → object URL
          const binary = atob(data.audio_base64);
          const bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
          }
          const blob = new Blob([bytes], { type: data.mime_type || "audio/mpeg" });
          const url = URL.createObjectURL(blob);
          audioUrlRef.current = url;
          playBlobUrl(url);
        } catch {
          playFallback(replyText);
        }
      } else {
        // Backend TTS unavailable — use browser synthesis
        playFallback(replyText);
      }
    })();

    return () => {
      cancelled = true;
      stopAll();
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
    };
  }, [ticketId, isInquiry, replyText, playBlobUrl, playFallback, stopAll]);

  // ── Replay handler ────────────────────────────────────────────────────────
  const handleReplay = () => {
    if (uiState === "playing") return;
    if (audioUrlRef.current) {
      playBlobUrl(audioUrlRef.current);
    } else {
      playFallback(replyText);
    }
  };

  if (uiState === "loading") {
    return <div className="custAudioLoading">Preparing audio reply…</div>;
  }

  return (
    <button
      className="custAudioBtn"
      type="button"
      onClick={handleReplay}
      disabled={uiState === "playing"}
      aria-label="Replay audio confirmation"
    >
      {uiState === "playing" ? "Playing…" : "▶ Replay"}
    </button>
  );
}

// ─── Main component ────────────────────────────────────────────────────────────

export default function CustomerFillForm({ embedded = false, onCancel }) {
  const [type, setType] = useState("Auto");
  const [mode, setMode] = useState("Text");
  const [assetType, setAssetType] = useState("Office");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");

  const [attachments, setAttachments] = useState([]);
  const fileInputRef = useRef(null);

  const BYTES_PER_KB = 1024;
  const BYTES_PER_MB = BYTES_PER_KB * BYTES_PER_KB;

  const formatBytes = (bytes) => {
    if (typeof bytes !== "number" || Number.isNaN(bytes)) return "";
    if (bytes < BYTES_PER_KB) return `${bytes} B`;
    const kb = bytes / BYTES_PER_KB;
    if (kb < BYTES_PER_KB) return `${kb.toFixed(1)} KB`;
    const mb = bytes / BYTES_PER_MB;
    return `${mb.toFixed(1)} MB`;
  };

  const openFilePicker = () => {
    if (fileInputRef.current) fileInputRef.current.click();
  };

  const onFilesSelected = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    setAttachments((prev) => {
      const next = [...prev];
      for (const f of files) {
        const exists = next.some(
          (x) => x.name === f.name && x.size === f.size && x.lastModified === f.lastModified
        );
        if (!exists) next.push(f);
      }
      return next;
    });

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
  };

  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const cancelRecordingRef = useRef(false);

  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);

  const [voiceStage, setVoiceStage] = useState("idle");
  const [draftTranscript, setDraftTranscript] = useState("");
  const [latestAudioFeatures, setLatestAudioFeatures] = useState(null);

  // ── Success state: set after submission, triggers success screen ───────────
  // { ticketId, isInquiry, replyText }
  const [submitted, setSubmitted] = useState(null);

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
    setSubject("");
    setMessage("");
    setAssetType("Office");
    setType("Auto");
    setMode("Text");
    setAttachments([]);
    setIsRecording(false);
    setIsTranscribing(false);
    setVoiceStage("idle");
    setDraftTranscript("");
    setLatestAudioFeatures(null);
    cleanupStream();
  };

  // ── Submit ─────────────────────────────────────────────────────────────────
  const submit = async (e) => {
    e.preventDefault();
    const details = (message || "").trim();
    if (!details) {
      alert("Please provide ticket details before submitting.");
      return;
    }

    try {
      const orchestratorResult = await submitTextComplaint(details, {
        ticket_type: type === "Auto" ? null : type.toLowerCase(),
        asset_type: assetType,
        has_audio: mode === "Audio",
        audio_features: mode === "Audio" ? latestAudioFeatures : null,
      });

      const isInquiry = !orchestratorResult?.ticket_id;
      const ticketId = orchestratorResult?.ticket_id ?? null;

      // Build a readable fallback text (shown in card + used by SpeechSynthesis
      // if backend TTS is unavailable).
      const replyText = isInquiry
        ? (orchestratorResult?.chatbot_response || "Your inquiry has been received. Our team will respond shortly.")
        : `Your complaint has been successfully logged. Ticket ID: ${ticketId}. Our team will review your concern and respond as soon as possible.`;

      resetForm();

      // Show success screen — AudioReplyPlayer fetches and plays TTS
      // independently so the card appears immediately.
      setSubmitted({ ticketId, isInquiry, replyText });
    } catch (err) {
      console.error("Ticket creation failed:", err);
      alert(`Error creating ticket: ${err.message}`);
    }
  };

  // ── Recording helpers ──────────────────────────────────────────────────────
  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;

    chunksRef.current = [];
    cancelRecordingRef.current = false;

    const preferredTypes = ["audio/webm;codecs=opus","audio/webm","audio/mp4"];
    const supportedType = typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported
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
        const mimeType = recorder.mimeType || supportedType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: mimeType });
        const filename = mimeType.includes("mp4") ? "mic.mp4" : "mic.webm";
        const data = await transcribeAudio(blob, filename);
        setDraftTranscript(data?.transcript || "");
        setLatestAudioFeatures(data?.audio_features || null);
        setVoiceStage("review");
      } catch (err) {
        console.error("Transcription failed:", err);
        alert("Transcription failed (demo). Please try again.");
        setVoiceStage("idle");
      } finally {
        setIsTranscribing(false);
      }
    };

    recorder.start();
    setIsRecording(true);
    setDraftTranscript("");
    setVoiceStage("recording");
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
    setVoiceStage("idle");
  };

  const insertTranscript = () => {
    const t = (draftTranscript || "").trim();
    if (!t) {
      setVoiceStage("idle");
      return;
    }
    setMessage((prev) => (prev ? `${prev}\n${t}` : t));
    setDraftTranscript("");
    setVoiceStage("idle");
  };

  const handleCancel = () => {
    if (embedded) {
      if (typeof onCancel === "function") onCancel();
      return;
    }
    window.history.back();
  };

  // ── Success screen ─────────────────────────────────────────────────────────
  if (submitted) {
    const successContent = (
      <div className="custFormPage">
        <PageHeader
          title="Submission Confirmed"
          subtitle="Your request has been received."
        />
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
              Ticket ID: <strong>{submitted.ticketId}</strong>
            </div>
          )}

          <p className="custSuccessText">{submitted.replyText}</p>

          <AudioReplyPlayer
            ticketId={submitted.ticketId}
            isInquiry={submitted.isInquiry}
            replyText={submitted.replyText}
          />

          <button
            type="button"
            className="primaryPillBtn"
            onClick={() => setSubmitted(null)}
          >
            Submit Another
          </button>
        </div>
      </div>
    );

    if (embedded) return successContent;
    return <Layout role="customer">{successContent}</Layout>;
  }

  // ── Normal form ────────────────────────────────────────────────────────────
  const content = (
    <div className={`custFormPage ${embedded ? "custFormPage--embedded" : ""}`}>
      <PageHeader
        title="Fill a Form"
        subtitle="Submit a complaint or inquiry using text or audio."
      />

      <form className="custFormCard" onSubmit={submit}>
        <div className="custFormGrid">
          <div className="custField custField--span2">
            <div className="custTwoPillsRow">
              <div className="custTwoPillsItem">
                <label className="custLabel">Ticket Type (optional)</label>
                <div className="custPillHolder">
                  <PillSelect
                    value={type}
                    onChange={setType}
                    ariaLabel="Select request type"
                    options={[
                      { value: "Auto", label: "Auto" },
                      { value: "Complaint", label: "Complaint" },
                      { value: "Inquiry", label: "Inquiry" },
                    ]}
                  />
                </div>
              </div>

              <div className="custTwoPillsItem">
                <label className="custLabel">Asset</label>
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
            </div>
          </div>

          <div className="custField custField--span2">
            <label className="custLabel">Subject (optional)</label>
            <input
              className="custInput"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Optional short summary (e.g., Access card not working)"
            />
          </div>

          <div className="custField custField--span2">
            <label className="custLabel">Input Method</label>
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
                    </span>
                    <span className="custVoiceStartText">Tap to record</span>
                  </button>
                )}

                {(voiceStage === "recording" || isTranscribing) && (
                  <div
                    className={`custVoiceBar ${voiceStage === "recording" ? "custVoiceBar--recording" : ""} ${
                      isTranscribing ? "custVoiceBar--transcribing" : ""
                    }`}
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
                      {isTranscribing ? "Transcribing…" : "Listening…"}
                    </div>

                    <div className="custVoiceActions">
                      <button
                        type="button"
                        className="custVoiceIconBtn custVoiceIconBtn--cancel"
                        onClick={cancelRecording}
                        disabled={isTranscribing || !isRecording}
                        aria-label="Cancel recording"
                      >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
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
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
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
                      <div className="custHint">Review & edit transcript, then ✓ to insert.</div>
                      <div className="custVoiceActions">
                        <button
                          type="button"
                          className="custVoiceIconBtn custVoiceIconBtn--cancel"
                          onClick={discardTranscript}
                          aria-label="Discard transcript"
                        >
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
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
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
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
                      className="custVoiceDraft"
                      value={draftTranscript}
                      onChange={(e) => setDraftTranscript(e.target.value)}
                      rows={3}
                      placeholder="Transcript will appear here…"
                    />
                  </div>
                )}
              </div>
            )}

            <textarea
              className="custTextarea"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Describe what happened. Include time/location if possible."
              rows={7}
              required
            />


            <div className="custAttachSection">
              <div className="custAttachHeader">
                <div>
                  <div className="custAttachLabel">Attachments (optional)</div>
                  <div className="custAttachHint">
                    Add screenshots, PDFs, or other files to help explain your issue.
                  </div>
                </div>

                <button
                  type="button"
                  className="custAttachBtn"
                  onClick={openFilePicker}
                  aria-label="Attach files"
                >
                  <span className="custAttachIcon" aria-hidden="true">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
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
                  type="file"
                  className="custFileInput"
                  multiple
                  onChange={onFilesSelected}
                  accept="image/*,application/pdf,.doc,.docx,.xls,.xlsx,.txt"
                />
              </div>

              {attachments.length > 0 && (
                <div className="custFileChips" role="list" aria-label="Attached files">
                  {attachments.map((f) => (
                    <div
                      key={`${f.name}-${f.size}-${f.lastModified}`}
                      className="custFileChip"
                      role="listitem"
                      title={f.name}
                    >
                      <span className="custFileName">{f.name}</span>
                      <span className="custFileMeta">{formatBytes(f.size)}</span>
                      <button
                        type="button"
                        className="custFileRemove"
                        onClick={() => removeAttachment(f)}
                        aria-label={`Remove ${f.name}`}
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
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
