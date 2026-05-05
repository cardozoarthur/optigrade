from app.models.entities import (
    Assignment,
    AvailabilityKind,
    Campus,
    ConstraintStrength,
    Course,
    CourseKind,
    DegreeProgram,
    Professor,
    ProfessorAvailability,
    ProfessorConstraint,
    ProfessorContract,
    ProfessorQualification,
    Room,
    RoomKind,
    Student,
    StudentCourseRequest,
    TimeSlot,
    OptimizationRun,
)
from app.services.optimizer import build_snapshot, diagnose_snapshot, run_optimization


def test_diagnosis_detects_course_without_qualified_professor(db_session) -> None:
    db_session.add(
        Course(
            name="Calculo I",
            workload_hours=4,
            kind=CourseKind.mandatory,
            recommended_semester=1,
            expected_demand=20,
        )
    )
    db_session.add(Professor(name="Docente"))
    db_session.add(Room(name="Sala", capacity=30, kind=RoomKind.lecture))
    db_session.add(TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10"))
    db_session.commit()

    diagnosis = diagnose_snapshot(build_snapshot(db_session))

    assert any(item["code"] == "no_qualified_professor" for item in diagnosis)


def test_snapshot_accepts_minimum_viable_data(db_session) -> None:
    course = Course(
        name="Calculo I",
        workload_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    professor = Professor(name="Docente")
    room = Room(name="Sala", capacity=30, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    db_session.add_all([course, professor, room, slot])
    db_session.flush()
    db_session.add(ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=6))
    db_session.add(ProfessorQualification(professor_id=professor.id, course_id=course.id))
    db_session.commit()

    diagnosis = diagnose_snapshot(build_snapshot(db_session))

    assert diagnosis == []


def test_run_optimization_generates_assignments(db_session) -> None:
    course = Course(
        name="Calculo I",
        workload_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    professor = Professor(name="Docente")
    room = Room(name="Sala", capacity=30, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    db_session.add_all([course, professor, room, slot])
    db_session.flush()
    db_session.add(ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=6))
    db_session.add(ProfessorQualification(professor_id=professor.id, course_id=course.id))
    run = OptimizationRun(profile="fast", parameters={"attempts": 4, "local_steps": 2})
    db_session.add(run)
    db_session.commit()

    result = run_optimization(db_session, run)

    assert result.metrics["assigned_sessions"] == 1
    assert result.metrics["hard_conflicts"] == 0


def test_professor_below_minimum_load_is_soft_warning(db_session) -> None:
    course = Course(
        name="Calculo I",
        workload_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    professor = Professor(name="Docente Alocado")
    idle_professor = Professor(name="Docente Subutilizado")
    room = Room(name="Sala", capacity=30, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    db_session.add_all([course, professor, idle_professor, room, slot])
    db_session.flush()
    db_session.add(ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=6))
    db_session.add(ProfessorContract(professor_id=idle_professor.id, min_hours=2, max_hours=6))
    db_session.add(ProfessorQualification(professor_id=professor.id, course_id=course.id))
    run = OptimizationRun(profile="fast", parameters={"attempts": 4, "local_steps": 2})
    db_session.add(run)
    db_session.commit()

    result = run_optimization(db_session, run)

    assert result.status == "feasible"
    assert result.metrics["hard_conflicts"] == 0
    assert result.metrics["min_load_warnings"] == 1
    assert result.metrics["min_load_shortfall"] == 2
    assert result.metrics["min_load_diagnostics"][0]["professor_id"] == idle_professor.id


def test_regular_curriculum_course_respects_degree_program_window(db_session) -> None:
    program = DegreeProgram(
        name="Administracao Noturno",
        code="ADM-N",
        schedule_start_minute=19 * 60,
        schedule_end_minute=22 * 60,
    )
    db_session.add(program)
    db_session.flush()
    course = Course(
        name="Teoria Geral da Administracao",
        degree_program_id=program.id,
        workload_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    professor = Professor(name="Docente")
    room = Room(name="Sala", capacity=30, kind=RoomKind.lecture)
    morning = TimeSlot(day=0, start_minute=8 * 60, end_minute=10 * 60, label="Seg 08-10")
    night = TimeSlot(day=0, start_minute=19 * 60, end_minute=21 * 60, label="Seg 19-21")
    db_session.add_all([course, professor, room, morning, night])
    db_session.flush()
    db_session.add(ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=6))
    db_session.add(ProfessorQualification(professor_id=professor.id, course_id=course.id))
    run = OptimizationRun(profile="fast", parameters={"attempts": 4, "local_steps": 2})
    db_session.add(run)
    db_session.commit()

    result = run_optimization(db_session, run)
    assignment = db_session.query(Assignment).filter(Assignment.run_id == result.id).one()

    assert result.metrics["hard_conflicts"] == 0
    assert assignment.time_slot_id == night.id


def test_course_uses_room_in_compatible_campus(db_session) -> None:
    anglo = Campus(name="Campus Anglo")
    capao = Campus(name="Campus Capao")
    db_session.add_all([anglo, capao])
    db_session.flush()
    course = Course(
        name="Calculo I",
        campus_id=anglo.id,
        workload_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    professor = Professor(name="Docente")
    wrong_room = Room(name="Sala Capao", campus_id=capao.id, capacity=80, kind=RoomKind.lecture)
    right_room = Room(name="Sala Anglo", campus_id=anglo.id, capacity=30, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    db_session.add_all([course, professor, wrong_room, right_room, slot])
    db_session.flush()
    db_session.add(ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=6))
    db_session.add(ProfessorQualification(professor_id=professor.id, course_id=course.id))
    run = OptimizationRun(profile="fast", parameters={"attempts": 4, "local_steps": 2})
    db_session.add(run)
    db_session.commit()

    result = run_optimization(db_session, run)
    assignment = db_session.query(Assignment).filter(Assignment.run_id == result.id).one()

    assert result.metrics["hard_conflicts"] == 0
    assert assignment.room_id == right_room.id


def test_shared_context_does_not_merge_courses_from_different_campuses(db_session) -> None:
    anglo = Campus(name="Campus Anglo")
    capao = Campus(name="Campus Capao")
    production = DegreeProgram(name="Engenharia de Producao", code="EP", campus_id=anglo.id)
    computing = DegreeProgram(name="Ciencia da Computacao", code="CC", campus_id=capao.id)
    db_session.add_all([anglo, capao])
    db_session.flush()
    production.campus_id = anglo.id
    computing.campus_id = capao.id
    db_session.add_all([production, computing])
    db_session.flush()
    db_session.add_all(
        [
            Course(
                name="Calculo A",
                campus_id=anglo.id,
                degree_program_id=production.id,
                workload_hours=2,
                theoretical_hours=2,
                kind=CourseKind.mandatory,
                recommended_semester=1,
                expected_demand=20,
                context_key="calculo-a",
                shareable=True,
            ),
            Course(
                name="Calculo A",
                campus_id=capao.id,
                degree_program_id=computing.id,
                workload_hours=2,
                theoretical_hours=2,
                kind=CourseKind.mandatory,
                recommended_semester=1,
                expected_demand=25,
                context_key="calculo-a",
                shareable=True,
            ),
        ]
    )
    db_session.commit()

    snapshot = build_snapshot(db_session)

    assert len(snapshot.courses) == 2
    assert sorted(item.expected_demand for item in snapshot.courses) == [20, 25]


def test_elective_reoffer_uses_professor_availability_without_degree_window(db_session) -> None:
    program = DegreeProgram(
        name="Administracao Manha",
        code="ADM-M",
        schedule_start_minute=8 * 60,
        schedule_end_minute=12 * 60,
    )
    db_session.add(program)
    db_session.flush()
    course = Course(
        name="Topicos Especiais",
        degree_program_id=program.id,
        workload_hours=2,
        kind=CourseKind.elective,
        recommended_semester=6,
        expected_demand=12,
    )
    professor = Professor(name="Docente")
    room = Room(name="Sala", capacity=20, kind=RoomKind.lecture)
    night = TimeSlot(day=0, start_minute=19 * 60, end_minute=21 * 60, label="Seg 19-21")
    db_session.add_all([course, professor, room, night])
    db_session.flush()
    db_session.add(ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=6))
    db_session.add(ProfessorQualification(professor_id=professor.id, course_id=course.id))
    db_session.commit()

    snapshot = build_snapshot(db_session)

    assert snapshot.courses[0].regular_time_windows == ()
    assert diagnose_snapshot(snapshot) == []


def test_borrowed_professor_only_applies_to_matching_semester(db_session) -> None:
    course = Course(
        name="Topicos em IA",
        workload_hours=2,
        kind=CourseKind.elective,
        recommended_semester=6,
        expected_demand=15,
    )
    professor = Professor(name="Docente Emprestado", department="Computacao")
    room = Room(name="Sala", capacity=30, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    db_session.add_all([course, professor, room, slot])
    db_session.flush()
    db_session.add(
        ProfessorContract(
            professor_id=professor.id,
            min_hours=0,
            max_hours=2,
            semester="2026/2",
            is_borrowed=True,
            borrowed_from_department="Departamento externo",
        )
    )
    db_session.add(ProfessorQualification(professor_id=professor.id, course_id=course.id))
    db_session.commit()

    current_snapshot = build_snapshot(db_session, semester="2026/2")
    previous_snapshot = build_snapshot(db_session, semester="2026/1")

    assert [item.name for item in current_snapshot.professors] == ["Docente Emprestado"]
    assert previous_snapshot.professors == []
    assert any(
        item["code"] == "no_qualified_professor" for item in diagnose_snapshot(previous_snapshot)
    )


def test_structured_professor_availability_constraint_blocks_slot(db_session) -> None:
    course = Course(
        name="Calculo I",
        workload_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    professor = Professor(name="Docente")
    room = Room(name="Sala", capacity=30, kind=RoomKind.lecture)
    monday = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    tuesday = TimeSlot(day=1, start_minute=480, end_minute=600, label="Ter 08-10")
    db_session.add_all([course, professor, room, monday, tuesday])
    db_session.flush()
    db_session.add(ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=4))
    db_session.add(ProfessorQualification(professor_id=professor.id, course_id=course.id))
    db_session.add(
        ProfessorConstraint(
            professor_id=professor.id,
            natural_language="Nao posso segunda de manha",
            structured_rule={
                "rule": {
                    "type": "availability",
                    "days": [0],
                    "start_minute": 0,
                    "end_minute": 1440,
                    "preference": -5,
                }
            },
            strength=ConstraintStrength.hard,
        )
    )
    run = OptimizationRun(profile="fast", parameters={"attempts": 4, "local_steps": 2})
    db_session.add(run)
    db_session.commit()

    result = run_optimization(db_session, run)
    assignment = db_session.query(Assignment).filter(Assignment.run_id == result.id).one()

    assert result.metrics["hard_conflicts"] == 0
    assert assignment.time_slot_id == tuesday.id


def test_hard_availability_accepts_ufpel_100_minute_window_inside_120_minute_slot(db_session) -> None:
    course = Course(
        name="Calculo I",
        workload_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    professor = Professor(name="Docente")
    room = Room(name="Sala", capacity=30, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    db_session.add_all([course, professor, room, slot])
    db_session.flush()
    db_session.add(ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=4))
    db_session.add(ProfessorQualification(professor_id=professor.id, course_id=course.id))
    db_session.add(
        ProfessorAvailability(
            professor_id=professor.id,
            day=0,
            start_minute=480,
            end_minute=580,
            kind=AvailabilityKind.available,
            strength=ConstraintStrength.hard,
        )
    )
    run = OptimizationRun(profile="fast", parameters={"attempts": 4, "local_steps": 2})
    db_session.add(run)
    db_session.commit()

    result = run_optimization(db_session, run)

    assert result.status == "feasible"
    assert result.metrics["hard_conflicts"] == 0


def test_supervised_internship_does_not_expand_to_one_session_per_two_hours(db_session) -> None:
    course = Course(
        name="Estagio Curricular Profissionalizante",
        workload_hours=20,
        kind=CourseKind.mandatory,
        recommended_semester=8,
        expected_demand=10,
    )
    professor = Professor(name="Docente")
    room = Room(name="Sala", capacity=30, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    db_session.add_all([course, professor, room, slot])
    db_session.flush()
    db_session.add(ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=4))
    db_session.add(ProfessorQualification(professor_id=professor.id, course_id=course.id))
    run = OptimizationRun(profile="fast", parameters={"attempts": 4, "local_steps": 2})
    db_session.add(run)
    db_session.commit()

    result = run_optimization(db_session, run)

    assert result.status == "feasible"
    assert result.metrics["assigned_sessions"] == 1


def test_shared_context_groups_equivalent_courses(db_session) -> None:
    campus = Campus(name="Campus Anglo", city="Pelotas")
    production = DegreeProgram(name="Engenharia de Producao", code="EP")
    civil = DegreeProgram(name="Engenharia Civil", code="EC")
    db_session.add_all([campus, production, civil])
    db_session.flush()
    production.campus_id = campus.id
    civil.campus_id = campus.id

    production_calculus = Course(
        code="MAT-CALC-A-EP",
        name="Calculo A",
        campus_id=campus.id,
        degree_program_id=production.id,
        workload_hours=2,
        theoretical_hours=2,
        practical_hours=0,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
        context_key="calculo-a:engenharias",
    )
    civil_calculus = Course(
        code="MAT-CALC-A-EC",
        name="Calculo A",
        campus_id=campus.id,
        degree_program_id=civil.id,
        workload_hours=2,
        theoretical_hours=2,
        practical_hours=0,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=25,
        context_key="calculo-a:engenharias",
    )
    professor = Professor(name="Docente de Matematica")
    room = Room(name="Sala grande", capacity=50, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    db_session.add_all([production_calculus, civil_calculus, professor, room, slot])
    db_session.flush()
    db_session.add(ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=4))
    db_session.add(
        ProfessorQualification(professor_id=professor.id, course_id=production_calculus.id)
    )
    db_session.commit()

    snapshot = build_snapshot(db_session)
    shared_course = snapshot.courses[0]

    assert len(snapshot.courses) == 1
    assert shared_course.expected_demand == 45
    assert shared_course.theoretical_hours == 2
    assert shared_course.context_key == "calculo-a:engenharias"
    assert set(shared_course.source_course_ids) == {production_calculus.id, civil_calculus.id}
    assert shared_course.id in snapshot.qualifications[professor.id]
    assert diagnose_snapshot(snapshot) == []


def test_demand_solver_uses_alternatives_to_avoid_tiny_leftover_section(db_session) -> None:
    program = DegreeProgram(name="Engenharia de Producao", code="EP")
    db_session.add(program)
    db_session.flush()
    calculus = Course(
        name="Calculo A",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=2,
        expected_demand=20,
    )
    physics = Course(
        name="Fisica I",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=2,
        expected_demand=20,
    )
    room = Room(name="Sala regular", capacity=50, kind=RoomKind.lecture)
    db_session.add_all([calculus, physics, room])
    db_session.flush()
    students = [
        Student(name=f"Aluno {index:02d}", degree_program_id=program.id, current_semester=2)
        for index in range(53)
    ]
    db_session.add_all(students)
    db_session.flush()
    for index, student in enumerate(students):
        if index < 50:
            db_session.add(
                StudentCourseRequest(
                    student_id=student.id,
                    course_id=calculus.id,
                    target_semester="2026/2",
                    priority=5,
                )
            )
        elif index < 52:
            group = f"recuperacao-{index}"
            db_session.add_all(
                [
                    StudentCourseRequest(
                        student_id=student.id,
                        course_id=calculus.id,
                        target_semester="2026/2",
                        priority=5,
                        preference_order=1,
                        alternative_group=group,
                    ),
                    StudentCourseRequest(
                        student_id=student.id,
                        course_id=physics.id,
                        target_semester="2026/2",
                        priority=5,
                        preference_order=2,
                        alternative_group=group,
                    ),
                ]
            )
        else:
            db_session.add(
                StudentCourseRequest(
                    student_id=student.id,
                    course_id=physics.id,
                    target_semester="2026/2",
                    priority=5,
                )
            )
    db_session.commit()

    snapshot = build_snapshot(db_session, semester="2026/2", demand_driven=True)
    demand_by_name = {course.name: course.expected_demand for course in snapshot.courses}

    assert demand_by_name == {"Calculo A": 50, "Fisica I": 3}
    assert snapshot.student_demand_plan["alternative_assignments"] == 2
    assert snapshot.student_demand_plan["unplanned_choice_groups"] == 0


def test_demand_driven_solver_prunes_sections_when_teacher_capacity_is_insufficient(
    db_session,
) -> None:
    program = DegreeProgram(name="Engenharia de Producao", code="EP")
    db_session.add(program)
    db_session.flush()
    calculus = Course(
        name="Calculo A",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=80,
    )
    professor = Professor(name="Docente Calculo")
    room = Room(name="Sala 50", capacity=50, kind=RoomKind.lecture)
    available_slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    unavailable_slot = TimeSlot(day=1, start_minute=480, end_minute=600, label="Ter 08-10")
    run = OptimizationRun(
        semester="2026/2",
        profile="fast",
        parameters={"student_demand_only": True, "attempts": 8, "local_steps": 4},
    )
    db_session.add_all([calculus, professor, room, available_slot, unavailable_slot, run])
    db_session.flush()
    db_session.add_all(
        [
            ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=2),
            ProfessorQualification(professor_id=professor.id, course_id=calculus.id),
            ProfessorAvailability(
                professor_id=professor.id,
                day=0,
                start_minute=480,
                end_minute=600,
                kind=AvailabilityKind.available,
                strength=ConstraintStrength.hard,
            ),
        ]
    )
    students = [
        Student(name=f"Aluno {index:02d}", degree_program_id=program.id, current_semester=1)
        for index in range(55)
    ]
    db_session.add_all(students)
    db_session.flush()
    db_session.add_all(
        [
            StudentCourseRequest(
                student_id=student.id,
                course_id=calculus.id,
                target_semester="2026/2",
                priority=5,
            )
            for student in students
        ]
    )
    db_session.commit()

    result = run_optimization(db_session, run)
    pruning = result.metrics["student_demand_plan"]["teacher_capacity_pruned_sections"]
    assignment = db_session.query(Assignment).filter(Assignment.run_id == result.id).one()

    assert result.status == "feasible"
    assert result.metrics["hard_conflicts"] == 0
    assert result.metrics["assigned_sessions"] == 1
    assert result.metrics["student_demand_plan"]["teacher_capacity_unplanned_students"] == 5
    assert len(pruning) == 1
    assert pruning[0]["planned_students"] == 5
    assert pruning[0]["reason"].startswith("Capacidade docente indisponivel")
    assert result.metrics["planned_sections"][0]["planned_students"] == 50
    assert assignment.time_slot_id == available_slot.id


def test_solver_respects_multiple_hard_availability_windows_in_the_same_day(
    db_session,
) -> None:
    program = DegreeProgram(name="Computacao", code="CC")
    db_session.add(program)
    db_session.flush()
    algorithms = Course(
        name="Algoritmos",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    data_structures = Course(
        name="Estruturas de Dados",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=2,
        expected_demand=20,
    )
    professor = Professor(name="Docente Computacao")
    room = Room(name="Sala", capacity=30, kind=RoomKind.lecture)
    morning = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    afternoon = TimeSlot(day=0, start_minute=840, end_minute=960, label="Seg 14-16")
    blocked = TimeSlot(day=1, start_minute=480, end_minute=600, label="Ter 08-10")
    run = OptimizationRun(
        semester="2026/2",
        profile="fast",
        parameters={"attempts": 8, "local_steps": 4},
    )
    db_session.add_all(
        [algorithms, data_structures, professor, room, morning, afternoon, blocked, run]
    )
    db_session.flush()
    db_session.add_all(
        [
            ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=4),
            ProfessorQualification(professor_id=professor.id, course_id=algorithms.id),
            ProfessorQualification(professor_id=professor.id, course_id=data_structures.id),
            ProfessorAvailability(
                professor_id=professor.id,
                day=0,
                start_minute=480,
                end_minute=600,
                kind=AvailabilityKind.available,
                strength=ConstraintStrength.hard,
            ),
            ProfessorAvailability(
                professor_id=professor.id,
                day=0,
                start_minute=840,
                end_minute=960,
                kind=AvailabilityKind.available,
                strength=ConstraintStrength.hard,
            ),
        ]
    )
    db_session.commit()

    result = run_optimization(db_session, run)
    assigned_slot_ids = {
        assignment.time_slot_id
        for assignment in db_session.query(Assignment).filter(Assignment.run_id == result.id).all()
    }

    assert result.status == "feasible"
    assert result.metrics["hard_conflicts"] == 0
    assert result.metrics["assigned_sessions"] == 2
    assert assigned_slot_ids == {morning.id, afternoon.id}
    assert blocked.id not in assigned_slot_ids
