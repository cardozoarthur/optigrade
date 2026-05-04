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
from app.services.student_planning import student_demand_summary


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
    source_course_to_snapshot_course: dict[str, str]
    student_demand_requests: int = 0
    student_demand_raw_requests: int = 0
    student_demand_blocked_requests: int = 0
    student_regular_requests: int = 0
    student_reoffer_requests: int = 0
    student_elective_requests: int = 0


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
    demand_driven = bool(params.get("student_demand_only", profile != "official_ufpel"))

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
    for item in best.assignments:
        db.add(
            Assignment(
                run_id=run.id,
                course_id=representative_course_id(snapshot, item.course_id),
                professor_id=item.professor_id,
                room_id=item.room_id,
                time_slot_id=item.time_slot_id,
                session_index=item.session_index,
                hard_violations=item.hard_violations,
                soft_violations=item.soft_violations,
                origin=item.origin,
            )
        )

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    run.status = RunStatus.feasible if best.objectives["hard_conflicts"] == 0 else RunStatus.infeasible
    run.metrics = best.metrics | {
        "elapsed_ms": elapsed_ms,
        "semester": run.semester,
        "profile": profile,
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
    demand_summary = student_demand_summary(db, semester)
    requested_demand_by_course = demand_summary.demand_by_course
    raw_courses = db.query(Course).all()
    if demand_driven and requested_demand_by_course:
        raw_courses = demand_driven_courses(raw_courses, requested_demand_by_course)
    courses, source_course_to_snapshot_course = build_course_snapshot(
        raw_courses, campus_by_id, degree_program_by_id, requested_demand_by_course
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
        snapshot_course_id = source_course_to_snapshot_course.get(item.course_id)
        if snapshot_course_id:
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
        snapshot_course_id = source_course_to_snapshot_course.get(item.course_id)
        if not snapshot_course_id:
            continue
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
        student_demand_requests=demand_summary.eligible_requests,
        student_demand_raw_requests=demand_summary.total_requests,
        student_demand_blocked_requests=demand_summary.blocked_requests,
        student_regular_requests=demand_summary.regular_requests,
        student_reoffer_requests=demand_summary.reoffer_requests,
        student_elective_requests=demand_summary.elective_requests,
    )


def build_course_snapshot(
    raw_courses: list[Course],
    campus_by_id: dict[str, Campus],
    degree_program_by_id: dict[str, DegreeProgram],
    requested_demand_by_course: dict[str, int] | None = None,
) -> tuple[list[CourseData], dict[str, str]]:
    requested_demand_by_course = requested_demand_by_course or {}
    grouped: dict[tuple[Any, ...], list[Course]] = {}
    for course in raw_courses:
        grouped.setdefault(course_group_key(course), []).append(course)

    courses: list[CourseData] = []
    source_to_snapshot: dict[str, str] = {}
    for group in grouped.values():
        course_data = merge_course_group(
            group, campus_by_id, degree_program_by_id, requested_demand_by_course
        )
        courses.append(course_data)
        for source_course_id in course_data.source_course_ids:
            source_to_snapshot[source_course_id] = course_data.id

    courses.sort(key=lambda item: (item.recommended_semester, item.name, item.id))
    return courses, source_to_snapshot


def demand_driven_courses(
    raw_courses: list[Course],
    requested_demand_by_course: dict[str, int],
) -> list[Course]:
    requested_ids = {course_id for course_id, demand in requested_demand_by_course.items() if demand > 0}
    if not requested_ids:
        return raw_courses
    return [course for course in raw_courses if course.id in requested_ids]


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
    return CourseData(
        id=snapshot_id,
        name=course_group_name(group, context_key),
        code=common_value([course.code for course in group]),
        workload_hours=representative.workload_hours,
        theoretical_hours=theoretical_hours,
        practical_hours=practical_hours,
        kind=representative.kind.value,
        recommended_semester=min(course.recommended_semester for course in group),
        expected_demand=sum(
            max(course.expected_demand, requested_demand_by_course.get(course.id, 0))
            for course in group
        ),
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
    )


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


def snapshot_course_id_for_db_course(snapshot: Snapshot, db_course_id: str) -> str:
    return snapshot.source_course_to_snapshot_course.get(db_course_id, db_course_id)


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
            source_course_id: snapshot_course_id
            for source_course_id, snapshot_course_id in snapshot.source_course_to_snapshot_course.items()
            if snapshot_course_id in official_course_ids
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
    for course in snapshot.courses:
        sessions = max(1, math.ceil(course.workload_hours / 2))
        for session_index in range(sessions):
            session_queue.append((course, session_index))

    session_queue.sort(
        key=lambda item: (
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
            item.day == slot.day
            and item.start_minute <= slot.start_minute
            and item.end_minute >= slot.end_minute
            for item in available_hard
        )
    return True


def availability_preference(availability: list[AvailabilityData], slot: SlotData) -> int:
    score = 0
    for item in availability:
        if item.day != slot.day:
            continue
        covered = item.start_minute <= slot.start_minute and item.end_minute >= slot.end_minute
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
        else max(1, math.ceil(course.workload_hours / 2))
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
