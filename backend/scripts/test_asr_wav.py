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
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import argparse
import asyncio
import io
import math
import struct
import wave

from app.config import settings
from app.providers.sarvam_asr import SarvamASRProvider


def generate_synthetic_pcm_wav(duration_seconds: float = 3.0, sample_rate: int = 16000) -> bytes:
    """Generates a synthetic 16kHz mono 16-bit PCM WAV (440Hz tone)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        total_samples = int(duration_seconds * sample_rate)
        data = bytearray()
        for i in range(total_samples):
            # 440 Hz tone modulated
            val = int(16000.0 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            data.extend(struct.pack("<h", val))
        wf.writeframes(data)
    return buf.getvalue()


async def run_asr_test(wav_path: str | None, language: str, verbose: bool = False) -> None:
    print("=" * 60)
    print(f"BhashaLive ASR Verification Test (Language: {language})")
    print("=" * 60)

    if not settings.is_sarvam_asr_configured:
        print("[WARN] SARVAM_API_KEY is not set or placeholder. Test will verify local plumbing.")

    audio_bytes: bytes
    if wav_path and os.path.exists(wav_path):
        print(f"Reading audio from: {wav_path}")
        with wave.open(wav_path, "rb") as wf:
            channels = wf.getnchannels()
            rate = wf.getframerate()
            width = wf.getsampwidth()
            print(f"Audio details: {channels} channels, {rate} Hz, {width * 8}-bit")
            audio_bytes = wf.readframes(wf.getnframes())
    elif os.path.exists("sample_tamil_16k.wav"):
        print("Using generated speech sample: sample_tamil_16k.wav ('நான் நாளைக்கு சென்னைக்கு போகிறேன்.')")
        with wave.open("sample_tamil_16k.wav", "rb") as wf:
            audio_bytes = wf.readframes(wf.getnframes())
    else:
        print("No WAV file specified. Generating 3.0s synthetic 16kHz mono PCM...")
        wav_data = generate_synthetic_pcm_wav(3.0)
        # Extract raw PCM data skipping 44-byte WAV header
        audio_bytes = wav_data[44:]

    provider = SarvamASRProvider()

    async def consume_events():
        try:
            async for event in provider.events():
                prefix = "[FINAL]" if event.is_final else "[PARTIAL]"
                print(f"  {prefix} text='{event.text}' (conf={event.confidence:.2f}, stab={event.stability_score:.2f})")
                if verbose and event.raw_data:
                    print(f"    Raw: {event.raw_data}")
        except Exception as e:
            print(f"[ERROR in event loop] {e}")

    try:
        print(f"Starting ASR session for language: {language}...")
        await provider.start(language=language)
        print("Connected to Sarvam ASR! Streaming audio chunks...")

        consumer_task = asyncio.create_task(consume_events())

        # Stream in 100ms chunks (3200 bytes for 16kHz 16-bit mono)
        chunk_size = 3200
        for offset in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[offset : offset + chunk_size]
            await provider.send_audio(chunk)
            await asyncio.sleep(0.1)  # Simulate real-time streaming pace

        print("Finished sending audio. Flushing buffer...")
        await provider.flush()
        await asyncio.sleep(1.0)

        consumer_task.cancel()
        await provider.close()
        print("ASR test completed successfully.")

    except Exception as e:
        print(f"[Test Error] {e}")
        await provider.close()


def main():
    parser = argparse.ArgumentParser(description="Test Sarvam Realtime ASR with WAV")
    parser.add_argument("--wav", type=str, default=None, help="Path to 16kHz mono WAV file")
    parser.add_argument("--lang", type=str, default="ta-IN", help="Language code (default: ta-IN)")
    parser.add_argument("--verbose", action="store_true", help="Print raw provider messages")
    args = parser.parse_args()

    asyncio.run(run_asr_test(args.wav, args.lang, args.verbose))


if __name__ == "__main__":
    main()
