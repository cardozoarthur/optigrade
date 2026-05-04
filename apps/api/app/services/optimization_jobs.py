from __future__ import annotations

import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import OptimizationRun, RunStatus
from app.services.enrollment import run_enrollment_round
from app.services.optimizer import run_optimization

FINAL_STATUSES = {RunStatus.feasible, RunStatus.infeasible, RunStatus.failed}

_executor = ThreadPoolExecutor(max_workers=max(1, min(settings.optigrade_max_threads, 4)))
_queued_run_ids: set[str] = set()
_queue_lock = threading.Lock()


def enqueue_optimization_run(run_id: str) -> None:
    with _queue_lock:
        if run_id in _queued_run_ids:
            return
        _queued_run_ids.add(run_id)
    _executor.submit(_run_optimization_job, run_id)


def recover_optimization_jobs() -> None:
    with SessionLocal() as db:
        interrupted = (
            db.query(OptimizationRun)
            .filter(OptimizationRun.status == RunStatus.running)
            .all()
        )
        for run in interrupted:
            run.status = RunStatus.failed
            run.finished_at = datetime.now(timezone.utc)
            run.explanation = "Execucao interrompida por reinicio da API."
            run.metrics = run.metrics | {"error": "api_restart"}
        pending = (
            db.query(OptimizationRun)
            .filter(OptimizationRun.status == RunStatus.pending)
            .all()
        )
        db.commit()

    for run in pending:
        enqueue_optimization_run(run.id)


def find_active_run(
    db: Session,
    *,
    semester: str,
    profile: str,
    parameters: dict,
) -> OptimizationRun | None:
    runs = (
        db.query(OptimizationRun)
        .filter(
            OptimizationRun.semester == semester,
            OptimizationRun.profile == profile,
            OptimizationRun.status.in_([RunStatus.pending, RunStatus.running]),
        )
        .order_by(OptimizationRun.created_at.desc())
        .limit(25)
        .all()
    )
    return next((run for run in runs if run.parameters == parameters), None)


def _run_optimization_job(run_id: str) -> None:
    try:
        with SessionLocal() as db:
            run = db.get(OptimizationRun, run_id)
            if not run or run.status in FINAL_STATUSES:
                return
            result = run_optimization(db, run)
            _maybe_run_automatic_enrollment(db, result)
    except Exception as exc:  # pragma: no cover - defensive production path
        _mark_run_failed(run_id, exc)
    finally:
        with _queue_lock:
            _queued_run_ids.discard(run_id)


def _mark_run_failed(run_id: str, exc: Exception) -> None:
    with SessionLocal() as db:
        run = db.get(OptimizationRun, run_id)
        if not run:
            return
        run.status = RunStatus.failed
        run.finished_at = datetime.now(timezone.utc)
        run.explanation = "Falha ao executar otimizacao em background."
        run.metrics = run.metrics | {
            "error": str(exc),
            "traceback": traceback.format_exc(limit=8),
        }
        db.commit()


def _maybe_run_automatic_enrollment(db: Session, run: OptimizationRun) -> None:
    auto_enrollment = bool(run.parameters.get("auto_enrollment", True))
    if not auto_enrollment or run.metrics.get("student_demand_requests", 0) <= 0:
        return
    stage = str(run.parameters.get("enrollment_stage") or "pre_enrollment")
    summary = run_enrollment_round(
        db,
        target_semester=run.semester,
        stage=stage,
        run_id=run.id,
    )
    run.metrics = run.metrics | {"enrollment_round": summary}
    db.commit()
