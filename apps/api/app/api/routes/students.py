import unicodedata

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    Course,
    CourseRestriction,
    ConstraintStrength,
    DegreeProgram,
    Student,
    StudentCourseHistory,
    StudentCourseRequest,
    StudentEnrollment,
)
from app.schemas import (
    CourseRestrictionBatchCreate,
    CourseRestrictionCreate,
    CourseRestrictionRead,
    StudentCourseChoiceSelectionCreate,
    StudentCourseHistoryCreate,
    StudentCourseHistoryRead,
    StudentCoursePlanCreate,
    StudentCourseRequestCreate,
    StudentCourseRequestRead,
    StudentCourseSelectionCreate,
    StudentEnrollmentRead,
    StudentCreate,
    StudentRead,
    StudentSuggestionsRead,
)
from app.services.student_planning import build_student_suggestions

router = APIRouter()


@router.get("/students", response_model=list[StudentRead])
def list_students(db: Session = Depends(get_db)) -> list[Student]:
    return db.query(Student).order_by(Student.name).all()


@router.post("/students", response_model=StudentRead)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)) -> Student:
    if not db.get(DegreeProgram, payload.degree_program_id):
        raise HTTPException(status_code=404, detail="Curso nao encontrado")
    student = Student(**payload.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/students/{student_id}", response_model=StudentRead)
def get_student(student_id: str, db: Session = Depends(get_db)) -> Student:
    return require_student(db, student_id)


@router.put("/students/{student_id}", response_model=StudentRead)
def update_student(
    student_id: str, payload: StudentCreate, db: Session = Depends(get_db)
) -> Student:
    if not db.get(DegreeProgram, payload.degree_program_id):
        raise HTTPException(status_code=404, detail="Curso nao encontrado")
    student = require_student(db, student_id)
    for key, value in payload.model_dump().items():
        setattr(student, key, value)
    db.commit()
    db.refresh(student)
    return student


@router.delete("/students/{student_id}")
def delete_student(student_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    student = require_student(db, student_id)
    db.delete(student)
    db.commit()
    return {"ok": True}


@router.get("/students/{student_id}/history", response_model=list[StudentCourseHistoryRead])
def list_student_history(
    student_id: str, db: Session = Depends(get_db)
) -> list[StudentCourseHistory]:
    require_student(db, student_id)
    return (
        db.query(StudentCourseHistory)
        .filter(StudentCourseHistory.student_id == student_id)
        .order_by(StudentCourseHistory.semester, StudentCourseHistory.created_at)
        .all()
    )


@router.post("/students/{student_id}/history", response_model=StudentCourseHistoryRead)
def add_student_history(
    student_id: str, payload: StudentCourseHistoryCreate, db: Session = Depends(get_db)
) -> StudentCourseHistory:
    student = require_student(db, student_id)
    course = require_course(db, payload.course_id)
    validate_student_course(db, student, course)
    history = StudentCourseHistory(student_id=student_id, **payload.model_dump())
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


@router.get("/students/{student_id}/course-requests", response_model=list[StudentCourseRequestRead])
def list_student_requests(
    student_id: str, target_semester: str | None = None, db: Session = Depends(get_db)
) -> list[StudentCourseRequest]:
    require_student(db, student_id)
    query = db.query(StudentCourseRequest).filter(StudentCourseRequest.student_id == student_id)
    if target_semester:
        query = query.filter(StudentCourseRequest.target_semester == target_semester)
    return query.order_by(StudentCourseRequest.target_semester, StudentCourseRequest.created_at).all()


@router.get("/students/{student_id}/enrollments", response_model=list[StudentEnrollmentRead])
def list_student_enrollments(
    student_id: str,
    target_semester: str | None = None,
    stage: str | None = None,
    db: Session = Depends(get_db),
) -> list[StudentEnrollment]:
    require_student(db, student_id)
    query = db.query(StudentEnrollment).filter(StudentEnrollment.student_id == student_id)
    if target_semester:
        query = query.filter(StudentEnrollment.target_semester == target_semester)
    if stage:
        query = query.filter(StudentEnrollment.stage == stage)
    return query.order_by(StudentEnrollment.target_semester, StudentEnrollment.status).all()


@router.post("/students/{student_id}/course-requests", response_model=list[StudentCourseRequestRead])
def select_student_courses(
    student_id: str, payload: StudentCourseSelectionCreate, db: Session = Depends(get_db)
) -> list[StudentCourseRequest]:
    student = require_student(db, student_id)
    requests: list[StudentCourseRequest] = []
    for index, course_id in enumerate(payload.course_ids, start=1):
        course = require_course(db, course_id)
        validate_student_course(db, student, course)
        alternative_group = payload.alternative_group or f"course:{course_id}"
        existing = (
            db.query(StudentCourseRequest)
            .filter(
                StudentCourseRequest.student_id == student_id,
                StudentCourseRequest.course_id == course_id,
                StudentCourseRequest.target_semester == payload.target_semester,
                StudentCourseRequest.alternative_group == alternative_group,
            )
            .first()
        )
        request = existing or StudentCourseRequest(
            student_id=student_id,
            course_id=course_id,
            target_semester=payload.target_semester,
        )
        request.priority = payload.priority
        request.preference_order = index
        request.alternative_group = alternative_group
        apply_request_time_fields(request, payload)
        request.stage = "pre_enrollment"
        request.note = payload.note
        request.source = "student"
        db.add(request)
        requests.append(request)
    db.commit()
    for request in requests:
        db.refresh(request)
    return requests


@router.post("/students/{student_id}/course-requests/choices", response_model=list[StudentCourseRequestRead])
def select_student_course_choices(
    student_id: str, payload: StudentCourseChoiceSelectionCreate, db: Session = Depends(get_db)
) -> list[StudentCourseRequest]:
    student = require_student(db, student_id)
    requests: list[StudentCourseRequest] = []
    for item in payload.choices:
        course = require_course(db, item.course_id)
        validate_student_course(db, student, course)
        alternative_group = item.alternative_group or "default"
        existing = (
            db.query(StudentCourseRequest)
            .filter(
                StudentCourseRequest.student_id == student_id,
                StudentCourseRequest.course_id == item.course_id,
                StudentCourseRequest.target_semester == payload.target_semester,
                StudentCourseRequest.alternative_group == alternative_group,
            )
            .first()
        )
        request = existing or StudentCourseRequest(
            student_id=student_id,
            course_id=item.course_id,
            target_semester=payload.target_semester,
            alternative_group=alternative_group,
        )
        request.priority = item.priority
        request.preference_order = item.preference_order
        apply_request_time_fields(request, item)
        request.stage = "pre_enrollment"
        request.note = item.note
        request.source = "student"
        db.add(request)
        requests.append(request)
    db.commit()
    for request in requests:
        db.refresh(request)
    return requests


@router.post("/students/{student_id}/course-requests/plan", response_model=list[StudentCourseRequestRead])
def submit_complex_student_course_plan(
    student_id: str, payload: StudentCoursePlanCreate, db: Session = Depends(get_db)
) -> list[StudentCourseRequest]:
    student = require_student(db, student_id)
    db.query(StudentCourseRequest).filter(
        StudentCourseRequest.student_id == student_id,
        StudentCourseRequest.target_semester == payload.target_semester,
        or_(
            StudentCourseRequest.alternative_group == payload.alternative_group,
            StudentCourseRequest.alternative_group.like(f"{payload.alternative_group}:%"),
        ),
        StudentCourseRequest.stage == payload.stage,
    ).delete(synchronize_session=False)

    requests: list[StudentCourseRequest] = []
    for branch in sorted(payload.branches, key=lambda item: item.preference_order):
        alternative_group = scoped_alternative_group(payload.alternative_group, branch.choice_group)
        for item_index, item in enumerate(branch.items, start=1):
            course = require_course(db, item.course_id)
            validate_student_course(db, student, course)
            request = StudentCourseRequest(
                student_id=student_id,
                course_id=item.course_id,
                target_semester=payload.target_semester,
                priority=item.priority if item.priority is not None else branch.priority,
                preference_order=branch.preference_order,
                alternative_group=alternative_group,
                stage=payload.stage,
                source=payload.source,
                note=complex_plan_item_note(branch.label, item.note, item_index),
            )
            apply_request_time_fields(request, item)
            db.add(request)
            requests.append(request)
    db.commit()
    for request in requests:
        db.refresh(request)
    return requests


@router.post(
    "/students/{student_id}/course-requests/single", response_model=StudentCourseRequestRead
)
def create_student_request(
    student_id: str, payload: StudentCourseRequestCreate, db: Session = Depends(get_db)
) -> StudentCourseRequest:
    student = require_student(db, student_id)
    course = require_course(db, payload.course_id)
    validate_student_course(db, student, course)
    request = StudentCourseRequest(student_id=student_id, **payload.model_dump())
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@router.get("/students/{student_id}/suggestions", response_model=StudentSuggestionsRead)
def get_student_suggestions(
    student_id: str, target_semester: str = "2026/2", db: Session = Depends(get_db)
) -> dict[str, object]:
    student = require_student(db, student_id)
    return {
        "student_id": student.id,
        "target_semester": target_semester,
        "suggestions": build_student_suggestions(db, student, target_semester),
    }


@router.get("/course-restrictions", response_model=list[CourseRestrictionRead])
def list_course_restrictions(db: Session = Depends(get_db)) -> list[CourseRestriction]:
    return db.query(CourseRestriction).order_by(CourseRestriction.course_id).all()


@router.post("/course-restrictions", response_model=CourseRestrictionRead)
def create_course_restriction(
    payload: CourseRestrictionCreate, db: Session = Depends(get_db)
) -> CourseRestriction:
    validate_course_restriction(db, payload)
    restriction = CourseRestriction(**payload.model_dump())
    db.add(restriction)
    db.commit()
    db.refresh(restriction)
    return restriction


@router.post("/course-restrictions/batch", response_model=list[CourseRestrictionRead])
def create_course_restriction_batch(
    payload: CourseRestrictionBatchCreate, db: Session = Depends(get_db)
) -> list[CourseRestriction]:
    restrictions: list[CourseRestriction] = []
    for required_course_id in payload.required_course_ids:
        restriction_payload = CourseRestrictionCreate(
            course_id=payload.course_id,
            required_course_id=required_course_id,
            kind=payload.kind,
            strength=payload.strength,
            minimum_grade=payload.minimum_grade,
            note=payload.note,
        )
        validate_course_restriction(db, restriction_payload)
        restriction = CourseRestriction(**restriction_payload.model_dump())
        db.add(restriction)
        restrictions.append(restriction)
    db.commit()
    for restriction in restrictions:
        db.refresh(restriction)
    return restrictions


@router.put("/course-restrictions/{restriction_id}", response_model=CourseRestrictionRead)
def update_course_restriction(
    restriction_id: str, payload: CourseRestrictionCreate, db: Session = Depends(get_db)
) -> CourseRestriction:
    restriction = db.get(CourseRestriction, restriction_id)
    if not restriction:
        raise HTTPException(status_code=404, detail="Restricao nao encontrada")
    validate_course_restriction(db, payload)
    for key, value in payload.model_dump().items():
        setattr(restriction, key, value)
    db.commit()
    db.refresh(restriction)
    return restriction


@router.delete("/course-restrictions/{restriction_id}")
def delete_course_restriction(
    restriction_id: str, db: Session = Depends(get_db)
) -> dict[str, bool]:
    restriction = db.get(CourseRestriction, restriction_id)
    if not restriction:
        raise HTTPException(status_code=404, detail="Restricao nao encontrada")
    db.delete(restriction)
    db.commit()
    return {"ok": True}


def validate_course_restriction(db: Session, payload: CourseRestrictionCreate) -> None:
    if payload.course_id == payload.required_course_id:
        raise HTTPException(status_code=422, detail="Cadeira nao pode exigir ela mesma")
    course = require_course(db, payload.course_id)
    required_course = require_course(db, payload.required_course_id)
    if (
        course.degree_program_id
        and required_course.degree_program_id
        and course.degree_program_id != required_course.degree_program_id
        and not (
            course.context_key
            and required_course.context_key
            and course.context_key == required_course.context_key
        )
    ):
        raise HTTPException(
            status_code=422,
            detail="Restricao entre cadeiras de cursos diferentes exige equivalencia por contexto",
        )


def require_student(db: Session, student_id: str) -> Student:
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Aluno nao encontrado")
    return student


def require_course(db: Session, course_id: str) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Cadeira nao encontrada")
    return course


def validate_student_course(db: Session, student: Student, course: Course) -> None:
    if not course.degree_program_id or course.degree_program_id == student.degree_program_id:
        return
    if course.context_key and course.shareable:
        equivalent = (
            db.query(Course)
            .filter(
                Course.degree_program_id == student.degree_program_id,
                Course.context_key == course.context_key,
                Course.shareable.is_(True),
            )
            .first()
        )
        if equivalent:
            return
    raise HTTPException(status_code=422, detail="Cadeira nao pertence ao curso do aluno")


def apply_request_time_fields(request: StudentCourseRequest, payload: object) -> None:
    request.desired_day = getattr(payload, "desired_day", None)
    request.desired_start_minute = getattr(payload, "desired_start_minute", None)
    request.desired_end_minute = getattr(payload, "desired_end_minute", None)
    request.time_preference_strength = (
        getattr(payload, "time_preference_strength", None) or ConstraintStrength.soft
    )


def complex_plan_item_note(branch_label: str | None, item_note: str | None, item_index: int) -> str:
    parts = [part for part in (branch_label, item_note) if part]
    if parts:
        return " | ".join(parts)
    return f"Item {item_index} do pacote de preferencias"


def scoped_alternative_group(base: str, choice_group: str | None) -> str:
    if not choice_group:
        return base[:80]
    safe_group = sanitize_group_key(choice_group)
    if not safe_group:
        return base[:80]
    max_base_length = max(1, 79 - len(safe_group))
    return f"{base[:max_base_length]}:{safe_group}"[:80]


def sanitize_group_key(value: str) -> str:
    stripped = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in stripped if not unicodedata.combining(char)).lower()
    normalized = normalized.replace(" ", "-")
    safe = "".join(char if char.isalnum() or char in "-_:" else "-" for char in normalized)
    return safe.strip("-")[:48]
