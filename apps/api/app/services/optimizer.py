from __future__ import annotations

import math
import random
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    Assignment,
    AvailabilityKind,
    Campus,
    ConstraintStrength,
    Course,
    CourseKind,
    DegreeProgram,
    OptimizationRun,
    Professor,
    ProfessorAvailability,
    ProfessorContract,
    ProfessorConstraint,
    ProfessorCoursePreference,
    ProfessorQualification,
    Room,
    RoomKind,
    RunStatus,
    TimeSlot,
)
from app.services.student_planning import (
    DemandChoice,
    StudentDemandChoiceSummary,
    demand_from_allocations,
    student_demand_choice_summary,
)

PLANNING_SECTION_CAPACITY = 50
PLANNING_MIN_SECTION_DEMAND = 3
SECTION_SESSION_OFFSET = 100


@dataclass(frozen=True)
class CourseData:
    id: str
    name: str
    code: str | None
    workload_hours: int
    theoretical_hours: int
    practical_hours: int
    kind: str
    recommended_semester: int
    expected_demand: int
    requires_lab: bool
    criticality: int
    context_key: str | None
    shareable: bool
    source_course_ids: tuple[str, ...]
    campus_id: str | None = None
    degree_program_id: str | None = None
    campus_names: tuple[str, ...] = ()
    degree_program_names: tuple[str, ...] = ()
    regular_time_windows: tuple[tuple[int, int], ...] = ()
    official_schedule: tuple[tuple[int, int, int], ...] = ()
    section_index: int = 0
    section_count: int = 1
    planned_total_demand: int = 0
    planned_unserved_demand: int = 0
    section_strategy: str = "single"


@dataclass(frozen=True)
class ProfessorData:
    id: str
    name: str
    department: str
    is_borrowed: bool
    borrowed_from_department: str | None


@dataclass(frozen=True)
class ContractData:
    min_hours: int
    max_hours: int
    semester: str | None = None
    is_borrowed: bool = False
    borrowed_from_department: str | None = None


@dataclass(frozen=True)
class RoomData:
    id: str
    name: str
    capacity: int
    kind: str
    campus_id: str | None = None


@dataclass(frozen=True)
class SlotData:
    id: str
    day: int
    start_minute: int
    end_minute: int
    label: str

    @property
    def hours(self) -> float:
        return (self.end_minute - self.start_minute) / 60


@dataclass(frozen=True)
class AvailabilityData:
    day: int
    start_minute: int
    end_minute: int
    kind: str
    strength: str


@dataclass(frozen=True)
class PreferenceData:
    course_id: str
    preference: int
    strength: str


@dataclass(frozen=True)
class Snapshot:
    semester: str
    courses: list[CourseData]
    professors: list[ProfessorData]
    rooms: list[RoomData]
    slots: list[SlotData]
    contracts: dict[str, ContractData]
    qualifications: dict[str, set[str]]
    availability: dict[str, list[AvailabilityData]]
    preferences: dict[str, dict[str, PreferenceData]]
    source_course_to_snapshot_course: dict[str, tuple[str, ...]]
    student_demand_requests: int = 0
    student_demand_raw_requests: int = 0
    student_demand_blocked_requests: int = 0
    student_regular_requests: int = 0
    student_reoffer_requests: int = 0
    student_elective_requests: int = 0
    student_demand_plan: dict[str, Any] | None = None


@dataclass
class ProposedAssignment:
    course_id: str
    professor_id: str
    room_id: str
    time_slot_id: str
    session_index: int
    hard_violations: list[dict[str, Any]]
    soft_violations: list[dict[str, Any]]
    origin: str = "optimized"


@dataclass
class CandidateSolution:
    assignments: list[ProposedAssignment]
    metrics: dict[str, Any]
    objectives: dict[str, float]
    explanation: str
    score: float


@dataclass(frozen=True)
class DemandPlan:
    demand_by_course: dict[str, int]
    first_choice_demand_by_course: dict[str, int]
    all_eligible_demand_by_course: dict[str, int]
    selected_choices: dict[tuple[str, str], DemandChoice]
    unplanned_choices: dict[tuple[str, str], DemandChoice]
    alternative_assignments: int
    metrics: dict[str, Any]


PROFILE_SETTINGS = {
    "fast": {"attempts": 80, "local_steps": 80},
    "balanced": {"attempts": 240, "local_steps": 180},
    "deep": {"attempts": 720, "local_steps": 360},
    "official_ufpel": {"attempts": 0, "local_steps": 0},
}


def run_optimization(db: Session, run: OptimizationRun) -> OptimizationRun:
    started = time.perf_counter()
    profile = run.profile if run.profile in PROFILE_SETTINGS else settings.optigrade_optimizer_profile
    params = PROFILE_SETTINGS.get(profile, PROFILE_SETTINGS["balanced"]) | run.parameters
    demand_driven = bool(params.get("student_demand_only", False))

    run.status = RunStatus.running
    db.commit()

    snapshot = build_snapshot(db, semester=run.semester, demand_driven=demand_driven)
    if profile == "official_ufpel":
        snapshot = official_schedule_snapshot(snapshot)

    diagnosis = diagnose_snapshot(snapshot)
    if diagnosis:
        run.status = RunStatus.infeasible
        run.metrics = {"hard_conflicts": len(diagnosis), "diagnosis": diagnosis}
        run.pareto_front = []
        run.explanation = "Cenario inviavel antes da busca: " + "; ".join(d["message"] for d in diagnosis[:4])
        run.score = None
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        return run

    if profile == "official_ufpel":
        ranked = [build_official_schedule_solution(snapshot)]
        best = ranked[0]
    else:
        large_instance = is_large_instance(snapshot)
        attempts = int(params["attempts"])
        local_steps = int(params["local_steps"])
        if large_instance:
            attempts = min(attempts, 16)
            local_steps = min(local_steps, 40)
        max_worker_cap = 4 if large_instance else 24
        max_workers = max(1, min(settings.optigrade_max_threads, attempts, max_worker_cap))
        seeds = [random.randrange(1_000_000_000) for _ in range(attempts)]

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            solutions = list(executor.map(lambda seed: build_solution(snapshot, seed), seeds))

        improved = [improve_solution(snapshot, solution, local_steps) for solution in solutions]
        cp_sat_solution = None if large_instance else _try_cp_sat(snapshot, profile)
        if cp_sat_solution:
            improved.append(cp_sat_solution)
        rust_solution = None if large_instance else _try_optional_rust(snapshot, profile)
        if rust_solution:
            improved.append(rust_solution)
        feasible = [solution for solution in improved if solution.objectives["hard_conflicts"] == 0]
        ranked = sorted(feasible or improved, key=lambda item: item.score)
        best = ranked[0]

    run.assignments.clear()
    course_by_snapshot_id = {course.id: course for course in snapshot.courses}
    for item in best.assignments:
        course = course_by_snapshot_id.get(item.course_id)
        db.add(
            Assignment(
                run_id=run.id,
                course_id=representative_course_id(snapshot, item.course_id),
                professor_id=item.professor_id,
                room_id=item.room_id,
                time_slot_id=item.time_slot_id,
                session_index=persisted_session_index(course, item.session_index),
                hard_violations=item.hard_violations,
                soft_violations=item.soft_violations,
                origin=item.origin,
            )
        )

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    final_status = RunStatus.feasible if best.objectives["hard_conflicts"] == 0 else RunStatus.infeasible
    wait_for_auto_enrollment = (
        final_status == RunStatus.feasible
        and bool(run.parameters.get("auto_enrollment", False))
        and snapshot.student_demand_requests > 0
    )
    run.status = RunStatus.running if wait_for_auto_enrollment else final_status
    run.metrics = best.metrics | {
        "elapsed_ms": elapsed_ms,
        "semester": run.semester,
        "profile": profile,
        "optimization_status": final_status.value,
        "post_processing": "automatic_enrollment" if wait_for_auto_enrollment else None,
        "attempts": int(params["attempts"]),
        "workers": 0 if profile == "official_ufpel" else max_workers,
        "effective_attempts": 0 if profile == "official_ufpel" else attempts,
        "effective_local_steps": 0 if profile == "official_ufpel" else local_steps,
        "adaptive_large_instance": profile != "official_ufpel" and is_large_instance(snapshot),
        "borrowed_professors": [
            {
                "id": professor.id,
                "name": professor.name,
                "borrowed_from_department": professor.borrowed_from_department,
                "load": best.metrics.get("load_by_professor", {}).get(professor.id, 0),
            }
            for professor in snapshot.professors
            if professor.is_borrowed
        ],
        "shared_course_groups": shared_course_group_metrics(snapshot),
        "academic_context_groups": len(
            [course for course in snapshot.courses if len(course.source_course_ids) > 1]
        ),
        "student_demand_requests": snapshot.student_demand_requests,
        "student_demand_raw_requests": snapshot.student_demand_raw_requests,
        "student_demand_blocked_requests": snapshot.student_demand_blocked_requests,
        "student_regular_requests": snapshot.student_regular_requests,
        "student_reoffer_requests": snapshot.student_reoffer_requests,
        "student_elective_requests": snapshot.student_elective_requests,
        "student_demand_only": demand_driven,
        "student_demand_plan": snapshot.student_demand_plan or {},
        "planned_sections": planned_sections_metrics(snapshot),
        "portfolio": [
            "precheck",
            "cp_sat_baseline",
            "multi_start_greedy",
            "local_search",
            "rust_optional",
            "pareto_ranking",
            "official_ufpel_schedule" if profile == "official_ufpel" else "optimized_schedule",
        ],
    }
    run.pareto_front = [
        {
            "rank": index + 1,
            "score": solution.score,
            "objectives": solution.objectives,
            "explanation": solution.explanation,
        }
        for index, solution in enumerate(ranked[:8])
    ]
    run.explanation = best.explanation
    run.score = best.score
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run


def _try_optional_rust(snapshot: Snapshot, profile: str) -> CandidateSolution | None:
    from app.services.rust_bridge import try_rust_optimizer

    return try_rust_optimizer(snapshot, profile)


def _try_cp_sat(snapshot: Snapshot, profile: str) -> CandidateSolution | None:
    from app.services.cp_sat_solver import solve_cp_sat_baseline

    timeout = 2.0 if profile == "fast" else 5.0 if profile == "balanced" else 12.0
    return solve_cp_sat_baseline(snapshot, max_seconds=timeout)


def is_large_instance(snapshot: Snapshot) -> bool:
    return snapshot.student_demand_requests >= 5_000 or len(snapshot.courses) >= 180


def build_snapshot(
    db: Session,
    semester: str = "2026/2",
    demand_driven: bool = False,
) -> Snapshot:
    raw_contracts = {item.professor_id: item for item in db.query(ProfessorContract).all()}
    active_professors: list[Professor] = []
    contracts: dict[str, ContractData] = {}
    for professor in db.query(Professor).all():
        contract = raw_contracts.get(professor.id)
        if not contract:
            active_professors.append(professor)
            continue
        if not contract_applies_to_semester(contract, semester):
            continue
        active_professors.append(professor)
        contracts[professor.id] = ContractData(
            min_hours=contract.min_hours,
            max_hours=contract.max_hours,
            semester=contract.semester,
            is_borrowed=contract.is_borrowed,
            borrowed_from_department=contract.borrowed_from_department,
        )
    active_professor_ids = {professor.id for professor in active_professors}

    campus_by_id = {item.id: item for item in db.query(Campus).all()}
    degree_program_by_id = {item.id: item for item in db.query(DegreeProgram).all()}
    rooms = [
        RoomData(
            id=item.id,
            name=item.name,
            capacity=item.capacity,
            kind=item.kind.value,
            campus_id=item.campus_id,
        )
        for item in db.query(Room).all()
    ]
    raw_courses = db.query(Course).all()
    demand_choices = student_demand_choice_summary(db, semester)
    demand_plan = solve_student_demand_plan(
        demand_choices,
        raw_courses,
        rooms,
        demand_driven=demand_driven,
    )
    requested_demand_by_course = (
        demand_plan.demand_by_course
        if demand_driven
        else demand_plan.first_choice_demand_by_course
    )
    if demand_driven:
        raw_courses = demand_driven_courses(raw_courses, requested_demand_by_course)
    courses, source_course_to_snapshot_course = build_course_snapshot(
        raw_courses,
        campus_by_id,
        degree_program_by_id,
        requested_demand_by_course,
        rooms,
        demand_driven=demand_driven,
    )
    professors = [
        ProfessorData(
            id=item.id,
            name=item.name,
            department=item.department,
            is_borrowed=contracts.get(item.id, ContractData(0, 12)).is_borrowed,
            borrowed_from_department=contracts.get(item.id, ContractData(0, 12)).borrowed_from_department,
        )
        for item in active_professors
    ]
    slots = [
        SlotData(
            id=item.id,
            day=item.day,
            start_minute=item.start_minute,
            end_minute=item.end_minute,
            label=item.label,
        )
        for item in db.query(TimeSlot).all()
    ]
    qualifications: dict[str, set[str]] = {}
    for item in db.query(ProfessorQualification).all():
        if item.professor_id not in active_professor_ids:
            continue
        snapshot_course_ids = source_course_to_snapshot_course.get(item.course_id, ())
        for snapshot_course_id in snapshot_course_ids:
            qualifications.setdefault(item.professor_id, set()).add(snapshot_course_id)
    availability: dict[str, list[AvailabilityData]] = {}
    for item in db.query(ProfessorAvailability).all():
        if item.professor_id not in active_professor_ids:
            continue
        availability.setdefault(item.professor_id, []).append(
            AvailabilityData(
                day=item.day,
                start_minute=item.start_minute,
                end_minute=item.end_minute,
                kind=item.kind.value,
                strength=item.strength.value,
            )
        )
    preferences: dict[str, dict[str, PreferenceData]] = {}
    for item in db.query(ProfessorCoursePreference).all():
        if item.professor_id not in active_professor_ids:
            continue
        snapshot_course_ids = source_course_to_snapshot_course.get(item.course_id, ())
        if not snapshot_course_ids:
            continue
        for snapshot_course_id in snapshot_course_ids:
            preference = PreferenceData(
                course_id=snapshot_course_id,
                preference=item.preference,
                strength=item.strength.value,
            )
            professor_preferences = preferences.setdefault(item.professor_id, {})
            current = professor_preferences.get(snapshot_course_id)
            if current is None or preference.preference > current.preference:
                professor_preferences[snapshot_course_id] = preference
    for item in db.query(ProfessorConstraint).all():
        if item.professor_id not in active_professor_ids:
            continue
        apply_professor_structured_constraint(item, courses, availability, preferences)
    teacher_pruning: list[dict[str, Any]] = []
    if demand_driven:
        courses, teacher_pruning = prune_courses_for_teaching_capacity(
            courses,
            professors,
            slots,
            contracts,
            qualifications,
            availability,
        )
        kept_course_ids = {course.id for course in courses}
        source_course_to_snapshot_course = {
            source_course_id: tuple(
                course_id for course_id in snapshot_course_ids if course_id in kept_course_ids
            )
            for source_course_id, snapshot_course_ids in source_course_to_snapshot_course.items()
            if any(course_id in kept_course_ids for course_id in snapshot_course_ids)
        }
        qualifications = {
            professor_id: course_ids & kept_course_ids
            for professor_id, course_ids in qualifications.items()
            if course_ids & kept_course_ids
        }
        preferences = {
            professor_id: {
                course_id: preference
                for course_id, preference in professor_preferences.items()
                if course_id in kept_course_ids
            }
            for professor_id, professor_preferences in preferences.items()
            if any(course_id in kept_course_ids for course_id in professor_preferences)
        }
        demand_plan.metrics["teacher_capacity_pruned_sections"] = teacher_pruning
        demand_plan.metrics["teacher_capacity_unplanned_students"] = sum(
            int(item["planned_students"]) for item in teacher_pruning
        )
    return Snapshot(
        semester=semester,
        courses=courses,
        professors=professors,
        rooms=rooms,
        slots=slots,
        contracts=contracts,
        qualifications=qualifications,
        availability=availability,
        preferences=preferences,
        source_course_to_snapshot_course=source_course_to_snapshot_course,
        student_demand_requests=demand_choices.eligible_requests,
        student_demand_raw_requests=demand_choices.total_requests,
        student_demand_blocked_requests=demand_choices.blocked_requests,
        student_regular_requests=demand_choices.regular_requests,
        student_reoffer_requests=demand_choices.reoffer_requests,
        student_elective_requests=demand_choices.elective_requests,
        student_demand_plan=demand_plan.metrics,
    )


@dataclass(frozen=True)
class DemandPlanningBucket:
    key: tuple[Any, ...]
    label: str
    course_ids: tuple[str, ...]
    regular_capacity: int
    large_capacity: int


def solve_student_demand_plan(
    choice_summary: StudentDemandChoiceSummary,
    raw_courses: list[Course],
    rooms: list[RoomData],
    *,
    demand_driven: bool,
) -> DemandPlan:
    ordered_choices = choice_summary.choices_by_group
    allocations = {
        group: choices[0]
        for group, choices in ordered_choices.items()
        if choices
    }
    course_by_id = {course.id: course for course in raw_courses}
    bucket_by_course = {
        course.id: course_group_key(course)
        for course in raw_courses
    }
    buckets = build_demand_planning_buckets(raw_courses, rooms)

    if demand_driven and allocations:
        allocations = optimize_student_choice_allocations(
            ordered_choices,
            allocations,
            bucket_by_course,
            buckets,
        )

    selected_choices, unplanned_choices = suppress_unviable_small_remainders(
        allocations,
        bucket_by_course,
        buckets,
    )
    demand_by_course = demand_from_allocations(selected_choices.values())
    first_choice_demand = choice_summary.first_choice_demand_by_course
    alternative_assignments = sum(
        1
        for group, choice in selected_choices.items()
        if ordered_choices.get(group) and ordered_choices[group][0].request.id != choice.request.id
    )
    planned_bucket_metrics = demand_planning_bucket_metrics(
        demand_by_course,
        bucket_by_course,
        buckets,
        course_by_id,
    )
    metrics = {
        "demand_solver_enabled": demand_driven,
        "choice_groups": choice_summary.choice_groups,
        "eligible_requests": choice_summary.eligible_requests,
        "blocked_requests": choice_summary.blocked_requests,
        "planned_choice_groups": len(selected_choices),
        "unplanned_choice_groups": len(unplanned_choices),
        "alternative_assignments": alternative_assignments,
        "first_choice_demand_by_course": first_choice_demand,
        "all_eligible_demand_by_course": choice_summary.all_eligible_demand_by_course,
        "selected_demand_by_course": demand_by_course,
        "unplanned_demand_by_course": demand_from_allocations(unplanned_choices.values()),
        "planning_buckets": planned_bucket_metrics[:80],
    }
    return DemandPlan(
        demand_by_course=demand_by_course,
        first_choice_demand_by_course=first_choice_demand,
        all_eligible_demand_by_course=choice_summary.all_eligible_demand_by_course,
        selected_choices=selected_choices,
        unplanned_choices=unplanned_choices,
        alternative_assignments=alternative_assignments,
        metrics=metrics,
    )


def build_demand_planning_buckets(
    raw_courses: list[Course],
    rooms: list[RoomData],
) -> dict[tuple[Any, ...], DemandPlanningBucket]:
    grouped: dict[tuple[Any, ...], list[Course]] = {}
    for course in raw_courses:
        grouped.setdefault(course_group_key(course), []).append(course)

    buckets: dict[tuple[Any, ...], DemandPlanningBucket] = {}
    for key, group in grouped.items():
        representative = group[0]
        campus_id = common_value([course.campus_id for course in group])
        compatible_capacities = sorted(
            room.capacity
            for room in rooms
            if (not campus_id or not room.campus_id or room.campus_id == campus_id)
            and (not representative.requires_lab or room.kind == RoomKind.lab.value)
        )
        regular_capacity = max(
            [capacity for capacity in compatible_capacities if capacity <= PLANNING_SECTION_CAPACITY],
            default=PLANNING_SECTION_CAPACITY,
        )
        large_capacity = max(
            [capacity for capacity in compatible_capacities if capacity > PLANNING_SECTION_CAPACITY],
            default=0,
        )
        buckets[key] = DemandPlanningBucket(
            key=key,
            label=demand_bucket_label(group),
            course_ids=tuple(course.id for course in group),
            regular_capacity=regular_capacity,
            large_capacity=large_capacity,
        )
    return buckets


def optimize_student_choice_allocations(
    ordered_choices: dict[tuple[str, str], tuple[DemandChoice, ...]],
    initial_allocations: dict[tuple[str, str], DemandChoice],
    bucket_by_course: dict[str, tuple[Any, ...]],
    buckets: dict[tuple[Any, ...], DemandPlanningBucket],
) -> dict[tuple[str, str], DemandChoice]:
    allocations = dict(initial_allocations)
    course_demand = demand_from_allocations(allocations.values())
    bucket_demand = bucket_demand_from_course_demand(course_demand, bucket_by_course)

    for _round in range(8):
        changed = False
        problem_buckets = sorted(
            (
                (bucket_problem_weight(bucket_demand.get(bucket_key, 0), bucket), bucket_key)
                for bucket_key, bucket in buckets.items()
            ),
            reverse=True,
        )
        for problem_weight, bucket_key in problem_buckets:
            if problem_weight <= 0:
                continue
            batch_move = best_batch_move_from_problem_bucket(
                bucket_key,
                ordered_choices,
                allocations,
                bucket_by_course,
                buckets,
                bucket_demand,
            )
            if batch_move:
                for group, alternative in batch_move:
                    previous = allocations[group]
                    previous_bucket_key = bucket_by_course[previous.demand_course.id]
                    next_bucket_key = bucket_by_course[alternative.demand_course.id]
                    allocations[group] = alternative
                    bucket_demand[previous_bucket_key] = bucket_demand.get(previous_bucket_key, 0) - 1
                    bucket_demand[next_bucket_key] = bucket_demand.get(next_bucket_key, 0) + 1
                changed = True
                break
            group_keys = [
                group
                for group, choice in allocations.items()
                if bucket_by_course.get(choice.demand_course.id) == bucket_key
            ]
            group_keys.sort(
                key=lambda group: (
                    allocations[group].request.priority,
                    -allocations[group].request.preference_order,
                    allocations[group].request.created_at,
                )
            )
            for group in group_keys:
                current_choice = allocations[group]
                best_choice: DemandChoice | None = None
                best_delta = 0.0
                for alternative in ordered_choices.get(group, ()):
                    if alternative.request.id == current_choice.request.id:
                        continue
                    source_bucket_key = bucket_by_course.get(current_choice.demand_course.id)
                    target_bucket_key = bucket_by_course.get(alternative.demand_course.id)
                    if not source_bucket_key or not target_bucket_key:
                        continue
                    if source_bucket_key == target_bucket_key:
                        continue
                    source_bucket = buckets.get(source_bucket_key)
                    target_bucket = buckets.get(target_bucket_key)
                    if not source_bucket or not target_bucket:
                        continue
                    delta = demand_move_delta(
                        current_choice,
                        alternative,
                        bucket_demand,
                        source_bucket,
                        target_bucket,
                    )
                    if delta < best_delta:
                        best_delta = delta
                        best_choice = alternative
                if best_choice is None:
                    continue
                allocations[group] = best_choice
                previous_bucket_key = bucket_by_course[current_choice.demand_course.id]
                next_bucket_key = bucket_by_course[best_choice.demand_course.id]
                bucket_demand[previous_bucket_key] = bucket_demand.get(previous_bucket_key, 0) - 1
                bucket_demand[next_bucket_key] = bucket_demand.get(next_bucket_key, 0) + 1
                changed = True
                break
            if changed:
                break
        if not changed:
            break
    return allocations


def best_batch_move_from_problem_bucket(
    source_bucket_key: tuple[Any, ...],
    ordered_choices: dict[tuple[str, str], tuple[DemandChoice, ...]],
    allocations: dict[tuple[str, str], DemandChoice],
    bucket_by_course: dict[str, tuple[Any, ...]],
    buckets: dict[tuple[Any, ...], DemandPlanningBucket],
    bucket_demand: dict[tuple[Any, ...], int],
) -> list[tuple[tuple[str, str], DemandChoice]]:
    source_bucket = buckets.get(source_bucket_key)
    if not source_bucket:
        return []
    _sizes, unserved, _strategy = planned_section_sizes_from_capacity(
        bucket_demand.get(source_bucket_key, 0),
        source_bucket.regular_capacity,
        source_bucket.large_capacity,
    )
    if unserved <= 0:
        return []

    alternatives_by_bucket: dict[tuple[Any, ...], list[tuple[tuple[str, str], DemandChoice]]] = {}
    for group, current_choice in allocations.items():
        if bucket_by_course.get(current_choice.demand_course.id) != source_bucket_key:
            continue
        for alternative in ordered_choices.get(group, ()):
            target_bucket_key = bucket_by_course.get(alternative.demand_course.id)
            if (
                not target_bucket_key
                or target_bucket_key == source_bucket_key
                or alternative.request.id == current_choice.request.id
            ):
                continue
            alternatives_by_bucket.setdefault(target_bucket_key, []).append((group, alternative))
            break

    best_delta = 0.0
    best_move: list[tuple[tuple[str, str], DemandChoice]] = []
    source_demand = bucket_demand.get(source_bucket_key, 0)
    for target_bucket_key, candidates in alternatives_by_bucket.items():
        target_bucket = buckets.get(target_bucket_key)
        if not target_bucket:
            continue
        candidates.sort(
            key=lambda item: (
                allocations[item[0]].request.priority,
                item[1].request.preference_order,
                allocations[item[0]].request.created_at,
            )
        )
        target_demand = bucket_demand.get(target_bucket_key, 0)
        max_count = min(unserved, len(candidates), source_demand)
        for move_count in range(1, max_count + 1):
            batch = candidates[:move_count]
            before = (
                demand_bucket_cost(source_demand, source_bucket)
                + demand_bucket_cost(target_demand, target_bucket)
                + sum(demand_choice_penalty(allocations[group]) for group, _alternative in batch)
            )
            after = (
                demand_bucket_cost(source_demand - move_count, source_bucket)
                + demand_bucket_cost(target_demand + move_count, target_bucket)
                + sum(demand_choice_penalty(alternative) for _group, alternative in batch)
            )
            delta = after - before
            if delta < best_delta:
                best_delta = delta
                best_move = batch
    return best_move


def demand_move_delta(
    current_choice: DemandChoice,
    alternative: DemandChoice,
    bucket_demand: dict[tuple[Any, ...], int],
    source_bucket: DemandPlanningBucket,
    target_bucket: DemandPlanningBucket,
) -> float:
    source_demand = bucket_demand.get(source_bucket.key, 0)
    target_demand = bucket_demand.get(target_bucket.key, 0)
    before = (
        demand_bucket_cost(source_demand, source_bucket)
        + demand_bucket_cost(target_demand, target_bucket)
        + demand_choice_penalty(current_choice)
    )
    after = (
        demand_bucket_cost(source_demand - 1, source_bucket)
        + demand_bucket_cost(target_demand + 1, target_bucket)
        + demand_choice_penalty(alternative)
    )
    return after - before


def suppress_unviable_small_remainders(
    allocations: dict[tuple[str, str], DemandChoice],
    bucket_by_course: dict[str, tuple[Any, ...]],
    buckets: dict[tuple[Any, ...], DemandPlanningBucket],
) -> tuple[dict[tuple[str, str], DemandChoice], dict[tuple[str, str], DemandChoice]]:
    selected = dict(allocations)
    unplanned: dict[tuple[str, str], DemandChoice] = {}
    bucket_demand = bucket_demand_from_course_demand(
        demand_from_allocations(selected.values()),
        bucket_by_course,
    )
    for bucket_key, demand in sorted(bucket_demand.items(), key=lambda item: item[1]):
        bucket = buckets.get(bucket_key)
        if not bucket or demand <= 0:
            continue
        _sizes, unserved, _strategy = planned_section_sizes_from_capacity(
            demand,
            bucket.regular_capacity,
            bucket.large_capacity,
        )
        if unserved <= 0:
            continue
        candidates = [
            group
            for group, choice in selected.items()
            if bucket_by_course.get(choice.demand_course.id) == bucket_key
        ]
        candidates.sort(
            key=lambda group: (
                selected[group].request.priority,
                -selected[group].request.preference_order,
                selected[group].request.created_at,
            )
        )
        for group in candidates[:unserved]:
            unplanned[group] = selected.pop(group)
    return selected, unplanned


def demand_bucket_cost(demand: int, bucket: DemandPlanningBucket) -> float:
    if demand <= 0:
        return 0.0
    sizes, unserved, strategy = planned_section_sizes_from_capacity(
        demand,
        bucket.regular_capacity,
        bucket.large_capacity,
    )
    if not sizes:
        return demand * 900.0
    large_room_penalty = 0.0
    if "large" in strategy:
        large_room_penalty = max(0, bucket.large_capacity - max(sizes)) * 0.06
    section_count_penalty = len(sizes) * 34.0
    residual_penalty = unserved * 1_200.0
    balance_penalty = statistics.pstdev(sizes) if len(sizes) > 1 else 0.0
    return section_count_penalty + residual_penalty + large_room_penalty + balance_penalty


def demand_choice_penalty(choice: DemandChoice) -> float:
    return max(0, choice.request.preference_order - 1) * 18.0 - choice.request.priority * 0.5


def bucket_problem_weight(demand: int, bucket: DemandPlanningBucket) -> float:
    if demand <= 0:
        return 0.0
    sizes, unserved, _strategy = planned_section_sizes_from_capacity(
        demand,
        bucket.regular_capacity,
        bucket.large_capacity,
    )
    if not sizes:
        return demand * 100.0
    return unserved * 100.0


def bucket_demand_from_course_demand(
    course_demand: dict[str, int],
    bucket_by_course: dict[str, tuple[Any, ...]],
) -> dict[tuple[Any, ...], int]:
    bucket_demand: dict[tuple[Any, ...], int] = {}
    for course_id, demand in course_demand.items():
        bucket_key = bucket_by_course.get(course_id)
        if not bucket_key:
            continue
        bucket_demand[bucket_key] = bucket_demand.get(bucket_key, 0) + demand
    return bucket_demand


def demand_planning_bucket_metrics(
    demand_by_course: dict[str, int],
    bucket_by_course: dict[str, tuple[Any, ...]],
    buckets: dict[tuple[Any, ...], DemandPlanningBucket],
    course_by_id: dict[str, Course],
) -> list[dict[str, Any]]:
    bucket_demand = bucket_demand_from_course_demand(demand_by_course, bucket_by_course)
    metrics: list[dict[str, Any]] = []
    for bucket_key, demand in sorted(bucket_demand.items(), key=lambda item: (-item[1], str(item[0]))):
        bucket = buckets.get(bucket_key)
        if not bucket or demand <= 0:
            continue
        sizes, unserved, strategy = planned_section_sizes_from_capacity(
            demand,
            bucket.regular_capacity,
            bucket.large_capacity,
        )
        metrics.append(
            {
                "bucket": bucket.label,
                "course_ids": [course_id for course_id in bucket.course_ids if course_id in course_by_id],
                "selected_demand": demand,
                "planned_sections": len(sizes),
                "planned_section_sizes": sizes,
                "unplanned_remainder": unserved,
                "strategy": strategy,
                "regular_capacity": bucket.regular_capacity,
                "large_capacity": bucket.large_capacity,
            }
        )
    return metrics


def demand_bucket_label(group: list[Course]) -> str:
    representative = group[0]
    context_key = normalize_context_key(representative.context_key)
    if len(group) > 1 and context_key:
        return f"context:{context_key}:{representative.campus_id or 'any'}"
    return f"course:{representative.id}"


def prune_courses_for_teaching_capacity(
    courses: list[CourseData],
    professors: list[ProfessorData],
    slots: list[SlotData],
    contracts: dict[str, ContractData],
    qualifications: dict[str, set[str]],
    availability: dict[str, list[AvailabilityData]],
) -> tuple[list[CourseData], list[dict[str, Any]]]:
    professor_by_id = {professor.id: professor for professor in professors}
    owned_courses: dict[str, list[CourseData]] = {}
    for course in courses:
        qualified_professors = [
            professor_id
            for professor_id, course_ids in qualifications.items()
            if course.id in course_ids
        ]
        if len(qualified_professors) == 1:
            owned_courses.setdefault(qualified_professors[0], []).append(course)

    removed_course_ids: set[str] = set()
    pruning: list[dict[str, Any]] = []
    for professor_id, professor_courses in owned_courses.items():
        capacity_hours = professor_teaching_capacity_hours(
            professor_id,
            slots,
            contracts,
            availability,
        )
        required_hours = sum(course_required_hours(course) for course in professor_courses)
        if required_hours <= capacity_hours:
            continue
        removable = sorted(
            professor_courses,
            key=lambda course: (
                course.section_index == 0,
                course.criticality,
                course.expected_demand,
                course.recommended_semester,
                course.name,
            ),
        )
        for course in removable:
            if required_hours <= capacity_hours:
                break
            removed_course_ids.add(course.id)
            required_hours -= course_required_hours(course)
            professor = professor_by_id.get(professor_id)
            pruning.append(
                {
                    "course_id": course.id,
                    "course_name": course.name,
                    "db_course_id": course.source_course_ids[0] if course.source_course_ids else course.id,
                    "professor_id": professor_id,
                    "professor_name": professor.name if professor else professor_id,
                    "planned_students": course.expected_demand,
                    "section_index": course.section_index,
                    "required_hours": course_required_hours(course),
                    "capacity_hours": capacity_hours,
                    "reason": "Capacidade docente indisponivel para abrir esta turma sem conflito hard.",
                }
            )
    if not removed_course_ids:
        return courses, []
    return [course for course in courses if course.id not in removed_course_ids], pruning


def professor_teaching_capacity_hours(
    professor_id: str,
    slots: list[SlotData],
    contracts: dict[str, ContractData],
    availability: dict[str, list[AvailabilityData]],
) -> float:
    contract = contracts.get(professor_id, ContractData(min_hours=0, max_hours=12))
    windows = availability.get(professor_id, [])
    hard_available = [
        item
        for item in windows
        if item.strength == ConstraintStrength.hard.value
        and item.kind == AvailabilityKind.available.value
    ]
    if not hard_available:
        return float(contract.max_hours)
    available_hours = sum(
        slot.hours
        for slot in slots
        if professor_can_teach(windows, slot)
    )
    return min(float(contract.max_hours), available_hours)


def course_required_hours(course: CourseData) -> float:
    return course_required_session_count(course) * 2.0


def course_required_session_count(course: CourseData) -> int:
    if is_async_or_supervised_activity(course):
        return 1
    return max(1, math.ceil(course.workload_hours / 2))


def is_async_or_supervised_activity(course: CourseData) -> bool:
    name = course.name.upper()
    return any(
        marker in name
        for marker in (
            "ESTÁGIO",
            "ESTAGIO",
            "TRABALHO DE CONCLUSÃO",
            "TRABALHO DE CONCLUSAO",
            " TCC",
            "(EAD",
            " EAD",
        )
    )


def build_course_snapshot(
    raw_courses: list[Course],
    campus_by_id: dict[str, Campus],
    degree_program_by_id: dict[str, DegreeProgram],
    requested_demand_by_course: dict[str, int] | None = None,
    rooms: list[RoomData] | None = None,
    *,
    demand_driven: bool = False,
) -> tuple[list[CourseData], dict[str, tuple[str, ...]]]:
    requested_demand_by_course = requested_demand_by_course or {}
    grouped: dict[tuple[Any, ...], list[Course]] = {}
    for course in raw_courses:
        grouped.setdefault(course_group_key(course), []).append(course)

    courses: list[CourseData] = []
    source_to_snapshot: dict[str, list[str]] = {}
    for group in grouped.values():
        course_data = merge_course_group(
            group,
            campus_by_id,
            degree_program_by_id,
            requested_demand_by_course,
            demand_driven=demand_driven,
        )
        expanded_courses = expand_course_sections(course_data, rooms or [], demand_driven=demand_driven)
        courses.extend(expanded_courses)
        for source_course_id in course_data.source_course_ids:
            source_to_snapshot.setdefault(source_course_id, []).extend(
                course.id for course in expanded_courses
            )

    courses.sort(key=lambda item: (item.recommended_semester, item.name, item.id))
    return courses, {key: tuple(value) for key, value in source_to_snapshot.items()}


def demand_driven_courses(
    raw_courses: list[Course],
    requested_demand_by_course: dict[str, int],
) -> list[Course]:
    requested_ids = {course_id for course_id, demand in requested_demand_by_course.items() if demand > 0}
    if not requested_ids:
        return []
    requested_group_keys = {
        course_group_key(course)
        for course in raw_courses
        if course.id in requested_ids
    }
    return [
        course
        for course in raw_courses
        if course.id in requested_ids or course_group_key(course) in requested_group_keys
    ]


def course_group_key(course: Course) -> tuple[Any, ...]:
    context_key = normalize_context_key(course.context_key)
    theoretical_hours = effective_theoretical_hours(course)
    practical_hours = course.practical_hours or 0
    official_schedule_key = official_schedule_for_group([course])
    if course.shareable and context_key:
        return (
            "context",
            context_key,
            course.campus_id,
            course.workload_hours,
            theoretical_hours,
            practical_hours,
            course.requires_lab,
            course.kind.value,
            official_schedule_key,
        )
    return ("course", course.id)


def merge_course_group(
    group: list[Course],
    campus_by_id: dict[str, Campus],
    degree_program_by_id: dict[str, DegreeProgram],
    requested_demand_by_course: dict[str, int],
    *,
    demand_driven: bool,
) -> CourseData:
    representative = group[0]
    source_ids = tuple(course.id for course in group)
    context_key = normalize_context_key(representative.context_key)
    theoretical_hours = effective_theoretical_hours(representative)
    practical_hours = representative.practical_hours or 0
    is_shared_context = len(group) > 1 and bool(context_key)
    snapshot_id = (
        stable_context_course_id(representative, theoretical_hours, practical_hours)
        if is_shared_context
        else representative.id
    )
    campus_names = tuple(
        sorted(
            {
                campus_by_id[course.campus_id].name
                for course in group
                if course.campus_id and course.campus_id in campus_by_id
            }
        )
    )
    degree_program_names = tuple(
        sorted(
            {
                degree_program_by_id[course.degree_program_id].name
                for course in group
                if course.degree_program_id and course.degree_program_id in degree_program_by_id
            }
        )
    )
    expected_demand = sum(
        requested_demand_by_course.get(course.id, 0)
        if demand_driven and requested_demand_by_course
        else max(course.expected_demand, requested_demand_by_course.get(course.id, 0))
        for course in group
    )
    return CourseData(
        id=snapshot_id,
        name=course_group_name(group, context_key),
        code=common_value([course.code for course in group]),
        workload_hours=representative.workload_hours,
        theoretical_hours=theoretical_hours,
        practical_hours=practical_hours,
        kind=representative.kind.value,
        recommended_semester=min(course.recommended_semester for course in group),
        expected_demand=expected_demand,
        requires_lab=representative.requires_lab,
        criticality=max(course.criticality for course in group),
        context_key=context_key,
        shareable=representative.shareable,
        source_course_ids=source_ids,
        campus_id=common_value([course.campus_id for course in group]),
        degree_program_id=common_value([course.degree_program_id for course in group]),
        campus_names=campus_names,
        degree_program_names=degree_program_names,
        regular_time_windows=regular_time_windows_for_group(group, degree_program_by_id),
        official_schedule=official_schedule_for_group(group),
        planned_total_demand=expected_demand,
    )


def expand_course_sections(
    course: CourseData,
    rooms: list[RoomData],
    *,
    demand_driven: bool,
) -> list[CourseData]:
    if not demand_driven:
        return [course]
    if course.expected_demand < PLANNING_MIN_SECTION_DEMAND:
        return []

    section_sizes, unserved, strategy = planned_section_sizes(course, rooms)
    section_count = len(section_sizes)
    return [
        replace(
            course,
            id=section_course_id(course.id, index),
            name=section_course_name(course.name, index, section_count),
            expected_demand=size,
            section_index=index,
            section_count=section_count,
            planned_total_demand=course.expected_demand,
            planned_unserved_demand=unserved,
            section_strategy=strategy,
        )
        for index, size in enumerate(section_sizes)
    ]


def planned_section_sizes(course: CourseData, rooms: list[RoomData]) -> tuple[list[int], int, str]:
    compatible_capacities = sorted(
        room.capacity
        for room in rooms
        if room_matches_course_campus(course, room)
        and (not course.requires_lab or room.kind == RoomKind.lab.value)
    )
    regular_capacity = max(
        [capacity for capacity in compatible_capacities if capacity <= PLANNING_SECTION_CAPACITY],
        default=PLANNING_SECTION_CAPACITY,
    )
    large_capacity = max(
        [capacity for capacity in compatible_capacities if capacity > PLANNING_SECTION_CAPACITY],
        default=0,
    )
    return planned_section_sizes_from_capacity(course.expected_demand, regular_capacity, large_capacity)


def planned_section_sizes_from_capacity(
    demand: int,
    regular_capacity: int,
    large_capacity: int,
) -> tuple[list[int], int, str]:
    if demand < PLANNING_MIN_SECTION_DEMAND:
        return [], demand, "suppressed_below_minimum_section_demand"
    if demand <= regular_capacity:
        return [demand], 0, "single_regular_section"

    full_sections, remainder = divmod(demand, regular_capacity)
    section_sizes = [regular_capacity for _ in range(full_sections)]
    if remainder >= PLANNING_MIN_SECTION_DEMAND:
        section_sizes.append(remainder)
        return section_sizes, 0, "additional_section"
    if remainder == 0:
        return section_sizes, 0, "regular_sections"
    if large_capacity and section_sizes and section_sizes[-1] + remainder <= large_capacity:
        section_sizes[-1] += remainder
        return section_sizes, 0, "absorbed_small_remainder_in_large_room"
    return section_sizes, remainder, "suppressed_small_remainder"


def section_course_id(course_id: str, section_index: int) -> str:
    return course_id if section_index == 0 else f"{course_id}::turma-{section_index + 1}"


def section_course_name(course_name: str, section_index: int, section_count: int) -> str:
    if section_count <= 1:
        return course_name
    return f"{course_name} - Turma {section_index + 1}"


def effective_theoretical_hours(course: Course) -> int:
    if course.theoretical_hours:
        return course.theoretical_hours
    return max(0, course.workload_hours - (course.practical_hours or 0))


def normalize_context_key(context_key: str | None) -> str | None:
    normalized = (context_key or "").strip().lower()
    return normalized or None


def stable_context_course_id(course: Course, theoretical_hours: int, practical_hours: int) -> str:
    identity = "|".join(
        [
            normalize_context_key(course.context_key) or course.id,
            str(course.workload_hours),
            str(theoretical_hours),
            str(practical_hours),
            str(course.requires_lab),
            course.kind.value,
        ]
    )
    return f"ctx-{uuid.uuid5(uuid.NAMESPACE_URL, identity)}"


def course_group_name(group: list[Course], context_key: str | None) -> str:
    names = list(dict.fromkeys(course.name for course in group))
    base_name = names[0] if len(names) == 1 else (context_key or "contexto compartilhado")
    if len(group) == 1:
        return base_name
    return f"{base_name} ({len(group)} cursos)"


def common_value(values: list[str | None]) -> str | None:
    present = {value for value in values if value}
    return present.pop() if len(present) == 1 else None


def regular_time_windows_for_group(
    group: list[Course], degree_program_by_id: dict[str, DegreeProgram]
) -> tuple[tuple[int, int], ...]:
    windows: set[tuple[int, int]] = set()
    for course in group:
        if not is_regular_curriculum_course(course):
            continue
        if not course.degree_program_id:
            continue
        degree_program = degree_program_by_id.get(course.degree_program_id)
        if not degree_program:
            continue
        start = degree_program.schedule_start_minute
        end = degree_program.schedule_end_minute
        if start is None or end is None:
            continue
        windows.add((start, end))
    return tuple(sorted(windows))


def official_schedule_for_group(group: list[Course]) -> tuple[tuple[int, int, int], ...]:
    schedule: set[tuple[int, int, int]] = set()
    for course in group:
        for item in course.official_schedule or []:
            try:
                day = int(item["day"])
                start = int(item["start_minute"])
                end = int(item["end_minute"])
            except (KeyError, TypeError, ValueError):
                continue
            schedule.add((day, start, end))
    return tuple(sorted(schedule))


def is_regular_curriculum_course(course: Course) -> bool:
    return course.kind == CourseKind.mandatory and bool(course.degree_program_id)


def representative_course_id(snapshot: Snapshot, snapshot_course_id: str) -> str:
    course = next((item for item in snapshot.courses if item.id == snapshot_course_id), None)
    if not course:
        return snapshot_course_id
    return course.source_course_ids[0] if course.source_course_ids else course.id


def persisted_session_index(course: CourseData | None, session_index: int) -> int:
    if not course:
        return session_index
    return course.section_index * SECTION_SESSION_OFFSET + session_index


def snapshot_course_id_for_db_course(snapshot: Snapshot, db_course_id: str) -> str:
    snapshot_course_ids = snapshot.source_course_to_snapshot_course.get(db_course_id)
    return snapshot_course_ids[0] if snapshot_course_ids else db_course_id


def planned_sections_metrics(snapshot: Snapshot) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for course in snapshot.courses:
        planned_capacity_target = course.expected_demand
        sections.append(
            {
                "snapshot_course_id": course.id,
                "db_course_id": representative_course_id(snapshot, course.id),
                "section_index": course.section_index,
                "section_label": f"Turma {course.section_index + 1}",
                "course_name": course.name,
                "source_course_ids": list(course.source_course_ids),
                "planned_students": course.expected_demand,
                "planned_capacity_target": planned_capacity_target,
                "planned_total_demand": course.planned_total_demand or course.expected_demand,
                "planned_unserved_demand": course.planned_unserved_demand,
                "section_count": course.section_count,
                "strategy": course.section_strategy,
            }
        )
    return sections


def shared_course_group_metrics(snapshot: Snapshot) -> list[dict[str, Any]]:
    return [
        {
            "id": course.id,
            "name": course.name,
            "context_key": course.context_key,
            "source_course_ids": list(course.source_course_ids),
            "degree_programs": list(course.degree_program_names),
            "campuses": list(course.campus_names),
            "workload_hours": course.workload_hours,
            "theoretical_hours": course.theoretical_hours,
            "practical_hours": course.practical_hours,
            "expected_demand": course.expected_demand,
            "regular_time_windows": [
                {"start_minute": start, "end_minute": end}
                for start, end in course.regular_time_windows
            ],
        }
        for course in snapshot.courses
        if len(course.source_course_ids) > 1
    ]


def official_schedule_snapshot(snapshot: Snapshot) -> Snapshot:
    official_courses = [course for course in snapshot.courses if course.official_schedule]
    official_course_ids = {course.id for course in official_courses}
    official_campus_ids = {course.campus_id for course in official_courses if course.campus_id}
    official_professor_ids = {
        professor_id
        for professor_id, course_ids in snapshot.qualifications.items()
        if course_ids & official_course_ids
    }
    return replace(
        snapshot,
        courses=official_courses,
        professors=[
            professor for professor in snapshot.professors if professor.id in official_professor_ids
        ],
        rooms=[
            room
            for room in snapshot.rooms
            if not official_campus_ids or room.campus_id in official_campus_ids
        ],
        contracts={
            professor_id: contract
            for professor_id, contract in snapshot.contracts.items()
            if professor_id in official_professor_ids
        },
        qualifications={
            professor_id: course_ids & official_course_ids
            for professor_id, course_ids in snapshot.qualifications.items()
            if professor_id in official_professor_ids and course_ids & official_course_ids
        },
        availability={
            professor_id: windows
            for professor_id, windows in snapshot.availability.items()
            if professor_id in official_professor_ids
        },
        preferences={
            professor_id: {
                course_id: preference
                for course_id, preference in professor_preferences.items()
                if course_id in official_course_ids
            }
            for professor_id, professor_preferences in snapshot.preferences.items()
            if professor_id in official_professor_ids
            and any(course_id in official_course_ids for course_id in professor_preferences)
        },
        source_course_to_snapshot_course={
            source_course_id: tuple(
                snapshot_course_id
                for snapshot_course_id in snapshot_course_ids
                if snapshot_course_id in official_course_ids
            )
            for source_course_id, snapshot_course_ids in snapshot.source_course_to_snapshot_course.items()
            if any(snapshot_course_id in official_course_ids for snapshot_course_id in snapshot_course_ids)
        },
    )


def contract_applies_to_semester(contract: ProfessorContract, semester: str) -> bool:
    if contract.semester is None:
        return True
    return contract.semester == semester


def apply_professor_structured_constraint(
    constraint: ProfessorConstraint,
    courses: list[CourseData],
    availability: dict[str, list[AvailabilityData]],
    preferences: dict[str, dict[str, PreferenceData]],
) -> None:
    rule = normalized_professor_rule(constraint.structured_rule)
    rule_type = str(rule.get("type") or "").lower()
    if not rule_type or rule_type == "note":
        return

    if rule_type in {"availability", "time_window", "preference"}:
        availability_rules = availability_from_professor_rule(rule, constraint.strength.value)
        if availability_rules:
            availability.setdefault(constraint.professor_id, []).extend(availability_rules)

    if rule_type in {"course_preference", "course", "preference"}:
        target = str(rule.get("target") or "").strip().lower()
        if not target:
            return
        preference_value = safe_rule_int(rule.get("preference"), 3)
        professor_preferences = preferences.setdefault(constraint.professor_id, {})
        for course in courses:
            haystacks = [
                course.name.lower(),
                (course.context_key or "").lower(),
                (course.code or "").lower(),
            ]
            if not any(target in haystack for haystack in haystacks):
                continue
            current = professor_preferences.get(course.id)
            preference = PreferenceData(
                course_id=course.id,
                preference=preference_value,
                strength=constraint.strength.value,
            )
            if current is None or abs(preference.preference) > abs(current.preference):
                professor_preferences[course.id] = preference


def normalized_professor_rule(raw_rule: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw_rule, dict):
        return {}
    nested = raw_rule.get("rule")
    if isinstance(nested, dict):
        return nested
    return raw_rule


def availability_from_professor_rule(
    rule: dict[str, Any],
    strength: str,
) -> list[AvailabilityData]:
    days = rule_days(rule.get("days"))
    if not days:
        return []
    start_minute = safe_rule_int(rule.get("start_minute"), 0)
    end_minute = safe_rule_int(rule.get("end_minute"), 1440)
    if end_minute <= start_minute:
        return []
    preference = safe_rule_int(rule.get("preference"), 0)
    rule_type = str(rule.get("type") or "").lower()
    if preference < 0:
        kind = AvailabilityKind.unavailable.value
    elif rule_type == "preference":
        kind = AvailabilityKind.preferred.value
    else:
        kind = AvailabilityKind.available.value
    return [
        AvailabilityData(
            day=day,
            start_minute=start_minute,
            end_minute=end_minute,
            kind=kind,
            strength=strength,
        )
        for day in days
    ]


def rule_days(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, int):
        return [value] if 0 <= value <= 6 else []
    if isinstance(value, str):
        return [int(value)] if value.isdigit() and 0 <= int(value) <= 6 else []
    if isinstance(value, list):
        days: list[int] = []
        for item in value:
            try:
                day = int(item)
            except (TypeError, ValueError):
                continue
            if 0 <= day <= 6:
                days.append(day)
        return sorted(set(days))
    return []


def safe_rule_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def diagnose_snapshot(snapshot: Snapshot) -> list[dict[str, str]]:
    diagnosis: list[dict[str, str]] = []
    if not snapshot.courses:
        diagnosis.append({"code": "no_courses", "message": "Nenhuma disciplina cadastrada"})
    if not snapshot.professors:
        diagnosis.append({"code": "no_professors", "message": "Nenhum professor cadastrado"})
    if not snapshot.rooms:
        diagnosis.append({"code": "no_rooms", "message": "Nenhuma sala cadastrada"})
    if not snapshot.slots:
        diagnosis.append({"code": "no_slots", "message": "Nenhum slot de tempo cadastrado"})

    for course in snapshot.courses:
        qualified = [
            professor
            for professor in snapshot.professors
            if course.id in snapshot.qualifications.get(professor.id, set())
        ]
        if not qualified:
            diagnosis.append(
                {
                    "code": "no_qualified_professor",
                    "message": f"{course.name} nao tem professor habilitado",
                }
            )
        compatible_rooms = [
            room
            for room in snapshot.rooms
            if room_matches_course_campus(course, room)
            and room.capacity >= course.expected_demand
            and (not course.requires_lab or room.kind == RoomKind.lab.value)
        ]
        if not compatible_rooms:
            diagnosis.append(
                {"code": "no_room_capacity", "message": f"{course.name} nao tem sala compativel"}
            )
        if course.regular_time_windows and not any(
            slot_matches_course_regular_window(course, slot) for slot in snapshot.slots
        ):
            windows = ", ".join(format_minute_window(start, end) for start, end in course.regular_time_windows)
            diagnosis.append(
                {
                    "code": "no_regular_course_slot",
                    "message": f"{course.name} nao tem slot dentro do horario regular do curso ({windows})",
                }
            )
    return diagnosis


def build_solution(snapshot: Snapshot, seed: int) -> CandidateSolution:
    rng = random.Random(seed)
    course_by_id = {course.id: course for course in snapshot.courses}
    room_by_id = {room.id: room for room in snapshot.rooms}
    slot_by_id = {slot.id: slot for slot in snapshot.slots}
    professor_load = {professor.id: 0.0 for professor in snapshot.professors}
    professor_slot: set[tuple[str, str]] = set()
    room_slot: set[tuple[str, str]] = set()
    course_slot: set[tuple[str, str]] = set()
    assignments: list[ProposedAssignment] = []
    hard_failures: list[dict[str, Any]] = []

    session_queue: list[tuple[CourseData, int]] = []
    flexibility_by_course = {
        course.id: course_flexibility(snapshot, course)
        for course in snapshot.courses
    }
    for course in snapshot.courses:
        sessions = course_required_session_count(course)
        for session_index in range(sessions):
            session_queue.append((course, session_index))

    session_queue.sort(
        key=lambda item: (
            flexibility_by_course.get(item[0].id, 999_999),
            -course_required_session_count(item[0]),
            -item[0].criticality,
            -item[0].expected_demand,
            item[0].recommended_semester,
            rng.random(),
        )
    )

    for course, session_index in session_queue:
        candidates = enumerate_candidates(
            snapshot,
            course,
            professor_load,
            professor_slot,
            room_slot,
            course_slot,
            rng,
        )
        if not candidates:
            hard_failures.append(
                {
                    "code": "unplaced_session",
                    "course_id": course.id,
                    "session_index": session_index,
                    "message": f"Nao foi possivel alocar {course.name} sessao {session_index + 1}",
                }
            )
            continue

        _, professor_id, room_id, slot_id, soft = min(candidates, key=lambda item: item[0])
        slot = slot_by_id[slot_id]
        professor_load[professor_id] += slot.hours
        professor_slot.add((professor_id, slot_id))
        room_slot.add((room_id, slot_id))
        course_slot.add((course.id, slot_id))
        assignments.append(
            ProposedAssignment(
                course_id=course.id,
                professor_id=professor_id,
                room_id=room_id,
                time_slot_id=slot_id,
                session_index=session_index,
                hard_violations=[],
                soft_violations=soft,
            )
        )

    return evaluate_solution(
        snapshot,
        assignments,
        hard_failures,
        course_by_id=course_by_id,
        room_by_id=room_by_id,
        slot_by_id=slot_by_id,
        professor_load=professor_load,
    )


def course_flexibility(snapshot: Snapshot, course: CourseData) -> int:
    options = 0
    for professor in snapshot.professors:
        if course.id not in snapshot.qualifications.get(professor.id, set()):
            continue
        for slot in snapshot.slots:
            if not slot_matches_course_regular_window(course, slot):
                continue
            if professor_can_teach(snapshot.availability.get(professor.id, []), slot):
                options += 1
    return options


def build_official_schedule_solution(snapshot: Snapshot) -> CandidateSolution:
    course_by_id = {course.id: course for course in snapshot.courses}
    room_by_id = {room.id: room for room in snapshot.rooms}
    slot_by_id = {slot.id: slot for slot in snapshot.slots}
    slot_by_window = {
        (slot.day, slot.start_minute, slot.end_minute): slot for slot in snapshot.slots
    }
    professor_load = {professor.id: 0.0 for professor in snapshot.professors}
    professor_slot: set[tuple[str, str]] = set()
    professor_slot_room: dict[tuple[str, str], str] = {}
    room_slot: set[tuple[str, str]] = set()
    room_slot_demand: dict[tuple[str, str], int] = {}
    assignments: list[ProposedAssignment] = []
    hard_failures: list[dict[str, Any]] = []

    for course in snapshot.courses:
        professors = [
            professor
            for professor in snapshot.professors
            if course.id in snapshot.qualifications.get(professor.id, set())
        ]
        if not professors:
            hard_failures.append(
                {
                    "code": "missing_official_professor",
                    "course_id": course.id,
                    "message": f"{course.name} nao possui professor oficial habilitado",
                }
            )
            continue
        for session_index, window in enumerate(course.official_schedule):
            slot = slot_by_window.get(window)
            if not slot:
                hard_failures.append(
                    {
                        "code": "missing_official_slot",
                        "course_id": course.id,
                        "message": f"{course.name} nao possui slot oficial {window}",
                    }
                )
                continue
            cooffered = next(
                (
                    (candidate, professor_slot_room[(candidate.id, slot.id)])
                    for candidate in professors
                    if (candidate.id, slot.id) in professor_slot_room
                    and room_by_id[professor_slot_room[(candidate.id, slot.id)]].capacity
                    >= room_slot_demand.get((professor_slot_room[(candidate.id, slot.id)], slot.id), 0)
                    + course.expected_demand
                    and room_matches_course_campus(
                        course, room_by_id[professor_slot_room[(candidate.id, slot.id)]]
                    )
                    and (
                        not course.requires_lab
                        or room_by_id[professor_slot_room[(candidate.id, slot.id)]].kind
                        == RoomKind.lab.value
                    )
                ),
                None,
            )
            if cooffered:
                professor, room_id = cooffered
                room_slot_demand[(room_id, slot.id)] = (
                    room_slot_demand.get((room_id, slot.id), 0) + course.expected_demand
                )
                assignments.append(
                    ProposedAssignment(
                        course_id=course.id,
                        professor_id=professor.id,
                        room_id=room_id,
                        time_slot_id=slot.id,
                        session_index=session_index,
                        hard_violations=[],
                        soft_violations=[
                            {
                                "code": "official_cooffered_session",
                                "message": "Sessao oficial compartilhada por docente e sala no mesmo horario.",
                            }
                        ],
                        origin="ufpel_official_cooffered",
                    )
                )
                continue
            professor = next(
                (
                    candidate
                    for candidate in professors
                    if (candidate.id, slot.id) not in professor_slot
                    and professor_load[candidate.id] + slot.hours
                    <= snapshot.contracts.get(candidate.id, ContractData(0, 20)).max_hours
                    and professor_can_teach(snapshot.availability.get(candidate.id, []), slot)
                ),
                None,
            )
            if not professor:
                hard_failures.append(
                    {
                        "code": "official_professor_conflict",
                        "course_id": course.id,
                        "message": f"{course.name} nao tem professor livre no horario oficial",
                    }
                )
                continue
            room = next(
                (
                    candidate
                    for candidate in sorted(
                        snapshot.rooms,
                        key=lambda item: (
                            item.capacity - course.expected_demand,
                            item.name,
                        ),
                    )
                    if (candidate.id, slot.id) not in room_slot
                    and room_matches_course_campus(course, candidate)
                    and candidate.capacity >= course.expected_demand
                    and (not course.requires_lab or candidate.kind == RoomKind.lab.value)
                ),
                None,
            )
            if not room:
                hard_failures.append(
                    {
                        "code": "official_room_conflict",
                        "course_id": course.id,
                        "message": f"{course.name} nao tem sala compativel livre no horario oficial",
                    }
                )
                continue
            professor_slot.add((professor.id, slot.id))
            professor_slot_room[(professor.id, slot.id)] = room.id
            room_slot.add((room.id, slot.id))
            room_slot_demand[(room.id, slot.id)] = course.expected_demand
            professor_load[professor.id] += slot.hours
            assignments.append(
                ProposedAssignment(
                    course_id=course.id,
                    professor_id=professor.id,
                    room_id=room.id,
                    time_slot_id=slot.id,
                    session_index=session_index,
                    hard_violations=[],
                    soft_violations=[],
                    origin="ufpel_official",
                )
            )

    return evaluate_solution(
        snapshot,
        assignments,
        hard_failures,
        course_by_id=course_by_id,
        room_by_id=room_by_id,
        slot_by_id=slot_by_id,
        professor_load=professor_load,
    )


def enumerate_candidates(
    snapshot: Snapshot,
    course: CourseData,
    professor_load: dict[str, float],
    professor_slot: set[tuple[str, str]],
    room_slot: set[tuple[str, str]],
    course_slot: set[tuple[str, str]],
    rng: random.Random,
) -> list[tuple[float, str, str, str, list[dict[str, Any]]]]:
    candidates: list[tuple[float, str, str, str, list[dict[str, Any]]]] = []
    for professor in snapshot.professors:
        if course.id not in snapshot.qualifications.get(professor.id, set()):
            continue
        contract = snapshot.contracts.get(professor.id, ContractData(min_hours=0, max_hours=12))
        for slot in snapshot.slots:
            if not slot_matches_course_regular_window(course, slot):
                continue
            if (professor.id, slot.id) in professor_slot or (course.id, slot.id) in course_slot:
                continue
            if professor_load[professor.id] + slot.hours > contract.max_hours:
                continue
            if not professor_can_teach(snapshot.availability.get(professor.id, []), slot):
                continue
            for room in snapshot.rooms:
                if (room.id, slot.id) in room_slot:
                    continue
                if not room_matches_course_campus(course, room):
                    continue
                if room.capacity < course.expected_demand:
                    continue
                if course.requires_lab and room.kind != RoomKind.lab.value:
                    continue

                soft: list[dict[str, Any]] = []
                preference = snapshot.preferences.get(professor.id, {}).get(course.id)
                preference_value = preference.preference if preference else 0
                availability_bonus = availability_preference(
                    snapshot.availability.get(professor.id, []), slot
                )
                room_slack = max(0, room.capacity - course.expected_demand)
                load_penalty = professor_load[professor.id] * 1.8
                day_penalty = same_day_fragmentation_penalty(snapshot, course, slot)
                score = (
                    room_slack * 0.08
                    + load_penalty
                    + day_penalty
                    - preference_value * 4
                    - availability_bonus * 2
                    + rng.random() * 3
                )
                if preference_value < 0:
                    soft.append(
                        {
                            "code": "teacher_avoids_course",
                            "weight": abs(preference_value),
                            "message": "Professor prefere evitar esta disciplina",
                        }
                    )
                if availability_bonus < 0:
                    soft.append(
                        {
                            "code": "non_preferred_time",
                            "weight": abs(availability_bonus),
                            "message": "Horario nao esta entre os preferidos do professor",
                        }
                    )
                candidates.append((score, professor.id, room.id, slot.id, soft))
    rng.shuffle(candidates)
    return candidates[:400]


def professor_can_teach(availability: list[AvailabilityData], slot: SlotData) -> bool:
    hard_windows = [item for item in availability if item.strength == ConstraintStrength.hard.value]
    for item in hard_windows:
        overlaps = item.day == slot.day and item.start_minute < slot.end_minute and slot.start_minute < item.end_minute
        if overlaps and item.kind == AvailabilityKind.unavailable.value:
            return False
    available_hard = [item for item in hard_windows if item.kind == AvailabilityKind.available.value]
    if available_hard:
        return any(
            availability_window_matches_slot(item, slot)
            for item in available_hard
        )
    return True


def availability_window_matches_slot(item: AvailabilityData, slot: SlotData) -> bool:
    if item.day != slot.day:
        return False
    overlap = min(item.end_minute, slot.end_minute) - max(item.start_minute, slot.start_minute)
    if overlap <= 0:
        return False
    slot_duration = slot.end_minute - slot.start_minute
    availability_duration = item.end_minute - item.start_minute
    required_overlap = min(slot_duration, availability_duration) * 0.95
    return overlap >= required_overlap and overlap >= 90


def availability_preference(availability: list[AvailabilityData], slot: SlotData) -> int:
    score = 0
    for item in availability:
        if item.day != slot.day:
            continue
        covered = availability_window_matches_slot(item, slot)
        overlaps = item.start_minute < slot.end_minute and slot.start_minute < item.end_minute
        if covered and item.kind == AvailabilityKind.preferred.value:
            score += 2
        if overlaps and item.kind == AvailabilityKind.unavailable.value and item.strength != "hard":
            score -= 3
    return score


def slot_matches_course_regular_window(course: CourseData, slot: SlotData) -> bool:
    if not course.regular_time_windows:
        return True
    return all(start <= slot.start_minute and end >= slot.end_minute for start, end in course.regular_time_windows)


def room_matches_course_campus(course: CourseData, room: RoomData) -> bool:
    if not course.campus_id or not room.campus_id:
        return True
    return course.campus_id == room.campus_id


def format_minute_window(start: int, end: int) -> str:
    return f"{start // 60:02d}:{start % 60:02d}-{end // 60:02d}:{end % 60:02d}"


def same_day_fragmentation_penalty(snapshot: Snapshot, course: CourseData, slot: SlotData) -> float:
    same_semester = [item for item in snapshot.courses if item.recommended_semester == course.recommended_semester]
    density = len(same_semester)
    if density <= 1:
        return 0.0
    return 0.15 * density * abs(slot.day - (course.recommended_semester % 5))


def improve_solution(
    snapshot: Snapshot, solution: CandidateSolution, local_steps: int
) -> CandidateSolution:
    if not solution.assignments or solution.objectives["hard_conflicts"] > 0:
        return solution
    best = solution
    rng = random.Random(int(solution.score * 10_000) % 1_000_000)

    for _ in range(local_steps):
        proposal = [ProposedAssignment(**assignment.__dict__) for assignment in best.assignments]
        index = rng.randrange(len(proposal))
        removed = proposal.pop(index)
        rebuilt = rebuild_with_fixed(snapshot, proposal, removed, rng)
        if rebuilt.score < best.score and rebuilt.objectives["hard_conflicts"] == 0:
            best = rebuilt
    return best


def rebuild_with_fixed(
    snapshot: Snapshot,
    fixed: list[ProposedAssignment],
    removed: ProposedAssignment,
    rng: random.Random,
) -> CandidateSolution:
    course_by_id = {course.id: course for course in snapshot.courses}
    room_by_id = {room.id: room for room in snapshot.rooms}
    slot_by_id = {slot.id: slot for slot in snapshot.slots}
    professor_load = {professor.id: 0.0 for professor in snapshot.professors}
    professor_slot: set[tuple[str, str]] = set()
    room_slot: set[tuple[str, str]] = set()
    course_slot: set[tuple[str, str]] = set()

    for assignment in fixed:
        slot = slot_by_id[assignment.time_slot_id]
        professor_load[assignment.professor_id] += slot.hours
        professor_slot.add((assignment.professor_id, assignment.time_slot_id))
        room_slot.add((assignment.room_id, assignment.time_slot_id))
        course_slot.add((assignment.course_id, assignment.time_slot_id))

    course = course_by_id[removed.course_id]
    candidates = enumerate_candidates(
        snapshot,
        course,
        professor_load,
        professor_slot,
        room_slot,
        course_slot,
        rng,
    )
    if not candidates:
        return evaluate_solution(
            snapshot,
            fixed,
            [{"code": "local_search_failed", "message": f"Sem realocacao para {course.name}"}],
            course_by_id=course_by_id,
            room_by_id=room_by_id,
            slot_by_id=slot_by_id,
            professor_load=professor_load,
        )
    _, professor_id, room_id, slot_id, soft = min(candidates, key=lambda item: item[0])
    fixed.append(
        ProposedAssignment(
            course_id=removed.course_id,
            professor_id=professor_id,
            room_id=room_id,
            time_slot_id=slot_id,
            session_index=removed.session_index,
            hard_violations=[],
            soft_violations=soft,
        )
    )
    slot = slot_by_id[slot_id]
    professor_load[professor_id] += slot.hours
    return evaluate_solution(
        snapshot,
        fixed,
        [],
        course_by_id=course_by_id,
        room_by_id=room_by_id,
        slot_by_id=slot_by_id,
        professor_load=professor_load,
    )


def evaluate_solution(
    snapshot: Snapshot,
    assignments: list[ProposedAssignment],
    initial_hard: list[dict[str, Any]],
    *,
    course_by_id: dict[str, CourseData],
    room_by_id: dict[str, RoomData],
    slot_by_id: dict[str, SlotData],
    professor_load: dict[str, float],
) -> CandidateSolution:
    hard = list(initial_hard)
    professor_slot: dict[tuple[str, str], ProposedAssignment] = {}
    room_slot: dict[tuple[str, str], ProposedAssignment] = {}
    room_slot_demand: dict[tuple[str, str], int] = {}
    room_waste = 0.0
    preference_score = 0.0
    critical_sessions = 0
    assigned_sessions = len(assignments)
    min_load_diagnostics: list[dict[str, Any]] = []
    min_load_shortfall = 0.0

    for assignment in assignments:
        course = course_by_id[assignment.course_id]
        room = room_by_id[assignment.room_id]
        key_prof = (assignment.professor_id, assignment.time_slot_id)
        key_room = (assignment.room_id, assignment.time_slot_id)
        existing_professor_assignment = professor_slot.get(key_prof)
        existing_room_assignment = room_slot.get(key_room)
        if existing_professor_assignment and not assignments_can_share_official_session(
            existing_professor_assignment, assignment
        ):
            hard.append({"code": "professor_conflict", "assignment": assignment.course_id})
        if existing_room_assignment and not assignments_can_share_official_session(
            existing_room_assignment, assignment
        ):
            hard.append({"code": "room_conflict", "assignment": assignment.course_id})
        if assignment.course_id not in snapshot.qualifications.get(assignment.professor_id, set()):
            hard.append({"code": "professor_qualification", "assignment": assignment.course_id})
        professor_slot.setdefault(key_prof, assignment)
        room_slot.setdefault(key_room, assignment)
        room_slot_demand[key_room] = room_slot_demand.get(key_room, 0) + course.expected_demand
        slot = slot_by_id[assignment.time_slot_id]
        if not slot_matches_course_regular_window(course, slot):
            hard.append(
                {
                    "code": "regular_course_time_window",
                    "assignment": assignment.course_id,
                    "message": f"{course.name} fora do horario regular do curso",
                }
            )
        if room.capacity < course.expected_demand:
            hard.append({"code": "room_capacity", "assignment": assignment.course_id})
        if room_slot_demand[key_room] > room.capacity:
            hard.append({"code": "room_cooffered_capacity", "assignment": assignment.course_id})
        if not room_matches_course_campus(course, room):
            hard.append(
                {
                    "code": "room_campus",
                    "assignment": assignment.course_id,
                    "message": f"{course.name} alocada em campus incompativel",
                }
            )
        room_waste += max(0, room.capacity - course.expected_demand)
        pref = snapshot.preferences.get(assignment.professor_id, {}).get(assignment.course_id)
        preference_score += pref.preference if pref else 0
        critical_sessions += course.criticality

    for professor in snapshot.professors:
        contract = snapshot.contracts.get(professor.id)
        if not contract:
            continue
        load = professor_load.get(professor.id, 0.0)
        if load < contract.min_hours:
            shortfall = round(contract.min_hours - load, 2)
            min_load_shortfall += shortfall
            min_load_diagnostics.append(
                {
                    "code": "min_load",
                    "professor_id": professor.id,
                    "shortfall_hours": shortfall,
                    "message": f"{professor.name} abaixo da carga minima",
                }
            )
        if load > contract.max_hours:
            hard.append(
                {
                    "code": "max_load",
                    "professor_id": professor.id,
                    "message": f"{professor.name} acima da carga maxima",
                }
            )

    loads = [
        professor_load.get(professor.id, 0.0)
        for professor in snapshot.professors
        if professor_load.get(professor.id, 0.0) > 0
        or snapshot.contracts.get(professor.id, ContractData(0, 12)).min_hours > 0
    ]
    load_balance = statistics.pstdev(loads) if len(loads) > 1 else 0.0
    student_holes = estimate_student_holes(assignments, course_by_id, slot_by_id)
    soft_penalty = sum(len(assignment.soft_violations) for assignment in assignments)
    total_required = sum(
        len(course.official_schedule)
        if course.official_schedule
        else course_required_session_count(course)
        for course in snapshot.courses
    )
    raw_coverage = assigned_sessions / total_required if total_required else 0
    coverage = min(1.0, raw_coverage)
    overcoverage_sessions = max(0, assigned_sessions - total_required)
    objectives = {
        "hard_conflicts": float(len(hard)),
        "preference_loss": max(0.0, 40.0 - preference_score),
        "load_imbalance": round(load_balance, 3),
        "room_waste": round(room_waste, 3),
        "student_holes": float(student_holes),
        "coverage_loss": round(max(0.0, 1 - coverage) * 100, 3),
        "criticality_loss": max(0.0, 120.0 - critical_sessions),
        "soft_penalty": float(soft_penalty),
        "min_load_shortfall": round(min_load_shortfall, 3),
    }
    score = (
        objectives["hard_conflicts"] * 100_000
        + objectives["coverage_loss"] * 2_000
        + objectives["preference_loss"] * 8
        + objectives["load_imbalance"] * 30
        + objectives["room_waste"] * 0.15
        + objectives["student_holes"] * 15
        + objectives["criticality_loss"] * 2
        + objectives["soft_penalty"] * 20
        + objectives["min_load_shortfall"] * 4
    )
    metrics = {
        "hard_conflicts": len(hard),
        "soft_conflicts": soft_penalty,
        "min_load_warnings": len(min_load_diagnostics),
        "min_load_shortfall": round(min_load_shortfall, 2),
        "assigned_sessions": assigned_sessions,
        "required_sessions": total_required,
        "coverage": round(coverage, 3),
        "raw_coverage": round(raw_coverage, 3),
        "overcoverage_sessions": overcoverage_sessions,
        "preference_score": preference_score,
        "room_waste": round(room_waste, 2),
        "load_by_professor": {professor.id: professor_load.get(professor.id, 0) for professor in snapshot.professors},
        "hard_diagnostics": hard[:20],
        "min_load_diagnostics": min_load_diagnostics[:20],
    }
    explanation = (
        (
            "Solucao viavel sem conflitos obrigatorios."
            if not min_load_diagnostics
            else (
                "Solucao viavel sem conflitos obrigatorios; "
                f"{len(min_load_diagnostics)} alertas de carga minima docente."
            )
        )
        if not hard
        else f"Solucao com {len(hard)} violacoes obrigatorias; veja hard_diagnostics."
    )
    return CandidateSolution(assignments, metrics, objectives, explanation, round(score, 3))


def assignments_can_share_official_session(
    left: ProposedAssignment, right: ProposedAssignment
) -> bool:
    return left.origin.startswith("ufpel_official") and right.origin.startswith("ufpel_official")


def estimate_student_holes(
    assignments: list[ProposedAssignment],
    course_by_id: dict[str, CourseData],
    slot_by_id: dict[str, SlotData],
) -> int:
    by_semester_day: dict[tuple[int, int], list[SlotData]] = {}
    for assignment in assignments:
        course = course_by_id[assignment.course_id]
        slot = slot_by_id[assignment.time_slot_id]
        by_semester_day.setdefault((course.recommended_semester, slot.day), []).append(slot)

    holes = 0
    for slots in by_semester_day.values():
        ordered = sorted(slots, key=lambda item: item.start_minute)
        for left, right in zip(ordered, ordered[1:]):
            gap = right.start_minute - left.end_minute
            if gap >= 90:
                holes += 1
    return holes


def validate_manual_assignments(db: Session, run_id: str) -> list[dict[str, Any]]:
    snapshot = build_snapshot(db)
    assignments = db.query(Assignment).filter(Assignment.run_id == run_id).all()
    proposed = [
        ProposedAssignment(
            course_id=snapshot_course_id_for_db_course(snapshot, item.course_id),
            professor_id=item.professor_id,
            room_id=item.room_id,
            time_slot_id=item.time_slot_id,
            session_index=item.session_index,
            hard_violations=[],
            soft_violations=[],
            origin=item.origin,
        )
        for item in assignments
    ]
    course_by_id = {course.id: course for course in snapshot.courses}
    room_by_id = {room.id: room for room in snapshot.rooms}
    slot_by_id = {slot.id: slot for slot in snapshot.slots}
    professor_load = {professor.id: 0.0 for professor in snapshot.professors}
    for item in proposed:
        professor_load[item.professor_id] += slot_by_id[item.time_slot_id].hours
    evaluated = evaluate_solution(
        snapshot,
        proposed,
        [],
        course_by_id=course_by_id,
        room_by_id=room_by_id,
        slot_by_id=slot_by_id,
        professor_load=professor_load,
    )
    return evaluated.metrics["hard_diagnostics"]
