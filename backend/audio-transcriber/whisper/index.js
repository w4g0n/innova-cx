import express from "express";
import multer from "multer";
import cors from "cors";
import { spawn } from "child_process";
import fs from "fs";
import path from "path";

const app = express();
app.use(cors());
const sentimentUrl =
  process.env.SENTIMENT_URL || "http://innovacx-sentiment:8002";

// ------------------------------------
// Upload config
// ------------------------------------
const UPLOAD_DIR = "uploads";
const upload = multer({ dest: UPLOAD_DIR });

// ------------------------------------
// Routes
// ------------------------------------
app.post("/transcribe", upload.single("audio"), async (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: "No audio file provided" });
  }

  const audioPath = req.file.path;

  console.log("🎙️ Received audio:", audioPath);

  const py = spawn("python3", ["analyze.py", audioPath]);

  let stdout = "";
  let stderr = "";

  py.stdout.on("data", (data) => {
    stdout += data.toString();
  });

  py.stderr.on("data", (data) => {
    stderr += data.toString();
  });

  py.on("close", (code) => {
    // Always cleanup uploaded file
    try {
      if (fs.existsSync(audioPath)) {
        fs.unlinkSync(audioPath);
      }
    } catch (err) {
      console.warn("⚠️ Failed to cleanup audio file:", err.message);
    }

    if (code !== 0 || stderr) {
      console.error("🐍 Python error:");
      console.error(stderr || `Exited with code ${code}`);
      return res.status(500).json({ error: "Audio processing failed" });
    }

    let result;
    try {
      result = JSON.parse(stdout);
    } catch (err) {
      console.error("❌ Invalid Python output:");
      console.error(stdout);
      return res.status(500).json({ error: "Invalid analyzer output" });
    }

    console.log("🎧 Audio score:", result.audio_score);

    let sentiment = null;
    if (result.transcript) {
      try {
        const sentimentRes = await fetch(sentimentUrl + "/analyze-combined", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: result.transcript,
            audio_features: result.audio_features || null,
          }),
        });

        if (sentimentRes.ok) {
          sentiment = await sentimentRes.json();
          console.log(
            "🧠 Sentiment (combined):",
            `text=${sentiment.text_sentiment}`,
            `audio=${sentiment.audio_sentiment}`,
            `combined=${sentiment.combined_sentiment}`
          );
        } else {
          console.warn("🧠 Sentiment request failed:", sentimentRes.status);
        }
      } catch (err) {
        console.warn("🧠 Sentiment request error:", err?.message || err);
      }
    }

    return res.json({
      transcript: result.transcript,
      audio_score: result.audio_score,
      audio_features: result.audio_features || null,
      sentiment,
    });
  });
});

// ------------------------------------
// Server
// ------------------------------------
const PORT = 3001;
app.listen(PORT, () => {
  console.log(`✅ Whisper service running on http://localhost:${PORT}`);
});
