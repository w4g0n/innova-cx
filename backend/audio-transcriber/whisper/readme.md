LOCAL WHISPER TRANSCRIPTION APP
README
This project records audio from the browser, sends it to a local backend, and transcribes the audio using Whisper running locally (no OpenAI API, no billing).



REQUIREMENTS
Before starting, make sure these are installed:
Node.js version 18 or higher
Python version 3.9 or higher
macOS or Linux
You can check by running:
node -v
python3 --version



PROJECT STRUCTURE
After unzipping, the folder should contain:
index.js
transcribe.py
package.json
whisper-frontend folder
index.html
mic.js
uploads folder
transcripts folder



SETUP (FIRST TIME ONLY)
Step 1
Open Terminal and go into the project folder (the one with index.js):
cd path/to/whisper
Step 2
Create a Python virtual environment:
python3 -m venv whisper-env
Step 3
Activate the virtual environment:
source whisper-env/bin/activate
You should now see (whisper-env) in the terminal.
Step 4
Install Whisper dependency:
pip install faster-whisper
Step 5
Install Node dependencies:
npm install



RUNNING THE APPLICATION
You must do these steps every time you want to run the app.
Step 1
Activate the Python virtual environment:
source whisper-env/bin/activate
Step 2
Start the backend server:
node index.js
You should see:
Server running on 3001
Leave this terminal open.
Step 3
Open a browser and go to:
http://localhost:3001



HOW TO USE
Click Start Recording
Speak clearly
Click Stop Recording
What happens:
Audio files are saved in the uploads folder
Transcription text files are saved in the transcripts folder



TEST SENTENCE
Read this out loud to test transcription:
I booked a late flight from Dubai to Chicago for one hundred and seventy-nine dollars, even though the weather was humid and noisy.



TROUBLESHOOTING
Problem: uploads folder fills but transcripts folder is empty
Fix:
Make sure (whisper-env) is active
Test Whisper manually by running:
python3 transcribe.py uploads/<any-audio-file>
If this command fails, transcription will not work.