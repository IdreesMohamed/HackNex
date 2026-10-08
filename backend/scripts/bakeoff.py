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

import asyncio
import json
import time

from app.config import settings
from app.providers.azure_translator import AzureTranslationProvider
from app.providers.sarvam_translate import SarvamTranslationProvider


async def run_bakeoff():
    fixtures_path = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "eval_sentences.json")
    if not os.path.exists(fixtures_path):
        print(f"Error: Fixture not found at {fixtures_path}")
        return

    with open(fixtures_path, "r", encoding="utf-8") as f:
        sentences = json.load(f)

    print("=" * 80)
    print("BhashaLive Translation Bakeoff Evaluation")
    print("=" * 80)
    print(f"{'Category':<20} | {'Pair':<12} | {'Provider':<10} | {'Latency (ms)':<12} | {'Output'}")
    print("-" * 80)

    sarvam = SarvamTranslationProvider()
    azure = AzureTranslationProvider()

    for item in sentences:
        category = item["category"]
        src = item["source_language"]
        tgt = item["target_language"]
        text = item["text"]
        pair_str = f"{src}->{tgt}"

        # Evaluate Sarvam if configured
        if settings.is_sarvam_translate_configured:
            try:
                t0 = time.perf_counter()
                out_sarvam = await sarvam.translate(text, src, tgt)
                lat_sarvam = round((time.perf_counter() - t0) * 1000, 2)
                print(f"{category:<20} | {pair_str:<12} | {'Sarvam':<10} | {lat_sarvam:<12.2f} | {out_sarvam}")
            except Exception as e:
                print(f"{category:<20} | {pair_str:<12} | {'Sarvam':<10} | {'ERR':<12} | {e}")
        else:
            print(f"{category:<20} | {pair_str:<12} | {'Sarvam':<10} | {'UNCONFIGURED':<12} | [Set SARVAM_API_KEY]")

        # Evaluate Azure if configured
        if settings.is_azure_translator_configured:
            try:
                t0 = time.perf_counter()
                out_azure = await azure.translate(text, src, tgt)
                lat_azure = round((time.perf_counter() - t0) * 1000, 2)
                print(f"{category:<20} | {pair_str:<12} | {'Azure':<10} | {lat_azure:<12.2f} | {out_azure}")
            except Exception as e:
                print(f"{category:<20} | {pair_str:<12} | {'Azure':<10} | {'ERR':<12} | {e}")
        else:
            print(f"{category:<20} | {pair_str:<12} | {'Azure':<10} | {'UNCONFIGURED':<12} | [Set AZURE_TRANSLATOR_KEY]")

        print("-" * 80)


if __name__ == "__main__":
    asyncio.run(run_bakeoff())
