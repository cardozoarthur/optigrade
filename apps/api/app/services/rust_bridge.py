from __future__ import annotations

import json
import subprocess

from app.core.config import settings
from app.services.optimizer import (
    CandidateSolution,
    ProposedAssignment,
    Snapshot,
    evaluate_solution,
)


def try_rust_optimizer(snapshot: Snapshot, profile: str) -> CandidateSolution | None:
    if not settings.optigrade_optimizer_bin:
        return None

    payload = {
        "courses": [
            {
                "id": item.id,
                "workload_hours": item.workload_hours,
                "expected_demand": item.expected_demand,
                "requires_lab": item.requires_lab,
                "criticality": item.criticality,
            }
            for item in snapshot.courses
        ],
        "professors": [{"id": item.id} for item in snapshot.professors],
        "rooms": [
            {"id": item.id, "capacity": item.capacity, "kind": item.kind} for item in snapshot.rooms
        ],
        "slots": [
            {
                "id": item.id,
                "day": item.day,
                "start_minute": item.start_minute,
                "end_minute": item.end_minute,
            }
            for item in snapshot.slots
        ],
        "qualifications": [
            {"professor_id": professor_id, "course_id": course_id}
            for professor_id, course_ids in snapshot.qualifications.items()
            for course_id in course_ids
        ],
        "contracts": [
            {
                "professor_id": professor_id,
                "min_hours": contract.min_hours,
                "max_hours": contract.max_hours,
            }
            for professor_id, contract in snapshot.contracts.items()
        ],
        "preferences": [
            {
                "professor_id": professor_id,
                "course_id": course_id,
                "preference": preference.preference,
            }
            for professor_id, preferences in snapshot.preferences.items()
            for course_id, preference in preferences.items()
        ],
        "population": 128 if profile == "fast" else 320 if profile == "balanced" else 720,
        "generations": 80 if profile == "fast" else 180 if profile == "balanced" else 420,
        "seed": 42,
    }

    try:
        completed = subprocess.run(
            [settings.optigrade_optimizer_bin],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    data = json.loads(completed.stdout)
    assignments = [
        ProposedAssignment(
            course_id=item["course_id"],
            professor_id=item["professor_id"],
            room_id=item["room_id"],
            time_slot_id=item["time_slot_id"],
            session_index=item["session_index"],
            hard_violations=[],
            soft_violations=[],
            origin="rust_optimizer",
        )
        for item in data.get("assignments", [])
    ]
    slot_by_id = {slot.id: slot for slot in snapshot.slots}
    professor_load = {professor.id: 0.0 for professor in snapshot.professors}
    for assignment in assignments:
        professor_load[assignment.professor_id] += slot_by_id[assignment.time_slot_id].hours

    return evaluate_solution(
        snapshot,
        assignments,
        [],
        course_by_id={course.id: course for course in snapshot.courses},
        room_by_id={room.id: room for room in snapshot.rooms},
        slot_by_id=slot_by_id,
        professor_load=professor_load,
    )
