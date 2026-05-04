from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import StudentEnrollment
from app.schemas import EnrollmentRoundCreate, EnrollmentRoundRead, StudentEnrollmentRead
from app.services.enrollment import run_enrollment_round

router = APIRouter()


@router.get("/enrollments", response_model=list[StudentEnrollmentRead])
def list_enrollments(
    target_semester: str = "2026/2",
    stage: str | None = None,
    db: Session = Depends(get_db),
) -> list[StudentEnrollment]:
    query = db.query(StudentEnrollment).filter(
        StudentEnrollment.target_semester == target_semester
    )
    if stage:
        query = query.filter(StudentEnrollment.stage == stage)
    return query.order_by(
        StudentEnrollment.status,
        StudentEnrollment.course_id,
        StudentEnrollment.score.desc(),
    ).all()


@router.post("/rounds", response_model=EnrollmentRoundRead)
def create_enrollment_round(
    payload: EnrollmentRoundCreate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return run_enrollment_round(
        db,
        target_semester=payload.target_semester,
        stage=payload.stage,
        run_id=payload.run_id,
    )
