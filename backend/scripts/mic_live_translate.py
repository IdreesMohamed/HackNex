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
import json
import time
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
        import io, wave, numpy as np
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
            data = np.frombuffer(frames, dtype=np.int16)
            sd.play(data, rate)
            sd.wait()
    except Exception as e:
        pass

try:
    import sounddevice as sd
except ImportError:
    print("[ERROR] sounddevice is not installed. Run: pip install sounddevice")
    sys.exit(1)

from app.security import create_ws_token

# ANSI styling
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CLEAR_LINE = "\033[2K\r"


async def run_live_mic(
    ws_url: str,
    api_url: str,
    src_lang: str,
    tgt_lang: str,
    device_index: int | None = None,
):
    print("=" * 70)
    print(f"{BOLD}{GREEN}BhashaLive Real-Time Microphone Speech Translation{RESET}")
    print(f"Translating: {BOLD}{CYAN}{src_lang}{RESET}  --->  {BOLD}{MAGENTA}{tgt_lang}{RESET}")
    print("=" * 70)

    # 1. Obtain session and token via REST API
    session_id = None
    token = None
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(
                f"{api_url}/sessions",
                json={"source_language": src_lang, "target_language": tgt_lang},
            )
            if resp.status_code == 201:
                sess_data = resp.json()
                session_id = sess_data["session_id"]
                token = sess_data["ws_token"]
                print(f"[AUTH] Session established: {session_id}")
    except Exception as e:
        print(f"[AUTH] REST API fallback ({e}); using developer session token.")

    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())
        token = create_ws_token(session_id, expires_in_seconds=1800)

    # 2. Connect to WebSocket
    connect_url = f"{ws_url}?token={token}&session_id={session_id}"
    try:
        ws_conn = websockets.connect(connect_url, origin="http://localhost:5173")
    except TypeError:
        ws_conn = websockets.connect(connect_url, extra_headers={"Origin": "http://localhost:5173"})

    async with ws_conn as ws:
        print(f"{GREEN}[CONNECTED]{RESET} WebSocket connection active.")

        # Send session.start
        start_payload = {
            "type": "session.start",
            "session_id": session_id,
            "source_language": src_lang,
            "target_language": tgt_lang,
            "ws_token": token,
        }
        await ws.send(json.dumps(start_payload))

        audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        # Microphone input callback
        def mic_callback(indata, frames, time_info, status):
            if status:
                pass
            # indata is numpy int16 array of shape (frames, 1)
            raw_bytes = indata.tobytes()
            loop.call_soon_threadsafe(audio_queue.put_nowait, raw_bytes)

        # Audio streaming task
        async def stream_audio_worker():
            while not stop_event.is_set():
                try:
                    chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.1)
                    await ws.send(chunk)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    if not stop_event.is_set():
                        print(f"[STREAM ERROR] {e}")
                    break

        # Receiver loop for live transcription & translation
        async def listen_worker():
            try:
                async for msg in ws:
                    event = json.loads(msg)
                    etype = event.get("type")

                    if etype == "session.status":
                        st = event.get("state")
                        prov = event.get("provider")
                        if st == "streaming":
                            print(f"{GREEN}[MIC ACTIVE]{RESET} Speak into your microphone now... (Press Ctrl+C to stop)\n")

                    elif etype == "transcript.partial":
                        text = event.get("text", "").strip()
                        if text:
                            sys.stdout.write(f"{CLEAR_LINE}{YELLOW}[Speaking...]{RESET} {text}")
                            sys.stdout.flush()

                    elif etype == "transcript.final":
                        text = event.get("text", "").strip()
                        if text:
                            sys.stdout.write(f"{CLEAR_LINE}{BOLD}{CYAN}[Original ({src_lang})]{RESET} >>> {text} <<<\n")
                            sys.stdout.flush()

                    elif etype == "translation.partial":
                        tr_text = event.get("translated_text", "").strip()
                        if tr_text:
                            sys.stdout.write(f"{CLEAR_LINE}{DIM}[Translating...]{RESET} {tr_text}")
                            sys.stdout.flush()

                    elif etype == "translation.final":
                        tr_text = event.get("translated_text", "").strip()
                        call_lat = event.get("translation_latency_ms", 0.0)
                        e2e = event.get("end_to_end_latency_ms", 0.0)
                        if tr_text:
                            sys.stdout.write(
                                f"{CLEAR_LINE}{BOLD}{GREEN}[Translation ({tgt_lang})]{RESET} *** {tr_text} *** "
                                f"{DIM}(Latency: {call_lat:.0f}ms | E2E: {e2e:.0f}ms){RESET}\n"
                            )
                            sys.stdout.flush()
                            audio_b64 = event.get("audio_base64")
                            if audio_b64:
                                sys.stdout.write(f"{BOLD}{YELLOW}🔊 Playing translated voice...{RESET}\n\n")
                                sys.stdout.flush()
                                play_audio(base64.b64decode(audio_b64))
                            else:
                                try:
                                    async with httpx.AsyncClient(timeout=8.0) as client:
                                        r = await client.post(
                                            f"{api_url}/tts",
                                            json={"text": tr_text, "target_language": tgt_lang},
                                        )
                                        if r.status_code == 200:
                                            sys.stdout.write(f"{BOLD}{YELLOW}🔊 Playing translated voice (via /api/tts)...{RESET}\n\n")
                                            sys.stdout.flush()
                                            play_audio(base64.b64decode(r.json()["audio_base64"]))
                                except Exception:
                                    pass

                    elif etype == "error":
                        code = event.get("code")
                        safe_msg = event.get("safe_message")
                        print(f"\n{BOLD}\033[91m[ERROR {code}]{RESET} {safe_msg}")

            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"\n[RECV ERROR] {e}")

        stream_task = asyncio.create_task(stream_audio_worker())
        listen_task = asyncio.create_task(listen_worker())

        # Start 16kHz mono int16 audio input stream
        # blocksize=1600 samples = 100ms at 16000Hz (3200 bytes per chunk)
        sample_rate = 16000
        block_size = 1600

        try:
            with sd.InputStream(
                samplerate=sample_rate,
                blocksize=block_size,
                device=device_index,
                channels=1,
                dtype="int16",
                callback=mic_callback,
            ):
                # Keep running until Ctrl+C
                while not stop_event.is_set():
                    await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            print(f"\n\n{YELLOW}[STOPPING]{RESET} Ending speech session...")
        finally:
            stop_event.set()
            try:
                await ws.send(json.dumps({"type": "session.end"}))
                await asyncio.sleep(2.0)
            except Exception:
                pass
            stream_task.cancel()
            listen_task.cancel()
            print(f"{GREEN}[FINISHED]{RESET} Microphone session ended successfully.\n")


def main():
    parser = argparse.ArgumentParser(description="BhashaLive Live Microphone Speech Translation")
    parser.add_argument("--src", default="ta-IN", help="Source language (e.g. ta-IN, hi-IN, en-IN)")
    parser.add_argument("--tgt", default="en-IN", help="Target language (e.g. en-IN, ta-IN, hi-IN)")
    parser.add_argument("--ws", default="ws://localhost:8000/ws/translate", help="WebSocket URL")
    parser.add_argument("--api", default="http://localhost:8000/api", help="REST API URL")
    parser.add_argument("--device", type=int, default=None, help="Input audio device index (optional)")
    parser.add_argument("--list-devices", action="store_true", help="List audio input devices and exit")
    args = parser.parse_args()

    if args.list_devices:
        print("\nAvailable Audio Input Devices:")
        print(sd.query_devices())
        return

    try:
        asyncio.run(run_live_mic(args.ws, args.api, args.src, args.tgt, args.device))
    except KeyboardInterrupt:
        print("\nExiting BhashaLive Live Client.")


if __name__ == "__main__":
    main()
