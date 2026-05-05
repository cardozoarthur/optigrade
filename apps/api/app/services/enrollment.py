from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import (
    Assignment,
    ConstraintStrength,
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
    TimeSlot,
)
from app.services.student_planning import (
    completed_contexts_by_course,
    completed_history_by_course,
    course_completion_key,
    course_eligible_for_student,
    eligibility_course_for_student,
    regular_relation_for_student,
    restrictions_for_courses,
)
from app.services.course_identity import academic_context_key, academic_group_identity


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
    assignment_windows = (
        assignment_windows_by_bucket(db, run_id, capacity_plan.bucket_by_course)
        if run_id
        else None
    )
    used_by_bucket = {bucket_id: 0 for bucket_id in capacity_plan.capacity_by_bucket}
    candidates_by_group: dict[tuple[str, str], list[EnrollmentCandidate]] = {}
    status_by_request_id: dict[str, str] = {}
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
            status_by_request_id[request.id] = EnrollmentStatus.blocked.value
            continue
        score, breakdown = score_enrollment_candidate(db, student, course, eligibility_course, request)
        group = (student.id, request.alternative_group or f"course:{course.id}")
        candidates_by_group.setdefault(group, []).append(
            EnrollmentCandidate(request, student, course, eligibility_course, score, breakdown)
        )

    branches_by_group = candidate_branches_by_group(candidates_by_group)
    allocated_by_group: dict[tuple[str, str], list[EnrollmentCandidate]] = {}
    solver_planned_request_ids = planned_request_ids_for_run(db, run_id)
    solver_planned_allocations = 0
    if solver_planned_request_ids:
        for group, branches in branches_by_group.items():
            planned = next(
                (
                    branch
                    for branch in branches.values()
                    if {candidate.request.id for candidate in branch} <= solver_planned_request_ids
                ),
                None,
            )
            if not planned:
                continue
            if branch_has_capacity(planned, capacity_plan, used_by_bucket, capacity_by_course, assignment_windows):
                allocated_by_group[group] = planned
                reserve_branch_capacity(planned, capacity_plan, used_by_bucket)
                solver_planned_allocations += len(planned)

    max_order = max(
        (
            preference_order
            for branches in branches_by_group.values()
            for preference_order in branches
        ),
        default=0,
    )
    for preference_order in range(1, max_order + 1):
        round_branches = [
            (group, branch)
            for group, branches in branches_by_group.items()
            if group not in allocated_by_group
            for branch_order, branch in branches.items()
            if branch_order == preference_order
        ]
        round_branches.sort(
            key=lambda item: (
                -branch_score(item[1]),
                branch_preference_order(item[1]),
                -branch_priority(item[1]),
                item[1][0].student.current_semester,
                item[1][0].student.registration_number or item[1][0].student.name,
            )
        )
        for group, branch in round_branches:
            if group in allocated_by_group:
                continue
            if not branch_has_capacity(branch, capacity_plan, used_by_bucket, capacity_by_course, assignment_windows):
                continue
            allocated_by_group[group] = branch
            reserve_branch_capacity(branch, capacity_plan, used_by_bucket)

    students_without_enrollment_before_rescue = students_without_enrollment_count(
        candidates_by_group,
        allocated_by_group,
        rescue_allocations={},
    )
    rescue_allocations, rescue_displacements = rescue_students_without_enrollment(
        candidates_by_group,
        allocated_by_group,
        capacity_plan,
        used_by_bucket,
        capacity_by_course,
        assignment_windows,
    )
    rescue_request_ids = set(rescue_allocations)

    enrolled = 0
    waitlisted = 0
    superseded = 0
    enrolled_by_course: dict[str, int] = {}
    waitlisted_by_course: dict[str, int] = {}
    for group, values in candidates_by_group.items():
        allocated = allocated_by_group.get(group)
        allocated_request_ids = {
            candidate.request.id for candidate in allocated
        } if allocated else set()
        allocated_order = branch_preference_order(allocated) if allocated else None
        for candidate in values:
            if candidate.request.id in allocated_request_ids:
                enrolled += 1
                enrolled_by_course[candidate.course.id] = (
                    enrolled_by_course.get(candidate.course.id, 0) + 1
                )
                status = EnrollmentStatus.enrolled.value
                reason = "Alocado pela rodada automatica"
            elif candidate.request.id in rescue_request_ids:
                enrolled += 1
                enrolled_by_course[candidate.course.id] = (
                    enrolled_by_course.get(candidate.course.id, 0) + 1
                )
                status = EnrollmentStatus.enrolled.value
                reason = "Alocado em turma de resgate para evitar semestre sem matricula"
            elif allocated:
                superseded += 1
                status = EnrollmentStatus.superseded.value
                reason = (
                    "Opcao anterior substituida pela escolha otimizada do solver"
                    if allocated_order is not None
                    and candidate.request.preference_order < allocated_order
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
            status_by_request_id[candidate.request.id] = status

    db.commit()
    unplanned_after_enrollment = unplanned_request_status_summary(
        db,
        run_id,
        status_by_request_id,
    )
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
        "unplanned_after_enrollment": unplanned_after_enrollment,
        "rescue_enrolled": len(rescue_allocations),
        "rescue_displaced_allocations": rescue_displacements,
        "students_without_enrollment_before_rescue": students_without_enrollment_before_rescue,
        "students_without_enrollment_after_rescue": students_without_enrollment_count(
            candidates_by_group,
            allocated_by_group,
            rescue_allocations=rescue_allocations,
        ),
    }


def course_capacity_by_id(db: Session, run_id: str | None) -> dict[str, int]:
    return course_capacity_plan(db, run_id).capacity_by_course


def candidate_branches_by_group(
    candidates_by_group: dict[tuple[str, str], list[EnrollmentCandidate]],
) -> dict[tuple[str, str], dict[int, list[EnrollmentCandidate]]]:
    grouped: dict[tuple[str, str], dict[int, list[EnrollmentCandidate]]] = {}
    for group, candidates in candidates_by_group.items():
        branches = grouped.setdefault(group, {})
        for candidate in candidates:
            branches.setdefault(candidate.request.preference_order, []).append(candidate)
        for branch in branches.values():
            branch.sort(key=lambda item: (item.request.created_at, item.course.name))
    return grouped


def branch_has_capacity(
    branch: list[EnrollmentCandidate],
    capacity_plan: EnrollmentCapacityPlan,
    used_by_bucket: dict[str, int],
    capacity_by_course: dict[str, int],
    assignment_windows: dict[str, list[tuple[int, int, int]]] | None = None,
) -> bool:
    simulated_usage = dict(used_by_bucket)
    for candidate in branch:
        if not candidate_has_capacity(
            candidate,
            capacity_plan,
            simulated_usage,
            capacity_by_course,
            assignment_windows,
        ):
            return False
        reserve_candidate_capacity(candidate, capacity_plan, simulated_usage)
    return True


def reserve_branch_capacity(
    branch: list[EnrollmentCandidate],
    capacity_plan: EnrollmentCapacityPlan,
    used_by_bucket: dict[str, int],
) -> None:
    for candidate in branch:
        reserve_candidate_capacity(candidate, capacity_plan, used_by_bucket)


def branch_score(branch: list[EnrollmentCandidate]) -> float:
    return sum(candidate.score for candidate in branch)


def branch_priority(branch: list[EnrollmentCandidate]) -> float:
    if not branch:
        return 0
    return sum(candidate.request.priority for candidate in branch) / len(branch)


def branch_preference_order(branch: list[EnrollmentCandidate] | None) -> int | None:
    if not branch:
        return None
    return min(candidate.request.preference_order for candidate in branch)


def rescue_students_without_enrollment(
    candidates_by_group: dict[tuple[str, str], list[EnrollmentCandidate]],
    allocated_by_group: dict[tuple[str, str], list[EnrollmentCandidate]],
    capacity_plan: EnrollmentCapacityPlan,
    used_by_bucket: dict[str, int],
    capacity_by_course: dict[str, int],
    assignment_windows: dict[str, list[tuple[int, int, int]]] | None,
) -> tuple[dict[str, EnrollmentCandidate], list[dict[str, Any]]]:
    allocated_student_ids = {
        candidate.student.id
        for branch in allocated_by_group.values()
        for candidate in branch
    }
    candidates_by_student: dict[str, list[EnrollmentCandidate]] = {}
    for (student_id, _group), candidates in candidates_by_group.items():
        if student_id in allocated_student_ids:
            continue
        unique_by_request = {
            candidate.request.id: candidate
            for candidate in candidates
        }
        candidates_by_student.setdefault(student_id, []).extend(unique_by_request.values())

    student_ids = sorted(
        candidates_by_student,
        key=lambda student_id: (
            -max(candidate.student.current_semester for candidate in candidates_by_student[student_id]),
            -max(candidate.score for candidate in candidates_by_student[student_id]),
            min(
                candidate.student.registration_number or candidate.student.name
                for candidate in candidates_by_student[student_id]
            ),
        ),
    )
    rescue_allocations: dict[str, EnrollmentCandidate] = {}
    displacements: list[dict[str, Any]] = []
    for student_id in student_ids:
        candidates = sorted(
            candidates_by_student[student_id],
            key=lambda candidate: (
                candidate.request.preference_order,
                -candidate.request.priority,
                -candidate.score,
                candidate.request.created_at,
                candidate.course.name,
            ),
        )
        for candidate in candidates:
            if not candidate_has_capacity(
                candidate,
                capacity_plan,
                used_by_bucket,
                capacity_by_course,
                assignment_windows,
            ):
                continue
            rescue_allocations[candidate.request.id] = candidate
            reserve_candidate_capacity(candidate, capacity_plan, used_by_bucket)
            break
        if any(candidate.student.id == student_id for candidate in rescue_allocations.values()):
            continue
        for candidate in candidates:
            displacement = displace_redundant_allocation_for_candidate(
                candidate,
                allocated_by_group,
                capacity_plan,
                used_by_bucket,
                capacity_by_course,
                assignment_windows,
            )
            if displacement is None:
                continue
            rescue_allocations[candidate.request.id] = candidate
            reserve_candidate_capacity(candidate, capacity_plan, used_by_bucket)
            allocated_by_group[(candidate.student.id, f"rescue:{candidate.request.id}")] = [candidate]
            displacements.append(displacement)
            break
    return rescue_allocations, displacements


def displace_redundant_allocation_for_candidate(
    candidate: EnrollmentCandidate,
    allocated_by_group: dict[tuple[str, str], list[EnrollmentCandidate]],
    capacity_plan: EnrollmentCapacityPlan,
    used_by_bucket: dict[str, int],
    capacity_by_course: dict[str, int],
    assignment_windows: dict[str, list[tuple[int, int, int]]] | None,
) -> dict[str, Any] | None:
    bucket_id = capacity_plan.bucket_by_course.get(candidate.course.id, candidate.course.id)
    if assignment_windows is not None and not request_time_is_scheduled(
        candidate.request,
        assignment_windows.get(bucket_id, []),
    ):
        return None

    allocated_count_by_student: dict[str, int] = {}
    for branch in allocated_by_group.values():
        for allocated_candidate in branch:
            allocated_count_by_student[allocated_candidate.student.id] = (
                allocated_count_by_student.get(allocated_candidate.student.id, 0) + 1
            )

    victim_groups = sorted(
        (
            (group, branch)
            for group, branch in allocated_by_group.items()
            if any(
                capacity_plan.bucket_by_course.get(item.course.id, item.course.id) == bucket_id
                for item in branch
            )
            and branch[0].student.id != candidate.student.id
            and allocated_count_by_student.get(branch[0].student.id, 0) - len(branch) >= 1
        ),
        key=lambda item: (
            branch_score(item[1]),
            branch_priority(item[1]),
            -len(item[1]),
            item[1][0].student.current_semester,
            item[1][0].student.registration_number or item[1][0].student.name,
        ),
    )
    for victim_group, victim_branch in victim_groups:
        release_branch_capacity(victim_branch, capacity_plan, used_by_bucket)
        if candidate_has_capacity(
            candidate,
            capacity_plan,
            used_by_bucket,
            capacity_by_course,
            assignment_windows,
        ):
            allocated_by_group.pop(victim_group, None)
            return {
                "rescued_student_id": candidate.student.id,
                "rescued_request_id": candidate.request.id,
                "rescued_course_id": candidate.course.id,
                "displaced_student_id": victim_branch[0].student.id,
                "displaced_request_ids": [item.request.id for item in victim_branch],
                "reason": (
                    "Vaga realocada de aluno ja atendido para evitar aluno sem nenhuma turma."
                ),
            }
        reserve_branch_capacity(victim_branch, capacity_plan, used_by_bucket)
    return None


def release_branch_capacity(
    branch: list[EnrollmentCandidate],
    capacity_plan: EnrollmentCapacityPlan,
    used_by_bucket: dict[str, int],
) -> None:
    for candidate in branch:
        bucket_id = capacity_plan.bucket_by_course.get(candidate.course.id, candidate.course.id)
        used_by_bucket[bucket_id] = max(0, used_by_bucket.get(bucket_id, 0) - 1)


def students_without_enrollment_count(
    candidates_by_group: dict[tuple[str, str], list[EnrollmentCandidate]],
    allocated_by_group: dict[tuple[str, str], list[EnrollmentCandidate]],
    *,
    rescue_allocations: dict[str, EnrollmentCandidate],
) -> int:
    student_ids = {student_id for student_id, _group in candidates_by_group}
    allocated_student_ids = {
        candidate.student.id
        for branch in allocated_by_group.values()
        for candidate in branch
    }
    rescued_student_ids = {
        candidate.student.id
        for candidate in rescue_allocations.values()
    }
    return len(student_ids - allocated_student_ids - rescued_student_ids)


def candidate_has_capacity(
    candidate: EnrollmentCandidate,
    capacity_plan: EnrollmentCapacityPlan,
    used_by_bucket: dict[str, int],
    capacity_by_course: dict[str, int],
    assignment_windows: dict[str, list[tuple[int, int, int]]] | None = None,
) -> bool:
    bucket_id = capacity_plan.bucket_by_course.get(candidate.course.id, candidate.course.id)
    if assignment_windows is not None and not request_time_is_scheduled(
        candidate.request,
        assignment_windows.get(bucket_id, []),
    ):
        return False
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


def unplanned_request_status_summary(
    db: Session,
    run_id: str | None,
    status_by_request_id: dict[str, str],
) -> dict[str, Any]:
    if not run_id:
        return {
            "total": 0,
            "enrolled": 0,
            "waitlisted": 0,
            "blocked": 0,
            "superseded": 0,
            "unknown": 0,
            "remaining": 0,
            "remaining_request_ids": [],
        }
    run = db.get(OptimizationRun, run_id)
    demand_plan = (run.metrics or {}).get("student_demand_plan") if run else None
    if not isinstance(demand_plan, dict):
        return {
            "total": 0,
            "enrolled": 0,
            "waitlisted": 0,
            "blocked": 0,
            "superseded": 0,
            "unknown": 0,
            "remaining": 0,
            "remaining_request_ids": [],
        }
    raw_request_ids = demand_plan.get("unplanned_request_ids")
    if not isinstance(raw_request_ids, list):
        return {
            "total": 0,
            "enrolled": 0,
            "waitlisted": 0,
            "blocked": 0,
            "superseded": 0,
            "unknown": 0,
            "remaining": 0,
            "remaining_request_ids": [],
        }
    request_ids = [request_id for request_id in raw_request_ids if isinstance(request_id, str)]
    counts = {
        "total": len(request_ids),
        "enrolled": 0,
        "waitlisted": 0,
        "blocked": 0,
        "superseded": 0,
        "unknown": 0,
    }
    remaining_request_ids: list[str] = []
    for request_id in request_ids:
        status = status_by_request_id.get(request_id)
        if status in counts:
            counts[status] += 1
        else:
            counts["unknown"] += 1
        if status in {EnrollmentStatus.waitlisted.value, EnrollmentStatus.blocked.value} or status is None:
            remaining_request_ids.append(request_id)
    counts["remaining"] = len(remaining_request_ids)
    counts["remaining_request_ids"] = remaining_request_ids
    return counts


def assignment_windows_by_bucket(
    db: Session,
    run_id: str | None,
    bucket_by_course: dict[str, str],
) -> dict[str, list[tuple[int, int, int]]]:
    if not run_id:
        return {}
    rows = (
        db.query(Assignment.course_id, TimeSlot.day, TimeSlot.start_minute, TimeSlot.end_minute)
        .join(TimeSlot, TimeSlot.id == Assignment.time_slot_id)
        .filter(Assignment.run_id == run_id)
        .all()
    )
    windows: dict[str, list[tuple[int, int, int]]] = {}
    for course_id, day, start_minute, end_minute in rows:
        bucket_id = bucket_by_course.get(course_id, f"course:{course_id}")
        windows.setdefault(bucket_id, []).append((int(day), int(start_minute), int(end_minute)))
    return windows


def request_time_is_scheduled(
    request: StudentCourseRequest,
    assignment_windows: list[tuple[int, int, int]],
) -> bool:
    if request.time_preference_strength != ConstraintStrength.hard:
        return True
    if (
        request.desired_day is None
        or request.desired_start_minute is None
        or request.desired_end_minute is None
    ):
        return True
    return any(
        time_window_matches_request(
            request.desired_day,
            request.desired_start_minute,
            request.desired_end_minute,
            day,
            start_minute,
            end_minute,
        )
        for day, start_minute, end_minute in assignment_windows
    )


def time_window_matches_request(
    desired_day: int,
    desired_start_minute: int,
    desired_end_minute: int,
    day: int,
    start_minute: int,
    end_minute: int,
) -> bool:
    if desired_day != day:
        return False
    overlap = min(desired_end_minute, end_minute) - max(desired_start_minute, start_minute)
    if overlap <= 0:
        return False
    slot_duration = end_minute - start_minute
    desired_duration = desired_end_minute - desired_start_minute
    return overlap >= min(slot_duration, desired_duration) * 0.95 and overlap >= 60


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
    academic_identity = academic_group_identity(course)
    if academic_identity:
        return "|".join(academic_identity)
    context_key = academic_context_key(course)
    if course.shareable and context_key:
        return f"context|{context_key}"
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
    target_context = course_completion_key(course)
    for history in rows:
        history_course = course_by_id.get(history.course_id)
        if not history_course:
            continue
        if history.course_id == course.id:
            return history
        if target_context and course_completion_key(history_course) == target_context:
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
            and (context_key := course_completion_key(required_course))
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
