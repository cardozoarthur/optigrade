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
    Room,
    RoomKind,
    Student,
    StudentCourseHistory,
    StudentCourseRequest,
    StudentCourseStatus,
    StudentEnrollment,
    TimeSlot,
)
from app.services.enrollment import run_enrollment_round


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
