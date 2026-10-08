import os
import sys

# Ensure backend root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import time
import httpx
from app.config import settings


async def check_all_providers():
    print("=" * 70)
    print("BhashaLive Backend Provider & Infrastructure Diagnostics")
    print("=" * 70)

    # 1. Sarvam ASR
    print("\n1. Sarvam Saaras Realtime STT:")
    print(f"   - Configured: {settings.is_sarvam_asr_configured}")
    print(f"   - WebSocket URL: {settings.sarvam_asr_url}")
    print(f"   - Model: {settings.sarvam_asr_model}")
    if settings.is_sarvam_asr_configured:
        print("   - API Key present: [OK]")
    else:
        print("   - API Key: [MISSING - Set SARVAM_API_KEY in .env]")

    # 2. Sarvam Translate
    print("\n2. Sarvam Mayura Translate:")
    print(f"   - Configured: {settings.is_sarvam_translate_configured}")
    print(f"   - Endpoint: {settings.sarvam_translate_url}")
    if settings.is_sarvam_translate_configured:
        try:
            t0 = time.perf_counter()
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.post(
                    settings.sarvam_translate_url,
                    headers={"api-subscription-key": settings.sarvam_api_key},
                    json={
                        "input": "வணக்கம்",
                        "source_language_code": "ta-IN",
                        "target_language_code": "en-IN",
                        "model": settings.sarvam_translate_model,
                    },
                )
                ms = (time.perf_counter() - t0) * 1000
                if res.status_code == 200:
                    print(f"   - Ping Test: [SUCCESS in {ms:.1f}ms] Output: {res.json().get('translated_text')}")
                else:
                    print(f"   - Ping Test: [FAILED - HTTP {res.status_code}] {res.text}")
        except Exception as e:
            print(f"   - Ping Test: [FAILED] {e}")

    # 3. Azure Speech Fallback
    print("\n3. Azure AI Speech Fallback:")
    print(f"   - Configured: {settings.is_azure_speech_configured}")
    print(f"   - Region: {settings.azure_speech_region or '[Not Set]'}")

    # 4. Azure Translator Fallback
    print("\n4. Azure AI Translator Fallback:")
    print(f"   - Configured: {settings.is_azure_translator_configured}")
    print(f"   - Endpoint: {settings.azure_translator_endpoint}")

    # 5. Database Connection
    print("\n5. PostgreSQL Persistence:")
    print(f"   - Enabled: {settings.enable_persistence}")
    print(f"   - URL: {settings.database_url}")
    try:
        from app.db.session import engine
        if engine:
            async with engine.connect() as conn:
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
                print("   - DB Connectivity: [CONNECTED]")
        else:
            print("   - DB Connectivity: [ENGINE NOT INITIALIZED]")
    except Exception as e:
        print(f"   - DB Connectivity: [OFFLINE - {e}] (App safely uses MemoryStore fallback)")

    # 6. Redis Connection
    print("\n6. Redis Cache:")
    print(f"   - URL: {settings.redis_url}")
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2.0)
        await r.ping()
        print("   - Redis Connectivity: [CONNECTED]")
        await r.close()
    except Exception as e:
        print(f"   - Redis Connectivity: [OFFLINE] (App safely operates with in-memory limiter)")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(check_all_providers())
