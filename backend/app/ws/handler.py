import json
import logging
import uuid
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.errors import ErrorCode, SAFE_ERROR_MESSAGES
from app.languages import is_language_supported
from app.providers.sarvam_asr import SarvamASRProvider
from app.providers.sarvam_translate import SarvamTranslationProvider
from app.schemas import WSError, WSPong, WSSessionStart, WSSessionStatus
from app.security import is_origin_allowed, verify_ws_token
from app.store import memory_store
from app.ws.pipeline import SessionPipeline

logger = logging.getLogger("bhashalive.ws.handler")
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/translate")
async def websocket_translate_endpoint(
    websocket: WebSocket,
    token: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """Realtime speech translation WebSocket endpoint.

    Accepts PCM audio frames (16kHz mono linear16) and yields live transcript/translation events.
    """
    origin = websocket.headers.get("origin")
    if not is_origin_allowed(origin, settings.allowed_ws_origins_list):
        logger.warning(f"Rejected WS connection from disallowed origin: {origin}")
        await websocket.close(code=1008, reason="Disallowed Origin")
        return

    await websocket.accept()
    logger.info("Client accepted at /ws/translate")

    pipeline: Optional[SessionPipeline] = None
    active_session_id: Optional[str] = None

    try:
        # 1. Handshake: First message MUST be session.start (or token in query)
        first_frame = await websocket.receive()
        if first_frame.get("type") == "websocket.disconnect":
            return

        first_text = first_frame.get("text")
        if not first_text:
            await websocket.send_json(
                WSError(
                    code=ErrorCode.MALFORMED_EVENT.value,
                    safe_message="First message must be session.start JSON frame.",
                    retryable=False,
                ).model_dump()
            )
            await websocket.close(code=1003)
            return

        try:
            start_data = json.loads(first_text)
            start_event = WSSessionStart.model_validate(start_data)
        except Exception as e:
            logger.warning(f"Invalid session.start payload: {e}")
            await websocket.send_json(
                WSError(
                    code=ErrorCode.MALFORMED_EVENT.value,
                    safe_message="Invalid session.start event structure.",
                    retryable=False,
                ).model_dump()
            )
            await websocket.close(code=1003)
            return

        # Validate token
        provided_token = start_event.ws_token or token
        expected_session = start_event.session_id or session_id
        if provided_token:
            valid, token_sess_id = verify_ws_token(provided_token, expected_session_id=expected_session)
            if not valid:
                logger.warning("WebSocket token verification failed")
                await websocket.send_json(
                    WSError(
                        code=ErrorCode.UNAUTHORIZED_ORIGIN.value,
                        safe_message="Invalid or expired session token.",
                        retryable=False,
                    ).model_dump()
                )
                await websocket.close(code=1008)
                return

        # Validate language codes
        src_lang = start_event.source_language
        tgt_lang = start_event.target_language
        if not is_language_supported(src_lang) or not is_language_supported(tgt_lang):
            await websocket.send_json(
                WSError(
                    code=ErrorCode.UNSUPPORTED_LANGUAGE.value,
                    safe_message=SAFE_ERROR_MESSAGES[ErrorCode.UNSUPPORTED_LANGUAGE],
                    retryable=False,
                ).model_dump()
            )
            await websocket.close(code=1003)
            return

        # Setup session ID and register in store
        active_session_id = start_event.session_id or session_id or str(uuid.uuid4())
        memory_store.create_session(
            session_id=active_session_id,
            source_language=src_lang,
            target_language=tgt_lang,
            provider="sarvam",
            status="connected",
        )

        # Provider availability check
        if not settings.is_sarvam_asr_configured and not settings.is_azure_speech_configured:
            logger.warning(f"Session {active_session_id} start rejected: provider not configured")
            await websocket.send_json(
                WSError(
                    code=ErrorCode.PROVIDER_NOT_CONFIGURED.value,
                    safe_message=SAFE_ERROR_MESSAGES[ErrorCode.PROVIDER_NOT_CONFIGURED],
                    retryable=False,
                ).model_dump()
            )
            await websocket.close(code=1011)
            return

        # Instantiate providers and pipeline
        asr_provider = SarvamASRProvider()
        translation_provider = SarvamTranslationProvider()

        pipeline = SessionPipeline(
            session_id=active_session_id,
            source_language=src_lang,
            target_language=tgt_lang,
            send_json=websocket.send_json,
            asr_provider=asr_provider,
            translation_provider=translation_provider,
        )

        await websocket.send_json(
            WSSessionStatus(
                state="connected",
                provider="sarvam",
                session_id=active_session_id,
            ).model_dump()
        )

        # Start background pipeline
        await pipeline.start()

        # 2. Main message processing loop
        while True:
            frame = await websocket.receive()
            frame_type = frame.get("type")

            if frame_type == "websocket.disconnect":
                break

            # Handle binary audio frame
            if "bytes" in frame and frame["bytes"]:
                chunk = frame["bytes"]
                if len(chunk) > settings.max_audio_chunk_bytes:
                    logger.warning(
                        f"Audio chunk exceeded MAX_AUDIO_CHUNK_BYTES ({len(chunk)} > {settings.max_audio_chunk_bytes})"
                    )
                    await websocket.send_json(
                        WSError(
                            code=ErrorCode.INVALID_AUDIO_CHUNK.value,
                            safe_message=SAFE_ERROR_MESSAGES[ErrorCode.INVALID_AUDIO_CHUNK],
                            retryable=True,
                        ).model_dump()
                    )
                    continue

                await pipeline.push_audio(chunk)

            # Handle text control frames
            elif "text" in frame and frame["text"]:
                try:
                    payload = json.loads(frame["text"])
                    event_type = payload.get("type")

                    if event_type == "ping":
                        await websocket.send_json(WSPong().model_dump())

                    elif event_type == "session.end":
                        logger.info(f"Received session.end for {active_session_id}")
                        await pipeline.handle_end()
                        break

                    else:
                        logger.debug(f"Ignored unknown client frame type: {event_type}")

                except json.JSONDecodeError:
                    logger.warning("Received invalid non-JSON text frame")
                    # Safely ignore malformed frames without crashing the session

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from WebSocket: {active_session_id}")
    except Exception as e:
        logger.error(f"WebSocket session exception ({active_session_id}): {e}", exc_info=True)
        try:
            await websocket.send_json(
                WSError(
                    code=ErrorCode.INTERNAL_ERROR.value,
                    safe_message="Session ended unexpectedly.",
                    retryable=False,
                ).model_dump()
            )
        except Exception:
            pass
    finally:
        if pipeline:
            await pipeline.close()
        if active_session_id:
            memory_store.update_session(active_session_id, status="ended")
