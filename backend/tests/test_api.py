import pytest
from app.config import settings


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "bhashalive-backend"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_providers_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", None)
    monkeypatch.setattr(settings, "azure_speech_key", None)
    monkeypatch.setattr(settings, "azure_translator_key", None)

    response = await client.get("/api/health/providers")
    assert response.status_code == 200
    data = response.json()

    assert data["sarvam_asr"]["configured"] is False
    assert data["sarvam_asr"]["reachable"] is False
    assert data["sarvam_translate"]["configured"] is False
    assert data["azure_speech"]["configured"] is False
    assert data["azure_translator"]["configured"] is False


@pytest.mark.asyncio
async def test_languages_endpoint(client):
    response = await client.get("/api/languages")
    assert response.status_code == 200
    data = response.json()
    assert "languages" in data
    codes = [l["code"] for l in data["languages"]]
    assert "en-IN" in codes
    assert "hi-IN" in codes
    assert "ta-IN" in codes

    ta = next(l for l in data["languages"] if l["code"] == "ta-IN")
    assert ta["validated"] is True


@pytest.mark.asyncio
async def test_sessions_crud_and_hard_delete(client):
    # 1. Create session
    create_resp = await client.post(
        "/api/sessions",
        json={"source_language": "ta-IN", "target_language": "en-IN"},
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert "session_id" in created_data
    assert "ws_token" in created_data
    session_id = created_data["session_id"]

    # 2. Get session
    get_resp = await client.get(f"/api/sessions/{session_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["session_id"] == session_id

    # 3. Simulate adding a segment
    from app.store import memory_store
    memory_store.save_segment(
        session_id,
        {
            "id": "seg-1",
            "session_id": session_id,
            "sequence_no": 1,
            "source_text": "வணக்கம்",
            "translated_text": "Hello",
            "confidence": 0.99,
            "stability_score": 1.0,
            "rewrite_count": 0,
            "created_at": 1700000000.0,
        },
    )

    # 4. Get segments
    seg_resp = await client.get(f"/api/sessions/{session_id}/segments")
    assert seg_resp.status_code == 200
    segs = seg_resp.json()
    assert len(segs) == 1
    assert segs[0]["source_text"] == "வணக்கம்"

    # 5. Export JSON
    exp_json = await client.get(f"/api/sessions/{session_id}/export?format=json")
    assert exp_json.status_code == 200
    assert "segments" in exp_json.json()

    # 6. Export SRT
    exp_srt = await client.get(f"/api/sessions/{session_id}/export?format=srt")
    assert exp_srt.status_code == 200
    assert "-->" in exp_srt.text
    assert "Hello" in exp_srt.text

    # 7. Export TXT
    exp_txt = await client.get(f"/api/sessions/{session_id}/export?format=txt")
    assert exp_txt.status_code == 200
    assert "வணக்கம்" in exp_txt.text

    # 8. Hard DELETE
    del_resp = await client.delete(f"/api/sessions/{session_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

    # 9. Verify completely gone
    get_after = await client.get(f"/api/sessions/{session_id}")
    assert get_after.status_code == 404
    assert memory_store.get_segments(session_id) == []


@pytest.mark.asyncio
async def test_glossary_crud(client):
    create_resp = await client.post(
        "/api/glossary",
        json={
            "term": "HackNex",
            "source_language": "en-IN",
            "target_language": "ta-IN",
            "preferred_translation": "HackNex",
        },
    )
    assert create_resp.status_code == 201
    term_data = create_resp.json()
    assert term_data["term"] == "HackNex"

    list_resp = await client.get("/api/glossary?source_language=en-IN")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(i["term"] == "HackNex" for i in items)


@pytest.mark.asyncio
async def test_metrics_summary(client):
    resp = await client.get("/api/metrics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "aggregates" in data
