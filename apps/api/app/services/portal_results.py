from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.api.routes.optimization import (
    assignment_section_key,
    display_enrollments_by_assignment_section,
    planned_sections_by_key,
)
from app.models.entities import (
    Assignment,
    Campus,
    Course,
    DegreeProgram,
    OptimizationRun,
    Professor,
    Room,
    RunStatus,
    Student,
    StudentCourseRequest,
    StudentEnrollment,
    TimeSlot,
)
from app.services.enrollment import enrollment_bucket_key

READY_STATUSES = {RunStatus.feasible, RunStatus.infeasible}
ACTIVE_STATUSES = {RunStatus.pending, RunStatus.running}


def build_student_portal_result(
    db: Session,
    *,
    student: Student,
    semester: str,
) -> dict[str, Any]:
    submitted_after = latest_student_request_created_at(db, student.id, semester)
    run = latest_portal_run(db, semester=semester, submitted_after=submitted_after)
    base = portal_result_base(run)
    if not run or base["status"] != "ready":
        return base

    assignments, lookup = result_lookup(db, run)
    section_enrollments = lookup["section_enrollments"]
    wanted_sections: dict[str, StudentEnrollment] = {}
    for section_key, enrollments in section_enrollments.items():
        for enrollment in enrollments:
            if enrollment.student_id == student.id:
                wanted_sections[section_key] = enrollment
                break

    calendar = []
    for assignment in assignments:
        section_key = assignment_section_key(assignment, lookup["bucket_by_course"])
        enrollment = wanted_sections.get(section_key)
        if not enrollment:
            continue
        calendar.append(calendar_entry(assignment, lookup, enrollment=enrollment))

    pending = (
        db.query(StudentEnrollment)
        .filter(
            StudentEnrollment.run_id == run.id,
            StudentEnrollment.student_id == student.id,
            StudentEnrollment.status != "enrolled",
        )
        .order_by(StudentEnrollment.score.desc(), StudentEnrollment.created_at)
        .all()
    )

    return {
        **base,
        "calendar": calendar,
        "unallocated": [student_unallocated_entry(item, lookup["courses"], lookup["programs"]) for item in pending],
    }


def build_teacher_portal_result(
    db: Session,
    *,
    professor_id: str,
    semester: str,
    submitted_after: datetime | None,
) -> dict[str, Any]:
    run = latest_portal_run(db, semester=semester, submitted_after=submitted_after)
    base = portal_result_base(run)
    if not run or base["status"] != "ready":
        return base

    assignments, lookup = result_lookup(db, run)
    professor_assignments = [
        assignment for assignment in assignments if assignment.professor_id == professor_id
    ]
    return {
        **base,
        "calendar": [
            calendar_entry(
                assignment,
                lookup,
                enrollments=lookup["section_enrollments"].get(
                    assignment_section_key(assignment, lookup["bucket_by_course"]),
                    [],
                ),
            )
            for assignment in professor_assignments
        ],
        "unallocated": [],
    }


def latest_portal_run(
    db: Session,
    *,
    semester: str,
    submitted_after: datetime | None,
) -> OptimizationRun | None:
    runs = (
        db.query(OptimizationRun)
        .filter(
            OptimizationRun.semester == semester,
            OptimizationRun.profile == "balanced",
        )
        .order_by(OptimizationRun.created_at.desc())
        .limit(50)
        .all()
    )
    valid_runs = [
        run
        for run in runs
        if submitted_after is None or as_aware(run.created_at) >= as_aware(submitted_after)
    ]
    trabalho_runs = [
        run
        for run in valid_runs
        if isinstance(run.parameters, dict) and run.parameters.get("source") == "trabalho"
    ]
    return (trabalho_runs or valid_runs or [None])[0]


def latest_student_request_created_at(db: Session, student_id: str, semester: str) -> datetime | None:
    request = (
        db.query(StudentCourseRequest)
        .filter(
            StudentCourseRequest.student_id == student_id,
            StudentCourseRequest.target_semester == semester,
            StudentCourseRequest.stage == "pre_enrollment",
            StudentCourseRequest.source == "presentation",
        )
        .order_by(StudentCourseRequest.created_at.desc())
        .first()
    )
    return request.created_at if request else None


def portal_result_base(run: OptimizationRun | None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    if not run:
        return {
            "status": "waiting",
            "run_id": None,
            "run_status": None,
            "updated_at": now,
            "message": "Aguardando o administrador iniciar a rodada automática.",
            "calendar": [],
            "unallocated": [],
        }
    if run.status in ACTIVE_STATUSES:
        return {
            "status": "running",
            "run_id": run.id,
            "run_status": enum_value(run.status),
            "updated_at": now,
            "message": "Rodada automática em processamento.",
            "calendar": [],
            "unallocated": [],
        }
    if run.status == RunStatus.failed:
        return {
            "status": "failed",
            "run_id": run.id,
            "run_status": enum_value(run.status),
            "updated_at": now,
            "message": run.explanation or "A rodada falhou antes de gerar calendário.",
            "calendar": [],
            "unallocated": [],
        }
    if run.status in READY_STATUSES:
        return {
            "status": "ready",
            "run_id": run.id,
            "run_status": enum_value(run.status),
            "updated_at": now,
            "message": run.explanation,
            "calendar": [],
            "unallocated": [],
        }
    return {
        "status": "waiting",
        "run_id": run.id,
        "run_status": enum_value(run.status),
        "updated_at": now,
        "message": "Aguardando resultado consolidado.",
        "calendar": [],
        "unallocated": [],
    }


def result_lookup(db: Session, run: OptimizationRun) -> tuple[list[Assignment], dict[str, Any]]:
    assignments = (
        db.query(Assignment)
        .join(TimeSlot, TimeSlot.id == Assignment.time_slot_id)
        .filter(Assignment.run_id == run.id)
        .order_by(TimeSlot.day, TimeSlot.start_minute, Assignment.course_id, Assignment.session_index)
        .all()
    )
    courses = {course.id: course for course in db.query(Course).all()}
    rooms = {room.id: room for room in db.query(Room).all()}
    slots = {slot.id: slot for slot in db.query(TimeSlot).all()}
    professors = {professor.id: professor for professor in db.query(Professor).all()}
    campuses = {campus.id: campus for campus in db.query(Campus).all()}
    programs = {program.id: program for program in db.query(DegreeProgram).all()}
    bucket_by_course = {course.id: enrollment_bucket_key(course) for course in courses.values()}
    planned_sections = planned_sections_by_key(run, bucket_by_course)
    section_enrollments = display_enrollments_by_assignment_section(
        db,
        run,
        assignments,
        courses,
        rooms,
        bucket_by_course,
        planned_sections,
    )
    return assignments, {
        "courses": courses,
        "rooms": rooms,
        "slots": slots,
        "professors": professors,
        "campuses": campuses,
        "programs": programs,
        "bucket_by_course": bucket_by_course,
        "planned_sections": planned_sections,
        "section_enrollments": section_enrollments,
    }


def calendar_entry(
    assignment: Assignment,
    lookup: dict[str, Any],
    *,
    enrollment: StudentEnrollment | None = None,
    enrollments: list[StudentEnrollment] | None = None,
) -> dict[str, Any]:
    courses: dict[str, Course] = lookup["courses"]
    professors: dict[str, Professor] = lookup["professors"]
    rooms: dict[str, Room] = lookup["rooms"]
    slots: dict[str, TimeSlot] = lookup["slots"]
    campuses: dict[str, Campus] = lookup["campuses"]
    programs: dict[str, DegreeProgram] = lookup["programs"]
    planned_sections: dict[str, dict[str, Any]] = lookup["planned_sections"]
    bucket_by_course: dict[str, str] = lookup["bucket_by_course"]

    course = courses.get(assignment.course_id)
    professor = professors.get(assignment.professor_id)
    room = rooms.get(assignment.room_id)
    slot = slots.get(assignment.time_slot_id)
    campus = campuses.get(room.campus_id) if room and room.campus_id else None
    program = programs.get(course.degree_program_id or "") if course else None
    section_key = assignment_section_key(assignment, bucket_by_course)
    section = planned_sections.get(section_key) or {}
    student_rows = enrollments or ([enrollment] if enrollment else [])
    first_enrollment = enrollment or (student_rows[0] if student_rows else None)
    request = first_enrollment.request if first_enrollment else None
    requested_course = courses.get(request.course_id) if request else None
    origin_program = (
        programs.get(first_enrollment.student.degree_program_id)
        if first_enrollment and first_enrollment.student
        else None
    )

    return {
        "id": assignment.id,
        "course_id": assignment.course_id,
        "course_name": course.name if course else "Cadeira",
        "course_code": course.code if course else None,
        "course_degree_program_name": program.name if program else None,
        "course_period": course.official_period if course else None,
        "section_label": section.get("section_label") or f"Turma {int(assignment.session_index or 0) // 100 + 1}",
        "professor_id": professor.id if professor else assignment.professor_id,
        "professor_name": professor.name if professor else "Professor",
        "room_name": room.name if room else None,
        "campus_name": campus.name if campus else None,
        "day": slot.day if slot else 0,
        "start_minute": slot.start_minute if slot else 0,
        "end_minute": slot.end_minute if slot else 0,
        "status": first_enrollment.status if first_enrollment else "scheduled",
        "score": first_enrollment.score if first_enrollment else None,
        "score_breakdown": first_enrollment.score_breakdown if first_enrollment else {},
        "reason": first_enrollment.reason if first_enrollment else None,
        "decision_type": decision_type(first_enrollment, assignment, request),
        "requested_course_name": requested_course.name if requested_course else None,
        "origin_degree_program_name": origin_program.name if origin_program else None,
        "enrolled_count": len(student_rows),
        "students": [
            {
                "id": item.student_id,
                "name": item.student.name if item.student else item.student_id,
                "degree_program_name": (
                    programs.get(item.student.degree_program_id).name
                    if item.student and programs.get(item.student.degree_program_id)
                    else None
                ),
                "score": item.score,
                "reason": item.reason,
            }
            for item in student_rows[:80]
        ],
    }


def student_unallocated_entry(
    enrollment: StudentEnrollment,
    courses: dict[str, Course],
    programs: dict[str, DegreeProgram],
) -> dict[str, Any]:
    course = courses.get(enrollment.course_id)
    program = programs.get(course.degree_program_id or "") if course else None
    return {
        "id": enrollment.id,
        "course_id": enrollment.course_id,
        "course_name": course.name if course else "Cadeira",
        "course_degree_program_name": program.name if program else None,
        "status": enrollment.status,
        "score": enrollment.score,
        "reason": enrollment.reason,
    }


def decision_type(
    enrollment: StudentEnrollment | None,
    assignment: Assignment,
    request: StudentCourseRequest | None,
) -> str:
    if not enrollment:
        return "aula do professor"
    reason = (enrollment.reason or "").lower()
    if "resgate" in reason:
        return "resgate do sistema"
    if enrollment.course_id != assignment.course_id:
        return "equivalência entre cursos"
    if request and request.preference_order == 1:
        return "escolha principal do aluno"
    if request and request.preference_order > 1:
        return "alternativa da fila do aluno"
    return "alocação automática"


def enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", str(value))


def as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
