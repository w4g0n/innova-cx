let recorder = null;
let chunks = [];
let recording = false;

const btn = document.getElementById("recordBtn");

btn.onclick = async () => {
  // START RECORDING
  if (!recording) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    chunks = [];
    recorder = new MediaRecorder(stream);

    recorder.ondataavailable = e => chunks.push(e.data);

    recorder.onstop = async () => {
      const blob = new Blob(chunks, { type: "audio/webm" });

      const formData = new FormData();
      formData.append("audio", blob, "mic.webm");

      await fetch("/transcribe", {
        method: "POST",
        body: formData
      });

      console.log("Recording sent to backend");
    };

    recorder.start();
    recording = true;
    btn.textContent = "Stop Recording";
    console.log("Recording started");
  }

  // STOP RECORDING + SEND
  else {
    recorder.stop();
    recording = false;
    btn.textContent = "Start Recording";
    console.log("Recording stopped");
  }
};
