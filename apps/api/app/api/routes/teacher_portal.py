from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    Course,
    InvitationLink,
    ProfessorAvailability,
    ProfessorConstraint,
    ProfessorCoursePreference,
)
from app.schemas import TeacherPortalRead, TeacherPortalSubmit
from app.services.constraint_intelligence import interpret_teacher_constraint
from app.services.portal_results import as_aware, build_teacher_portal_result

router = APIRouter()


def _load_invitation(token: str, db: Session) -> InvitationLink:
    invitation = db.query(InvitationLink).filter(InvitationLink.token == token).one_or_none()
    now = datetime.now(timezone.utc)
    if not invitation or invitation.revoked or as_aware(invitation.expires_at) < now:
        raise HTTPException(status_code=404, detail="Convite invalido ou expirado")
    return invitation


@router.get("/{token}", response_model=TeacherPortalRead)
def get_portal(token: str, db: Session = Depends(get_db)) -> TeacherPortalRead:
    invitation = _load_invitation(token, db)
    courses = db.query(Course).order_by(Course.recommended_semester, Course.name).all()
    return TeacherPortalRead(
        professor_id=invitation.professor_id,
        professor_name=invitation.professor.name,
        semester=invitation.semester,
        submitted_at=invitation.submitted_at,
        courses=courses,
    )


@router.post("/{token}/submit")
def submit_constraints(
    token: str, payload: TeacherPortalSubmit, db: Session = Depends(get_db)
) -> dict[str, int | str]:
    invitation = _load_invitation(token, db)
    professor_id = invitation.professor_id

    db.query(ProfessorAvailability).filter(
        ProfessorAvailability.professor_id == professor_id,
        ProfessorAvailability.source == "teacher",
    ).delete()
    db.query(ProfessorCoursePreference).filter(
        ProfessorCoursePreference.professor_id == professor_id
    ).delete()

    for item in payload.availability:
        db.add(ProfessorAvailability(professor_id=professor_id, **item.model_dump()))
    for item in payload.course_preferences:
        db.add(ProfessorCoursePreference(professor_id=professor_id, **item.model_dump()))
    for item in payload.natural_language_constraints:
        interpreted = interpret_teacher_constraint(item.text)
        db.add(
            ProfessorConstraint(
                professor_id=professor_id,
                natural_language=item.text,
                structured_rule={
                    "rule": interpreted.rule,
                    "confidence": interpreted.confidence,
                    "explanation": interpreted.explanation,
                },
                strength=item.strength,
                confirmed=False,
            )
        )

    invitation.submitted_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "status": "submitted",
        "availability": len(payload.availability),
        "course_preferences": len(payload.course_preferences),
        "natural_language_constraints": len(payload.natural_language_constraints),
    }


@router.get("/{token}/result")
def get_portal_result(token: str, db: Session = Depends(get_db)) -> dict[str, object]:
    invitation = _load_invitation(token, db)
    return build_teacher_portal_result(
        db,
        professor_id=invitation.professor_id,
        semester=invitation.semester,
        submitted_after=invitation.submitted_at,
    )
