from app.models.entities import (
    Assignment,
    Campus,
    ConstraintStrength,
    Course,
    CourseKind,
    CourseRestriction,
    CourseRestrictionKind,
    DegreeProgram,
    OptimizationRun,
    Professor,
    ProfessorContract,
    ProfessorQualification,
    Room,
    RoomKind,
    RunStatus,
    Student,
    StudentCourseHistory,
    StudentCourseRequest,
    StudentCourseStatus,
    StudentEnrollment,
    TimeSlot,
)
from app.services.enrollment import run_enrollment_round
from app.services.optimization_jobs import _maybe_run_automatic_enrollment
from app.services.optimizer import run_optimization


def test_enrollment_round_uses_alternative_queue_until_student_is_allocated(db_session) -> None:
    program = DegreeProgram(name="Engenharia", code="ENG")
    db_session.add(program)
    db_session.flush()
    calculus_a = Course(
        name="Calculo A",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=1,
    )
    calculus_b = Course(
        name="Calculo A - Turma alternativa",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=1,
    )
    students = [
        Student(name="Aluno 1", degree_program_id=program.id, current_semester=2),
        Student(name="Aluno 2", degree_program_id=program.id, current_semester=2),
    ]
    db_session.add_all([calculus_a, calculus_b, *students])
    db_session.flush()
    for student in students:
        db_session.add_all(
            [
                StudentCourseRequest(
                    student_id=student.id,
                    course_id=calculus_a.id,
                    target_semester="2026/2",
                    alternative_group="dependencia-calculo",
                    preference_order=1,
                    priority=5,
                ),
                StudentCourseRequest(
                    student_id=student.id,
                    course_id=calculus_b.id,
                    target_semester="2026/2",
                    alternative_group="dependencia-calculo",
                    preference_order=2,
                    priority=5,
                ),
            ]
        )
    db_session.commit()

    summary = run_enrollment_round(db_session, "2026/2")
    enrollments = (
        db_session.query(StudentEnrollment)
        .filter(StudentEnrollment.status == "enrolled")
        .order_by(StudentEnrollment.course_id)
        .all()
    )

    assert summary["enrolled"] == 2
    assert summary["unallocated_groups"] == 0
    assert {item.course_id for item in enrollments} == {calculus_a.id, calculus_b.id}


def test_enrollment_round_uses_prerequisite_grades_as_tiebreaker(db_session) -> None:
    program = DegreeProgram(name="Computacao", code="CC")
    db_session.add(program)
    db_session.flush()
    prerequisite = Course(
        name="Algoritmos",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=40,
    )
    advanced = Course(
        name="Estruturas de Dados",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=2,
        expected_demand=1,
    )
    high_grade = Student(name="Aluno Nota Alta", degree_program_id=program.id, current_semester=2)
    low_grade = Student(name="Aluno Nota Baixa", degree_program_id=program.id, current_semester=2)
    db_session.add_all([prerequisite, advanced, high_grade, low_grade])
    db_session.flush()
    db_session.add(
        CourseRestriction(
            course_id=advanced.id,
            required_course_id=prerequisite.id,
            kind=CourseRestrictionKind.prerequisite,
            strength=ConstraintStrength.hard,
            minimum_grade=6,
        )
    )
    db_session.add_all(
        [
            StudentCourseHistory(
                student_id=high_grade.id,
                course_id=prerequisite.id,
                status=StudentCourseStatus.completed,
                semester="2026/1",
                grade=9,
            ),
            StudentCourseHistory(
                student_id=low_grade.id,
                course_id=prerequisite.id,
                status=StudentCourseStatus.completed,
                semester="2026/1",
                grade=6,
            ),
            StudentCourseRequest(
                student_id=high_grade.id,
                course_id=advanced.id,
                target_semester="2026/2",
                alternative_group="ed",
                preference_order=1,
                priority=3,
            ),
            StudentCourseRequest(
                student_id=low_grade.id,
                course_id=advanced.id,
                target_semester="2026/2",
                alternative_group="ed",
                preference_order=1,
                priority=3,
            ),
        ]
    )
    db_session.commit()

    run_enrollment_round(db_session, "2026/2")
    enrolled = (
        db_session.query(StudentEnrollment)
        .filter(StudentEnrollment.status == "enrolled")
        .one()
    )

    assert enrolled.student_id == high_grade.id
    assert enrolled.score_breakdown["dependency_grade_average"] == 9


def test_enrollment_uses_solver_planned_capacity_instead_of_full_room_capacity(db_session) -> None:
    program = DegreeProgram(name="Engenharia", code="ENG")
    course = Course(
        name="Calculo A",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=80,
    )
    professor = Professor(name="Docente")
    room = Room(name="Auditorio", capacity=200, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    run = OptimizationRun(
        metrics={
            "planned_sections": [
                {
                    "db_course_id": "pending",
                    "section_index": 0,
                    "planned_students": 52,
                }
            ]
        }
    )
    db_session.add_all([program, course, professor, room, slot, run])
    db_session.flush()
    run.metrics = {
        "planned_sections": [
            {
                "db_course_id": course.id,
                "section_index": 0,
                "planned_students": 52,
            }
        ]
    }
    db_session.add(
        Assignment(
            run_id=run.id,
            course_id=course.id,
            professor_id=professor.id,
            room_id=room.id,
            time_slot_id=slot.id,
            session_index=0,
        )
    )
    students = [
        Student(name=f"Aluno {index}", degree_program_id=program.id, current_semester=2)
        for index in range(60)
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

    summary = run_enrollment_round(db_session, "2026/2", run_id=run.id)

    assert summary["capacity_by_course"][course.id] == 52
    assert summary["enrolled"] == 52
    assert summary["waitlisted"] == 8


def test_enrollment_shares_capacity_between_equivalent_course_contexts(db_session) -> None:
    campus = Campus(name="Campus Porto")
    production = DegreeProgram(name="Engenharia de Producao", code="EP")
    civil = DegreeProgram(name="Engenharia Civil", code="EC")
    db_session.add_all([campus, production, civil])
    db_session.flush()
    production.campus_id = campus.id
    civil.campus_id = campus.id
    production_calculus = Course(
        name="Calculo A Producao",
        campus_id=campus.id,
        degree_program_id=production.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=80,
        context_key="calculo-a",
        shareable=True,
    )
    civil_calculus = Course(
        name="Calculo A Civil",
        campus_id=campus.id,
        degree_program_id=civil.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=80,
        context_key="calculo-a",
        shareable=True,
    )
    professor = Professor(name="Docente")
    room = Room(name="Sala", campus_id=campus.id, capacity=50, kind=RoomKind.lecture)
    slot = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    run = OptimizationRun()
    db_session.add_all([production_calculus, civil_calculus, professor, room, slot, run])
    db_session.flush()
    db_session.add(
        Assignment(
            run_id=run.id,
            course_id=production_calculus.id,
            professor_id=professor.id,
            room_id=room.id,
            time_slot_id=slot.id,
            session_index=0,
        )
    )
    students = [
        Student(name=f"Aluno {index}", degree_program_id=production.id, current_semester=2)
        for index in range(60)
    ]
    db_session.add_all(students)
    db_session.flush()
    db_session.add_all(
        [
            StudentCourseRequest(
                student_id=student.id,
                course_id=production_calculus.id if index < 30 else civil_calculus.id,
                target_semester="2026/2",
                priority=5,
            )
            for index, student in enumerate(students)
        ]
    )
    db_session.commit()

    summary = run_enrollment_round(db_session, "2026/2", run_id=run.id)

    assert summary["capacity_by_course"][production_calculus.id] == 50
    assert summary["capacity_by_course"][civil_calculus.id] == 50
    assert summary["enrolled"] == 50
    assert summary["waitlisted"] == 10


def test_enrollment_blocks_when_any_hard_prerequisite_is_missing(db_session) -> None:
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
        expected_demand=30,
    )
    calculus = Course(
        name="Calculo A",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=30,
    )
    operations_research = Course(
        name="Pesquisa Operacional",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=3,
        expected_demand=2,
    )
    complete_student = Student(
        name="Aluno com prerequisitos",
        degree_program_id=program.id,
        current_semester=3,
        registration_number="2026001",
    )
    missing_student = Student(
        name="Aluno sem calculo",
        degree_program_id=program.id,
        current_semester=3,
        registration_number="2026002",
    )
    db_session.add_all(
        [algorithms, calculus, operations_research, complete_student, missing_student]
    )
    db_session.flush()
    db_session.add_all(
        [
            CourseRestriction(
                course_id=operations_research.id,
                required_course_id=algorithms.id,
                kind=CourseRestrictionKind.prerequisite,
                strength=ConstraintStrength.hard,
                minimum_grade=6,
            ),
            CourseRestriction(
                course_id=operations_research.id,
                required_course_id=calculus.id,
                kind=CourseRestrictionKind.prerequisite,
                strength=ConstraintStrength.hard,
                minimum_grade=6,
            ),
            StudentCourseHistory(
                student_id=complete_student.id,
                course_id=algorithms.id,
                status=StudentCourseStatus.completed,
                semester="2026/1",
                grade=8,
            ),
            StudentCourseHistory(
                student_id=complete_student.id,
                course_id=calculus.id,
                status=StudentCourseStatus.completed,
                semester="2026/1",
                grade=7,
            ),
            StudentCourseHistory(
                student_id=missing_student.id,
                course_id=algorithms.id,
                status=StudentCourseStatus.completed,
                semester="2026/1",
                grade=9,
            ),
            StudentCourseRequest(
                student_id=complete_student.id,
                course_id=operations_research.id,
                target_semester="2026/2",
                priority=5,
            ),
            StudentCourseRequest(
                student_id=missing_student.id,
                course_id=operations_research.id,
                target_semester="2026/2",
                priority=5,
            ),
        ]
    )
    db_session.commit()

    summary = run_enrollment_round(db_session, "2026/2")
    statuses = {
        enrollment.student_id: enrollment.status
        for enrollment in db_session.query(StudentEnrollment).all()
    }

    assert summary["enrolled"] == 1
    assert summary["blocked"] == 1
    assert statuses[complete_student.id] == "enrolled"
    assert statuses[missing_student.id] == "blocked"


def test_solver_selected_alternatives_drive_automatic_enrollment(db_session) -> None:
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
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=80,
        context_key="calculo-a",
        shareable=True,
    )
    civil_calculus = Course(
        name="Calculo A Civil",
        campus_id=campus.id,
        degree_program_id=civil.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=1,
        expected_demand=80,
        context_key="calculo-a",
        shareable=True,
    )
    statistics = Course(
        name="Estatistica",
        campus_id=campus.id,
        degree_program_id=production.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=2,
        expected_demand=40,
        context_key="estatistica-engenharia",
        shareable=True,
    )
    calculus_professor = Professor(name="Docente Calculo")
    statistics_professor = Professor(name="Docente Estatistica")
    room = Room(name="Sala 50", campus_id=campus.id, capacity=50, kind=RoomKind.lecture)
    morning = TimeSlot(day=0, start_minute=480, end_minute=600, label="Seg 08-10")
    afternoon = TimeSlot(day=0, start_minute=600, end_minute=720, label="Seg 10-12")
    run = OptimizationRun(
        semester="2026/2",
        profile="fast",
        parameters={
            "student_demand_only": True,
            "auto_enrollment": True,
            "attempts": 12,
            "local_steps": 4,
        },
    )
    db_session.add_all(
        [
            production_calculus,
            civil_calculus,
            statistics,
            calculus_professor,
            statistics_professor,
            room,
            morning,
            afternoon,
            run,
        ]
    )
    db_session.flush()
    db_session.add_all(
        [
            ProfessorContract(
                professor_id=calculus_professor.id,
                min_hours=0,
                max_hours=4,
            ),
            ProfessorContract(
                professor_id=statistics_professor.id,
                min_hours=0,
                max_hours=4,
            ),
            ProfessorQualification(
                professor_id=calculus_professor.id,
                course_id=production_calculus.id,
            ),
            ProfessorQualification(
                professor_id=statistics_professor.id,
                course_id=statistics.id,
            ),
        ]
    )

    students = [
        Student(
            name=f"Aluno EP {index:02d}",
            degree_program_id=production.id,
            current_semester=2,
            registration_number=f"EP{index:03d}",
        )
        for index in range(53)
    ]
    db_session.add_all(students)
    db_session.flush()
    for index, student in enumerate(students):
        if index < 50:
            db_session.add(
                StudentCourseRequest(
                    student_id=student.id,
                    course_id=production_calculus.id,
                    target_semester="2026/2",
                    priority=5,
                    alternative_group=f"calculo-{index}",
                )
            )
        elif index < 52:
            group = f"reoferta-{index}"
            db_session.add_all(
                [
                    StudentCourseRequest(
                        student_id=student.id,
                        course_id=civil_calculus.id,
                        target_semester="2026/2",
                        priority=5,
                        preference_order=1,
                        alternative_group=group,
                    ),
                    StudentCourseRequest(
                        student_id=student.id,
                        course_id=statistics.id,
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
                    course_id=statistics.id,
                    target_semester="2026/2",
                    priority=5,
                    alternative_group="estatistica-final",
                )
            )
    db_session.commit()

    result = run_optimization(db_session, run)
    _maybe_run_automatic_enrollment(db_session, result)
    db_session.refresh(result)

    enrollments = db_session.query(StudentEnrollment).all()
    enrolled_by_course: dict[str, int] = {}
    superseded_reasons: list[str] = []
    for enrollment in enrollments:
        if enrollment.status == "enrolled":
            enrolled_by_course[enrollment.course_id] = enrolled_by_course.get(enrollment.course_id, 0) + 1
        if enrollment.status == "superseded":
            superseded_reasons.append(enrollment.reason or "")

    assert result.status == RunStatus.feasible
    assert result.metrics["hard_conflicts"] == 0
    assert result.metrics["student_demand_plan"]["alternative_assignments"] == 2
    assert result.metrics["enrollment_round"]["enrolled"] == 53
    assert result.metrics["enrollment_round"]["waitlisted"] == 0
    assert result.metrics["enrollment_round"]["solver_planned_allocations"] == 53
    assert enrolled_by_course[production_calculus.id] == 50
    assert enrolled_by_course[statistics.id] == 3
    assert superseded_reasons == [
        "Opcao anterior substituida pela escolha otimizada do solver",
        "Opcao anterior substituida pela escolha otimizada do solver",
    ]


def test_enrollment_allocates_whole_complex_branch_and_checks_requested_time(
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
    algebra = Course(
        name="Algebra Linear",
        degree_program_id=program.id,
        workload_hours=2,
        theoretical_hours=2,
        kind=CourseKind.mandatory,
        recommended_semester=2,
        expected_demand=20,
    )
    geometry = Course(
        name="Geometria Analitica",
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
    student = Student(name="Aluno complexo", degree_program_id=program.id, current_semester=2)
    professor = Professor(name="Docente")
    room = Room(name="Sala", capacity=30, kind=RoomKind.lecture)
    monday = TimeSlot(day=0, start_minute=19 * 60, end_minute=21 * 60, label="Seg 19-21")
    tuesday = TimeSlot(day=1, start_minute=8 * 60, end_minute=10 * 60, label="Ter 08-10")
    wednesday = TimeSlot(day=2, start_minute=8 * 60, end_minute=10 * 60, label="Qua 08-10")
    friday = TimeSlot(day=4, start_minute=8 * 60, end_minute=10 * 60, label="Sex 08-10")
    run = OptimizationRun(
        metrics={
            "student_demand_plan": {"selected_request_ids": []},
            "planned_sections": [],
        }
    )
    db_session.add_all(
        [
            calculus,
            algebra,
            geometry,
            physics,
            student,
            professor,
            room,
            monday,
            tuesday,
            wednesday,
            friday,
            run,
        ]
    )
    db_session.flush()
    branch_one = StudentCourseRequest(
        student_id=student.id,
        course_id=calculus.id,
        target_semester="2026/2",
        priority=5,
        preference_order=1,
        alternative_group="trajetoria",
        desired_day=0,
        desired_start_minute=19 * 60,
        desired_end_minute=21 * 60,
    )
    branch_two = [
        StudentCourseRequest(
            student_id=student.id,
            course_id=algebra.id,
            target_semester="2026/2",
            priority=4,
            preference_order=2,
            alternative_group="trajetoria",
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
            alternative_group="trajetoria",
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
            alternative_group="trajetoria",
            desired_day=4,
            desired_start_minute=8 * 60,
            desired_end_minute=10 * 60,
        ),
    ]
    db_session.add(branch_one)
    db_session.add_all(branch_two)
    db_session.flush()
    run.metrics = {
        "student_demand_plan": {
            "selected_request_ids": [request.id for request in branch_two],
        },
        "planned_sections": [
            {"db_course_id": algebra.id, "section_index": 0, "planned_students": 1},
            {"db_course_id": geometry.id, "section_index": 0, "planned_students": 1},
            {"db_course_id": physics.id, "section_index": 0, "planned_students": 1},
        ],
    }
    db_session.add_all(
        [
            Assignment(
                run_id=run.id,
                course_id=calculus.id,
                professor_id=professor.id,
                room_id=room.id,
                time_slot_id=wednesday.id,
            ),
            Assignment(
                run_id=run.id,
                course_id=algebra.id,
                professor_id=professor.id,
                room_id=room.id,
                time_slot_id=tuesday.id,
            ),
            Assignment(
                run_id=run.id,
                course_id=geometry.id,
                professor_id=professor.id,
                room_id=room.id,
                time_slot_id=wednesday.id,
            ),
            Assignment(
                run_id=run.id,
                course_id=physics.id,
                professor_id=professor.id,
                room_id=room.id,
                time_slot_id=friday.id,
            ),
        ]
    )
    db_session.commit()

    summary = run_enrollment_round(db_session, "2026/2", run_id=run.id)
    enrollments = db_session.query(StudentEnrollment).all()
    enrolled_course_ids = {
        enrollment.course_id for enrollment in enrollments if enrollment.status == "enrolled"
    }
    superseded_course_ids = {
        enrollment.course_id for enrollment in enrollments if enrollment.status == "superseded"
    }

    assert summary["enrolled"] == 3
    assert summary["superseded"] == 1
    assert summary["solver_planned_allocations"] == 3
    assert enrolled_course_ids == {algebra.id, geometry.id, physics.id}
    assert superseded_course_ids == {calculus.id}
