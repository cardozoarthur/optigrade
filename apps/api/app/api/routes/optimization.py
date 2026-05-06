from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    Assignment,
    Campus,
    Course,
    DegreeProgram,
    OptimizationRun,
    Professor,
    ProfessorAvailability,
    ProfessorConstraint,
    ProfessorContract,
    ProfessorCoursePreference,
    ProfessorQualification,
    Room,
    RunStatus,
    Student,
    StudentCourseRequest,
    StudentEnrollment,
    TimeSlot,
)
from app.schemas import (
    AssignmentRead,
    ManualAdjustmentCreate,
    OptimizationRunCreate,
    OptimizationRunRead,
)
from app.services.enrollment import enrollment_bucket_key
from app.services.optimization_jobs import (
    enqueue_optimization_run,
    find_active_run,
    needs_automatic_enrollment_resume,
)
from app.services.optimizer import validate_manual_assignments

router = APIRouter()


@router.get("/runs", response_model=list[OptimizationRunRead])
def list_runs(db: Session = Depends(get_db)) -> list[OptimizationRun]:
    runs = db.query(OptimizationRun).order_by(OptimizationRun.created_at.desc()).limit(25).all()
    for run in runs:
        if needs_automatic_enrollment_resume(run):
            enqueue_optimization_run(run.id)
    return runs


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
    if run.status == RunStatus.pending or needs_automatic_enrollment_resume(run):
        enqueue_optimization_run(run.id)
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


@router.get("/runs/{run_id}/details")
def get_run_details(run_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    run = db.get(OptimizationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")

    assignments = (
        db.query(Assignment)
        .join(TimeSlot, TimeSlot.id == Assignment.time_slot_id)
        .filter(Assignment.run_id == run_id)
        .order_by(TimeSlot.day, TimeSlot.start_minute, Assignment.course_id, Assignment.session_index)
        .all()
    )
    courses = {course.id: course for course in db.query(Course).all()}
    professors = {professor.id: professor for professor in db.query(Professor).all()}
    rooms = {room.id: room for room in db.query(Room).all()}
    slots = {slot.id: slot for slot in db.query(TimeSlot).all()}
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

    professor_ids = {assignment.professor_id for assignment in assignments}
    availability = group_by_professor(
        db.query(ProfessorAvailability).filter(ProfessorAvailability.professor_id.in_(professor_ids)).all()
        if professor_ids
        else []
    )
    preferences = group_preferences(
        db.query(ProfessorCoursePreference).filter(ProfessorCoursePreference.professor_id.in_(professor_ids)).all()
        if professor_ids
        else []
    )
    constraints = group_by_professor(
        db.query(ProfessorConstraint).filter(ProfessorConstraint.professor_id.in_(professor_ids)).all()
        if professor_ids
        else []
    )
    qualifications = group_qualifications(
        db.query(ProfessorQualification).filter(ProfessorQualification.professor_id.in_(professor_ids)).all()
        if professor_ids
        else []
    )
    contracts = {
        contract.professor_id: contract
        for contract in (
            db.query(ProfessorContract).filter(ProfessorContract.professor_id.in_(professor_ids)).all()
            if professor_ids
            else []
        )
    }

    details = []
    for assignment in assignments:
        course = courses.get(assignment.course_id)
        professor = professors.get(assignment.professor_id)
        room = rooms.get(assignment.room_id)
        slot = slots.get(assignment.time_slot_id)
        campus = campuses.get(room.campus_id) if room and room.campus_id else None
        section_key = assignment_section_key(assignment, bucket_by_course)
        section_plan = planned_sections.get(section_key)
        assignment_preferences = preferences.get((assignment.professor_id, assignment.course_id), [])
        assignment_availability = availability.get(assignment.professor_id, [])
        assignment_qualifications = qualifications.get((assignment.professor_id, assignment.course_id), [])
        details.append(
            {
                "assignment": assignment_summary(assignment),
                "course": course_summary(course, programs, campuses),
                "section": section_plan,
                "professor": professor_detail(
                    professor,
                    contracts.get(assignment.professor_id),
                    assignment_availability,
                    assignment_preferences,
                    constraints.get(assignment.professor_id, []),
                    assignment_qualifications,
                    slot,
                ),
                "room": room_summary(room, campus),
                "slot": slot_summary(slot),
                "decision": {
                    "section_key": section_key,
                    "origin": assignment.origin,
                    "fixed": assignment.fixed,
                    "why_professor": professor_assignment_reasons(
                        professor,
                        contracts.get(assignment.professor_id),
                        assignment_availability,
                        assignment_preferences,
                        assignment_qualifications,
                        slot,
                        assignment,
                    ),
                    "why_time_room": time_room_reasons(course, room, slot, campus, section_plan, assignment),
                },
                "enrollments": [
                    enrollment_detail(item, assignment, courses, programs)
                    for item in section_enrollments.get(section_key, [])
                ],
            }
        )
    return {"run_id": run_id, "assignments": details}


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


def planned_sections_by_key(
    run: OptimizationRun,
    bucket_by_course: dict[str, str],
) -> dict[str, dict[str, Any]]:
    planned_sections = (run.metrics or {}).get("planned_sections")
    if not isinstance(planned_sections, list):
        return {}
    values: dict[str, dict[str, Any]] = {}
    for section in planned_sections:
        if not isinstance(section, dict):
            continue
        course_id = section.get("db_course_id")
        if not isinstance(course_id, str):
            continue
        try:
            section_index = int(section.get("section_index") or 0)
        except (TypeError, ValueError):
            section_index = 0
        bucket_id = bucket_by_course.get(course_id, f"course:{course_id}")
        values[f"{bucket_id}:{section_index}"] = section
    return values


def display_enrollments_by_assignment_section(
    db: Session,
    run: OptimizationRun,
    assignments: list[Assignment],
    courses: dict[str, Course],
    rooms: dict[str, Room],
    bucket_by_course: dict[str, str],
    planned_sections: dict[str, dict[str, Any]],
) -> dict[str, list[StudentEnrollment]]:
    enrolled = (
        db.query(StudentEnrollment)
        .filter(
            StudentEnrollment.run_id == run.id,
            StudentEnrollment.target_semester == run.semester,
            StudentEnrollment.status == "enrolled",
        )
        .order_by(StudentEnrollment.course_id, StudentEnrollment.score.desc(), StudentEnrollment.student_id)
        .all()
    )
    enrollments_by_bucket: dict[str, list[StudentEnrollment]] = defaultdict(list)
    for enrollment in enrolled:
        bucket_id = bucket_by_course.get(enrollment.course_id, f"course:{enrollment.course_id}")
        enrollments_by_bucket[bucket_id].append(enrollment)

    assignments_by_section: dict[str, list[Assignment]] = defaultdict(list)
    for assignment in assignments:
        assignments_by_section[assignment_section_key(assignment, bucket_by_course)].append(assignment)

    result: dict[str, list[StudentEnrollment]] = {}
    sections_by_bucket: dict[str, list[str]] = defaultdict(list)
    for key in assignments_by_section:
        bucket_id, _section_index = key.rsplit(":", 1)
        sections_by_bucket[bucket_id].append(key)

    for bucket_id, section_keys in sections_by_bucket.items():
        ordered_sections = sorted(section_keys, key=lambda key: int(key.rsplit(":", 1)[1]))
        cursor = 0
        bucket_enrollments = enrollments_by_bucket.get(bucket_id, [])
        for section_key in ordered_sections:
            capacity = display_section_capacity(
                section_key,
                assignments_by_section[section_key],
                rooms,
                planned_sections,
            )
            result[section_key] = bucket_enrollments[cursor : cursor + capacity]
            cursor += capacity
        if cursor < len(bucket_enrollments) and ordered_sections:
            for index, enrollment in enumerate(bucket_enrollments[cursor:]):
                result.setdefault(ordered_sections[index % len(ordered_sections)], []).append(enrollment)
    return result


def display_section_capacity(
    section_key: str,
    assignments: list[Assignment],
    rooms: dict[str, Room],
    planned_sections: dict[str, dict[str, Any]],
) -> int:
    section = planned_sections.get(section_key)
    if isinstance(section, dict):
        try:
            planned_students = int(section.get("planned_students") or 0)
        except (TypeError, ValueError):
            planned_students = 0
        if planned_students > 0:
            return planned_students
    capacities = [
        room.capacity
        for assignment in assignments
        if (room := rooms.get(assignment.room_id)) is not None
    ]
    return min(capacities) if capacities else 0


def assignment_section_key(assignment: Assignment, bucket_by_course: dict[str, str]) -> str:
    bucket_id = bucket_by_course.get(assignment.course_id, f"course:{assignment.course_id}")
    section_index = int(assignment.session_index or 0) // 100
    return f"{bucket_id}:{section_index}"


def assignment_summary(assignment: Assignment) -> dict[str, Any]:
    return {
        "id": assignment.id,
        "run_id": assignment.run_id,
        "course_id": assignment.course_id,
        "professor_id": assignment.professor_id,
        "room_id": assignment.room_id,
        "time_slot_id": assignment.time_slot_id,
        "session_index": assignment.session_index,
        "section_index": int(assignment.session_index or 0) // 100,
        "fixed": assignment.fixed,
        "hard_violations": assignment.hard_violations or [],
        "soft_violations": assignment.soft_violations or [],
        "origin": assignment.origin,
    }


def course_summary(
    course: Course | None,
    programs: dict[str, DegreeProgram],
    campuses: dict[str, Campus],
) -> dict[str, Any] | None:
    if not course:
        return None
    program = programs.get(course.degree_program_id or "")
    campus = campuses.get(course.campus_id or "")
    return {
        "id": course.id,
        "code": course.code,
        "name": course.name,
        "degree_program_id": course.degree_program_id,
        "degree_program_name": program.name if program else None,
        "campus_id": course.campus_id,
        "campus_name": campus.name if campus else None,
        "workload_hours": course.workload_hours,
        "theoretical_hours": course.theoretical_hours,
        "practical_hours": course.practical_hours,
        "kind": enum_value(course.kind),
        "recommended_semester": course.recommended_semester,
        "requires_lab": course.requires_lab,
        "context_key": course.context_key,
        "shareable": course.shareable,
        "official_period": course.official_period,
        "official_class": course.official_class,
    }


def professor_detail(
    professor: Professor | None,
    contract: ProfessorContract | None,
    availability: list[ProfessorAvailability],
    preferences: list[ProfessorCoursePreference],
    constraints: list[ProfessorConstraint],
    qualifications: list[ProfessorQualification],
    slot: TimeSlot | None,
) -> dict[str, Any] | None:
    if not professor:
        return None
    return {
        "id": professor.id,
        "name": professor.name,
        "email": professor.email,
        "department": professor.department,
        "contract": contract_summary(contract),
        "availability": [availability_summary(item, slot) for item in availability],
        "course_preferences": [preference_summary(item) for item in preferences],
        "constraints": [constraint_summary(item) for item in constraints],
        "qualifications": [qualification_summary(item) for item in qualifications],
    }


def contract_summary(contract: ProfessorContract | None) -> dict[str, Any] | None:
    if not contract:
        return None
    return {
        "min_hours": contract.min_hours,
        "max_hours": contract.max_hours,
        "regime": contract.regime,
        "semester": contract.semester,
        "is_borrowed": contract.is_borrowed,
        "borrowed_from_department": contract.borrowed_from_department,
        "legal_notes": contract.legal_notes,
        "loan_notes": contract.loan_notes,
    }


def availability_summary(item: ProfessorAvailability, slot: TimeSlot | None) -> dict[str, Any]:
    return {
        "day": item.day,
        "start_minute": item.start_minute,
        "end_minute": item.end_minute,
        "kind": enum_value(item.kind),
        "strength": enum_value(item.strength),
        "source": item.source,
        "matches_assignment": slot_covers_availability(item, slot),
    }


def preference_summary(item: ProfessorCoursePreference) -> dict[str, Any]:
    return {
        "course_id": item.course_id,
        "preference": item.preference,
        "strength": enum_value(item.strength),
        "note": item.note,
    }


def constraint_summary(item: ProfessorConstraint) -> dict[str, Any]:
    return {
        "natural_language": item.natural_language,
        "structured_rule": item.structured_rule,
        "strength": enum_value(item.strength),
        "confirmed": item.confirmed,
    }


def qualification_summary(item: ProfessorQualification) -> dict[str, Any]:
    return {
        "course_id": item.course_id,
        "strength": enum_value(item.strength),
        "source": item.source,
    }


def room_summary(room: Room | None, campus: Campus | None) -> dict[str, Any] | None:
    if not room:
        return None
    return {
        "id": room.id,
        "name": room.name,
        "capacity": room.capacity,
        "kind": enum_value(room.kind),
        "campus_id": room.campus_id,
        "campus_name": campus.name if campus else None,
    }


def slot_summary(slot: TimeSlot | None) -> dict[str, Any] | None:
    if not slot:
        return None
    return {
        "id": slot.id,
        "day": slot.day,
        "start_minute": slot.start_minute,
        "end_minute": slot.end_minute,
        "label": slot.label,
    }


def enrollment_detail(
    enrollment: StudentEnrollment,
    assignment: Assignment,
    courses: dict[str, Course],
    programs: dict[str, DegreeProgram],
) -> dict[str, Any]:
    student = enrollment.student
    request = enrollment.request
    requested_course = courses.get(request.course_id) if request else courses.get(enrollment.course_id)
    assigned_course = courses.get(assignment.course_id)
    origin_program = programs.get(student.degree_program_id) if student else None
    return {
        "id": enrollment.id,
        "status": enrollment.status,
        "score": enrollment.score,
        "score_breakdown": enrollment.score_breakdown or {},
        "reason": enrollment.reason,
        "decision_type": enrollment_decision_type(enrollment, assignment, request),
        "student": {
            "id": student.id if student else enrollment.student_id,
            "name": student.name if student else enrollment.student_id,
            "registration_number": student.registration_number if student else None,
            "current_semester": student.current_semester if student else None,
            "degree_program_id": student.degree_program_id if student else None,
            "degree_program_name": origin_program.name if origin_program else None,
        },
        "request": request_summary(request),
        "requested_course": course_minimal_summary(requested_course),
        "assigned_course": course_minimal_summary(assigned_course),
        "why_this_section": enrollment_section_reasons(enrollment, assignment, request, requested_course, assigned_course),
    }


def request_summary(request: StudentCourseRequest | None) -> dict[str, Any] | None:
    if not request:
        return None
    return {
        "id": request.id,
        "course_id": request.course_id,
        "priority": request.priority,
        "preference_order": request.preference_order,
        "alternative_group": request.alternative_group,
        "desired_day": request.desired_day,
        "desired_start_minute": request.desired_start_minute,
        "desired_end_minute": request.desired_end_minute,
        "time_preference_strength": enum_value(request.time_preference_strength),
        "source": request.source,
        "note": request.note,
    }


def course_minimal_summary(course: Course | None) -> dict[str, Any] | None:
    if not course:
        return None
    return {
        "id": course.id,
        "code": course.code,
        "name": course.name,
        "degree_program_id": course.degree_program_id,
        "context_key": course.context_key,
        "workload_hours": course.workload_hours,
        "theoretical_hours": course.theoretical_hours,
        "practical_hours": course.practical_hours,
    }


def enrollment_decision_type(
    enrollment: StudentEnrollment,
    assignment: Assignment,
    request: StudentCourseRequest | None,
) -> str:
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


def enrollment_section_reasons(
    enrollment: StudentEnrollment,
    assignment: Assignment,
    request: StudentCourseRequest | None,
    requested_course: Course | None,
    assigned_course: Course | None,
) -> list[str]:
    reasons = []
    if request and request.preference_order == 1:
        reasons.append("O pedido estava na primeira posição da fila do aluno.")
    elif request:
        reasons.append(f"O pedido estava na posição {request.preference_order} da fila de alternativas.")
    if enrollment.course_id != assignment.course_id and requested_course and assigned_course:
        reasons.append(
            "A vaga foi exibida nesta turma por equivalência de contexto, carga horária e cadeira entre cursos."
        )
    if enrollment.reason:
        reasons.append(enrollment.reason)
    if request and request.desired_day is not None:
        reasons.append("A preferência de horário declarada pelo aluno entrou como restrição da rodada.")
    if not reasons:
        reasons.append("A rodada automática selecionou esta oferta pelo melhor encaixe entre demanda, vagas e restrições.")
    return reasons


def professor_assignment_reasons(
    professor: Professor | None,
    contract: ProfessorContract | None,
    availability: list[ProfessorAvailability],
    preferences: list[ProfessorCoursePreference],
    qualifications: list[ProfessorQualification],
    slot: TimeSlot | None,
    assignment: Assignment,
) -> list[str]:
    reasons = []
    if professor:
        reasons.append(f"{professor.name} estava habilitado ou vinculado à cadeira no cadastro docente.")
    if qualifications:
        sources = ", ".join(sorted({item.source for item in qualifications if item.source}))
        reasons.append(f"Habilitação registrada como {qualifications[0].strength.value}; origem: {sources or 'cadastro'}.")
    if contract:
        reasons.append(
            f"Contrato modelado com mínimo {contract.min_hours}h e máximo {contract.max_hours}h no semestre."
        )
    matching_windows = [item for item in availability if slot_covers_availability(item, slot)]
    if matching_windows:
        kinds = ", ".join(sorted({item.kind.value for item in matching_windows}))
        reasons.append(f"Horário coberto por janela docente cadastrada ({kinds}).")
    else:
        reasons.append("A oferta não encontrou janela docente explícita; se regular obrigatória, a regra de oferta pode forçar disponibilidade.")
    if preferences:
        preference = preferences[0].preference
        if preference > 0:
            reasons.append(f"O professor declarou preferência positiva pela cadeira (+{preference}).")
        elif preference < 0:
            reasons.append(f"O professor declarou preferência negativa pela cadeira ({preference}), tratada como custo soft.")
        else:
            reasons.append("O professor tinha preferência neutra para a cadeira.")
    if assignment.soft_violations:
        reasons.append("Soft constraints desta alocação foram penalizadas, mas não bloquearam a solução.")
    if assignment.hard_violations:
        reasons.append("Há violações hard registradas nesta oferta e ela precisa revisão manual.")
    return reasons


def time_room_reasons(
    course: Course | None,
    room: Room | None,
    slot: TimeSlot | None,
    campus: Campus | None,
    section_plan: dict[str, Any] | None,
    assignment: Assignment,
) -> list[str]:
    reasons = []
    if room:
        reasons.append(f"Sala {room.name} oferece {room.capacity} lugares físicos.")
    if campus:
        reasons.append(f"Campus da oferta: {campus.name}.")
    if course and course.requires_lab:
        reasons.append("Cadeira exige laboratório; a sala foi filtrada por tipo compatível.")
    if section_plan and section_plan.get("strategy"):
        reasons.append(f"Estratégia da turma: {section_plan['strategy']}.")
    if slot:
        reasons.append("Horário escolhido dentro do conjunto de slots viáveis para a rodada.")
    if assignment.fixed:
        reasons.append("Oferta marcada como fixa/manual.")
    return reasons


def slot_covers_availability(item: ProfessorAvailability, slot: TimeSlot | None) -> bool:
    if not slot:
        return False
    return (
        item.day == slot.day
        and item.start_minute <= slot.start_minute
        and item.end_minute >= slot.end_minute
    )


def group_by_professor(items: list[Any]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for item in items:
        grouped[item.professor_id].append(item)
    return grouped


def group_preferences(items: list[ProfessorCoursePreference]) -> dict[tuple[str, str], list[ProfessorCoursePreference]]:
    grouped: dict[tuple[str, str], list[ProfessorCoursePreference]] = defaultdict(list)
    for item in items:
        grouped[(item.professor_id, item.course_id)].append(item)
    return grouped


def group_qualifications(items: list[ProfessorQualification]) -> dict[tuple[str, str], list[ProfessorQualification]]:
    grouped: dict[tuple[str, str], list[ProfessorQualification]] = defaultdict(list)
    for item in items:
        grouped[(item.professor_id, item.course_id)].append(item)
    return grouped


def enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value
