import express from "express";
import multer from "multer";
import fs from "fs";
import cors from "cors";
import OpenAI from "openai";
import path from "path";
import { fileURLToPath } from "url";
import "dotenv/config";
import { execFile } from "child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(cors());

app.use(express.static(path.join(__dirname, "whisper-frontend")));

app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "whisper-frontend", "index.html"));
});

const upload = multer({ dest: "uploads/" });

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

app.post("/transcribe", upload.single("audio"), async (req, res) => {
  console.log("🔥 /transcribe HIT");

  if (!req.file) return res.sendStatus(400);

  const audioPath = req.file.path;
  const outFile = `transcripts/transcript-${Date.now()}.txt`;

  execFile(
    "python3",
    ["transcribe.py", audioPath],
    (error, stdout, stderr) => {
      if (error) {
        console.error("❌ Whisper error:", stderr);
        return res.sendStatus(500);
      }

      if (!fs.existsSync("transcripts")) {
        fs.mkdirSync("transcripts");
      }

      fs.writeFileSync(outFile, stdout, "utf8");
      //fs.unlinkSync(audioPath);

      console.log("✅ Transcript written:", outFile);
      res.sendStatus(204);
    }
  );
});

app.listen(3001, () => {
  console.log("✅ Server running on 3001");
});
