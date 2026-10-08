import os
import sys

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure backend root is on PYTHONPATH
script_dir = os.path.dirname(os.path.abspath(__file__))
for candidate in [
    script_dir,
    os.path.join(script_dir, ".."),
    os.path.join(script_dir, "bhashalive", "backend"),
    os.path.join(script_dir, "..", "bhashalive", "backend"),
]:
    c_abs = os.path.abspath(candidate)
    if os.path.exists(os.path.join(c_abs, "app")) and c_abs not in sys.path:
        sys.path.insert(0, c_abs)
        break

import argparse
import asyncio
import base64
import io
import json
import math
import struct
import time
import wave
import httpx
import websockets

def play_audio(wav_bytes: bytes):
    """Plays WAV audio bytes out loud on speakers."""
    if not wav_bytes:
        return
    try:
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
            return
    except Exception:
        pass
    try:
        import sounddevice as sd
        import numpy as np
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
            data = np.frombuffer(frames, dtype=np.int16)
            sd.play(data, rate)
            sd.wait()
    except Exception as e:
        print(f"  [AUDIO PLAYBACK NOTICE] Could not play audio: {e}")

from app.security import create_ws_token


def generate_synthetic_audio(duration_sec: float = 3.0) -> bytes:
    """Generates 16kHz mono linear16 PCM audio."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        total_samples = int(duration_sec * 16000)
        data = bytearray()
        for i in range(total_samples):
            val = int(12000.0 * math.sin(2.0 * math.pi * 440.0 * i / 16000))
            data.extend(struct.pack("<h", val))
        wf.writeframes(data)
    # Return PCM data without WAV header
    return buf.getvalue()[44:]


def load_and_normalize_wav(wav_path: str, target_rate: int = 16000) -> bytes:
    """Reads any WAV file and resamples/converts to 16kHz mono linear16 PCM."""
    with wave.open(wav_path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        raw_frames = wf.readframes(wf.getnframes())

    if framerate == target_rate and n_channels == 1 and sampwidth == 2:
        return raw_frames

    try:
        import numpy as np
        from scipy import signal
        audio = np.frombuffer(raw_frames, dtype=np.int16)
        if n_channels > 1:
            audio = audio.reshape(-1, n_channels).mean(axis=1).astype(np.int16)
        if framerate != target_rate:
            target_samples = int(len(audio) * target_rate / framerate)
            audio = signal.resample(audio, target_samples).astype(np.int16)
        return audio.tobytes()
    except Exception as e:
        print(f"[WARN] Resampling skipped ({e}); using raw frames")
        return raw_frames


async def run_client_demo(
    ws_url: str,
    api_url: str,
    wav_path: str | None,
    src_lang: str,
    tgt_lang: str,
):
    print("=" * 70)
    print("BhashaLive WebSocket Client Demo")
    print(f"Connecting to: {ws_url} ({src_lang} -> {tgt_lang})")
    print("=" * 70)

    # 1. Obtain session and token via REST API or local signer
    session_id = None
    token = None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                f"{api_url}/sessions",
                json={"source_language": src_lang, "target_language": tgt_lang},
            )
            if resp.status_code == 201:
                sess_data = resp.json()
                session_id = sess_data["session_id"]
                token = sess_data["ws_token"]
                print(f"[AUTH] Created session {session_id} via REST API")
    except Exception as e:
        print(f"[AUTH] Could not connect to REST API ({e}); generating local developer token")

    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())
        token = create_ws_token(session_id, expires_in_seconds=1800)

    # 2. Prepare audio frames
    # Auto-detect WAV path with fallback to backend directory
    resolved_wav = None
    if wav_path:
        for candidate_path in [
            wav_path,
            os.path.join("bhashalive", "backend", wav_path),
            os.path.join(script_dir, "..", wav_path),
            os.path.join(script_dir, "..", "bhashalive", "backend", wav_path),
        ]:
            if os.path.exists(candidate_path) and not os.path.isdir(candidate_path):
                resolved_wav = candidate_path
                break

    if not resolved_wav:
        for default_name in [
            "sample_tamil_16k.wav",
            os.path.join("bhashalive", "backend", "sample_tamil_16k.wav"),
            os.path.join(script_dir, "..", "sample_tamil_16k.wav"),
            os.path.join(script_dir, "..", "bhashalive", "backend", "sample_tamil_16k.wav"),
        ]:
            if os.path.exists(default_name) and not os.path.isdir(default_name):
                resolved_wav = default_name
                break

    if resolved_wav:
        print(f"Loading and normalizing WAV: {resolved_wav}")
        raw_audio = load_and_normalize_wav(resolved_wav)
    else:
        print("Generating 3.0s synthetic 16kHz mono PCM audio...")
        raw_audio = generate_synthetic_audio(3.0)

    # 3. Connect to WebSocket
    connect_url = f"{ws_url}?token={token}&session_id={session_id}"
    try:
        ws_conn = websockets.connect(connect_url, origin="http://localhost:5173")
    except TypeError:
        ws_conn = websockets.connect(connect_url, extra_headers={"Origin": "http://localhost:5173"})

    async with ws_conn as ws:
        print("\nConnected to BhashaLive WebSocket server.")

        # Send session.start
        start_payload = {
            "type": "session.start",
            "session_id": session_id,
            "source_language": src_lang,
            "target_language": tgt_lang,
            "ws_token": token,
        }
        await ws.send(json.dumps(start_payload))

        ended_event = asyncio.Event()

        # Receiver loop
        async def listen_responses():
            try:
                async for msg in ws:
                    event = json.loads(msg)
                    etype = event.get("type")
                    if etype == "session.status":
                        state = event.get("state")
                        print(f"\n[STATUS] State: {state} | Provider: {event.get('provider')}")
                        if state == "ended":
                            ended_event.set()
                    elif etype == "transcript.partial":
                        print(f"  [TRANSCRIPT (Tentative)] {event.get('text')}")
                    elif etype == "transcript.final":
                        print(f"\n  [TRANSCRIPT (FINAL)] >>> {event.get('text')} <<<")
                    elif etype == "translation.partial":
                        print(f"  [TRANSLATION (Partial)] {event.get('translated_text')}")
                    elif etype == "translation.final":
                        e2e = event.get("end_to_end_latency_ms", 0.0)
                        call_lat = event.get("translation_latency_ms", 0.0)
                        tr_text = event.get("translated_text", "")
                        print(
                            f"\n  [TRANSLATION (FINAL)] *** {tr_text} *** "
                            f"(Latency: {call_lat}ms, E2E: {e2e}ms)"
                        )
                        audio_b64 = event.get("audio_base64")
                        if audio_b64:
                            print("  🔊 [AUDIO OUTPUT] Playing translated voice...")
                            play_audio(base64.b64decode(audio_b64))
                        elif tr_text:
                            try:
                                async with httpx.AsyncClient(timeout=8.0) as client:
                                    r = await client.post(
                                        f"{api_url}/tts",
                                        json={"text": tr_text, "target_language": tgt_lang},
                                    )
                                    if r.status_code == 200:
                                        print("  🔊 [AUDIO OUTPUT] Playing translated voice (via /api/tts)...")
                                        play_audio(base64.b64decode(r.json()["audio_base64"]))
                            except Exception:
                                pass
                    elif etype == "error":
                        print(f"\n  [ERROR] Code: {event.get('code')} - {event.get('safe_message')}")
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"[RECV ERROR] {e}")

        listen_task = asyncio.create_task(listen_responses())

        # Stream audio chunks (100ms chunks = 3200 bytes at 16kHz 16-bit mono)
        chunk_size = 3200
        print("\nStreaming audio chunks to server...")
        try:
            for offset in range(0, len(raw_audio), chunk_size):
                chunk = raw_audio[offset : offset + chunk_size]
                await ws.send(chunk)
                await asyncio.sleep(0.1)

            print("\nFinished sending audio. Sending session.end...")
            await ws.send(json.dumps({"type": "session.end"}))
            try:
                await asyncio.wait_for(ended_event.wait(), timeout=6.0)
            except asyncio.TimeoutError:
                pass
        except websockets.exceptions.ConnectionClosed:
            print("\n[INFO] Connection was closed by server (e.g. provider not configured or session ended).")

        listen_task.cancel()
        print("\nSession completed successfully.")


def main():
    parser = argparse.ArgumentParser(description="BhashaLive WebSocket Client Demo")
    parser.add_argument("--ws", default="ws://localhost:8000/ws/translate", help="WebSocket URL")
    parser.add_argument("--api", default="http://localhost:8000/api", help="REST API URL")
    parser.add_argument("--wav", default=None, help="Path to 16kHz mono WAV file")
    parser.add_argument("--src", default="ta-IN", help="Source language code")
    parser.add_argument("--tgt", default="en-IN", help="Target language code")
    args = parser.parse_args()

    asyncio.run(run_client_demo(args.ws, args.api, args.wav, args.src, args.tgt))


if __name__ == "__main__":
    main()
