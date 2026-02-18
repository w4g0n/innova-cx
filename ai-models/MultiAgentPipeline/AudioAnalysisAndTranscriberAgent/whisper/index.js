import express from "express";
import multer from "multer";
import cors from "cors";
import { spawn } from "child_process";
import fs from "fs";
import path from "path";

const app = express();
app.use(cors());

const audioAnalyzerUrl =
  process.env.AUDIO_ANALYZER_URL || "http://innovacx-audio-analyzer:8003";

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

  // --- 1. Transcribe via Python (Faster-Whisper) ---
  const transcriptPromise = new Promise((resolve, reject) => {
    const py = spawn("python3", ["analyze.py", audioPath]);

    let stdout = "";
    let stderr = "";

    py.stdout.on("data", (data) => { stdout += data.toString(); });
    py.stderr.on("data", (data) => { stderr += data.toString(); });

    py.on("close", (code) => {
      if (code !== 0 || stderr) {
        console.error("🐍 Python error:", stderr || `Exited with code ${code}`);
        return reject(new Error("Transcription failed"));
      }
      try {
        resolve(JSON.parse(stdout));
      } catch {
        console.error("❌ Invalid Python output:", stdout);
        reject(new Error("Invalid transcriber output"));
      }
    });
  });

  // --- 2. Forward audio to Audio Analyzer service (server-to-server) ---
  const audioAnalysisPromise = (async () => {
    try {
      const fileBuffer = fs.readFileSync(audioPath);
      const formData = new FormData();
      formData.append(
        "audio",
        new Blob([fileBuffer]),
        req.file.originalname || "audio.webm"
      );

      const analyzerRes = await fetch(`${audioAnalyzerUrl}/analyze`, {
        method: "POST",
        body: formData,
      });

      if (analyzerRes.ok) {
        const result = await analyzerRes.json();
        console.log("🔊 Audio analysis: score=", result.audio_score);
        return result;
      }
      console.warn("🔊 Audio analysis failed:", analyzerRes.status);
      return null;
    } catch (err) {
      console.warn("🔊 Audio analysis unavailable:", err?.message || err);
      return null;
    }
  })();

  // --- 3. Wait for both, then respond ---
  try {
    const [transcription, audioAnalysis] = await Promise.all([
      transcriptPromise,
      audioAnalysisPromise,
    ]);

    console.log("📝 Transcript:", (transcription.transcript || "").slice(0, 80));

    return res.json({
      transcript: transcription.transcript,
      audio_score: audioAnalysis?.audio_score ?? null,
      audio_features: audioAnalysis?.audio_features ?? null,
    });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  } finally {
    try {
      if (fs.existsSync(audioPath)) fs.unlinkSync(audioPath);
    } catch (cleanupErr) {
      console.warn("⚠️ Failed to cleanup audio file:", cleanupErr.message);
    }
  }
});

// ------------------------------------
// Server
// ------------------------------------
const PORT = 3001;
app.listen(PORT, () => {
  console.log(`✅ Whisper service running on http://localhost:${PORT}`);
});
