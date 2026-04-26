import asyncio
import logging
import uuid
from typing import Optional

from app.config import settings
from app.db import clips_repo, weights_repo
from app.models.job import CancelledError, EditRequest, Job, JobStatus, Stage
from app.pipeline import registry
from app.pipeline import fewshot
from app.pipeline.boundary import detect_silences, snap_boundaries
from app.pipeline.progress import bus
from app.pipeline.signals import emotion as em
from app.pipeline.signals import laughter as lg
from app.pipeline.signals import retention as rt
from app.pipeline.signals import tempo as tp
from app.pipeline.signals import volume as vl
from app.pipeline.signals.fusion import (
    SignalBundle, audio_interest_score, extract_peaks,
)
from app.pipeline.stages import download as dl
from app.pipeline.stages import render as rd
from app.pipeline.stages import score as sc
from app.pipeline.stages.asr import AsrResult, transcribe

log = logging.getLogger(__name__)


async def _emit(job_id: str, stage: Stage, pct: float, message: str) -> None:
    await registry.update(job_id, current_stage=stage, progress_pct=pct, message=message)
    await bus.publish(job_id, {"stage": stage.value, "pct": pct, "message": message})


async def create_job(req: EditRequest) -> Job:
    job = Job(id=uuid.uuid4().hex[:12], source_url=req.url, template_id=req.template_id)
    await registry.put(job)
    return job


def _extract_signals_sync(audio_path, asr: AsrResult, duration: float, heatmap):
    bundle = SignalBundle(
        retention=rt.retention_series(heatmap, duration),
        volume=vl.volume_series(audio_path, duration),
        tempo=tp.tempo_series(asr, duration),
        laughter=lg.laughter_series(audio_path, duration),
        emotion_joy=em.emotion_series(audio_path, duration)["joy"],
        emotion_surprise=em.emotion_series(audio_path, duration)["surprise"],
    )
    silences = detect_silences(audio_path)
    return bundle, silences


async def _check_cancelled(job_id: str) -> None:
    job = await registry.get(job_id)
    if job and job.status == JobStatus.CANCELLED:
        raise CancelledError()


async def run_job(job_id: str, llm_model: Optional[str] = None) -> None:
    job = await registry.get(job_id)
    if job is None:
        log.error("run_job: unknown job %s", job_id)
        return

    await registry.update(job_id, status=JobStatus.RUNNING)

    try:
        # 1. DOWNLOAD
        await _check_cancelled(job_id)
        await _emit(job_id, Stage.DOWNLOAD, 5, "영상 다운로드 중…")
        result = await dl.download(job.source_url)
        await _emit(job_id, Stage.DOWNLOAD, 20, f"다운로드 완료 — {result.title}")

        # 2. ASR (GPU-heavy → thread)
        await _check_cancelled(job_id)
        await _emit(job_id, Stage.ASR, 22, "Whisper 자막 추출 중…")
        asr: AsrResult = await asyncio.to_thread(transcribe, result.audio_path)
        await _emit(job_id, Stage.ASR, 45, f"자막 {len(asr.words)}개 단어 추출")

        # 3. SIGNALS
        await _check_cancelled(job_id)
        await _emit(job_id, Stage.SIGNALS, 48, "오디오 신호 분석 중…")
        bundle, silences = await asyncio.to_thread(
            _extract_signals_sync, result.audio_path, asr, result.duration, result.heatmap,
        )
        weights = weights_repo.current_weights()
        score_ts = audio_interest_score(bundle, weights)
        peaks = extract_peaks(score_ts, bundle)
        note = "retention 없음 — 4개 신호로 진행" if bundle.retention is None else f"피크 {len(peaks)}개 탐지"
        await _emit(job_id, Stage.SIGNALS, 62, note)

        # 4. SCORING (fewshot from past 👍/👎)
        await _check_cancelled(job_id)
        examples = fewshot.sample()
        await _emit(job_id, Stage.SCORING, 65,
                    f"LLM 재미 구간 분석 중… (fewshot {len(examples)}개)")
        candidates = await sc.score_candidates(
            asr, peaks, fewshot=examples, llm_model=llm_model,
        )
        if not candidates:
            raise RuntimeError("LLM이 유효한 구간을 제안하지 않음")

        # Boundary snap
        for cand in candidates:
            cand.start, cand.end = snap_boundaries(cand.start, cand.end, asr, silences)
        await _emit(job_id, Stage.SCORING, 75, f"{len(candidates)}개 후보 선정")

        # 5. RENDER + persist
        total = len(candidates)
        active_model = llm_model or settings.default_llm_model
        for idx, cand in enumerate(candidates):
            cand.template_id = job.template_id
            await _emit(
                job_id, Stage.RENDER,
                75 + (20 * idx / total),
                f"렌더링 {idx + 1}/{total} — {cand.title}",
            )
            await rd.render(result.video_path, cand, clip_id=f"{job_id}_{idx}", asr=asr)

            clip_db_id = clips_repo.save_clip(
                source_url=job.source_url,
                source_video_id=result.video_id,
                start_time=cand.start,
                end_time=cand.end,
                title=cand.title,
                reason=cand.reason,
                template_id=cand.template_id,
                llm_model=active_model,
                llm_score=cand.score,
                weights_snapshot=weights,
            )
            clips_repo.save_signals(clip_db_id, _clip_signal_stats(bundle, cand.start, cand.end))
            cand.clip_id = clip_db_id

        await registry.update(
            job_id, status=JobStatus.COMPLETED, progress_pct=100.0,
            candidates=candidates, message="완료",
        )
        await bus.publish(job_id, {"stage": "done", "pct": 100, "message": "완료"})

    except CancelledError:
        log.info("job %s cancelled", job_id)
    except Exception as e:
        log.exception("job %s failed", job_id)
        await registry.update(job_id, status=JobStatus.FAILED, error=str(e), message=f"실패: {e}")
        await bus.publish(job_id, {"stage": "error", "pct": 0, "message": str(e)})


def _clip_signal_stats(bundle: SignalBundle, start: float, end: float) -> dict:
    i0, i1 = int(start), max(int(end), int(start) + 1)

    def _peak(arr):
        return float(arr[i0:i1].max()) if arr.size > i0 else 0.0

    def _avg(arr):
        return float(arr[i0:i1].mean()) if arr.size > i0 else 0.0

    return {
        "retention_avg": _avg(bundle.retention) if bundle.retention is not None else None,
        "laughter_peak": _peak(bundle.laughter),
        "volume_peak": _peak(bundle.volume),
        "emotion_joy_peak": _peak(bundle.emotion_joy),
        "emotion_surprise_peak": _peak(bundle.emotion_surprise),
        "tempo_change": _peak(bundle.tempo),
        "clip_duration": end - start,
    }
