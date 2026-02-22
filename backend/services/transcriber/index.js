import express from "express";
import multer from "multer";
import cors from "cors";
import { spawn } from "child_process";
import fs from "fs";

const app = express();
app.use(cors());

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

  const py = spawn("python3", ["transcribe.py", audioPath]);

  let stdout = "";
  let stderr = "";

  py.stdout.on("data", (data) => {
    stdout += data.toString();
  });

  py.stderr.on("data", (data) => {
    stderr += data.toString();
  });

  py.on("close", async (code) => {
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

    return res.json({
      transcript: result.transcript,
      audio_score: 1.0,
      audio_features: null,
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
