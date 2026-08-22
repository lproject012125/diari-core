# DiariCore

**DiariCore** is a Progressive Web App (PWA) for mindful journaling. Users write private journal entries, tag their thoughts, optionally attach photos or dictate with voice, and receive **machine learning–based emotion and sentiment analysis** to help them notice patterns over time.

The system combines secure account management, PostgreSQL storage, interactive insights charts, and a suggestions page. ML output is a reflection aid. It is **not** a medical diagnosis.

**Author:** Tolentino, Lawrence Dave P.

---

## Key Features

- **Journal entry management:** Create, view, edit, and delete entries with title, body text, custom tags, photos, and entry date/time. Body length defaults to a **300-word cap** so live text stays close to the training-set length; raising that cap is a planned improvement after the dataset covers longer entries.
- **Custom tags:** Personalized tags with icons from a searchable library, plus default categories.
- **Emotion and sentiment analysis:** Fine-tuned **XLM-RoBERTa-Base** classifier (five classes: angry, anxious, happy, neutral, sad) with confidence scores. Inference runs on Hugging Face, not inside the Railway web process.
- **Dashboard and Insights:** Weekly mood trends, emotion breakdown charts, tag-based correlations, and journaling consistency metrics.
- **Suggestions:** Supportive copy and activity ideas. **Page content is currently static** (not a personalized recommender) and is planned for later improvement.
- **Voice entry:** Microphone capture with Web Speech and/or on-device Whisper, then hand-off into Write Entry. Reliable enough for normal use; recognition is not perfect.
- **Secure authentication:** Registration with privacy consent, email OTP (Brevo), password reset, optional Google Authenticator TOTP, login lockouts, and session-based login.
- **Progressive Web App:** Installable on desktop and mobile, service-worker caching, offline-tolerant drafts, and optional Web Push reminders when installed.
- **Admin tools:** Operator dashboard for a configured admin email (user listing, service tests, audit logs, settings). The current admin UI does **not** include disable-account or delete-account actions.

---

## Tech Stack

- **Frontend:** HTML5, CSS3, vanilla JavaScript (ES6+), Bootstrap 5, Chart.js, Lottie
- **Backend:** Python 3.10+ (3.12 recommended), Flask, Gunicorn
- **Database:** PostgreSQL on Railway (production); SQLite when `DATABASE_URL` is unset (local)
- **Machine learning:** Fine-tuned XLM-RoBERTa-Base (transformer), exported to ONNX, served via Hugging Face Space
- **Email / OTP:** Brevo transactional API
- **Two-factor authentication:** TOTP (Google Authenticator–compatible)
- **PWA:** Web App Manifest, service worker, Cache Storage, Web Push (VAPID)
- **Deployment:** [Railway](https://diari-core.up.railway.app/) (Flask + Gunicorn + PostgreSQL)
- **Version control:** [GitHub](https://github.com/lproject012125/diari-core)

---

## How It Works

1. **Write and save:** The user composes a journal entry. Tags and optional images are stored with the entry in PostgreSQL.
2. **Mood inference:** On save (or re-analyze), Flask (`space_nlp.py`) POSTs the entry text to the Hugging Face Space `POST /predict` endpoint. The model is **not** loaded on Railway.
3. **ML processing:** The Space loads the exported **ONNX** model from [sseia/diari-core-mood](https://huggingface.co/sseia/diari-core-mood) and returns emotion labels, sentiment, scores, and probability distributions.
4. **Storage and analytics:** Results are saved on `journal_entries` and power Dashboard, Entries, and Insights. The Suggestions page is a separate static UI, not generated from a second model.
5. **Fallback:** If the Space is cold-starting or unreachable, a keyword fallback in `space_nlp.py` still completes the save (less accurate than the trained model).

### Why Hugging Face (not on the web server)?

Railway **free-tier** RAM and CPU are not enough to run XLM-RoBERTa-Base (about 1 GB of weights plus tokenizer) next to Gunicorn and the app. Hosting inference on the same dyno would cause slow deploys, out-of-memory failures, and poor response times.

The workflow is:

- **Train / fine-tune** in **Google Colab** (`FinalProject_Resources/DiariCore_Model_Final_Cleaned.ipynb`)
- **Publish** artifacts to [Hugging Face Hub — diari-core-mood](https://huggingface.co/sseia/diari-core-mood/tree/main) (`model.onnx`, `model_quantized.onnx`, `pytorch_model.bin`, tokenizer files)
- **Serve** inference as a separate [HF Space — diaricore-inference](https://huggingface.co/spaces/sseia/diaricore-inference) (FastAPI + ONNX Runtime)

The live web app stays lightweight and only calls the Space over HTTP at runtime.

| Resource | Link |
|----------|------|
| **Model (Hub)** | https://huggingface.co/sseia/diari-core-mood |
| **Inference Space** | https://huggingface.co/spaces/sseia/diaricore-inference |

---

## Installation Instructions

### Prerequisites

- Python 3.10+ (3.12 recommended)
- Git
- Optional: PostgreSQL if not using SQLite locally

### 1. Clone the repository

```bash
git clone https://github.com/lproject012125/diari-core.git
cd diari-core
```

### 2. Create a virtual environment and install dependencies

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment (optional for local dev)

SQLite is used automatically when `DATABASE_URL` is not set.

| Variable | Purpose |
|----------|---------|
| `DATABASE_PATH` | SQLite file path (default: `diaricore.local.db`) |
| `DATABASE_URL` | PostgreSQL connection string (production / Railway) |
| `SECRET_KEY` | Flask session secret (required in production) |
| `SPACE_URL` | HF Space URL (default: `https://sseia-diaricore-inference.hf.space`) |
| `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME` | Email OTP (optional locally; codes may be logged instead) |
| `HF_API_TOKEN` or `HF_TOKEN` | Voice transcription via HF Inference (optional) |
| `UPLOADS_DIR` | Persistent image directory (set to a Railway volume in production) |
| `DIARI_ADMIN_EMAIL` | Allow-list for `/admin` |
| `ENTRY_WORD_MAX` | Journal word cap (default `300`) |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIM_EMAIL` | Web Push |
| `PUSH_CRON_SECRET` | Authorizes optional external cron dispatch |

See `LOCAL_DEV.md` and `ML_SETUP.md` for more detail. Do not commit API keys or connection strings.

### 4. Run locally

**One-command start (Windows):**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1
```

**Or run directly:**

```powershell
$env:DATABASE_PATH = "diaricore.local.db"
python app.py
```

Open **http://127.0.0.1:5000** and verify **http://127.0.0.1:5000/api/health**.

Mood analysis uses the hosted Hugging Face Space even locally (internet required). The first analyze after a Space sleep can take tens of seconds.

### Production deploy (Railway)

1. Connect [https://github.com/lproject012125/diari-core](https://github.com/lproject012125/diari-core) to a Railway project.
2. Add the PostgreSQL plugin (`DATABASE_URL` is injected).
3. Mount a volume and set `UPLOADS_DIR` so photos survive redeploys.
4. Set the environment variables above in Railway Variables (never in git).
5. Start via `Procfile`: `gunicorn app:app -c gunicorn.conf.py` (binds `0.0.0.0:$PORT`).

Live app: **https://diari-core.up.railway.app/**

---

## Author

Tolentino, Lawrence Dave P.

Special mention: Jen Issa Mari B. Dimayacyac, for substantial assistance on the machine-learning side of the project.

---

## Project Links

- **Live Deployment (Railway):** https://diari-core.up.railway.app/
- **GitHub Repository:** https://github.com/lproject012125/diari-core.git
- **Project Presentation (Google Slides):** https://docs.google.com/presentation/d/1jjBY2dVFIcDi_pvSQWGnR9x67_0Z5t7hMupsNOQbkPk/edit?usp=sharing
- **ML Model (Hugging Face Hub):** https://huggingface.co/sseia/diari-core-mood
- **ML Inference Space:** https://huggingface.co/spaces/sseia/diaricore-inference
- **System documentation (PDF):** `DiariCore_System_Documentation.pdf`

---

## Project Structure (overview)

| Path | Description |
|------|-------------|
| `app.py` | Main Flask application and API routes |
| `db.py` | Database schema and queries (PostgreSQL / SQLite) |
| `space_nlp.py` | Mood analysis via Hugging Face Space |
| `hf_space/` | Source for the inference Space deployment |
| `FinalProject_Resources/` | Training notebook and dataset |
| `static/`, `templates/` | Frontend assets and HTML |
| `docs/project-documentation/` | PDF documentation generator and figures |

---

*Created to help users journal mindfully and understand their emotional patterns through secure, data-driven reflection.*
