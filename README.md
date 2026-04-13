# InnovaCX

AI-powered customer experience platform built for **Dubai CommerCity (DCC)**. InnovaCX uses sentiment analysis, audio intelligence, and machine learning to automatically triage, prioritise, and route customer complaints — so every customer feels heard and every team works smarter.

| | |
|---|---|
| **Main** | https://innovacx.net |
| **Staff Login** | https://staff.innovacx.net/login |
| **YouTube** | https://www.youtube.com/@InnovaCXAI |

---

## Getting Started

> Assumes Git and Docker are installed.

**Step 1 — Clone the repository**
```bash
git clone https://github.com/w4g0n/innova-cx.git
cd innova-cx
```

**Step 2 — Configure environment variables**
```bash
cp .env.install .env
```

All values are pre-filled with safe development defaults — no editing required.

**Step 3 — Start the application**
```bash
docker compose --profile frontend up --build
```

Wait for `Application startup complete` before opening the browser.

**Step 4 — Open in your browser**

Open http://localhost:5173 in your browser.

**Default login credentials**

| Role | Email | Password |
|---|---|---|
| Customer | customer1@innovacx.net | Innova@2025 |
| Employee | ahmed@innovacx.net | Innova@2025 |
| Manager | hamad@innovacx.net | Innova@2025 |
| Operator | operator@innovacx.net | Innova@2025 |

---

## Skip MFA (after trying it once)

To disable MFA and log in with just email + password:

Press `Ctrl+C` to stop the app, then run:

```bash
echo "DISABLE_MFA=true" >> .env
docker compose --profile frontend up
```

---

## Team

| Name | Student ID | Email |
|---|---|---|
| Leen Naser | 8198731 | lmfn660@uowmail.edu.au |
| Majid Sharaf | 8104104 | mmsas879@uowmail.edu.au |
| Yara Saab | 8255593 | yefs367@uowmail.edu.au |
| Ali Al Maharif | 8526898 | aoam872@uowmail.edu.au |
| Hana Ayad | 8274484 | Haa210@uowmail.edu.edu |
| Rami Alassi | 8456434 | rtsa882@uowmail.edu.au |
| Hamad Subhi | 8489920 | has071@uowmail.edu.au |
