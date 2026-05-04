from __future__ import annotations

import os
import random
import unicodedata
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.entities import (
    Campus,
    Course,
    CourseKind,
    DegreeProgram,
    InvitationLink,
    PresentationToken,
    Professor,
    Room,
    Student,
    StudentCourseHistory,
    StudentCourseRequest,
    StudentCourseStatus,
)
from app.schemas import (
    PresentationLinkCreate,
    PresentationLinkRead,
    PresentationStatsRead,
    PresentationStudentChoicesCreate,
    PresentationStudentChoicesRead,
    PresentationStudentCreate,
    PresentationStudentCreatedRead,
    PresentationStudentTokenRead,
)
from app.services.student_planning import build_student_suggestions, course_eligible_for_student

router = APIRouter()


@router.get("/stats", response_model=PresentationStatsRead)
def stats(db: Session = Depends(get_db)) -> dict[str, float | int | datetime | None]:
    professors = db.query(Professor).count()
    students = db.query(Student).count()
    minimum_student_target = professors * 10
    return {
        "campuses": db.query(Campus).count(),
        "degree_programs": db.query(DegreeProgram).count(),
        "courses": db.query(Course).count(),
        "professors": professors,
        "students": students,
        "student_teacher_ratio": round(students / professors, 2) if professors else float(students),
        "minimum_student_target": minimum_student_target,
        "students_needed_for_minimum": max(0, minimum_student_target - students),
        "rooms": db.query(Room).count(),
        "threads": settings.optigrade_max_threads,
        "cpu_count": os.cpu_count() or 1,
        "memory_total_mb": memory_total_mb(),
        "updated_at": datetime.now(timezone.utc),
    }


@router.post("/teacher-link", response_model=PresentationLinkRead)
def create_teacher_link(
    payload: PresentationLinkCreate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    professor = db.get(Professor, payload.professor_id) if payload.professor_id else first_professor(db)
    if not professor:
        raise HTTPException(status_code=404, detail="Professor nao encontrado para o piloto")
    invitation = InvitationLink(
        professor_id=professor.id,
        token=token_urlsafe(48),
        semester=payload.semester,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    db.add(invitation)
    db.commit()
    return {
        "token": invitation.token,
        "url": f"{settings.next_public_app_url.rstrip('/')}/teacher/{invitation.token}",
        "expires_at": invitation.expires_at,
        "kind": "teacher",
    }


@router.post("/teacher-link/{token}/revoke")
def revoke_teacher_link(token: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    invitation = db.query(InvitationLink).filter(InvitationLink.token == token).one_or_none()
    if invitation:
        invitation.revoked = True
        db.commit()
    return {"ok": True}


@router.post("/student-link", response_model=PresentationLinkRead)
def create_student_link(
    payload: PresentationLinkCreate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    degree_program = (
        db.get(DegreeProgram, payload.degree_program_id)
        if payload.degree_program_id
        else production_engineering_program(db)
    )
    if not degree_program:
        raise HTTPException(status_code=404, detail="Engenharia de Producao nao encontrada no piloto")
    presentation_token = PresentationToken(
        token=token_urlsafe(36),
        kind="student",
        semester=payload.semester,
        degree_program_id=degree_program.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        revoked=False,
    )
    db.add(presentation_token)
    db.commit()
    return {
        "token": presentation_token.token,
        "url": f"{settings.next_public_app_url.rstrip('/')}/trabalho/alunos/{presentation_token.token}",
        "expires_at": presentation_token.expires_at,
        "kind": "student",
    }


@router.post("/student-link/{token}/revoke")
def revoke_student_link(token: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    presentation_token = (
        db.query(PresentationToken).filter(PresentationToken.token == token).one_or_none()
    )
    if presentation_token:
        presentation_token.revoked = True
        db.commit()
    return {"ok": True}


@router.get("/student-tokens/{token}", response_model=PresentationStudentTokenRead)
def get_student_token(token: str, db: Session = Depends(get_db)) -> dict[str, object]:
    presentation_token = require_student_token(db, token)
    degree_program = require_degree_program(db, presentation_token.degree_program_id)
    courses = courses_for_program(db, degree_program.id)
    return {
        "token": presentation_token.token,
        "semester": presentation_token.semester,
        "degree_program": degree_program,
        "courses": courses,
    }


@router.post(
    "/student-tokens/{token}/students",
    response_model=PresentationStudentCreatedRead,
)
def create_student_for_token(
    token: str,
    payload: PresentationStudentCreate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    presentation_token = require_student_token(db, token)
    degree_program = require_degree_program(db, presentation_token.degree_program_id)
    rng = random.Random(f"{token}:{payload.name}:{payload.email or ''}")
    student = Student(
        name=payload.name.strip(),
        email=payload.email,
        registration_number=f"TRAB-{rng.randrange(100000, 999999)}",
        degree_program_id=degree_program.id,
        current_semester=rng.randint(2, 6),
    )
    db.add(student)
    db.flush()
    seed_random_history(db, student, rng)
    db.commit()
    db.refresh(student)
    return {
        "student": student,
        "suggestions": {
            "student_id": student.id,
            "target_semester": presentation_token.semester,
            "suggestions": build_student_suggestions(db, student, presentation_token.semester),
        },
    }


@router.post(
    "/student-tokens/{token}/students/{student_id}/choices",
    response_model=PresentationStudentChoicesRead,
)
def submit_student_choices(
    token: str,
    student_id: str,
    payload: PresentationStudentChoicesCreate,
    db: Session = Depends(get_db),
) -> dict[str, list[StudentCourseRequest]]:
    presentation_token = require_student_token(db, token)
    student = db.get(Student, student_id)
    if not student or student.degree_program_id != presentation_token.degree_program_id:
        raise HTTPException(status_code=404, detail="Aluno nao encontrado para este QR Code")

    requests: list[StudentCourseRequest] = []
    for index, course_id in enumerate(payload.course_ids, start=1):
        course = db.get(Course, course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Cadeira nao encontrada")
        if not course_eligible_for_student(db, student, course):
            continue
        request = StudentCourseRequest(
            student_id=student.id,
            course_id=course.id,
            target_semester=presentation_token.semester,
            priority=max(1, 5 - index + 1),
            preference_order=index,
            alternative_group="fila-apresentacao" if payload.queue_mode else f"course:{course.id}",
            stage="pre_enrollment",
            source="presentation",
            note="Escolha enviada por QR Code da apresentacao",
        )
        db.add(request)
        requests.append(request)
    if not requests:
        raise HTTPException(status_code=422, detail="Nenhuma cadeira elegivel foi enviada")
    db.commit()
    for request in requests:
        db.refresh(request)
    return {"requests": requests}


def first_professor(db: Session) -> Professor | None:
    return db.query(Professor).order_by(Professor.name).first()


def production_engineering_program(db: Session) -> DegreeProgram | None:
    candidates = [
        item
        for item in db.query(DegreeProgram).order_by(DegreeProgram.name).all()
        if is_production_engineering(item.name)
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (is_synthetic_program(item), -course_count(db, item.id), item.name))[0]


def is_synthetic_program(program: DegreeProgram) -> bool:
    value = normalize_text(f"{program.name} {program.code or ''}")
    return "e2e" in value or "pilot" in value


def course_count(db: Session, degree_program_id: str) -> int:
    return db.query(Course).filter(Course.degree_program_id == degree_program_id).count()


def is_production_engineering(value: str) -> bool:
    normalized = normalize_text(value)
    return "engenharia" in normalized and "producao" in normalized


def normalize_text(value: str) -> str:
    stripped = unicodedata.normalize("NFKD", value)
    return "".join(char for char in stripped if not unicodedata.combining(char)).lower()


def require_student_token(db: Session, token: str) -> PresentationToken:
    presentation_token = db.query(PresentationToken).filter(PresentationToken.token == token).one_or_none()
    now = datetime.now(timezone.utc)
    if (
        not presentation_token
        or presentation_token.kind != "student"
        or presentation_token.revoked
        or as_aware(presentation_token.expires_at) < now
    ):
        raise HTTPException(status_code=404, detail="QR Code expirado ou revogado")
    return presentation_token


def as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def require_degree_program(db: Session, degree_program_id: str | None) -> DegreeProgram:
    degree_program = db.get(DegreeProgram, degree_program_id) if degree_program_id else None
    if not degree_program:
        raise HTTPException(status_code=404, detail="Curso nao encontrado para o QR Code")
    return degree_program


def courses_for_program(db: Session, degree_program_id: str) -> list[Course]:
    return (
        db.query(Course)
        .filter(Course.degree_program_id == degree_program_id)
        .order_by(Course.recommended_semester, Course.name)
        .all()
    )


def seed_random_history(db: Session, student: Student, rng: random.Random) -> None:
    courses = (
        db.query(Course)
        .filter(
            Course.degree_program_id == student.degree_program_id,
            Course.kind == CourseKind.mandatory,
            Course.recommended_semester < student.current_semester,
        )
        .order_by(Course.recommended_semester, Course.name)
        .all()
    )
    for course in courses:
        chance = rng.random()
        if chance < 0.68:
            status = StudentCourseStatus.completed
            grade = round(rng.uniform(6.0, 9.5), 1)
        elif chance < 0.84:
            status = StudentCourseStatus.failed
            grade = round(rng.uniform(2.0, 5.8), 1)
        else:
            continue
        db.add(
            StudentCourseHistory(
                student_id=student.id,
                course_id=course.id,
                status=status,
                semester=f"202{rng.randint(3, 5)}/{rng.randint(1, 2)}",
                grade=grade,
            )
        )


def memory_total_mb() -> int | None:
    try:
        with open("/proc/meminfo", encoding="utf-8") as meminfo:
            for line in meminfo:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        return None
    return None
