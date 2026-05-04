from app.models.entities import Course, CourseKind, Professor, Room, RoomKind, TimeSlot
from app.services.readiness import build_readiness_report


def test_readiness_reports_missing_required_data(db_session) -> None:
    report = build_readiness_report(db_session)

    assert report["status"] == "degraded"
    assert set(report["missing_required_data"]) == {
        "courses",
        "professors",
        "rooms",
        "time_slots",
    }


def test_readiness_reports_optimization_precheck(db_session) -> None:
    db_session.add(
        Course(
            name="Calculo I",
            workload_hours=2,
            theoretical_hours=2,
            kind=CourseKind.mandatory,
            recommended_semester=1,
            expected_demand=20,
        )
    )
    db_session.add(Professor(name="Docente"))
    db_session.add(Room(name="Sala", capacity=30, kind=RoomKind.lecture))
    db_session.add(TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10"))
    db_session.commit()

    report = build_readiness_report(db_session)

    assert report["status"] == "degraded"
    assert report["missing_required_data"] == []
    assert any(
        item["code"] == "no_qualified_professor"
        for item in report["optimization_precheck"]
    )
