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

  const response = await fetch(apiUrl("/api/chatbot/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
  const response = await fetch(`${API_CONFIG.orchestrator}/process/text`, {
    method: "POST",
    body,
  });

  if (!response.ok) {
    throw new Error("Orchestrator text processing failed");
  }

  return response.json();
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

export default {
  transcribeAudio,
  analyzeSentiment,
  analyzeCombinedSentiment,
  processAudioComplaint,
  sendChatMessage,
  checkSentimentHealth,
  submitTextComplaint,
  submitAudioComplaint,
};
