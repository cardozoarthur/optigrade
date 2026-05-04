import csv
from io import StringIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Course, DegreeProgram, Professor, Room, TimeSlot

router = APIRouter()


@router.post("/csv/{entity}")
async def import_csv(
    entity: str, file: UploadFile = File(...), db: Session = Depends(get_db)
) -> dict[str, int | str]:
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(StringIO(content))
    count = 0

    if entity == "degree-programs":
        for row in reader:
            schedule_start = optional_int(row.get("schedule_start_minute"))
            schedule_end = optional_int(row.get("schedule_end_minute"))
            validate_schedule_window(schedule_start, schedule_end)
            db.add(
                DegreeProgram(
                    name=row["name"],
                    code=row.get("code") or None,
                    department=row.get("department") or None,
                    campus_id=row.get("campus_id") or None,
                    schedule_start_minute=schedule_start,
                    schedule_end_minute=schedule_end,
                )
            )
            count += 1
    elif entity == "courses":
        for row in reader:
            db.add(
                Course(
                    name=row["name"],
                    code=row.get("code") or None,
                    campus_id=row.get("campus_id") or None,
                    degree_program_id=row.get("degree_program_id") or None,
                    workload_hours=int(row["workload_hours"]),
                    theoretical_hours=int(row.get("theoretical_hours") or row["workload_hours"]),
                    practical_hours=int(row.get("practical_hours") or 0),
                    kind=row.get("kind", "mandatory"),
                    recommended_semester=int(row["recommended_semester"]),
                    expected_demand=int(row["expected_demand"]),
                    requires_lab=row.get("requires_lab", "false").lower() == "true",
                    criticality=int(row.get("criticality", 3)),
                    context_key=row.get("context_key") or None,
                    shareable=row.get("shareable", "true").lower() == "true",
                )
            )
            count += 1
    elif entity == "professors":
        for row in reader:
            db.add(
                Professor(
                    name=row["name"],
                    email=row.get("email") or None,
                    department=row.get("department") or "UFPel",
                )
            )
            count += 1
    elif entity == "rooms":
        for row in reader:
            db.add(
                Room(
                    name=row["name"],
                    campus_id=row.get("campus_id") or None,
                    capacity=int(row["capacity"]),
                    kind=row.get("kind", "lecture"),
                )
            )
            count += 1
    elif entity == "timeslots":
        for row in reader:
            db.add(
                TimeSlot(
                    day=int(row["day"]),
                    start_minute=int(row["start_minute"]),
                    end_minute=int(row["end_minute"]),
                    label=row["label"],
                )
            )
            count += 1
    else:
        raise HTTPException(status_code=404, detail="Entidade de importacao desconhecida")

    db.commit()
    return {"entity": entity, "imported": count}


def optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def validate_schedule_window(start: int | None, end: int | None) -> None:
    if (start is None) != (end is None):
        raise HTTPException(status_code=400, detail="Horario de inicio e fim devem vir juntos")
    if start is not None and end is not None and end <= start:
        raise HTTPException(status_code=400, detail="Horario final deve ser posterior ao inicial")
