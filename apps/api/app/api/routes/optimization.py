from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Assignment, OptimizationRun
from app.schemas import (
    AssignmentRead,
    ManualAdjustmentCreate,
    OptimizationRunCreate,
    OptimizationRunRead,
)
from app.services.optimization_jobs import enqueue_optimization_run, find_active_run
from app.services.optimizer import validate_manual_assignments

router = APIRouter()


@router.get("/runs", response_model=list[OptimizationRunRead])
def list_runs(db: Session = Depends(get_db)) -> list[OptimizationRun]:
    return db.query(OptimizationRun).order_by(OptimizationRun.created_at.desc()).limit(25).all()


@router.post("/runs", response_model=OptimizationRunRead)
def create_run(payload: OptimizationRunCreate, db: Session = Depends(get_db)) -> OptimizationRun:
    active_run = find_active_run(
        db,
        semester=payload.semester,
        profile=payload.profile,
        parameters=payload.parameters,
    )
    if active_run:
        enqueue_optimization_run(active_run.id)
        return active_run

    run = OptimizationRun(
        semester=payload.semester,
        profile=payload.profile,
        parameters=payload.parameters,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    enqueue_optimization_run(run.id)
    return run


@router.get("/runs/{run_id}", response_model=OptimizationRunRead)
def get_run(run_id: str, db: Session = Depends(get_db)) -> OptimizationRun:
    run = db.get(OptimizationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")
    return run


@router.get("/runs/{run_id}/assignments", response_model=list[AssignmentRead])
def get_assignments(run_id: str, db: Session = Depends(get_db)) -> list[Assignment]:
    if not db.get(OptimizationRun, run_id):
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")
    return (
        db.query(Assignment)
        .filter(Assignment.run_id == run_id)
        .order_by(Assignment.course_id, Assignment.session_index)
        .all()
    )


@router.post("/runs/{run_id}/manual-adjustments")
def manual_adjustment(
    run_id: str, payload: ManualAdjustmentCreate, db: Session = Depends(get_db)
) -> dict[str, object]:
    run = db.get(OptimizationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")

    if payload.assignment_id:
        assignment = db.get(Assignment, payload.assignment_id)
        if not assignment or assignment.run_id != run_id:
            raise HTTPException(status_code=404, detail="Alocacao nao encontrada")
    else:
        assignment = Assignment(run_id=run_id)

    for key, value in payload.model_dump(exclude={"assignment_id"}).items():
        setattr(assignment, key, value)
    assignment.origin = "manual"
    db.add(assignment)
    db.commit()
    conflicts = validate_manual_assignments(db, run_id)
    return {"assignment_id": assignment.id, "hard_conflicts": conflicts}


@router.post("/runs/{run_id}/reoptimize", response_model=OptimizationRunRead)
def reoptimize(run_id: str, db: Session = Depends(get_db)) -> OptimizationRun:
    run = db.get(OptimizationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")
    parameters = run.parameters | {"parent_run_id": run.id, "mode": "partial_reoptimization"}
    active_run = find_active_run(
        db,
        semester=run.semester,
        profile=run.profile,
        parameters=parameters,
    )
    if active_run:
        enqueue_optimization_run(active_run.id)
        return active_run

    next_run = OptimizationRun(
        semester=run.semester,
        profile=run.profile,
        parameters=parameters,
    )
    db.add(next_run)
    db.commit()
    db.refresh(next_run)
    enqueue_optimization_run(next_run.id)
    return next_run
