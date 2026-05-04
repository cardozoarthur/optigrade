from __future__ import annotations

from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.entities import (
    Campus,
    Course,
    CourseRestriction,
    DegreeProgram,
    OptimizationRun,
    Professor,
    Room,
    Student,
    StudentCourseRequest,
    TimeSlot,
)
from app.services.optimizer import build_snapshot, diagnose_snapshot


def build_readiness_report(db: Session, semester: str = "2026/2") -> dict[str, Any]:
    db.execute(text("SELECT 1"))
    counts = {
        "campuses": count_rows(db, Campus),
        "degree_programs": count_rows(db, DegreeProgram),
        "courses": count_rows(db, Course),
        "course_restrictions": count_rows(db, CourseRestriction),
        "students": count_rows(db, Student),
        "student_course_requests": count_rows(db, StudentCourseRequest),
        "professors": count_rows(db, Professor),
        "rooms": count_rows(db, Room),
        "time_slots": count_rows(db, TimeSlot),
        "optimization_runs": count_rows(db, OptimizationRun),
    }
    missing_data = [
        key
        for key in ("courses", "professors", "rooms", "time_slots")
        if counts[key] == 0
    ]
    precheck = diagnose_snapshot(build_snapshot(db, semester=semester))
    latest_run = (
        db.query(OptimizationRun).order_by(OptimizationRun.created_at.desc()).first()
    )

    return {
        "status": "ready" if not missing_data and not precheck else "degraded",
        "database": "ok",
        "semester": semester,
        "counts": counts,
        "missing_required_data": missing_data,
        "optimization_precheck": precheck,
        "latest_run": latest_run_payload(latest_run),
    }


def count_rows(db: Session, model: type) -> int:
    return int(db.query(func.count(model.id)).scalar() or 0)


def latest_run_payload(run: OptimizationRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "status": run.status.value,
        "score": run.score,
        "hard_conflicts": (run.metrics or {}).get("hard_conflicts"),
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }
