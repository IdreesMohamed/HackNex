import datetime
from typing import Literal
from fastapi import APIRouter, Query, Response

from app.db.repo import get_session, get_session_segments
from app.errors import BhashaLiveException, ErrorCode

router = APIRouter(prefix="/sessions", tags=["Export"])


def format_srt_time(seconds: float) -> str:
    millis = int((seconds - int(seconds)) * 1000)
    secs = int(seconds) % 60
    mins = (int(seconds) // 60) % 60
    hours = int(seconds) // 3600
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"


@router.get("/{session_id}/export")
async def export_session_captions(
    session_id: str,
    format: Literal["json", "srt", "txt"] = Query("json"),
) -> Response:
    """Exports session transcript in JSON, SRT captions, or plain TXT format."""
    sess = await get_session(session_id)
    if not sess:
        raise BhashaLiveException(
            code=ErrorCode.INVALID_SESSION,
            safe_message="Session not found to export.",
            retryable=False,
        )

    segments = await get_session_segments(session_id)

    if format == "json":
        import json
        payload = {
            "session_id": session_id,
            "source_language": sess["source_language"],
            "target_language": sess["target_language"],
            "segments": segments,
        }
        return Response(
            content=json.dumps(payload, indent=2, ensure_ascii=False),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=bhashalive_{session_id}.json"},
        )

    elif format == "srt":
        srt_lines = []
        current_time = 0.0
        for idx, s in enumerate(segments, 1):
            start_str = format_srt_time(current_time)
            # Estimate segment duration based on word count
            duration = max(2.0, len(s.get("translated_text", "").split()) * 0.4)
            end_time = current_time + duration
            end_str = format_srt_time(end_time)

            srt_lines.append(str(idx))
            srt_lines.append(f"{start_str} --> {end_str}")
            srt_lines.append(s.get("translated_text", ""))
            srt_lines.append("")  # Empty line between entries
            current_time = end_time

        srt_content = "\n".join(srt_lines)
        return Response(
            content=srt_content,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=bhashalive_{session_id}.srt"},
        )

    else:  # txt
        txt_lines = [
            f"BhashaLive Bilingual Transcript (Session: {session_id})",
            f"Language Pair: {sess['source_language']} -> {sess['target_language']}",
            "=" * 60,
            "",
        ]
        for idx, s in enumerate(segments, 1):
            txt_lines.append(f"[{idx}] Source ({sess['source_language']}): {s.get('source_text')}")
            txt_lines.append(f"    Translation ({sess['target_language']}): {s.get('translated_text')}")
            txt_lines.append("")

        return Response(
            content="\n".join(txt_lines),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=bhashalive_{session_id}.txt"},
        )
