from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import (
    Assignment,
    Course,
    CourseRestrictionKind,
    EnrollmentStatus,
    OptimizationRun,
    Room,
    Student,
    StudentCourseHistory,
    StudentCourseRequest,
    StudentCourseStatus,
    StudentEnrollment,
)
from app.services.student_planning import (
    completed_contexts_by_course,
    completed_history_by_course,
    course_eligible_for_student,
    eligibility_course_for_student,
    normalize_context_key,
    regular_relation_for_student,
    restrictions_for_courses,
)


@dataclass(frozen=True)
class EnrollmentCandidate:
    request: StudentCourseRequest
    student: Student
    course: Course
    eligibility_course: Course
    score: float
    breakdown: dict[str, Any]


@dataclass(frozen=True)
class EnrollmentCapacityPlan:
    capacity_by_course: dict[str, int]
    capacity_by_bucket: dict[str, int]
    bucket_by_course: dict[str, str]


def run_enrollment_round(
    db: Session,
    target_semester: str,
    stage: str = "pre_enrollment",
    run_id: str | None = None,
) -> dict[str, object]:
    db.query(StudentEnrollment).filter(
        StudentEnrollment.target_semester == target_semester,
        StudentEnrollment.stage == stage,
    ).delete()

    requests = (
        db.query(StudentCourseRequest)
        .filter(
            StudentCourseRequest.target_semester == target_semester,
            StudentCourseRequest.stage == stage,
        )
        .order_by(
            StudentCourseRequest.student_id,
            StudentCourseRequest.alternative_group,
            StudentCourseRequest.preference_order,
            StudentCourseRequest.created_at,
        )
        .all()
    )
    capacity_plan = course_capacity_plan(db, run_id)
    capacity_by_course = capacity_plan.capacity_by_course
    used_by_bucket = {bucket_id: 0 for bucket_id in capacity_plan.capacity_by_bucket}
    candidates_by_group: dict[tuple[str, str], list[EnrollmentCandidate]] = {}
    blocked = 0

    for request in requests:
        student = db.get(Student, request.student_id)
        course = db.get(Course, request.course_id)
        if not student or not course:
            continue
        eligibility_course = eligibility_course_for_student(db, student, course)
        if not eligibility_course or not course_eligible_for_student(db, student, course):
            blocked += 1
            add_enrollment(
                db,
                request,
                course,
                target_semester,
                stage,
                run_id,
                EnrollmentStatus.blocked.value,
                0,
                {},
                "Restricoes academicas nao atendidas",
            )
            continue
        score, breakdown = score_enrollment_candidate(db, student, course, eligibility_course, request)
        group = (student.id, request.alternative_group or f"course:{course.id}")
        candidates_by_group.setdefault(group, []).append(
            EnrollmentCandidate(request, student, course, eligibility_course, score, breakdown)
        )

    allocated_by_group: dict[tuple[str, str], EnrollmentCandidate] = {}
    solver_planned_request_ids = planned_request_ids_for_run(db, run_id)
    solver_planned_allocations = 0
    if solver_planned_request_ids:
        for group, values in candidates_by_group.items():
            planned = next(
                (candidate for candidate in values if candidate.request.id in solver_planned_request_ids),
                None,
            )
            if not planned:
                continue
            if candidate_has_capacity(planned, capacity_plan, used_by_bucket, capacity_by_course):
                allocated_by_group[group] = planned
                reserve_candidate_capacity(planned, capacity_plan, used_by_bucket)
                solver_planned_allocations += 1

    max_order = max(
        (candidate.request.preference_order for values in candidates_by_group.values() for candidate in values),
        default=0,
    )
    for preference_order in range(1, max_order + 1):
        round_candidates = [
            candidate
            for group, values in candidates_by_group.items()
            if group not in allocated_by_group
            for candidate in values
            if candidate.request.preference_order == preference_order
        ]
        round_candidates.sort(
            key=lambda item: (
                -item.score,
                item.request.preference_order,
                -item.request.priority,
                item.student.current_semester,
                item.student.registration_number or item.student.name,
            )
        )
        for candidate in round_candidates:
            group = (
                candidate.student.id,
                candidate.request.alternative_group or f"course:{candidate.course.id}",
            )
            if group in allocated_by_group:
                continue
            if not candidate_has_capacity(candidate, capacity_plan, used_by_bucket, capacity_by_course):
                continue
            allocated_by_group[group] = candidate
            reserve_candidate_capacity(candidate, capacity_plan, used_by_bucket)

    enrolled = 0
    waitlisted = 0
    superseded = 0
    enrolled_by_course: dict[str, int] = {}
    waitlisted_by_course: dict[str, int] = {}
    for group, values in candidates_by_group.items():
        allocated = allocated_by_group.get(group)
        for candidate in values:
            if allocated and candidate.request.id == allocated.request.id:
                enrolled += 1
                enrolled_by_course[candidate.course.id] = (
                    enrolled_by_course.get(candidate.course.id, 0) + 1
                )
                status = EnrollmentStatus.enrolled.value
                reason = "Alocado pela rodada automatica"
            elif allocated:
                superseded += 1
                status = EnrollmentStatus.superseded.value
                reason = (
                    "Opcao anterior substituida pela escolha otimizada do solver"
                    if candidate.request.preference_order < allocated.request.preference_order
                    else "Alternativa posterior descartada porque uma opcao anterior foi alocada"
                )
            else:
                waitlisted += 1
                waitlisted_by_course[candidate.course.id] = (
                    waitlisted_by_course.get(candidate.course.id, 0) + 1
                )
                status = EnrollmentStatus.waitlisted.value
                reason = "Sem vaga nas alternativas informadas"
            add_enrollment(
                db,
                candidate.request,
                candidate.course,
                target_semester,
                stage,
                run_id,
                status,
                candidate.score,
                candidate.breakdown,
                reason,
            )

    db.commit()
    return {
        "target_semester": target_semester,
        "stage": stage,
        "run_id": run_id,
        "enrolled": enrolled,
        "waitlisted": waitlisted,
        "superseded": superseded,
        "blocked": blocked,
        "unallocated_groups": len(candidates_by_group) - len(allocated_by_group),
        "capacity_by_course": capacity_by_course,
        "capacity_by_bucket": capacity_plan.capacity_by_bucket,
        "bucket_by_course": capacity_plan.bucket_by_course,
        "enrolled_by_course": enrolled_by_course,
        "waitlisted_by_course": waitlisted_by_course,
        "solver_planned_allocations": solver_planned_allocations,
    }


def course_capacity_by_id(db: Session, run_id: str | None) -> dict[str, int]:
    return course_capacity_plan(db, run_id).capacity_by_course


def candidate_has_capacity(
    candidate: EnrollmentCandidate,
    capacity_plan: EnrollmentCapacityPlan,
    used_by_bucket: dict[str, int],
    capacity_by_course: dict[str, int],
) -> bool:
    bucket_id = capacity_plan.bucket_by_course.get(candidate.course.id, candidate.course.id)
    capacity = capacity_plan.capacity_by_bucket.get(
        bucket_id,
        capacity_by_course.get(candidate.course.id, candidate.course.expected_demand),
    )
    return used_by_bucket.get(bucket_id, 0) < capacity


def reserve_candidate_capacity(
    candidate: EnrollmentCandidate,
    capacity_plan: EnrollmentCapacityPlan,
    used_by_bucket: dict[str, int],
) -> None:
    bucket_id = capacity_plan.bucket_by_course.get(candidate.course.id, candidate.course.id)
    used_by_bucket[bucket_id] = used_by_bucket.get(bucket_id, 0) + 1


def planned_request_ids_for_run(db: Session, run_id: str | None) -> set[str]:
    if not run_id:
        return set()
    run = db.get(OptimizationRun, run_id)
    demand_plan = (run.metrics or {}).get("student_demand_plan") if run else None
    if not isinstance(demand_plan, dict):
        return set()
    request_ids = demand_plan.get("selected_request_ids")
    if not isinstance(request_ids, list):
        return set()
    return {request_id for request_id in request_ids if isinstance(request_id, str)}


def course_capacity_plan(db: Session, run_id: str | None) -> EnrollmentCapacityPlan:
    courses = db.query(Course).all()
    bucket_by_course = {course.id: enrollment_bucket_key(course) for course in courses}
    if not run_id:
        capacities = {course.id: course.expected_demand for course in courses}
        capacity_by_bucket: dict[str, int] = {}
        for course in courses:
            bucket_id = bucket_by_course[course.id]
            capacity_by_bucket[bucket_id] = capacity_by_bucket.get(bucket_id, 0) + course.expected_demand
        return EnrollmentCapacityPlan(capacities, capacity_by_bucket, bucket_by_course)

    capacities = {course.id: 0 for course in courses}
    capacity_by_bucket = {bucket_id: 0 for bucket_id in set(bucket_by_course.values())}
    planned_capacity_by_section = planned_capacity_by_assignment_section(db, run_id)
    rows = (
        db.query(Assignment.course_id, Assignment.session_index, Room.capacity)
        .join(Room, Room.id == Assignment.room_id)
        .filter(Assignment.run_id == run_id)
        .all()
    )
    section_capacities: dict[tuple[str, int], list[int]] = {}
    for course_id, session_index, room_capacity in rows:
        bucket_id = bucket_by_course.get(course_id, f"course:{course_id}")
        section_index = int(session_index or 0) // 100
        planned_capacity = planned_capacity_by_section.get((course_id, section_index))
        effective_capacity = int(room_capacity)
        if planned_capacity is not None:
            effective_capacity = min(effective_capacity, planned_capacity)
        section_capacities.setdefault((bucket_id, section_index), []).append(effective_capacity)

    for (bucket_id, _section_index), values in section_capacities.items():
        capacity_by_bucket[bucket_id] = capacity_by_bucket.get(bucket_id, 0) + min(values)
    for course in courses:
        bucket_id = bucket_by_course[course.id]
        capacities[course.id] = capacity_by_bucket.get(bucket_id, 0)
    return EnrollmentCapacityPlan(capacities, capacity_by_bucket, bucket_by_course)


def planned_capacity_by_assignment_section(
    db: Session,
    run_id: str,
) -> dict[tuple[str, int], int]:
    run = db.get(OptimizationRun, run_id)
    planned_sections = (run.metrics or {}).get("planned_sections") if run else None
    if not isinstance(planned_sections, list):
        return {}
    capacities: dict[tuple[str, int], int] = {}
    for section in planned_sections:
        if not isinstance(section, dict):
            continue
        course_id = section.get("db_course_id")
        if not isinstance(course_id, str):
            continue
        try:
            section_index = int(section.get("section_index") or 0)
            planned_students = int(section.get("planned_students") or 0)
        except (TypeError, ValueError):
            continue
        if planned_students > 0:
            capacities[(course_id, section_index)] = planned_students
    return capacities


def enrollment_bucket_key(course: Course) -> str:
    context_key = normalize_context_key(course.context_key)
    if course.shareable and context_key:
        return "|".join(
            [
                "context",
                context_key,
                course.campus_id or "any-campus",
                str(course.workload_hours),
                str(course.theoretical_hours or 0),
                str(course.practical_hours or 0),
                str(course.requires_lab),
                course.kind.value,
            ]
        )
    return f"course:{course.id}"


def score_enrollment_candidate(
    db: Session,
    student: Student,
    course: Course,
    eligibility_course: Course,
    request: StudentCourseRequest,
) -> tuple[float, dict[str, Any]]:
    completed = completed_history_by_course(db, student.id)
    completed_contexts = completed_contexts_by_course(db, completed)
    history = history_for_course_context(db, student, eligibility_course)
    relation = regular_relation_for_student(course, student, eligibility_course)
    semester_delay = max(0, student.current_semester - eligibility_course.recommended_semester)
    dependency_average = dependency_grade_average(db, eligibility_course, completed, completed_contexts)

    first_attempt = history is None
    failed_grade = history.grade if history and history.status == StudentCourseStatus.failed else None
    breakdown = {
        "first_attempt": 40 if first_attempt else 0,
        "regular": 25 if relation == "regular" else 0,
        "reoffer": 55 if relation == "reoffer" else 0,
        "semester_delay": semester_delay * 12,
        "failed_grade_pressure": round(max(0, 10 - failed_grade) * 5, 2) if failed_grade is not None else 0,
        "dependency_grade_average": round(dependency_average or 0, 2),
        "dependency_grade_bonus": round((dependency_average or 0) * 2, 2),
        "student_priority": request.priority * 3,
        "preference_order_penalty": -(request.preference_order - 1) * 4,
    }
    return float(sum(breakdown.values())), breakdown


def history_for_course_context(
    db: Session,
    student: Student,
    course: Course,
) -> StudentCourseHistory | None:
    rows = (
        db.query(StudentCourseHistory)
        .filter(StudentCourseHistory.student_id == student.id)
        .order_by(StudentCourseHistory.created_at.desc())
        .all()
    )
    course_by_id = {item.id: item for item in db.query(Course).all()}
    target_context = normalize_context_key(course.context_key)
    for history in rows:
        history_course = course_by_id.get(history.course_id)
        if not history_course:
            continue
        if history.course_id == course.id:
            return history
        if (
            target_context
            and history_course.shareable
            and normalize_context_key(history_course.context_key) == target_context
        ):
            return history
    return None


def dependency_grade_average(
    db: Session,
    course: Course,
    completed: dict[str, StudentCourseHistory],
    completed_contexts: dict[str, StudentCourseHistory],
) -> float | None:
    restrictions = restrictions_for_courses(db, [course.id]).get(course.id, [])
    grades: list[float] = []
    course_by_id = {item.id: item for item in db.query(Course).all()}
    for restriction in restrictions:
        if restriction.kind != CourseRestrictionKind.prerequisite:
            continue
        history = completed.get(restriction.required_course_id)
        required_course = course_by_id.get(restriction.required_course_id)
        if (
            not history
            and required_course
            and required_course.shareable
            and (context_key := normalize_context_key(required_course.context_key))
        ):
            history = completed_contexts.get(context_key)
        if history and history.grade is not None:
            grades.append(history.grade)
    if not grades:
        return None
    return sum(grades) / len(grades)


def add_enrollment(
    db: Session,
    request: StudentCourseRequest,
    course: Course,
    target_semester: str,
    stage: str,
    run_id: str | None,
    status: str,
    score: float,
    score_breakdown: dict[str, Any],
    reason: str,
) -> None:
    db.add(
        StudentEnrollment(
            student_id=request.student_id,
            course_id=course.id,
            request_id=request.id,
            run_id=run_id,
            target_semester=target_semester,
            stage=stage,
            status=status,
            score=score,
            score_breakdown=score_breakdown,
            reason=reason,
        )
    )
