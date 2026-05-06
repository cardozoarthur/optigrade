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
from app.services.optimizer import (
    build_snapshot,
    diagnose_snapshot,
    planned_section_sizes_from_capacity,
    run_optimization,
)


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


def test_demand_planner_adds_implicit_regular_offer_for_eligible_student(db_session) -> None:
    program = DegreeProgram(
        name="Engenharia de Producao",
        code="EP",
        schedule_start_minute=19 * 60,
        schedule_end_minute=22 * 60,
    )
    db_session.add(program)
    db_session.flush()
    course = Course(
        name="Pesquisa Operacional",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=4,
        expected_demand=20,
    )
    student = Student(name="Aluno Regular", degree_program_id=program.id, current_semester=4)
    professor = Professor(name="Docente")
    room = Room(name="Sala", capacity=20, kind=RoomKind.lecture)
    night = TimeSlot(day=0, start_minute=19 * 60, end_minute=21 * 60, label="Seg 19-21")
    db_session.add_all([course, student, professor, room, night])
    db_session.flush()
    db_session.add(ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=4))
    db_session.add(ProfessorQualification(professor_id=professor.id, course_id=course.id))
    db_session.commit()

    snapshot = build_snapshot(db_session, semester="2026/2", demand_driven=True)

    assert len(snapshot.courses) == 1
    assert snapshot.courses[0].name == "Pesquisa Operacional"
    assert snapshot.courses[0].expected_demand == 1
    assert snapshot.courses[0].regular_time_windows == ((19 * 60, 22 * 60),)
    assert snapshot.courses[0].section_strategy == "forced_minimum_coverage_section"
    assert snapshot.student_demand_requests == 0
    assert snapshot.student_demand_plan["mandatory_regular_floor_added_by_course"] == {course.id: 1}
    assert diagnose_snapshot(snapshot) == []


def test_regular_offer_forces_teacher_availability_when_no_official_window_matches(
    db_session,
) -> None:
    program = DegreeProgram(
        name="Engenharia de Producao",
        code="EP",
        schedule_start_minute=8 * 60,
        schedule_end_minute=12 * 60,
    )
    db_session.add(program)
    db_session.flush()
    course = Course(
        name="Calculo A",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    student = Student(name="Aluno Regular", degree_program_id=program.id, current_semester=1)
    professor = Professor(name="Docente")
    room = Room(name="Sala", capacity=20, kind=RoomKind.lecture)
    morning = TimeSlot(day=0, start_minute=8 * 60, end_minute=10 * 60, label="Seg 08-10")
    db_session.add_all([course, student, professor, room, morning])
    db_session.flush()
    db_session.add(ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=4))
    db_session.add(ProfessorQualification(professor_id=professor.id, course_id=course.id))
    db_session.add(
        ProfessorAvailability(
            professor_id=professor.id,
            day=1,
            start_minute=14 * 60,
            end_minute=18 * 60,
            kind=AvailabilityKind.available,
            strength=ConstraintStrength.hard,
        )
    )
    run = OptimizationRun(
        profile="fast",
        parameters={"student_demand_only": True, "attempts": 4, "local_steps": 2},
    )
    db_session.add(run)
    db_session.commit()

    result = run_optimization(db_session, run)
    assignment = db_session.query(Assignment).filter(Assignment.run_id == result.id).one()

    assert result.metrics["hard_conflicts"] == 0
    assert assignment.time_slot_id == morning.id
    assert assignment.soft_violations[0]["code"] == "forced_regular_teacher_availability"


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


def test_lab_shared_context_does_not_merge_courses_from_different_campuses(db_session) -> None:
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
                requires_lab=True,
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
                requires_lab=True,
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


def test_courses_with_teacher_suffix_are_planned_as_one_offer(db_session) -> None:
    program = DegreeProgram(name="Engenharia de Producao", code="EP")
    db_session.add(program)
    db_session.flush()
    tcc_one = Course(
        name="TRABALHO DE CONCLUSÃO DE CURSO (T1)",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=10,
        expected_demand=3,
        context_key="ufpel:15000963:t1",
    )
    tcc_four = Course(
        name="TRABALHO DE CONCLUSÃO DE CURSO (T4)",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=10,
        expected_demand=3,
        context_key="ufpel:15000963:t4",
    )
    professor_one = Professor(name="Docente T1")
    professor_four = Professor(name="Docente T4")
    room = Room(name="Sala 20", capacity=20, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    db_session.add_all([tcc_one, tcc_four, professor_one, professor_four, room, slot])
    db_session.flush()
    db_session.add_all(
        [
            ProfessorContract(professor_id=professor_one.id, min_hours=0, max_hours=4),
            ProfessorContract(professor_id=professor_four.id, min_hours=0, max_hours=4),
            ProfessorQualification(professor_id=professor_one.id, course_id=tcc_one.id),
            ProfessorQualification(professor_id=professor_four.id, course_id=tcc_four.id),
        ]
    )
    db_session.commit()

    snapshot = build_snapshot(db_session)
    shared_course = snapshot.courses[0]

    assert len(snapshot.courses) == 1
    assert shared_course.name == "TRABALHO DE CONCLUSÃO DE CURSO (2 cursos)"
    assert shared_course.expected_demand == 6
    assert shared_course.context_key == "ufpel:15000963"
    assert set(shared_course.source_course_ids) == {tcc_one.id, tcc_four.id}
    assert shared_course.id in snapshot.qualifications[professor_one.id]
    assert shared_course.id in snapshot.qualifications[professor_four.id]


def test_equivalent_regular_courses_with_same_turn_are_absorbed_into_one_offer_for_any_subject(
    db_session,
) -> None:
    production = DegreeProgram(
        name="Engenharia de Producao",
        code="EP",
        schedule_start_minute=19 * 60,
        schedule_end_minute=22 * 60,
    )
    civil = DegreeProgram(
        name="Engenharia Civil",
        code="EC",
        schedule_start_minute=18 * 60,
        schedule_end_minute=22 * 60,
    )
    db_session.add_all([production, civil])
    db_session.flush()
    production_chemistry = Course(
        name="QUÍMICA GERAL (T1)",
        degree_program_id=production.id,
        workload_hours=4,
        theoretical_hours=4,
        practical_hours=0,
        kind=CourseKind.mandatory,
        recommended_semester=2,
        expected_demand=1,
        context_key="ufpel:15001001:t1",
        shareable=True,
    )
    civil_chemistry = Course(
        name="QUÍMICA GERAL (T2)",
        degree_program_id=civil.id,
        workload_hours=4,
        theoretical_hours=4,
        practical_hours=0,
        kind=CourseKind.mandatory,
        recommended_semester=2,
        expected_demand=20,
        context_key="ufpel:15001001:t2",
        shareable=True,
    )
    students = [
        Student(name="Aluno EP", degree_program_id=production.id, current_semester=2),
        *[
            Student(name=f"Aluno EC {index}", degree_program_id=civil.id, current_semester=2)
            for index in range(20)
        ],
    ]
    db_session.add_all([production_chemistry, civil_chemistry, *students])
    db_session.commit()

    snapshot = build_snapshot(db_session, semester="2026/2", demand_driven=True)
    shared_course = snapshot.courses[0]

    assert len(snapshot.courses) == 1
    assert shared_course.name == "QUÍMICA GERAL (2 cursos)"
    assert shared_course.expected_demand == 21
    assert shared_course.context_key == "ufpel:15001001"
    assert shared_course.course_turns == ("noturno",)
    assert set(shared_course.source_course_ids) == {production_chemistry.id, civil_chemistry.id}
    assert snapshot.student_demand_plan["unplanned_request_count"] == 0


def test_demand_planner_closes_marginal_course_when_second_option_absorbs_students(
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
        expected_demand=3,
    )
    physics = Course(
        name="Fisica I",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=3,
    )
    professor = Professor(name="Docente Fisica")
    room = Room(name="Sala 50", capacity=50, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    db_session.add_all([calculus, physics, professor, room, slot])
    db_session.flush()
    db_session.add(ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=6))
    db_session.add(ProfessorQualification(professor_id=professor.id, course_id=physics.id))
    calculus_students = [
        Student(name=f"Aluno Calculo {index}", degree_program_id=program.id, current_semester=2)
        for index in range(3)
    ]
    physics_students = [
        Student(name=f"Aluno Fisica {index}", degree_program_id=program.id, current_semester=2)
        for index in range(3)
    ]
    db_session.add_all([*calculus_students, *physics_students])
    db_session.flush()
    for index, student in enumerate(calculus_students):
        db_session.add_all(
            [
                StudentCourseRequest(
                    student_id=student.id,
                    course_id=calculus.id,
                    target_semester="2026/2",
                    alternative_group=f"trajetoria-{index}",
                    preference_order=1,
                    priority=5,
                ),
                StudentCourseRequest(
                    student_id=student.id,
                    course_id=physics.id,
                    target_semester="2026/2",
                    alternative_group=f"trajetoria-{index}",
                    preference_order=2,
                    priority=5,
                ),
            ]
        )
    for student in physics_students:
        db_session.add(
            StudentCourseRequest(
                student_id=student.id,
                course_id=physics.id,
                target_semester="2026/2",
                priority=5,
            )
        )
    db_session.commit()

    snapshot = build_snapshot(db_session, demand_driven=True)

    assert [course.name for course in snapshot.courses] == ["Fisica I"]
    assert snapshot.courses[0].expected_demand == 6
    assert snapshot.student_demand_plan["selected_demand_by_course"] == {physics.id: 6}
    assert snapshot.student_demand_plan["alternative_assignments"] == 3
    assert (
        snapshot.student_demand_plan["choice_solver_assignments"]
        + snapshot.student_demand_plan["consolidated_choice_groups"]
    ) == 3
    assert snapshot.student_demand_plan["unplanned_choice_groups"] == 0
    assert diagnose_snapshot(snapshot) == []


def test_regular_floor_participates_in_solver_and_absorbs_reoffer_options(
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
        recommended_semester=2,
        expected_demand=20,
    )
    physics = Course(
        name="Fisica I",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    regular_student = Student(
        name="Aluno regular",
        degree_program_id=program.id,
        current_semester=2,
    )
    reoffer_students = [
        Student(name=f"Aluno reoferta {index}", degree_program_id=program.id, current_semester=3)
        for index in range(2)
    ]
    professor = Professor(name="Docente Calculo")
    room = Room(name="Sala 50", capacity=50, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    db_session.add_all([calculus, physics, regular_student, *reoffer_students, professor, room, slot])
    db_session.flush()
    db_session.add_all(
        [
            ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=4),
            ProfessorQualification(professor_id=professor.id, course_id=calculus.id),
        ]
    )
    for index, student in enumerate(reoffer_students):
        group = f"trajetoria-{index}"
        db_session.add_all(
            [
                StudentCourseRequest(
                    student_id=student.id,
                    course_id=physics.id,
                    target_semester="2026/2",
                    preference_order=1,
                    alternative_group=group,
                    priority=5,
                ),
                StudentCourseRequest(
                    student_id=student.id,
                    course_id=calculus.id,
                    target_semester="2026/2",
                    preference_order=2,
                    alternative_group=group,
                    priority=5,
                ),
            ]
        )
    db_session.commit()

    snapshot = build_snapshot(db_session, semester="2026/2", demand_driven=True)

    assert [course.name for course in snapshot.courses] == ["Calculo A"]
    assert snapshot.courses[0].expected_demand == 3
    assert snapshot.student_demand_plan["mandatory_regular_demand_by_course"] == {calculus.id: 1}
    assert snapshot.student_demand_plan["selected_incremental_request_demand_by_course"] == {
        calculus.id: 2
    }
    assert snapshot.student_demand_plan["selected_demand_by_course"] == {calculus.id: 3}
    assert snapshot.student_demand_plan["alternative_assignments"] == 2
    assert diagnose_snapshot(snapshot) == []


def test_demand_planner_restores_one_small_section_to_avoid_empty_student_semester(
    db_session,
) -> None:
    program = DegreeProgram(name="Engenharia de Producao", code="EP")
    db_session.add(program)
    db_session.flush()
    algebra = Course(
        name="Algebra Linear",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=1,
    )
    structures = Course(
        name="Estruturas de Dados",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=1,
    )
    student = Student(name="Aluno sem turma", degree_program_id=program.id, current_semester=2)
    professor = Professor(name="Docente")
    room = Room(name="Sala 20", capacity=20, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    db_session.add_all([algebra, structures, student, professor, room, slot])
    db_session.flush()
    db_session.add(ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=4))
    db_session.add_all(
        [
            ProfessorQualification(professor_id=professor.id, course_id=algebra.id),
            ProfessorQualification(professor_id=professor.id, course_id=structures.id),
            StudentCourseRequest(
                student_id=student.id,
                course_id=algebra.id,
                target_semester="2026/2",
                preference_order=1,
                priority=5,
            ),
            StudentCourseRequest(
                student_id=student.id,
                course_id=structures.id,
                target_semester="2026/2",
                preference_order=2,
                priority=5,
            ),
        ]
    )
    db_session.commit()

    snapshot = build_snapshot(db_session, demand_driven=True)

    assert len(snapshot.courses) == 1
    assert snapshot.courses[0].expected_demand == 1
    assert snapshot.courses[0].section_strategy == "forced_minimum_coverage_section"
    assert snapshot.student_demand_plan["minimum_coverage_restored_groups"] == 1
    assert snapshot.student_demand_plan["unplanned_choice_groups"] == 1
    assert diagnose_snapshot(snapshot) == []


def test_planned_sections_are_balanced_when_multiple_classes_are_opened() -> None:
    assert planned_section_sizes_from_capacity(60, 50, 0) == (
        [30, 30],
        0,
        "balanced_additional_section",
    )
    assert planned_section_sizes_from_capacity(103, 50, 60) == (
        [35, 34, 34],
        0,
        "balanced_additional_section",
    )
    assert planned_section_sizes_from_capacity(83, 50, 200) == (
        [42, 41],
        0,
        "balanced_additional_section",
    )
    assert planned_section_sizes_from_capacity(52, 50, 60) == (
        [52],
        0,
        "balanced_absorbed_small_remainder",
    )


def test_multiple_sections_prefer_different_professors_and_balanced_load(
    db_session,
) -> None:
    program = DegreeProgram(name="Engenharia de Producao", code="EP")
    db_session.add(program)
    db_session.flush()
    course = Course(
        name="Pesquisa Operacional",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=6,
        expected_demand=80,
    )
    professors = [Professor(name="Docente A"), Professor(name="Docente B")]
    room = Room(name="Sala 50", capacity=50, kind=RoomKind.lecture)
    slots = [
        TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10"),
        TimeSlot(day=1, start_minute=480, end_minute=600, label="Ter 08-10"),
    ]
    run = OptimizationRun(
        semester="2026/2",
        profile="fast",
        parameters={"student_demand_only": True, "attempts": 8, "local_steps": 4},
    )
    db_session.add_all([course, *professors, room, *slots, run])
    db_session.flush()
    db_session.add_all(
        [
            ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=4)
            for professor in professors
        ]
    )
    db_session.add_all(
        [
            ProfessorQualification(professor_id=professor.id, course_id=course.id)
            for professor in professors
        ]
    )
    students = [
        Student(name=f"Aluno PO {index:02d}", degree_program_id=program.id, current_semester=6)
        for index in range(80)
    ]
    db_session.add_all(students)
    db_session.flush()
    db_session.add_all(
        [
            StudentCourseRequest(
                student_id=student.id,
                course_id=course.id,
                target_semester="2026/2",
                priority=5,
            )
            for student in students
        ]
    )
    db_session.commit()

    result = run_optimization(db_session, run)
    assignments = db_session.query(Assignment).filter(Assignment.run_id == result.id).all()

    assert result.status == "feasible"
    assert result.metrics["hard_conflicts"] == 0
    assert sorted(section["planned_students"] for section in result.metrics["planned_sections"]) == [40, 40]
    assert len({assignment.professor_id for assignment in assignments}) == 2
    assert result.metrics["section_professor_concentration"] == 0


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
        recommended_semester=1,
        expected_demand=20,
    )
    physics = Course(
        name="Fisica I",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
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


def test_demand_solver_selects_complex_conditional_bundle_instead_of_single_course(
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
        expected_demand=20,
    )
    algebra = Course(
        name="Algebra Linear",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    geometry = Course(
        name="Geometria Analitica",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    international_relations = Course(
        name="Relacoes Internacionais",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.elective,
        recommended_semester=4,
        expected_demand=20,
    )
    elective = Course(
        name="Topicos de Engenharia",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.elective,
        recommended_semester=4,
        expected_demand=20,
    )
    physics = Course(
        name="Fisica I",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    room = Room(name="Sala regular", capacity=50, kind=RoomKind.lecture)
    db_session.add_all([calculus, algebra, geometry, international_relations, elective, physics, room])
    db_session.flush()

    calculus_students = [
        Student(name=f"Calculo {index:02d}", degree_program_id=program.id, current_semester=2)
        for index in range(50)
    ]
    seed_students = [
        Student(name=f"Base pacote {index}", degree_program_id=program.id, current_semester=2)
        for index in range(3)
    ]
    complex_students = [
        Student(name=f"Aluno complexo {index}", degree_program_id=program.id, current_semester=2)
        for index in range(2)
    ]
    db_session.add_all([*calculus_students, *seed_students, *complex_students])
    db_session.flush()
    for student in calculus_students:
        db_session.add(
            StudentCourseRequest(
                student_id=student.id,
                course_id=calculus.id,
                target_semester="2026/2",
                priority=5,
            )
        )
    for student, course in zip(seed_students, [algebra, geometry, physics], strict=True):
        db_session.add(
            StudentCourseRequest(
                student_id=student.id,
                course_id=course.id,
                target_semester="2026/2",
                priority=5,
            )
        )
    branch_two_request_ids: set[str] = set()
    for index, student in enumerate(complex_students):
        group = f"trajetoria-{index}"
        db_session.add_all(
            [
                StudentCourseRequest(
                    student_id=student.id,
                    course_id=calculus.id,
                    target_semester="2026/2",
                    priority=5,
                    preference_order=1,
                    alternative_group=group,
                    desired_day=0,
                    desired_start_minute=19 * 60,
                    desired_end_minute=21 * 60,
                ),
                StudentCourseRequest(
                    student_id=student.id,
                    course_id=international_relations.id,
                    target_semester="2026/2",
                    priority=4,
                    preference_order=1,
                    alternative_group=group,
                    desired_day=3,
                    desired_start_minute=19 * 60,
                    desired_end_minute=21 * 60,
                ),
                StudentCourseRequest(
                    student_id=student.id,
                    course_id=elective.id,
                    target_semester="2026/2",
                    priority=4,
                    preference_order=1,
                    alternative_group=group,
                    desired_day=4,
                    desired_start_minute=19 * 60,
                    desired_end_minute=21 * 60,
                ),
            ]
        )
        branch_two = [
            StudentCourseRequest(
                student_id=student.id,
                course_id=algebra.id,
                target_semester="2026/2",
                priority=4,
                preference_order=2,
                alternative_group=group,
                desired_day=1,
                desired_start_minute=8 * 60,
                desired_end_minute=10 * 60,
            ),
            StudentCourseRequest(
                student_id=student.id,
                course_id=geometry.id,
                target_semester="2026/2",
                priority=4,
                preference_order=2,
                alternative_group=group,
                desired_day=2,
                desired_start_minute=8 * 60,
                desired_end_minute=10 * 60,
            ),
            StudentCourseRequest(
                student_id=student.id,
                course_id=physics.id,
                target_semester="2026/2",
                priority=4,
                preference_order=2,
                alternative_group=group,
                desired_day=4,
                desired_start_minute=8 * 60,
                desired_end_minute=10 * 60,
            ),
        ]
        db_session.add_all(branch_two)
        db_session.flush()
        branch_two_request_ids.update(request.id for request in branch_two)
    db_session.commit()

    snapshot = build_snapshot(db_session, semester="2026/2", demand_driven=True)
    demand_by_name = {course.name: course.expected_demand for course in snapshot.courses}
    selected_request_ids = set(snapshot.student_demand_plan["selected_request_ids"])

    assert demand_by_name == {
        "Algebra Linear": 3,
        "Calculo A": 50,
        "Fisica I": 3,
        "Geometria Analitica": 3,
    }
    assert snapshot.student_demand_plan["alternative_assignments"] == 2
    assert snapshot.student_demand_plan["complex_bundle_groups"] == 2
    assert branch_two_request_ids <= selected_request_ids


def test_demand_solver_mixes_independent_course_level_choice_units(
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
        expected_demand=20,
    )
    algebra = Course(
        name="Algebra Linear",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    geometry = Course(
        name="Geometria Analitica",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    international_relations = Course(
        name="Relacoes Internacionais",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.elective,
        recommended_semester=4,
        expected_demand=20,
    )
    physics = Course(
        name="Fisica I",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    room = Room(name="Sala regular", capacity=50, kind=RoomKind.lecture)
    db_session.add_all([calculus, algebra, geometry, international_relations, physics, room])
    db_session.flush()

    calculus_students = [
        Student(name=f"Calculo {index:02d}", degree_program_id=program.id, current_semester=2)
        for index in range(50)
    ]
    seed_algebra = Student(name="Base algebra", degree_program_id=program.id, current_semester=2)
    seed_geometry = Student(name="Base geometria", degree_program_id=program.id, current_semester=2)
    seed_ri = Student(name="Base relacoes", degree_program_id=program.id, current_semester=2)
    complex_students = [
        Student(name=f"Aluno unidade {index}", degree_program_id=program.id, current_semester=2)
        for index in range(2)
    ]
    db_session.add_all([*calculus_students, seed_algebra, seed_geometry, seed_ri, *complex_students])
    db_session.flush()

    for student in calculus_students:
        db_session.add(
            StudentCourseRequest(
                student_id=student.id,
                course_id=calculus.id,
                target_semester="2026/2",
                priority=5,
            )
        )
    for student, course in [
        (seed_algebra, algebra),
        (seed_geometry, geometry),
        (seed_ri, international_relations),
    ]:
        db_session.add(
            StudentCourseRequest(
                student_id=student.id,
                course_id=course.id,
                target_semester="2026/2",
                priority=5,
            )
        )

    math_fallback_request_ids: set[str] = set()
    humanities_first_request_ids: set[str] = set()
    physics_fallback_request_ids: set[str] = set()
    for index, student in enumerate(complex_students):
        math_group = f"math-{index}"
        load_group = f"load-{index}"
        db_session.add(
            StudentCourseRequest(
                student_id=student.id,
                course_id=calculus.id,
                target_semester="2026/2",
                priority=5,
                preference_order=1,
                alternative_group=math_group,
            )
        )
        math_fallback = [
            StudentCourseRequest(
                student_id=student.id,
                course_id=algebra.id,
                target_semester="2026/2",
                priority=4,
                preference_order=2,
                alternative_group=math_group,
            ),
            StudentCourseRequest(
                student_id=student.id,
                course_id=geometry.id,
                target_semester="2026/2",
                priority=4,
                preference_order=2,
                alternative_group=math_group,
            ),
        ]
        humanities_first = StudentCourseRequest(
            student_id=student.id,
            course_id=international_relations.id,
            target_semester="2026/2",
            priority=5,
            preference_order=1,
            alternative_group=load_group,
        )
        physics_fallback = StudentCourseRequest(
            student_id=student.id,
            course_id=physics.id,
            target_semester="2026/2",
            priority=4,
            preference_order=2,
            alternative_group=load_group,
        )
        db_session.add_all([*math_fallback, humanities_first, physics_fallback])
        db_session.flush()
        math_fallback_request_ids.update(request.id for request in math_fallback)
        humanities_first_request_ids.add(humanities_first.id)
        physics_fallback_request_ids.add(physics_fallback.id)
    db_session.commit()

    snapshot = build_snapshot(db_session, semester="2026/2", demand_driven=True)
    demand_by_name = {course.name: course.expected_demand for course in snapshot.courses}
    selected_request_ids = set(snapshot.student_demand_plan["selected_request_ids"])

    assert demand_by_name == {
        "Algebra Linear": 3,
        "Calculo A": 50,
        "Geometria Analitica": 3,
        "Relacoes Internacionais": 3,
    }
    assert math_fallback_request_ids <= selected_request_ids
    assert humanities_first_request_ids <= selected_request_ids
    assert not physics_fallback_request_ids & selected_request_ids
    assert snapshot.student_demand_plan["alternative_assignments"] == 2
    assert snapshot.student_demand_plan["complex_bundle_groups"] == 2


def test_demand_solver_scores_institutional_value_instead_of_first_available_order(
    db_session,
) -> None:
    program = DegreeProgram(name="Engenharia de Producao", code="EP")
    db_session.add(program)
    db_session.flush()
    elective = Course(
        name="Topicos Livres",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.elective,
        recommended_semester=2,
        expected_demand=20,
    )
    critical = Course(
        name="Disciplina Critica",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=20,
    )
    room = Room(name="Sala regular", capacity=50, kind=RoomKind.lecture)
    students = [
        Student(name=f"Aluno valor {index}", degree_program_id=program.id, current_semester=3)
        for index in range(3)
    ]
    db_session.add_all([elective, critical, room, *students])
    db_session.flush()

    elective_request_ids: set[str] = set()
    critical_request_ids: set[str] = set()
    for index, student in enumerate(students):
        group = f"valor-institucional-{index}"
        elective_request = StudentCourseRequest(
            student_id=student.id,
            course_id=elective.id,
            target_semester="2026/2",
            alternative_group=group,
            preference_order=1,
            priority=1,
        )
        critical_request = StudentCourseRequest(
            student_id=student.id,
            course_id=critical.id,
            target_semester="2026/2",
            alternative_group=group,
            preference_order=2,
            priority=5,
        )
        db_session.add_all([elective_request, critical_request])
        db_session.flush()
        elective_request_ids.add(elective_request.id)
        critical_request_ids.add(critical_request.id)
    db_session.commit()

    snapshot = build_snapshot(db_session, semester="2026/2", demand_driven=True)
    selected_request_ids = set(snapshot.student_demand_plan["selected_request_ids"])

    assert {course.name: course.expected_demand for course in snapshot.courses} == {
        "Disciplina Critica": 3,
    }
    assert critical_request_ids <= selected_request_ids
    assert not elective_request_ids & selected_request_ids
    assert snapshot.student_demand_plan["alternative_assignments"] == 3
    assert snapshot.student_demand_plan["unplanned_choice_groups"] == 0


def test_optimizer_prefers_student_requested_time_window(db_session) -> None:
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
    professor = Professor(name="Docente Calculo")
    room = Room(name="Sala", capacity=30, kind=RoomKind.lecture)
    monday = TimeSlot(day=0, start_minute=19 * 60, end_minute=21 * 60, label="Seg 19-21")
    tuesday = TimeSlot(day=1, start_minute=8 * 60, end_minute=10 * 60, label="Ter 08-10")
    student = Student(name="Aluno", degree_program_id=program.id, current_semester=2)
    run = OptimizationRun(
        semester="2026/2",
        profile="fast",
        parameters={"student_demand_only": True, "attempts": 12, "local_steps": 4},
    )
    db_session.add_all([calculus, professor, room, monday, tuesday, student, run])
    db_session.flush()
    db_session.add_all(
        [
            ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=4),
            ProfessorQualification(professor_id=professor.id, course_id=calculus.id),
        ]
    )
    for index in range(3):
        learner = student if index == 0 else Student(
            name=f"Aluno extra {index}",
            degree_program_id=program.id,
            current_semester=2,
        )
        if index:
            db_session.add(learner)
            db_session.flush()
        db_session.add(
            StudentCourseRequest(
                student_id=learner.id,
                course_id=calculus.id,
                target_semester="2026/2",
                priority=5,
                desired_day=1,
                desired_start_minute=8 * 60,
                desired_end_minute=10 * 60,
            )
        )
    db_session.commit()

    result = run_optimization(db_session, run)
    assignment = db_session.query(Assignment).filter(Assignment.run_id == result.id).one()

    assert result.status == "feasible"
    assert result.metrics["hard_conflicts"] == 0
    assert assignment.time_slot_id == tuesday.id


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
