# BhashaLive Backend: Realtime Indic Speech Translation
**HackNex 2026 — Problem HNX26EPS03**

BhashaLive is a production-minded live translation backend designed specifically for Indian languages. It ingests streaming microphone audio over WebSockets, performs streaming speech recognition, schedules stable commits via an algorithmic **Adaptive Stability Scheduler**, and yields translated captions in real time.

---

## 1. Supported Languages
* **Must Have:** Indian English (`en-IN`), Hindi (`hi-IN`), Tamil (`ta-IN`)
* **Good to Have:** Telugu (`te-IN`), Kannada (`kn-IN`), Malayalam (`ml-IN` with quality gate)

---

## 2. Quickstart (Under 5 Minutes)

### Option A: Running with Docker Compose (Recommended)
Ensure Docker and Docker Compose are installed and running:
```bash
# 1. Copy sample environment
cp backend/.env.example backend/.env

# 2. Launch API + PostgreSQL + Redis
docker compose up --build
```
The FastAPI server will be available at `http://localhost:8000`.
Interactive OpenAPI docs are available at `http://localhost:8000/docs`.

---

### Option B: Running Locally with Python Virtualenv

```bash
# 1. Navigate to backend directory
cd backend

# 2. Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 3. Install pinned dependencies
pip install -r requirements.txt

# 4. Copy configuration
cp .env.example .env

# 5. Run database migrations (if PostgreSQL is running)
alembic upgrade head

# 6. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 3. Configuration & API Keys
All settings and credentials live in `backend/.env`. The application safely starts even if keys are absent, reporting provider readiness honestly at `GET /api/health/providers`.

| Key | Description | Default |
| :--- | :--- | :--- |
| `SARVAM_API_KEY` | Sarvam AI primary subscription key | Empty / Optional |
| `SARVAM_ASR_URL` | Sarvam Saaras realtime STT WebSocket | `wss://api.sarvam.ai/speech-to-text-realtime/ws` |
| `SARVAM_TRANSLATE_URL` | Sarvam Mayura translation endpoint | `https://api.sarvam.ai/translate` |
| `AZURE_SPEECH_KEY` | Azure Speech fallback key | Optional |
| `AZURE_SPEECH_REGION` | Azure Cognitive region (e.g. `centralindia`) | Optional |
| `AZURE_TRANSLATOR_KEY`| Azure Translator fallback key | Optional |
| `DATABASE_URL` | PostgreSQL async connection string | `postgresql+asyncpg://bhasha:bhasha@localhost:5432/bhashalive` |
| `REDIS_URL` | Redis cache connection string | `redis://localhost:6379/0` |
| `ENABLE_FALLBACK` | Automatically switch to Azure on failure | `true` |
| `ENABLE_PERSISTENCE` | Persist transcripts to PostgreSQL | `true` (falls back to MemoryStore) |

---

## 4. Diagnostic & Testing Scripts

### A. Check Provider Credentials & Databases
Pings all configured providers and storage engines to verify connectivity:
```bash
python scripts/check_providers.py
```

### B. Test Streaming ASR with a WAV File
Streams a 16kHz mono 16-bit PCM WAV to Sarvam ASR and prints real-time events:
```bash
# With real WAV file:
python scripts/test_asr_wav.py --wav path/to/sample.wav --lang ta-IN

# With automatic synthetic PCM generator:
python scripts/test_asr_wav.py --lang ta-IN
```

### C. Run the WebSocket Browser Simulator Demo
Simulates a client streaming audio over `/ws/translate` and prints live captions:
```bash
python scripts/ws_client_demo.py --src ta-IN --tgt en-IN
```

### D. Run the Baseline vs. Adaptive Ablation Study
Executes the ablation experiment comparing the **Adaptive Stability Scheduler** against the **Fixed 500ms Baseline**:
```bash
python scripts/ablation.py
```
*(Populates results table in `docs/ABLATION.md`).*

### E. Run Language Quality Bakeoff
Evaluates standard evaluation sentences across all providers:
```bash
python scripts/bakeoff.py
```

---

## 5. Running the Test Suite
The backend includes a comprehensive offline test suite with 100% mocked providers, fake clocks, and integration tests:

```bash
# Run all unit and integration tests
pytest -v
```

---

## 6. Cloud Deployment Notes (Render / Railway)

### Deploying on Railway / Render:
1. **Dockerfile:** Use the included multi-stage `Dockerfile` (`python:3.11-slim`, non-root user `bhashauser`).
2. **Environment Variables:** Provide `SARVAM_API_KEY`, `CORS_ORIGINS`, and database credentials in the dashboard.
3. **Health Check Path:** Set health check probe to `GET /api/health`.
4. **WebSocket Headers:** Ensure the reverse proxy forwards `Upgrade` and `Connection` headers and sets `X-Forwarded-Proto`. Uvicorn is already started with `--proxy-headers`.

---

## 7. Architecture & Documentation Links
* 📐 **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md):** Complete architecture diagram and judge pitch.
* 🔌 **[docs/WS_PROTOCOL.md](docs/WS_PROTOCOL.md):** WebSocket protocol specification and schemas.
* 📜 **[docs/PROVIDER_NOTES.md](docs/PROVIDER_NOTES.md):** Live doc verification findings for Sarvam AI and Azure AI.
* 📊 **[docs/ABLATION.md](docs/ABLATION.md):** Experimental ablation study comparing latency, rewrite counts, and API call volumes.
