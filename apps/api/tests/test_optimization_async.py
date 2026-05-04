from app.api.routes import optimization
from app.models.entities import OptimizationRun, RunStatus
from app.schemas import OptimizationRunCreate


def test_create_run_returns_pending_and_enqueues_background_job(monkeypatch, db_session) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(optimization, "enqueue_optimization_run", lambda run_id: enqueued.append(run_id))

    run = optimization.create_run(
        OptimizationRunCreate(
            semester="2026/2",
            profile="fast",
            parameters={"attempts": 4, "local_steps": 2},
        ),
        db_session,
    )

    assert run.status == RunStatus.pending
    assert run.finished_at is None
    assert enqueued == [run.id]


def test_create_run_reuses_equivalent_active_run(monkeypatch, db_session) -> None:
    enqueued: list[str] = []
    existing = OptimizationRun(
        semester="2026/2",
        profile="fast",
        parameters={"attempts": 4, "local_steps": 2},
        status=RunStatus.running,
    )
    db_session.add(existing)
    db_session.commit()
    monkeypatch.setattr(optimization, "enqueue_optimization_run", lambda run_id: enqueued.append(run_id))

    run = optimization.create_run(
        OptimizationRunCreate(
            semester="2026/2",
            profile="fast",
            parameters={"attempts": 4, "local_steps": 2},
        ),
        db_session,
    )

    assert run.id == existing.id
    assert enqueued == [existing.id]


def test_reoptimize_returns_new_pending_run(monkeypatch, db_session) -> None:
    enqueued: list[str] = []
    previous = OptimizationRun(
        semester="2026/2",
        profile="balanced",
        parameters={"student_demand_only": True},
        status=RunStatus.feasible,
    )
    db_session.add(previous)
    db_session.commit()
    monkeypatch.setattr(optimization, "enqueue_optimization_run", lambda run_id: enqueued.append(run_id))

    run = optimization.reoptimize(previous.id, db_session)

    assert run.id != previous.id
    assert run.status == RunStatus.pending
    assert run.parameters["parent_run_id"] == previous.id
    assert run.parameters["mode"] == "partial_reoptimization"
    assert enqueued == [run.id]
