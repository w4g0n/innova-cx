/**
 * API Service Layer
 *
 * Centralizes all backend API calls for the InnovaCX application.
 */

const API_CONFIG = {
  whisper: import.meta.env.VITE_WHISPER_URL || "http://localhost:3001",
  sentiment: import.meta.env.VITE_SENTIMENT_URL || "http://localhost:8002",
  chatbot: import.meta.env.VITE_CHATBOT_URL || "http://localhost:8001",
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

  const response = await fetch(`${API_CONFIG.whisper}/transcribe`, {
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
  // Step 1: Transcribe
  const transcription = await transcribeAudio(audioBlob);

  // Step 2: Analyze sentiment (with audio features if available)
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
 * @param {string} mode - Chat mode (inquiry/complaint)
 * @returns {Promise<{reply: string}>}
 */
export async function sendChatMessage(message, mode = "inquiry") {
  const response = await fetch(`${API_CONFIG.chatbot}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, mode }),
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

export default {
  transcribeAudio,
  analyzeSentiment,
  analyzeCombinedSentiment,
  processAudioComplaint,
  sendChatMessage,
  checkSentimentHealth,
};
