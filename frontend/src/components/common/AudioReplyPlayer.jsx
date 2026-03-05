import { useCallback, useEffect, useRef, useState } from "react";
import { getAudioReply } from "../../services/api";

/**
 * AudioReplyPlayer — fetches TTS audio from the backend on mount and
 * auto-plays it. Falls back to browser SpeechSynthesis when the backend
 * TTS service is unavailable (edge-tts not installed / returns 503).
 *
 * Props:
 *   ticketId   - ticket code (e.g. "CX-12345") or null
 *   isInquiry  - true for inquiry, false for complaint
 *   replyText  - text to speak (used for SpeechSynthesis fallback)
 */
export default function AudioReplyPlayer({ ticketId, isInquiry, replyText }) {
  const [uiState, setUiState] = useState("loading");
  const audioUrlRef = useRef(null);
  const audioElemRef = useRef(null);

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

  const playBlobUrl = useCallback(
    (url) => {
      stopAll();
      const audio = new Audio(url);
      audioElemRef.current = audio;
      audio.onended = () => setUiState("ready");
      audio.onerror = () => setUiState("ready");
      audio.play().catch(() => setUiState("ready"));
      setUiState("playing");
    },
    [stopAll],
  );

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
          const binary = atob(data.audio_base64);
          const bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
          }
          const blob = new Blob([bytes], {
            type: data.mime_type || "audio/mpeg",
          });
          const url = URL.createObjectURL(blob);
          audioUrlRef.current = url;
          playBlobUrl(url);
        } catch {
          playFallback(replyText);
        }
      } else {
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

  const handleReplay = () => {
    if (uiState === "playing") return;
    if (audioUrlRef.current) {
      playBlobUrl(audioUrlRef.current);
    } else {
      playFallback(replyText);
    }
  };

  if (uiState === "loading") {
    return (
      <div style={{ fontSize: 13, color: "#9ca3af", padding: "6px 0" }}>
        Preparing audio reply...
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={handleReplay}
      disabled={uiState === "playing"}
      aria-label="Replay audio confirmation"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        padding: "9px 22px",
        borderRadius: 999,
        border: "1.5px solid #6366f1",
        background: "transparent",
        color: "#6366f1",
        fontSize: 14,
        fontWeight: 500,
        cursor: uiState === "playing" ? "not-allowed" : "pointer",
        opacity: uiState === "playing" ? 0.55 : 1,
        transition: "background 0.15s, color 0.15s",
        fontFamily: "inherit",
      }}
    >
      {uiState === "playing" ? "Playing..." : "\u25B6 Replay"}
    </button>
  );
}
