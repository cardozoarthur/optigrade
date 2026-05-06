from app.api.routes import optimization, presentation
from app.models.entities import (
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
    ProfessorQualification,
    Room,
    RoomKind,
    RunStatus,
    Student,
    StudentCourseRequest,
    StudentEnrollment,
    TimeSlot,
)
from app.schemas import OptimizationRunCreate


def test_create_run_returns_pending_and_enqueues_background_job(monkeypatch, db_session) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(optimization, "enqueue_optimization_run", lambda run_id: enqueued.append(run_id))

    run = optimization.create_run(
        OptimizationRunCreate(
            semester="2026/2",
            profile="fast",
            parameters={"attempts": 4, "local_steps": 2},
        ),
        db_session,
    )

    assert run.status == RunStatus.pending
    assert run.finished_at is None
    assert enqueued == [run.id]


def test_create_run_reuses_equivalent_active_run(monkeypatch, db_session) -> None:
    enqueued: list[str] = []
    existing = OptimizationRun(
        semester="2026/2",
        profile="fast",
        parameters={"attempts": 4, "local_steps": 2},
        status=RunStatus.running,
    )
    db_session.add(existing)
    db_session.commit()
    monkeypatch.setattr(optimization, "enqueue_optimization_run", lambda run_id: enqueued.append(run_id))

    run = optimization.create_run(
        OptimizationRunCreate(
            semester="2026/2",
            profile="fast",
            parameters={"attempts": 4, "local_steps": 2},
        ),
        db_session,
    )

    assert run.id == existing.id
    assert enqueued == [existing.id]


def test_create_run_ignores_volatile_presentation_parameters(monkeypatch, db_session) -> None:
    enqueued: list[str] = []
    existing = OptimizationRun(
        semester="2026/2",
        profile="balanced",
        parameters={
            "student_demand_only": True,
            "auto_enrollment": True,
            "source": "trabalho",
            "presentation_run_id": "old-client-run",
            "requested_at": "2026-05-05T00:00:00Z",
        },
        status=RunStatus.pending,
    )
    db_session.add(existing)
    db_session.commit()
    monkeypatch.setattr(optimization, "enqueue_optimization_run", lambda run_id: enqueued.append(run_id))

    run = optimization.create_run(
        OptimizationRunCreate(
            semester="2026/2",
            profile="balanced",
            parameters={
                "student_demand_only": True,
                "auto_enrollment": True,
                "source": "trabalho",
                "presentation_run_id": "new-client-run",
                "requested_at": "2026-05-05T00:01:00Z",
            },
        ),
        db_session,
    )

    assert run.id == existing.id
    assert enqueued == [existing.id]


def test_get_run_requeues_pending_run(monkeypatch, db_session) -> None:
    enqueued: list[str] = []
    existing = OptimizationRun(
        semester="2026/2",
        profile="balanced",
        parameters={"student_demand_only": True},
        status=RunStatus.pending,
    )
    db_session.add(existing)
    db_session.commit()
    monkeypatch.setattr(optimization, "enqueue_optimization_run", lambda run_id: enqueued.append(run_id))

    run = optimization.get_run(existing.id, db_session)

    assert run.id == existing.id
    assert enqueued == [existing.id]


def test_reoptimize_returns_new_pending_run(monkeypatch, db_session) -> None:
    enqueued: list[str] = []
    previous = OptimizationRun(
        semester="2026/2",
        profile="balanced",
        parameters={"student_demand_only": True},
        status=RunStatus.feasible,
    )
    db_session.add(previous)
    db_session.commit()
    monkeypatch.setattr(optimization, "enqueue_optimization_run", lambda run_id: enqueued.append(run_id))

    run = optimization.reoptimize(previous.id, db_session)

    assert run.id != previous.id
    assert run.status == RunStatus.pending
    assert run.parameters["parent_run_id"] == previous.id
    assert run.parameters["mode"] == "partial_reoptimization"
    assert enqueued == [run.id]


def test_get_run_details_exposes_assignment_reasoning(db_session) -> None:
    campus = Campus(name="Campus Anglo", city="Pelotas")
    program = DegreeProgram(name="Engenharia de Producao", campus=campus)
    course = Course(
        name="Calculo A",
        campus=campus,
        degree_program=program,
        workload_hours=68,
        theoretical_hours=68,
        practical_hours=0,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=1,
        requires_lab=False,
        criticality=5,
        context_key="calculo-a",
        shareable=True,
    )
    professor = Professor(name="STEFFANI NIKOLI DAPPER", department="Centro de Engenharias")
    slot = TimeSlot(day=0, start_minute=19 * 60, end_minute=21 * 60, label="Seg 19:00")
    room = Room(name="Sala 101", campus_id=None, capacity=30, kind=RoomKind.lecture)
    run = OptimizationRun(
        semester="2026/2",
        profile="balanced",
        status=RunStatus.feasible,
        metrics={},
    )
    db_session.add_all([campus, program, course, professor, slot, room, run])
    db_session.flush()
    run.metrics = {
        "planned_sections": [
            {
                "db_course_id": course.id,
                "section_index": 0,
                "section_label": "Turma 1",
                "course_name": "Calculo A",
                "planned_students": 1,
                "strategy": "regular obrigatoria",
            }
        ]
    }
    room.campus_id = campus.id
    db_session.add_all(
        [
            ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=40, regime="DE/40h"),
            ProfessorQualification(professor_id=professor.id, course_id=course.id),
            ProfessorAvailability(
                professor_id=professor.id,
                day=0,
                start_minute=18 * 60,
                end_minute=22 * 60,
                kind=AvailabilityKind.available,
                strength=ConstraintStrength.hard,
                source="pilot",
            ),
        ]
    )
    db_session.flush()
    assignment = optimization.Assignment(
        run_id=run.id,
        course_id=course.id,
        professor_id=professor.id,
        room_id=room.id,
        time_slot_id=slot.id,
        session_index=0,
        origin="optimized",
    )
    student = Student(name="Aluno Piloto", degree_program_id=program.id, current_semester=2)
    db_session.add_all([assignment, student])
    db_session.flush()
    request = StudentCourseRequest(
        student_id=student.id,
        course_id=course.id,
        target_semester="2026/2",
        priority=5,
        preference_order=1,
        alternative_group="fila",
        stage="pre_enrollment",
        source="presentation",
    )
    db_session.add(request)
    db_session.flush()
    db_session.add(
        StudentEnrollment(
            student_id=student.id,
            course_id=course.id,
            request_id=request.id,
            run_id=run.id,
            target_semester="2026/2",
            stage="pre_enrollment",
            status="enrolled",
            score=98,
            score_breakdown={"regular": 25},
            reason="Alocado pela rodada automatica",
        )
    )
    db_session.commit()

    details = optimization.get_run_details(run.id, db_session)

    assert details["run_id"] == run.id
    assert details["assignments"][0]["professor"]["name"] == "STEFFANI NIKOLI DAPPER"
    assert details["assignments"][0]["enrollments"][0]["student"]["degree_program_name"] == "Engenharia de Producao"
    assert details["assignments"][0]["enrollments"][0]["decision_type"] == "escolha principal do aluno"
    assert details["assignments"][0]["professor"]["availability"][0]["matches_assignment"] is True


def test_presentation_teacher_link_prefers_steffani(db_session) -> None:
    other = Professor(name="A DOCENTE", department="Teste")
    steffani = Professor(name="STEFFANI NIKOLI DAPPER", department="Centro de Engenharias")
    db_session.add_all([other, steffani])
    db_session.commit()

    selected = presentation.presentation_teacher_professor(db_session)

    assert selected.id == steffani.id
