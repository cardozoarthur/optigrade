from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from app.models.entities import RoomKind
from app.services.optimizer import (
    CandidateSolution,
    ContractData,
    ProposedAssignment,
    Snapshot,
    availability_preference,
    evaluate_solution,
    professor_can_teach,
    room_matches_course_campus,
    slot_matches_course_regular_window,
)


@dataclass(frozen=True)
class CpCandidate:
    course_id: str
    professor_id: str
    room_id: str
    slot_id: str
    session_index: int
    duration_minutes: int
    room_waste: int
    preference: int


def solve_cp_sat_baseline(snapshot: Snapshot, max_seconds: float = 5.0) -> CandidateSolution | None:
    sessions: list[tuple[str, int]] = []
    course_by_id = {course.id: course for course in snapshot.courses}
    room_by_id = {room.id: room for room in snapshot.rooms}
    slot_by_id = {slot.id: slot for slot in snapshot.slots}

    for course in snapshot.courses:
        required = max(1, -(-course.workload_hours // 2))
        for session_index in range(required):
            sessions.append((course.id, session_index))

    candidates_by_session: dict[tuple[str, int], list[CpCandidate]] = {}
    for course_id, session_index in sessions:
        course = course_by_id[course_id]
        session_candidates: list[CpCandidate] = []
        for professor in snapshot.professors:
            if course.id not in snapshot.qualifications.get(professor.id, set()):
                continue
            for slot in snapshot.slots:
                if not slot_matches_course_regular_window(course, slot):
                    continue
                if not professor_can_teach(snapshot.availability.get(professor.id, []), slot):
                    continue
                for room in snapshot.rooms:
                    if not room_matches_course_campus(course, room):
                        continue
                    if room.capacity < course.expected_demand:
                        continue
                    if course.requires_lab and room.kind != RoomKind.lab.value:
                        continue
                    preference = snapshot.preferences.get(professor.id, {}).get(course.id)
                    preference_value = preference.preference if preference else 0
                    preference_value += availability_preference(
                        snapshot.availability.get(professor.id, []), slot
                    )
                    session_candidates.append(
                        CpCandidate(
                            course_id=course.id,
                            professor_id=professor.id,
                            room_id=room.id,
                            slot_id=slot.id,
                            session_index=session_index,
                            duration_minutes=slot.end_minute - slot.start_minute,
                            room_waste=room.capacity - course.expected_demand,
                            preference=preference_value,
                        )
                    )
        if not session_candidates:
            return None
        candidates_by_session[(course_id, session_index)] = session_candidates

    model = cp_model.CpModel()
    variables: dict[tuple[str, int, int], cp_model.IntVar] = {}
    for session_key, candidates in candidates_by_session.items():
        session_vars = []
        for index, candidate in enumerate(candidates):
            var = model.new_bool_var(f"x_{candidate.course_id}_{candidate.session_index}_{index}")
            variables[(session_key[0], session_key[1], index)] = var
            session_vars.append(var)
        model.add_exactly_one(session_vars)

    constrain_at_most_one(model, variables, candidates_by_session, key=lambda item: (item.professor_id, item.slot_id))
    constrain_at_most_one(model, variables, candidates_by_session, key=lambda item: (item.room_id, item.slot_id))
    constrain_at_most_one(model, variables, candidates_by_session, key=lambda item: (item.course_id, item.slot_id))

    for professor in snapshot.professors:
        contract = snapshot.contracts.get(professor.id, ContractData(min_hours=0, max_hours=12))
        load_terms = []
        for session_key, candidates in candidates_by_session.items():
            for index, candidate in enumerate(candidates):
                if candidate.professor_id == professor.id:
                    load_terms.append(
                        candidate.duration_minutes * variables[(session_key[0], session_key[1], index)]
                    )
        if not load_terms:
            if contract.min_hours > 0:
                return None
            continue
        model.add(sum(load_terms) >= int(contract.min_hours * 60))
        model.add(sum(load_terms) <= int(contract.max_hours * 60))

    objective_terms = []
    for session_key, candidates in candidates_by_session.items():
        for index, candidate in enumerate(candidates):
            var = variables[(session_key[0], session_key[1], index)]
            objective_terms.append((candidate.room_waste * 10 - candidate.preference * 100) * var)
    model.minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_seconds
    solver.parameters.num_search_workers = 8
    status = solver.solve(model)
    if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        return None

    assignments: list[ProposedAssignment] = []
    professor_load = {professor.id: 0.0 for professor in snapshot.professors}
    for session_key, candidates in candidates_by_session.items():
        for index, candidate in enumerate(candidates):
            if solver.boolean_value(variables[(session_key[0], session_key[1], index)]):
                assignments.append(
                    ProposedAssignment(
                        course_id=candidate.course_id,
                        professor_id=candidate.professor_id,
                        room_id=candidate.room_id,
                        time_slot_id=candidate.slot_id,
                        session_index=candidate.session_index,
                        hard_violations=[],
                        soft_violations=[],
                        origin="cp_sat",
                    )
                )
                professor_load[candidate.professor_id] += candidate.duration_minutes / 60
                break

    return evaluate_solution(
        snapshot,
        assignments,
        [],
        course_by_id=course_by_id,
        room_by_id=room_by_id,
        slot_by_id=slot_by_id,
        professor_load=professor_load,
    )


def constrain_at_most_one(model, variables, candidates_by_session, key) -> None:
    grouped: dict[tuple[str, str], list[cp_model.IntVar]] = {}
    for session_key, candidates in candidates_by_session.items():
        for index, candidate in enumerate(candidates):
            grouped.setdefault(key(candidate), []).append(
                variables[(session_key[0], session_key[1], index)]
            )
    for group_vars in grouped.values():
        if len(group_vars) > 1:
            model.add_at_most_one(group_vars)
