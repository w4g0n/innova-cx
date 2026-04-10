/**
 * API Service Layer
 *
 * Centralizes all backend API calls for the InnovaCX application.
 */
import { API_BASE_URL, apiUrl } from "../config/apiBase";

function inferServiceBase(port, fallbackLocalhost) {
  if (typeof window !== "undefined" && window.location?.hostname) {
    const protocol = window.location.protocol === "https:" ? "https" : "http";
    return `${protocol}://${window.location.hostname}:${port}`;
  }
  return fallbackLocalhost;
}

const API_CONFIG = {
  backend: API_BASE_URL,
  sentiment:
    import.meta.env.VITE_SENTIMENT_BASE_URL ||
    import.meta.env.VITE_SENTIMENT_URL ||
    inferServiceBase(8002, "http://localhost:8002"),
  orchestrator:
    import.meta.env.VITE_ORCHESTRATOR_URL ||
    inferServiceBase(8004, "http://localhost:8004"),
};

let _csrfToken = null;

export async function getCsrfToken() {
  if (_csrfToken) return _csrfToken;
  try {
    const res = await fetch(apiUrl("/api/csrf-token"));
    if (res.ok) {
      const data = await res.json();
      _csrfToken = data.csrf_token;
    }
  } catch {
    // silently fail — server will reject the form with 403 if token is missing
  }
  return _csrfToken;
}

/**
 * Transcribe audio file using Whisper service
 * @param {Blob} audioBlob - Audio blob to transcribe
 * @param {string} filename - Filename for the audio
 * @returns {Promise<{transcript: string}>}
 */
export async function transcribeAudio(audioBlob, filename = "recording.mp4") {
  const formData = new FormData();
  formData.append("audio", audioBlob, filename);

  const response = await fetch(`${API_CONFIG.backend}/api/transcriber/transcribe`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Transcription failed");
  }

  return response.json();
}

/**
 * Analyze text sentiment using RoBERTa model
 * @param {string} text - Text to analyze
 * @returns {Promise<{text_sentiment: number, text_urgency: number, keywords: string[], category: string, mock_mode: boolean}>}
 */
export async function analyzeSentiment(text) {
  const response = await fetch(`${API_CONFIG.sentiment}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    throw new Error("Sentiment analysis failed");
  }

  return response.json();
}

/**
 * Analyze combined text + audio sentiment
 * @param {string} text - Text to analyze
 * @param {object|null} audioFeatures - Optional audio features from Whisper
 * @returns {Promise<object>}
 */
export async function analyzeCombinedSentiment(text, audioFeatures = null) {
  const response = await fetch(`${API_CONFIG.sentiment}/analyze-combined`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, audio_features: audioFeatures }),
  });

  if (!response.ok) {
    throw new Error("Combined sentiment analysis failed");
  }

  return response.json();
}

/**
 * Full audio pipeline: transcribe + analyze sentiment
 * @param {Blob} audioBlob - Audio blob to process
 * @returns {Promise<{transcript: string, sentiment: object}>}
 */
export async function processAudioComplaint(audioBlob) {
  const transcription = await transcribeAudio(audioBlob);

  const sentiment = await analyzeCombinedSentiment(
    transcription.transcript,
    transcription.audio_features || null
  );

  return {
    transcript: transcription.transcript,
    sentiment: sentiment,
    audioFeatures: transcription.audio_features,
  };
}

/**
 * Send message to chatbot
 * @param {string} message - User message
 * @param {{userId: string, sessionId?: string|null}} options
 * @returns {Promise<{session_id: string, response: string, response_type: string, show_buttons: string[], reply: string}>}
 */
export async function sendChatMessage(message, options = {}) {
  const { userId, sessionId = null } = options;
  if (!userId) {
    throw new Error("sendChatMessage requires options.userId");
  }

  const csrf = await getCsrfToken();
  const response = await fetch(apiUrl("/api/chatbot/chat"), {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
    body: JSON.stringify({ message, user_id: userId, session_id: sessionId }),
  });

  if (!response.ok) {
    throw new Error("Chatbot request failed");
  }

  return response.json();
}

/**
 * Check sentiment service health
 * @returns {Promise<{status: string, mock_mode: boolean}>}
 */
export async function checkSentimentHealth() {
  const response = await fetch(`${API_CONFIG.sentiment}/health`);
  return response.json();
}

/**
 * Submit a text complaint or inquiry via the orchestrator.
 * The orchestrator classifies, analyzes sentiment, scores priority,
 * and either creates a ticket (complaint) or returns a chatbot reply (inquiry).
 *
 * @param {string} text - The complaint or inquiry text
 * @returns {Promise<{type: string, ticket_id?: string|null, chatbot_response?: string, priority?: number, department?: string, sentiment?: number, classification_confidence?: number}>}
 */
export async function submitTextComplaint(text, options = {}) {
  const body = new URLSearchParams({ text });
  if (options.ticket_type) {
    body.set("ticket_type", options.ticket_type);
  }
  if (typeof options.has_audio === "boolean") {
    body.set("has_audio", String(options.has_audio));
  }
  if (options.audio_features) {
    body.set("audio_features", JSON.stringify(options.audio_features));
  }
  const response = await fetch(apiUrl("/api/orchestrator/process/text"), {
    method: "POST",
    credentials: "include",
    body,
  });

  if (!response.ok) {
    try {
      await response.json();
    } catch {
      // ignore parse failures; user-facing error remains generic
    }
    throw new Error(
      "We could not submit your request right now. Please try again in a moment."
    );
  }

  return response.json();
}

/**
 * Submit a customer ticket through backend ticket creation gate.
 * Flow: frontend -> backend (/api/customer/tickets) -> ticket gate insert -> orchestrator dispatch.
 *
 * @param {{
 *   type?: string,
 *   details: string,
 *   subject?: string,
 *   asset_type?: string,
 *   has_audio?: boolean,
 *   audio_features?: object|null,
 *   attachments?: Array<{name: string, type?: string, size?: number, lastModified?: number}>
 * }} payload
 * @returns {Promise<{ok: boolean, message?: string, ticket?: {ticketId?: string}}>}
 */
export async function submitCustomerTicket(payload = {}) {
  const rawUser = localStorage.getItem("user");
  let user = {};
  try {
    user = rawUser ? JSON.parse(rawUser) : {};
  } catch {
    user = {};
  }

  const details = String(payload.details || "").trim();
  const body = {
    name: String(user.full_name || user.name || "Customer"),
    email: String(user.email || ""),
    type: String(payload.type || "complaint"),
    asset_type: String(payload.asset_type || "General"),
    subject: String(payload.subject ?? ""),
    details,
    has_audio: Boolean(payload.has_audio),
    audio_features: payload.audio_features || null,
    attachments: Array.isArray(payload.attachments) ? payload.attachments : [],
  };

  const csrf = await getCsrfToken();
  const response = await fetch(apiUrl("/api/customer/tickets"), {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(
      "We could not submit your request right now. Please try again in a moment."
    );
  }

  return response.json();
}

/**
 * Upload attachment files for a customer ticket after it has been created.
 * @param {string} ticketCode
 * @param {File[]} files
 */
export async function uploadCustomerAttachments(ticketCode, files) {
  if (!files || files.length === 0) return;
  for (const file of files) {
    const fd = new FormData();
    fd.append("file", file);
    const csrf = await getCsrfToken();
    const res = await fetch(
      apiUrl(`/api/customer/tickets/${encodeURIComponent(ticketCode)}/attachments`),
      {
        method: "POST",
        credentials: "include",
        headers: {
          ...(csrf ? { "X-CSRF-Token": csrf } : {}),
        },
        body: fd,
      }
    );
    if (!res.ok) throw new Error(`Attachment upload failed (${res.status})`);
  }
}

/**
 * Submit an audio complaint via the orchestrator.
 * The orchestrator transcribes, classifies, analyzes sentiment, scores priority,
 * and creates a ticket.
 *
 * @param {Blob} audioBlob - The audio recording
 * @param {string} filename - Filename hint for the server
 * @returns {Promise<{type: string, ticket_id?: string|null, priority?: number, department?: string, sentiment?: number}>}
 */
export async function submitAudioComplaint(audioBlob, filename = "recording.webm") {
  const transcription = await transcribeAudio(audioBlob, filename);
  const transcript = (transcription?.transcript || "").trim();
  if (!transcript) {
    throw new Error("Audio transcription returned empty transcript");
  }
  return submitTextComplaint(transcript, {
    has_audio: true,
    audio_features: transcription?.audio_features || null,
  });
}

/**
 * Request a call-centre-style TTS audio reply for a submitted ticket.
 * Returns base64-encoded MP3 audio from the backend (edge-tts).
 * Returns null if the backend TTS service is unavailable so the caller
 * can fall back to browser SpeechSynthesis.
 *
 * @param {{ ticketId?: string|null, ticketType?: string, messageType?: string }} opts
 * @returns {Promise<{audio_base64: string, mime_type: string, text: string}|null>}
 */
export async function getAudioReply({
  ticketId = null,
  ticketType = "complaint",
  messageType = "ticket_logged",
} = {}) {
  try {
    const response = await fetch(apiUrl("/api/tts/speak"), {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message_type: messageType,
        ticket_id: ticketId ?? undefined,
        ticket_type: ticketType,
      }),
    });
    if (!response.ok) return null;
    const data = await response.json();
    if (!data?.audio_base64) return null;
    return data;
  } catch {
    return null;
  }
}

export default {
  transcribeAudio,
  analyzeSentiment,
  analyzeCombinedSentiment,
  processAudioComplaint,
  sendChatMessage,
  checkSentimentHealth,
  submitTextComplaint,
  submitCustomerTicket,
  submitAudioComplaint,
  getAudioReply,
};
