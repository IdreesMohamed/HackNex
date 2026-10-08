import asyncio
import logging
import time
import uuid
from typing import Awaitable, Callable, Dict, Optional

from app.config import settings
from app.errors import BhashaLiveException, ErrorCode
from app.providers.base import ASRProvider, TranslationProvider
from app.schemas import (
    WSError,
    WSSessionStatus,
    WSTranscriptFinal,
    WSTranscriptPartial,
    WSTranslationFinal,
    WSTranslationPartial,
)
from app.stability.baseline import FixedIntervalBaselineScheduler
from app.stability.scheduler import AdaptiveStabilityScheduler, CommitDecision
from app.store import memory_store

logger = logging.getLogger("bhashalive.ws.pipeline")


class SessionPipeline:
    """Orchestrates real-time speech translation for an active WebSocket session.

    Ensures that ASR event reading never blocks on translation network calls,
    maintains a stable segment_id per utterance, and handles cancel/supersede for partials.
    """

    def __init__(
        self,
        session_id: str,
        source_language: str,
        target_language: str,
        send_json: Callable[[Dict], Awaitable[None]],
        asr_provider: ASRProvider,
        translation_provider: TranslationProvider,
        max_audio_queue_size: int = 50,
    ):
        self.session_id = session_id
        self.source_language = source_language
        self.target_language = target_language
        self.send_json = send_json
        self.asr_provider = asr_provider
        self.translation_provider = translation_provider

        # Choose scheduler mode
        if settings.scheduler_mode == "fixed500":
            self.scheduler = FixedIntervalBaselineScheduler(fixed_interval_ms=500)
        else:
            self.scheduler = AdaptiveStabilityScheduler(source_language=source_language)

        # Audio buffer queue with drop-oldest policy under backpressure
        self.audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=max_audio_queue_size)

        # Segment tracking: stable segment_id per utterance
        self.current_segment_id: str = str(uuid.uuid4())
        self.sequence_no: int = 1
        self.last_source_text: str = ""
        self._final_transcript_emitted: bool = False

        # Latency timestamps
        self.t_audio_started: float = 0.0
        self.t_first_transcript: float = 0.0
        self.t_first_translation: float = 0.0
        self.t_speech_ended: float = 0.0

        # Concurrency & Tasks
        self._audio_task: Optional[asyncio.Task] = None
        self._events_task: Optional[asyncio.Task] = None
        self._active_translation_task: Optional[asyncio.Task] = None
        self._active_translation_span: str = ""
        self._is_running: bool = False
        self._is_degraded: bool = False

    async def start(self) -> None:
        """Starts upstream ASR and background worker tasks."""
        self._is_running = True
        try:
            await self.asr_provider.start(self.source_language)
        except Exception as e:
            logger.error(f"Failed to start ASR provider: {e}")
            raise

        self._audio_task = asyncio.create_task(self._process_audio_queue())
        self._events_task = asyncio.create_task(self._consume_asr_events())

        await self.send_json(
            WSSessionStatus(
                state="streaming",
                provider="sarvam",
                session_id=self.session_id,
            ).model_dump()
        )

    async def push_audio(self, chunk: bytes) -> None:
        """Enqueues incoming PCM audio chunk. Implements drop-oldest on backpressure."""
        if not self._is_running:
            return

        if self.t_audio_started == 0.0:
            self.t_audio_started = time.perf_counter()

        if self.audio_queue.full():
            try:
                # Drop oldest chunk to prevent unbounded buffer delay
                _ = self.audio_queue.get_nowait()
                logger.warning(f"Audio backpressure in session {self.session_id}: dropped oldest chunk")
            except asyncio.QueueEmpty:
                pass

        await self.audio_queue.put(chunk)

    async def _process_audio_queue(self) -> None:
        """Worker that sends audio chunks to upstream ASR."""
        while self._is_running:
            try:
                chunk = await self.audio_queue.get()
                await self.asr_provider.send_audio(chunk)
                self.audio_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error forwarding audio chunk to ASR: {e}")
                if not self._is_running:
                    break

    async def _consume_asr_events(self) -> None:
        """Worker that consumes ASR events from upstream engine without blocking on translation."""
        try:
            async for asr_event in self.asr_provider.events():
                now = time.perf_counter()
                if self.t_first_transcript == 0.0:
                    self.t_first_transcript = now
                    logger.debug(f"First transcript latency: {(now - self.t_audio_started)*1000:.2f}ms")

                text = asr_event.text
                if not text:
                    continue

                self.last_source_text = text

                # 1. Immediately emit transcript event to client
                if asr_event.is_final:
                    self.t_speech_ended = now
                    self._final_transcript_emitted = True
                    await self.send_json(
                        WSTranscriptFinal(
                            segment_id=self.current_segment_id,
                            text=text,
                            timestamp=now,
                        ).model_dump()
                    )
                else:
                    await self.send_json(
                        WSTranscriptPartial(
                            segment_id=self.current_segment_id,
                            text=text,
                            timestamp=now,
                            confidence=asr_event.confidence,
                            stability_score=asr_event.stability_score,
                        ).model_dump()
                    )

                # 2. Feed hypothesis into stability scheduler
                decision: CommitDecision = self.scheduler.feed_hypothesis(
                    segment_id=self.current_segment_id,
                    hypothesis=text,
                    is_final=asr_event.is_final,
                    src=self.source_language,
                    tgt=self.target_language,
                )

                # 3. Schedule translation if commit rule triggered
                if decision.should_translate:
                    self._schedule_translation(decision)

                # 4. If utterance is finalized, rotate segment_id for next utterance
                if asr_event.is_final:
                    # Let the current translation finish before segment rotation
                    asyncio.create_task(self._rotate_segment_after_final(self.current_segment_id, text))
                    self.current_segment_id = str(uuid.uuid4())
                    self.sequence_no += 1
                    self.t_audio_started = 0.0
                    self.t_first_transcript = 0.0
                    self.t_first_translation = 0.0
                    self._final_transcript_emitted = False
                    self.last_source_text = ""

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in ASR event consumer loop: {e}", exc_info=True)
            await self._handle_provider_degradation("ASR upstream disconnected.")

    def _schedule_translation(self, decision: CommitDecision) -> None:
        """Dispatches translation in a non-blocking concurrent task with cancel/supersede for partials."""
        # Cancel previous partial task if still in flight and superseded by newer text
        if self._active_translation_task and not self._active_translation_task.done():
            if not decision.is_final:
                logger.debug(
                    f"Superseding in-flight partial translation '{self._active_translation_span}' with '{decision.text_to_translate}'"
                )
                self._active_translation_task.cancel()

        self._active_translation_span = decision.text_to_translate
        seg_id = self.current_segment_id

        # Fast path: cache hit
        if decision.cached_translation:
            asyncio.create_task(
                self._emit_cached_translation(
                    seg_id=seg_id,
                    source_text=decision.text_to_translate,
                    translated_text=decision.cached_translation,
                    is_final=decision.is_final,
                )
            )
            return

        # Slow path: network translation task
        task = asyncio.create_task(
            self._execute_translation_task(
                seg_id=seg_id,
                text=decision.text_to_translate,
                is_final=decision.is_final,
            )
        )
        self._active_translation_task = task

    async def _emit_cached_translation(
        self,
        seg_id: str,
        source_text: str,
        translated_text: str,
        is_final: bool,
    ) -> None:
        """Immediately emits cached translation to client."""
        now = time.perf_counter()
        if is_final:
            audio_b64 = None
            if settings.enable_tts and settings.is_sarvam_tts_configured:
                try:
                    import base64
                    from app.providers.sarvam_tts import SarvamTTSProvider
                    tts_prov = SarvamTTSProvider()
                    wav_data = await tts_prov.synthesize(translated_text, self.target_language)
                    audio_b64 = base64.b64encode(wav_data).decode("utf-8")
                except Exception as e:
                    logger.warning(f"TTS synthesis failed for cached final translation: {e}")

            await self.send_json(
                WSTranslationFinal(
                    segment_id=seg_id,
                    translated_text=translated_text,
                    source_text=source_text,
                    translation_latency_ms=0.0,
                    end_to_end_latency_ms=round((now - self.t_audio_started) * 1000, 2)
                    if self.t_audio_started
                    else 0.0,
                    audio_base64=audio_b64,
                ).model_dump()
            )
        else:
            await self.send_json(
                WSTranslationPartial(
                    segment_id=seg_id,
                    translated_text=translated_text,
                    source_text=source_text,
                ).model_dump()
            )

    async def _execute_translation_task(
        self,
        seg_id: str,
        text: str,
        is_final: bool,
    ) -> None:
        """Asynchronously executes translation call and emits results."""
        t_call_start = time.perf_counter()
        try:
            translated = await self.translation_provider.translate(
                text=text,
                src=self.source_language,
                tgt=self.target_language,
            )
            t_call_end = time.perf_counter()
            call_latency_ms = round((t_call_end - t_call_start) * 1000, 2)

            if self.t_first_translation == 0.0:
                self.t_first_translation = t_call_end

            # Record in scheduler (computes rewrites & updates cache)
            self.scheduler.record_translation_result(
                segment_id=seg_id,
                source_text=text,
                translated_text=translated,
                src=self.source_language,
                tgt=self.target_language,
            )

            # Emit translation event
            if is_final:
                e2e_latency_ms = (
                    round((t_call_end - self.t_audio_started) * 1000, 2)
                    if self.t_audio_started
                    else call_latency_ms
                )
                audio_b64 = None
                if settings.enable_tts and settings.is_sarvam_tts_configured:
                    try:
                        import base64
                        from app.providers.sarvam_tts import SarvamTTSProvider
                        tts_prov = SarvamTTSProvider()
                        wav_data = await tts_prov.synthesize(translated, self.target_language)
                        audio_b64 = base64.b64encode(wav_data).decode("utf-8")
                    except Exception as e:
                        logger.warning(f"TTS synthesis failed for final translation: {e}")

                await self.send_json(
                    WSTranslationFinal(
                        segment_id=seg_id,
                        translated_text=translated,
                        source_text=text,
                        translation_latency_ms=call_latency_ms,
                        end_to_end_latency_ms=e2e_latency_ms,
                        audio_base64=audio_b64,
                    ).model_dump()
                )

                # Persist completed segment and metrics to store (off-path)
                from app.db.repo import enqueue_segment, enqueue_metric
                metrics = self.scheduler.get_metrics(seg_id)
                enqueue_segment({
                    "id": seg_id,
                    "session_id": self.session_id,
                    "sequence_no": self.sequence_no,
                    "source_text": text,
                    "translated_text": translated,
                    "confidence": 1.0,
                    "stability_score": 1.0,
                    "rewrite_count": metrics.get("rewrite_count", 0),
                    "created_at": time.time(),
                })
                enqueue_metric({
                    "session_id": self.session_id,
                    "segment_id": seg_id,
                    "kind": "end_to_end_latency_ms",
                    "value_ms": e2e_latency_ms,
                    "provider": "sarvam",
                })
            else:
                await self.send_json(
                    WSTranslationPartial(
                        segment_id=seg_id,
                        translated_text=translated,
                        source_text=text,
                    ).model_dump()
                )

        except asyncio.CancelledError:
            logger.debug(f"Translation task for span '{text}' was superseded/cancelled")
        except Exception as e:
            logger.warning(f"Translation call failed: {e}")
            # Keep source captions alive, emit retryable error and set degraded state
            await self._handle_provider_degradation("Translation service degraded; showing transcript.")

    async def _handle_provider_degradation(self, reason: str) -> None:
        """Marks session as degraded without terminating it."""
        if not self._is_degraded:
            self._is_degraded = True
            await self.send_json(
                WSSessionStatus(
                    state="degraded",
                    provider="sarvam",
                    session_id=self.session_id,
                ).model_dump()
            )
            await self.send_json(
                WSError(
                    code=ErrorCode.TRANSLATION_FAILED.value,
                    safe_message=reason,
                    retryable=True,
                ).model_dump()
            )

    async def _rotate_segment_after_final(self, seg_id: str, final_text: str) -> None:
        """Ensures any in-flight final translation task is completed before segment state reset."""
        if self._active_translation_task and not self._active_translation_task.done():
            try:
                await asyncio.wait_for(self._active_translation_task, timeout=3.0)
            except Exception:
                pass

    async def handle_end(self) -> None:
        """Flushes audio and upstream ASR, waits for pending final translation, and emits ended state."""
        try:
            # 1. Drain audio queue to upstream ASR
            drain_deadline = time.perf_counter() + 2.0
            while not self.audio_queue.empty() and time.perf_counter() < drain_deadline:
                await asyncio.sleep(0.05)

            # 2. Flush ASR provider (sends silence to trigger VAD endpointing)
            await self.asr_provider.flush()

            # 3. Wait for final events from upstream ASR
            await asyncio.sleep(1.2)

            # 4. If there was transcribed text but no final commit was triggered yet, finalize it now
            if self.last_source_text and not self._final_transcript_emitted:
                now = time.perf_counter()
                self._final_transcript_emitted = True
                await self.send_json(
                    WSTranscriptFinal(
                        segment_id=self.current_segment_id,
                        text=self.last_source_text,
                        timestamp=now,
                    ).model_dump()
                )
                decision = CommitDecision(
                    should_translate=True,
                    text_to_translate=self.last_source_text,
                    is_final=True,
                    committed_text=self.last_source_text,
                    stability_score=1.0,
                    trigger_reason="session_end",
                )
                self._schedule_translation(decision)

            # 5. Wait for active translation task to complete
            if self._active_translation_task and not self._active_translation_task.done():
                await asyncio.wait_for(self._active_translation_task, timeout=4.0)
        except Exception as e:
            logger.warning(f"Error during pipeline flush on end: {e}")
        finally:
            await self.send_json(
                WSSessionStatus(
                    state="ended",
                    provider="sarvam",
                    session_id=self.session_id,
                ).model_dump()
            )
            await self.close()

    async def close(self) -> None:
        """Stops all tasks and closes the upstream ASR provider."""
        self._is_running = False
        if self._audio_task and not self._audio_task.done():
            self._audio_task.cancel()
        if self._events_task and not self._events_task.done():
            self._events_task.cancel()
        if self._active_translation_task and not self._active_translation_task.done():
            self._active_translation_task.cancel()

        try:
            await self.asr_provider.close()
        except Exception as e:
            logger.debug(f"Error closing ASR provider: {e}")
