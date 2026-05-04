from app.models.entities import (
    ConstraintStrength,
    Course,
    CourseKind,
    CourseRestriction,
    CourseRestrictionKind,
    DegreeProgram,
    Student,
    StudentCourseHistory,
    StudentCourseRequest,
    StudentCourseStatus,
    StudentEnrollment,
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
