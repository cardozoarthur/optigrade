from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    InvitationLink,
    Professor,
    ProfessorAvailability,
    ProfessorContract,
    ProfessorConstraint,
    ProfessorCoursePreference,
    ProfessorQualification,
)
from app.schemas import (
    BorrowedProfessorCreate,
    InvitationRead,
    NaturalLanguageConstraintCreate,
    ProfessorAvailabilityCreate,
    ProfessorContractCreate,
    ProfessorCoursePreferenceCreate,
    ProfessorCreate,
    ProfessorQualificationCreate,
    ProfessorRead,
    TeacherPortalSubmit,
)
from app.services.constraint_intelligence import interpret_teacher_constraint

router = APIRouter()


@router.get("", response_model=list[ProfessorRead])
def list_professors(db: Session = Depends(get_db)) -> list[Professor]:
    return db.query(Professor).order_by(Professor.name).all()


@router.post("", response_model=ProfessorRead)
def create_professor(payload: ProfessorCreate, db: Session = Depends(get_db)) -> Professor:
    professor = Professor(**payload.model_dump())
    db.add(professor)
    db.commit()
    db.refresh(professor)
    return professor


@router.put("/{professor_id}", response_model=ProfessorRead)
def update_professor(
    professor_id: str, payload: ProfessorCreate, db: Session = Depends(get_db)
) -> Professor:
    professor = require_professor(db, professor_id)
    for key, value in payload.model_dump().items():
        setattr(professor, key, value)
    db.commit()
    db.refresh(professor)
    return professor


@router.delete("/{professor_id}")
def delete_professor(professor_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    professor = require_professor(db, professor_id)
    db.delete(professor)
    db.commit()
    return {"ok": True}


@router.post("/borrowed", response_model=ProfessorRead)
def create_borrowed_professor(
    payload: BorrowedProfessorCreate, db: Session = Depends(get_db)
) -> Professor:
    if payload.min_hours > payload.max_hours:
        raise HTTPException(status_code=422, detail="Carga minima nao pode exceder a maxima")
    if not payload.semester.strip():
        raise HTTPException(status_code=422, detail="Professor emprestado precisa de semestre")

    professor = Professor(
        name=payload.name,
        email=payload.email,
        department=payload.department,
    )
    db.add(professor)
    db.flush()
    db.add(
        ProfessorContract(
            professor_id=professor.id,
            min_hours=payload.min_hours,
            max_hours=payload.max_hours,
            regime=payload.regime,
            semester=payload.semester,
            is_borrowed=True,
            borrowed_from_department=payload.borrowed_from_department,
            legal_notes=payload.legal_notes,
            loan_notes=payload.loan_notes,
        )
    )
    for window in payload.availability:
        db.add(ProfessorAvailability(professor_id=professor.id, **window.model_dump()))
    db.commit()
    db.refresh(professor)
    return professor


@router.get("/{professor_id}", response_model=ProfessorRead)
def get_professor(professor_id: str, db: Session = Depends(get_db)) -> Professor:
    return require_professor(db, professor_id)


@router.post("/{professor_id}/contract", response_model=ProfessorRead)
def upsert_contract(
    professor_id: str, payload: ProfessorContractCreate, db: Session = Depends(get_db)
) -> Professor:
    professor = require_professor(db, professor_id)
    if payload.min_hours > payload.max_hours:
        raise HTTPException(status_code=422, detail="Carga minima nao pode exceder a maxima")
    if payload.is_borrowed and not payload.semester:
        raise HTTPException(status_code=422, detail="Professor emprestado precisa de semestre")

    contract = professor.contract or ProfessorContract(professor_id=professor_id)
    for key, value in payload.model_dump().items():
        setattr(contract, key, value)
    db.add(contract)
    db.commit()
    db.refresh(professor)
    return professor


@router.post("/{professor_id}/qualifications")
def add_qualification(
    professor_id: str, payload: ProfessorQualificationCreate, db: Session = Depends(get_db)
) -> dict[str, str]:
    if not db.get(Professor, professor_id):
        raise HTTPException(status_code=404, detail="Professor nao encontrado")
    qualification = ProfessorQualification(professor_id=professor_id, **payload.model_dump())
    db.add(qualification)
    db.commit()
    return {"id": qualification.id}


@router.post("/{professor_id}/availability")
def add_availability(
    professor_id: str, payload: ProfessorAvailabilityCreate, db: Session = Depends(get_db)
) -> dict[str, str]:
    if not db.get(Professor, professor_id):
        raise HTTPException(status_code=404, detail="Professor nao encontrado")
    if payload.end_minute <= payload.start_minute:
        raise HTTPException(status_code=422, detail="Janela de horario invalida")
    availability = ProfessorAvailability(professor_id=professor_id, **payload.model_dump())
    db.add(availability)
    db.commit()
    return {"id": availability.id}


@router.post("/{professor_id}/course-preferences")
def add_course_preference(
    professor_id: str, payload: ProfessorCoursePreferenceCreate, db: Session = Depends(get_db)
) -> dict[str, str]:
    if not db.get(Professor, professor_id):
        raise HTTPException(status_code=404, detail="Professor nao encontrado")
    preference = ProfessorCoursePreference(professor_id=professor_id, **payload.model_dump())
    db.add(preference)
    db.commit()
    return {"id": preference.id}


@router.post("/{professor_id}/constraints")
def add_natural_constraint(
    professor_id: str, payload: NaturalLanguageConstraintCreate, db: Session = Depends(get_db)
) -> dict[str, str]:
    if not db.get(Professor, professor_id):
        raise HTTPException(status_code=404, detail="Professor nao encontrado")
    interpreted = interpret_teacher_constraint(payload.text)
    constraint = ProfessorConstraint(
        professor_id=professor_id,
        natural_language=payload.text,
        structured_rule={
            "rule": interpreted.rule,
            "confidence": interpreted.confidence,
            "explanation": interpreted.explanation,
            "source": "authenticated-professor",
        },
        strength=payload.strength,
        confirmed=False,
    )
    db.add(constraint)
    db.commit()
    return {"id": constraint.id}


@router.post("/{professor_id}/preference-batch")
def add_preference_batch(
    professor_id: str, payload: TeacherPortalSubmit, db: Session = Depends(get_db)
) -> dict[str, int]:
    if not db.get(Professor, professor_id):
        raise HTTPException(status_code=404, detail="Professor nao encontrado")

    for item in payload.availability:
        if item.end_minute <= item.start_minute:
            raise HTTPException(status_code=422, detail="Janela de horario invalida")
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
                    "source": "authenticated-professor",
                },
                strength=item.strength,
                confirmed=False,
            )
        )

    db.commit()
    return {
        "availability": len(payload.availability),
        "course_preferences": len(payload.course_preferences),
        "natural_language_constraints": len(payload.natural_language_constraints),
    }


@router.post("/{professor_id}/invitations", response_model=InvitationRead)
def create_invitation(
    professor_id: str, semester: str = "2026/2", db: Session = Depends(get_db)
) -> InvitationLink:
    if not db.get(Professor, professor_id):
        raise HTTPException(status_code=404, detail="Professor nao encontrado")
    invitation = InvitationLink(
        professor_id=professor_id,
        token=token_urlsafe(48),
        semester=semester,
        expires_at=datetime.now(timezone.utc) + timedelta(days=21),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation


def require_professor(db: Session, professor_id: str) -> Professor:
    professor = db.get(Professor, professor_id)
    if not professor:
        raise HTTPException(status_code=404, detail="Professor nao encontrado")
    return professor
