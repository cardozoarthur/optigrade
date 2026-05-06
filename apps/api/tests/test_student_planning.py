from app.api.routes import students as student_routes
from app.models.entities import (
    Campus,
    ConstraintStrength,
    Course,
    CourseKind,
    CourseRestriction,
    CourseRestrictionKind,
    DegreeProgram,
    Professor,
    ProfessorQualification,
    Room,
    RoomKind,
    Student,
    StudentCourseHistory,
    StudentCourseRequest,
    StudentCourseStatus,
    TimeSlot,
)
from app.schemas import StudentCoursePlanCreate
from app.services.optimizer import build_snapshot
from app.services.student_planning import build_student_suggestions
from app.services.student_planning import student_demand_summary
from app.ufpel_pilot_seed import (
    INSTITUTIONAL_BASE,
    AUDITORIUM_CAPACITY,
    PILOT_STUDENT_SOURCE,
    PILOT_STUDENT_TARGET_SEMESTER,
    PILOT_STUDENTS_PER_PROGRAM,
    REGULAR_ROOM_MAX_CAPACITY,
    REGULAR_ROOM_MIN_CAPACITY,
    regular_room_capacity,
    seed_students,
)


def test_student_suggestions_respect_completed_prerequisites(db_session) -> None:
    campus = Campus(name="Campus")
    program = DegreeProgram(name="Computacao", code="CC")
    db_session.add_all([campus, program])
    db_session.flush()
    program.campus_id = campus.id
    intro = Course(
        name="Algoritmos",
        campus_id=campus.id,
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=1,
    )
    advanced = Course(
        name="Estruturas de Dados",
        campus_id=campus.id,
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=2,
        expected_demand=1,
    )
    student = Student(name="Aluno", degree_program_id=program.id, current_semester=2)
    db_session.add_all([intro, advanced, student])
    db_session.flush()
    db_session.add(
        CourseRestriction(
            course_id=advanced.id,
            required_course_id=intro.id,
            kind=CourseRestrictionKind.prerequisite,
            strength=ConstraintStrength.hard,
            minimum_grade=6,
        )
    )
    db_session.commit()

    blocked = build_student_suggestions(db_session, student, "2026/2")
    advanced_suggestion = next(item for item in blocked if item["course"].id == advanced.id)

    assert advanced_suggestion["eligible"] is False
    assert advanced_suggestion["missing_requirements"][0].id == intro.id

    db_session.add(
        StudentCourseHistory(
            student_id=student.id,
            course_id=intro.id,
            status=StudentCourseStatus.completed,
            semester="2025/2",
            grade=7,
        )
    )
    db_session.commit()

    eligible = build_student_suggestions(db_session, student, "2026/2")
    advanced_suggestion = next(item for item in eligible if item["course"].id == advanced.id)

    assert advanced_suggestion["eligible"] is True
    assert advanced_suggestion["missing_requirements"] == []


def test_student_suggestions_require_multiple_prerequisites(db_session) -> None:
    program = DegreeProgram(name="Computacao", code="CC")
    db_session.add(program)
    db_session.flush()
    intro = Course(
        name="Algoritmos",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=1,
    )
    math = Course(
        name="Matematica Discreta",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=1,
    )
    advanced = Course(
        name="Analise de Algoritmos",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=3,
        expected_demand=1,
    )
    student = Student(name="Aluno", degree_program_id=program.id, current_semester=3)
    db_session.add_all([intro, math, advanced, student])
    db_session.flush()
    db_session.add_all(
        [
            CourseRestriction(
                course_id=advanced.id,
                required_course_id=intro.id,
                kind=CourseRestrictionKind.prerequisite,
                strength=ConstraintStrength.hard,
            ),
            CourseRestriction(
                course_id=advanced.id,
                required_course_id=math.id,
                kind=CourseRestrictionKind.prerequisite,
                strength=ConstraintStrength.hard,
            ),
            StudentCourseHistory(
                student_id=student.id,
                course_id=intro.id,
                status=StudentCourseStatus.completed,
                semester="2025/2",
                grade=7,
            ),
        ]
    )
    db_session.commit()

    suggestions = build_student_suggestions(db_session, student, "2026/2")
    advanced_suggestion = next(item for item in suggestions if item["course"].id == advanced.id)

    assert advanced_suggestion["eligible"] is False
    assert [item.id for item in advanced_suggestion["missing_requirements"]] == [math.id]


def test_student_suggestions_accept_equivalent_completed_course(db_session) -> None:
    campus = Campus(name="Campus")
    program = DegreeProgram(name="Engenharia Civil", code="EC")
    other_program = DegreeProgram(name="Engenharia de Producao", code="EP")
    db_session.add_all([campus, program, other_program])
    db_session.flush()
    program.campus_id = campus.id
    other_program.campus_id = campus.id
    calculus_civil = Course(
        name="Calculo A",
        campus_id=campus.id,
        degree_program_id=program.id,
        workload_hours=4,
        theoretical_hours=4,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=1,
        context_key="calculo-a:engenharias",
        shareable=True,
    )
    calculus_production = Course(
        name="Calculo A",
        campus_id=campus.id,
        degree_program_id=other_program.id,
        workload_hours=4,
        theoretical_hours=4,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=1,
        context_key="calculo-a:engenharias",
        shareable=True,
    )
    physics = Course(
        name="Fisica I",
        campus_id=campus.id,
        degree_program_id=program.id,
        workload_hours=4,
        theoretical_hours=4,
        kind=CourseKind.mandatory,
        recommended_semester=2,
        expected_demand=1,
    )
    student = Student(name="Aluno", degree_program_id=program.id, current_semester=2)
    db_session.add_all([calculus_civil, calculus_production, physics, student])
    db_session.flush()
    db_session.add_all(
        [
            CourseRestriction(
                course_id=physics.id,
                required_course_id=calculus_civil.id,
                kind=CourseRestrictionKind.prerequisite,
                strength=ConstraintStrength.hard,
                minimum_grade=6,
            ),
            StudentCourseHistory(
                student_id=student.id,
                course_id=calculus_production.id,
                status=StudentCourseStatus.completed,
                semester="2025/2",
                grade=8,
            ),
        ]
    )
    db_session.commit()

    suggestions = build_student_suggestions(db_session, student, "2026/2")
    physics_suggestion = next(item for item in suggestions if item["course"].id == physics.id)

    assert all(item["course"].id != calculus_civil.id for item in suggestions)
    assert physics_suggestion["eligible"] is True
    assert physics_suggestion["missing_requirements"] == []


def test_failed_shareable_course_can_be_reoffered_by_equivalent_program(db_session) -> None:
    campus = Campus(name="Campus Porto")
    production = DegreeProgram(name="Engenharia de Producao", code="EP", campus_id=campus.id)
    civil = DegreeProgram(name="Engenharia Civil", code="EC", campus_id=campus.id)
    db_session.add(campus)
    db_session.flush()
    production.campus_id = campus.id
    civil.campus_id = campus.id
    db_session.add_all([production, civil])
    db_session.flush()
    production_calculus = Course(
        name="Calculo A Producao",
        campus_id=campus.id,
        degree_program_id=production.id,
        workload_hours=4,
        theoretical_hours=4,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=40,
        context_key="calculo-a:engenharias",
        shareable=True,
    )
    civil_calculus = Course(
        name="Calculo A Civil",
        campus_id=campus.id,
        degree_program_id=civil.id,
        workload_hours=4,
        theoretical_hours=4,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=45,
        context_key="calculo-a:engenharias",
        shareable=True,
    )
    student = Student(name="Aluno", degree_program_id=production.id, current_semester=2)
    db_session.add_all([production_calculus, civil_calculus, student])
    db_session.flush()
    db_session.add(
        StudentCourseHistory(
            student_id=student.id,
            course_id=production_calculus.id,
            status=StudentCourseStatus.failed,
            semester="2026/1",
            grade=4.5,
        )
    )
    db_session.commit()

    suggestions = build_student_suggestions(db_session, student, "2026/2")
    civil_suggestion = next(item for item in suggestions if item["course"].id == civil_calculus.id)

    assert civil_suggestion["eligible"] is True
    assert civil_suggestion["regular_relation"] == "reoffer"
    assert "Reoferta equivalente disponivel em outro curso" in civil_suggestion["reasons"]

    db_session.add(
        StudentCourseRequest(
            student_id=student.id,
            course_id=civil_calculus.id,
            target_semester="2026/2",
            priority=5,
        )
    )
    db_session.commit()

    summary = student_demand_summary(db_session, "2026/2")

    assert summary.eligible_requests == 1
    assert summary.reoffer_requests == 1
    assert summary.demand_by_course == {civil_calculus.id: 1}


def test_failed_shareable_course_with_class_suffix_can_be_reoffered_by_equivalent_program(
    db_session,
) -> None:
    campus = Campus(name="Campus Porto")
    production = DegreeProgram(name="Engenharia de Producao", code="EP", campus_id=campus.id)
    civil = DegreeProgram(name="Engenharia Civil", code="EC", campus_id=campus.id)
    db_session.add(campus)
    db_session.flush()
    production.campus_id = campus.id
    civil.campus_id = campus.id
    db_session.add_all([production, civil])
    db_session.flush()
    production_chemistry = Course(
        name="QUÍMICA GERAL (T1)",
        campus_id=campus.id,
        degree_program_id=production.id,
        workload_hours=4,
        theoretical_hours=4,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=40,
        context_key="ufpel:15001001:t1",
        shareable=True,
    )
    civil_chemistry = Course(
        name="QUÍMICA GERAL (T2)",
        campus_id=campus.id,
        degree_program_id=civil.id,
        workload_hours=4,
        theoretical_hours=4,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=45,
        context_key="ufpel:15001001:t2",
        shareable=True,
    )
    student = Student(name="Aluno", degree_program_id=production.id, current_semester=2)
    db_session.add_all([production_chemistry, civil_chemistry, student])
    db_session.flush()
    db_session.add(
        StudentCourseHistory(
            student_id=student.id,
            course_id=production_chemistry.id,
            status=StudentCourseStatus.failed,
            semester="2026/1",
            grade=4.5,
        )
    )
    db_session.commit()

    suggestions = build_student_suggestions(db_session, student, "2026/2")
    civil_suggestion = next(item for item in suggestions if item["course"].id == civil_chemistry.id)

    assert civil_suggestion["eligible"] is True
    assert civil_suggestion["regular_relation"] == "reoffer"
    assert "Reoferta equivalente disponivel em outro curso" in civil_suggestion["reasons"]

    db_session.add(
        StudentCourseRequest(
            student_id=student.id,
            course_id=civil_chemistry.id,
            target_semester="2026/2",
            priority=5,
        )
    )
    db_session.commit()

    summary = student_demand_summary(db_session, "2026/2")

    assert summary.eligible_requests == 1
    assert summary.reoffer_requests == 1
    assert summary.demand_by_course == {civil_chemistry.id: 1}


def test_student_requests_increase_snapshot_demand(db_session) -> None:
    campus = Campus(name="Campus")
    program = DegreeProgram(name="Computacao", code="CC")
    db_session.add_all([campus, program])
    db_session.flush()
    program.campus_id = campus.id
    course = Course(
        name="Topicos Especiais",
        campus_id=campus.id,
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.elective,
        recommended_semester=4,
        expected_demand=1,
    )
    professor = Professor(name="Docente")
    room = Room(name="Sala", capacity=10, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    db_session.add_all([course, professor, room, slot])
    db_session.flush()
    students = [
        Student(name="Aluno 1", degree_program_id=program.id, current_semester=4),
        Student(name="Aluno 2", degree_program_id=program.id, current_semester=4),
    ]
    db_session.add_all(students)
    db_session.flush()
    for student in students:
        db_session.add(
            StudentCourseRequest(
                student_id=student.id,
                course_id=course.id,
                target_semester="2026/2",
                priority=3,
            )
        )
    db_session.add(ProfessorQualification(professor_id=professor.id, course_id=course.id))
    db_session.commit()

    snapshot = build_snapshot(db_session, semester="2026/2")

    assert snapshot.student_demand_requests == 2
    assert snapshot.courses[0].expected_demand == 2


def test_demand_driven_snapshot_only_keeps_requested_courses(db_session) -> None:
    program = DegreeProgram(name="Computacao", code="CC")
    db_session.add(program)
    db_session.flush()
    requested_course = Course(
        name="Banco de Dados",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=3,
        expected_demand=20,
    )
    unrequested_course = Course(
        name="Compiladores",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=5,
        expected_demand=20,
    )
    students = [
        Student(name=f"Aluno {index}", degree_program_id=program.id, current_semester=3)
        for index in range(3)
    ]
    db_session.add_all([requested_course, unrequested_course, *students])
    db_session.flush()
    db_session.add_all(
        [
            StudentCourseRequest(
                student_id=student.id,
                course_id=requested_course.id,
                target_semester="2026/2",
                priority=5,
            )
            for student in students
        ]
    )
    db_session.commit()

    snapshot = build_snapshot(db_session, semester="2026/2", demand_driven=True)

    assert [course.name for course in snapshot.courses] == ["Banco de Dados"]
    assert snapshot.student_demand_requests == 3


def test_demand_solver_opens_tiny_regular_section_when_needed(db_session) -> None:
    program = DegreeProgram(name="Computacao", code="CC")
    db_session.add(program)
    db_session.flush()
    requested_course = Course(
        name="Banco de Dados",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=3,
        expected_demand=20,
    )
    students = [
        Student(name=f"Aluno {index}", degree_program_id=program.id, current_semester=3)
        for index in range(2)
    ]
    db_session.add_all([requested_course, *students])
    db_session.flush()
    db_session.add_all(
        [
            StudentCourseRequest(
                student_id=student.id,
                course_id=requested_course.id,
                target_semester="2026/2",
                priority=5,
            )
            for student in students
        ]
    )
    db_session.commit()

    snapshot = build_snapshot(db_session, semester="2026/2", demand_driven=True)

    assert len(snapshot.courses) == 1
    assert snapshot.courses[0].name == "Banco de Dados"
    assert snapshot.courses[0].expected_demand == 2
    assert snapshot.courses[0].section_strategy == "forced_minimum_coverage_section"
    assert snapshot.student_demand_requests == 2
    assert snapshot.student_demand_plan["minimum_coverage_restored_groups"] == 0
    assert snapshot.student_demand_plan["unplanned_choice_groups"] == 0


def test_ineligible_student_request_does_not_increase_solver_demand(db_session) -> None:
    program = DegreeProgram(name="Computacao", code="CC")
    db_session.add(program)
    db_session.flush()
    intro = Course(
        name="Algoritmos",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=1,
    )
    advanced = Course(
        name="Analise de Algoritmos",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=3,
        expected_demand=1,
    )
    student = Student(name="Aluno", degree_program_id=program.id, current_semester=3)
    db_session.add_all([intro, advanced, student])
    db_session.flush()
    db_session.add_all(
        [
            CourseRestriction(
                course_id=advanced.id,
                required_course_id=intro.id,
                kind=CourseRestrictionKind.prerequisite,
                strength=ConstraintStrength.hard,
            ),
            StudentCourseRequest(
                student_id=student.id,
                course_id=advanced.id,
                target_semester="2026/2",
                priority=5,
            ),
        ]
    )
    db_session.commit()

    summary = student_demand_summary(db_session, "2026/2")
    snapshot = build_snapshot(db_session, semester="2026/2")

    assert summary.total_requests == 1
    assert summary.eligible_requests == 0
    assert summary.blocked_requests == 1
    assert summary.demand_by_course == {}
    assert snapshot.student_demand_requests == 0
    assert snapshot.student_demand_raw_requests == 1
    assert snapshot.student_demand_blocked_requests == 1


def test_ufpel_pilot_seed_creates_student_cohorts_for_multiple_programs(db_session) -> None:
    engineering = DegreeProgram(
        name="Engenharia Civil",
        code="UFPEL-6300",
        minimum_semesters=4,
    )
    computing = DegreeProgram(
        name="Ciencia da Computacao",
        code="UFPEL-3900",
        minimum_semesters=4,
    )
    db_session.add_all([engineering, computing])
    db_session.flush()

    for program, prefix in ((engineering, "ENG"), (computing, "COMP")):
        for semester in range(1, 5):
            db_session.add(
                Course(
                    code=f"{prefix}-{semester}",
                    name=f"Cadeira {prefix} {semester}",
                    degree_program_id=program.id,
                    workload_hours=2,
                    theoretical_hours=2,
                    kind=CourseKind.mandatory,
                    recommended_semester=semester,
                    expected_demand=20,
                    source_url=f"{INSTITUTIONAL_BASE}/disciplinas/cod/{prefix}{semester}",
                )
            )
    db_session.commit()

    stats = seed_students(db_session, {6300: engineering, 3900: computing})
    db_session.commit()

    assert stats["students"] == PILOT_STUDENTS_PER_PROGRAM * 2
    assert db_session.query(Student).count() == PILOT_STUDENTS_PER_PROGRAM * 2
    assert db_session.query(StudentCourseHistory).count() == stats["history"]
    assert (
        db_session.query(StudentCourseRequest)
        .filter(StudentCourseRequest.source == PILOT_STUDENT_SOURCE)
        .count()
        == stats["requests"]
    )

    summary = student_demand_summary(db_session, PILOT_STUDENT_TARGET_SEMESTER)
    assert summary.total_requests == stats["requests"]
    assert summary.eligible_requests == stats["requests"]
    assert summary.regular_requests > 0
    assert summary.reoffer_requests > 0


def test_pilot_regular_room_capacity_stays_between_10_and_50() -> None:
    capacities = [regular_room_capacity(index) for index in range(1, 40)]

    assert min(capacities) >= REGULAR_ROOM_MIN_CAPACITY
    assert max(capacities) <= REGULAR_ROOM_MAX_CAPACITY
    assert AUDITORIUM_CAPACITY == 200


def test_complex_plan_submission_scopes_alternatives_by_choice_group(db_session) -> None:
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
    student = Student(name="Aluno Plano", degree_program_id=program.id, current_semester=2)
    db_session.add_all([calculus, algebra, geometry, international_relations, student])
    db_session.commit()

    requests = student_routes.submit_complex_student_course_plan(
        student.id,
        StudentCoursePlanCreate(
            target_semester="2026/2",
            alternative_group="trajetoria-principal",
            branches=[
                {
                    "choice_group": "recuperar calculo",
                    "preference_order": 1,
                    "priority": 5,
                    "label": "Cálculo A",
                    "items": [{"course_id": calculus.id}],
                },
                {
                    "choice_group": "recuperar calculo",
                    "preference_order": 2,
                    "priority": 4,
                    "label": "Álgebra + Geometria",
                    "items": [{"course_id": algebra.id}, {"course_id": geometry.id}],
                },
                {
                    "choice_group": "humanas",
                    "preference_order": 1,
                    "priority": 5,
                    "label": "Relações Internacionais",
                    "items": [{"course_id": international_relations.id}],
                },
            ],
        ),
        db_session,
    )

    groups_by_course = {request.course_id: request.alternative_group for request in requests}
    assert groups_by_course[calculus.id] == "trajetoria-principal:recuperar-calculo"
    assert groups_by_course[algebra.id] == "trajetoria-principal:recuperar-calculo"
    assert groups_by_course[geometry.id] == "trajetoria-principal:recuperar-calculo"
    assert groups_by_course[international_relations.id] == "trajetoria-principal:humanas"
