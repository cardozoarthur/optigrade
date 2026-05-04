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
from app.services.optimizer import run_optimization, validate_manual_assignments
from app.services.enrollment import run_enrollment_round

router = APIRouter()


@router.get("/runs", response_model=list[OptimizationRunRead])
def list_runs(db: Session = Depends(get_db)) -> list[OptimizationRun]:
    return db.query(OptimizationRun).order_by(OptimizationRun.created_at.desc()).limit(25).all()


@router.post("/runs", response_model=OptimizationRunRead)
def create_run(payload: OptimizationRunCreate, db: Session = Depends(get_db)) -> OptimizationRun:
    run = OptimizationRun(
        semester=payload.semester,
        profile=payload.profile,
        parameters=payload.parameters,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    result = run_optimization(db, run)
    maybe_run_automatic_enrollment(db, result)
    db.refresh(result)
    return result


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
    next_run = OptimizationRun(
        semester=run.semester,
        profile=run.profile,
        parameters=run.parameters | {"parent_run_id": run.id, "mode": "partial_reoptimization"},
    )
    db.add(next_run)
    db.commit()
    db.refresh(next_run)
    result = run_optimization(db, next_run)
    maybe_run_automatic_enrollment(db, result)
    db.refresh(result)
    return result


def maybe_run_automatic_enrollment(db: Session, run: OptimizationRun) -> None:
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
