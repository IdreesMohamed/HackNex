# HackNex

Real-Time Indic Speech Translation & Application Platform for HackNex 2026.

## Architecture & Project Structure
- **`backend/`**: High-performance real-time speech translation backend built with FastAPI, WebSockets, Sarvam AI (Saaras STT, Mayura Translation, Bulbul TTS), Adaptive Stability Scheduler, and offline test suite.
- **`frontend/`**: Next.js / React web interface and dashboard.
- **`data/`**: Datasets and configuration artifacts.

### Backend Quickstart
See [`backend/README.md`](backend/README.md) for full instructions:
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```