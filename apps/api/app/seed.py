from __future__ import annotations

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.entities import (
    AvailabilityKind,
    Campus,
    ConstraintStrength,
    Course,
    CourseKind,
    CourseRestriction,
    CourseRestrictionKind,
    DegreeProgram,
    Professor,
    ProfessorAvailability,
    ProfessorContract,
    ProfessorCoursePreference,
    ProfessorQualification,
    Room,
    RoomKind,
    Student,
    StudentCourseHistory,
    StudentCourseRequest,
    StudentCourseStatus,
    TimeSlot,
)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Course).count() > 0:
            print("Seed skipped: data already exists.")
            return

        campus_anglo = Campus(name="Campus Anglo", city="Pelotas")
        campus_capao = Campus(name="Campus Capao do Leao", city="Capao do Leao")
        db.add_all([campus_anglo, campus_capao])
        db.flush()

        programs = [
            DegreeProgram(
                name="Engenharia de Producao",
                code="EP",
                department="Centro de Engenharias",
                campus_id=campus_anglo.id,
                schedule_start_minute=8 * 60,
                schedule_end_minute=18 * 60,
            ),
            DegreeProgram(
                name="Engenharia Civil",
                code="EC",
                department="Centro de Engenharias",
                campus_id=campus_anglo.id,
                schedule_start_minute=8 * 60,
                schedule_end_minute=12 * 60,
            ),
            DegreeProgram(
                name="Ciencia da Computacao",
                code="CC",
                department="Computacao",
                campus_id=campus_capao.id,
                schedule_start_minute=14 * 60,
                schedule_end_minute=18 * 60,
            ),
        ]
        db.add_all(programs)
        db.flush()
        program_by_code = {program.code: program for program in programs}

        courses = [
            Course(
                code="MAT-CALC-A-EP",
                name="Calculo A",
                campus_id=campus_anglo.id,
                degree_program_id=program_by_code["EP"].id,
                workload_hours=4,
                theoretical_hours=4,
                practical_hours=0,
                kind=CourseKind.mandatory,
                recommended_semester=1,
                expected_demand=45,
                criticality=5,
                context_key="calculo-a:engenharias",
                shareable=True,
            ),
            Course(
                code="MAT-CALC-A-EC",
                name="Calculo A",
                campus_id=campus_anglo.id,
                degree_program_id=program_by_code["EC"].id,
                workload_hours=4,
                theoretical_hours=4,
                practical_hours=0,
                kind=CourseKind.mandatory,
                recommended_semester=1,
                expected_demand=50,
                criticality=5,
                context_key="calculo-a:engenharias",
                shareable=True,
            ),
            Course(
                code="COMP-ALGPROG",
                name="Algoritmos e Programacao",
                campus_id=campus_capao.id,
                degree_program_id=program_by_code["CC"].id,
                workload_hours=4,
                theoretical_hours=2,
                practical_hours=2,
                kind=CourseKind.mandatory,
                recommended_semester=1,
                expected_demand=70,
                requires_lab=True,
                criticality=5,
                context_key="programacao-introdutoria:computacao",
            ),
            Course(
                code="MAT-ALG-LIN",
                name="Algebra Linear",
                campus_id=campus_capao.id,
                degree_program_id=program_by_code["CC"].id,
                workload_hours=4,
                theoretical_hours=4,
                practical_hours=0,
                kind=CourseKind.mandatory,
                recommended_semester=2,
                expected_demand=55,
                criticality=4,
                context_key="algebra-linear:exatas",
            ),
            Course(
                code="COMP-ED",
                name="Estruturas de Dados",
                campus_id=campus_capao.id,
                degree_program_id=program_by_code["CC"].id,
                workload_hours=4,
                theoretical_hours=2,
                practical_hours=2,
                kind=CourseKind.mandatory,
                recommended_semester=2,
                expected_demand=62,
                requires_lab=True,
                criticality=5,
                context_key="estruturas-de-dados:computacao",
            ),
            Course(
                code="COMP-BD",
                name="Banco de Dados",
                campus_id=campus_capao.id,
                degree_program_id=program_by_code["CC"].id,
                workload_hours=4,
                theoretical_hours=2,
                practical_hours=2,
                kind=CourseKind.mandatory,
                recommended_semester=3,
                expected_demand=48,
                requires_lab=True,
                criticality=4,
                context_key="banco-de-dados:computacao",
            ),
            Course(
                code="COMP-PO",
                name="Pesquisa Operacional",
                campus_id=campus_capao.id,
                degree_program_id=program_by_code["CC"].id,
                workload_hours=4,
                theoretical_hours=4,
                practical_hours=0,
                kind=CourseKind.mandatory,
                recommended_semester=5,
                expected_demand=38,
                criticality=5,
                context_key="pesquisa-operacional:exatas",
            ),
            Course(
                code="COMP-ES",
                name="Engenharia de Software",
                campus_id=campus_capao.id,
                degree_program_id=program_by_code["CC"].id,
                workload_hours=4,
                theoretical_hours=3,
                practical_hours=1,
                kind=CourseKind.mandatory,
                recommended_semester=4,
                expected_demand=45,
                criticality=4,
                context_key="engenharia-de-software:computacao",
            ),
            Course(
                code="COMP-IA-TOP",
                name="Topicos em IA Aplicada",
                campus_id=campus_capao.id,
                degree_program_id=program_by_code["CC"].id,
                workload_hours=2,
                theoretical_hours=1,
                practical_hours=1,
                kind=CourseKind.elective,
                recommended_semester=6,
                expected_demand=32,
                requires_lab=True,
                criticality=3,
                context_key="ia-aplicada:computacao",
            ),
            Course(
                code="COMP-SD",
                name="Sistemas Distribuidos",
                campus_id=campus_capao.id,
                degree_program_id=program_by_code["CC"].id,
                workload_hours=4,
                theoretical_hours=3,
                practical_hours=1,
                kind=CourseKind.mandatory,
                recommended_semester=6,
                expected_demand=36,
                criticality=4,
                context_key="sistemas-distribuidos:computacao",
            ),
        ]
        db.add_all(courses)
        db.flush()

        professors = [
            Professor(name="Ana Ribeiro", email="ana.ribeiro@ufpel.edu.br", department="Computacao"),
            Professor(name="Bruno Lima", email="bruno.lima@ufpel.edu.br", department="Computacao"),
            Professor(name="Carla Mendes", email="carla.mendes@ufpel.edu.br", department="Computacao"),
            Professor(name="Diego Souza", email="diego.souza@ufpel.edu.br", department="Matematica"),
            Professor(name="Elisa Torres", email="elisa.torres@ufpel.edu.br", department="Computacao"),
            Professor(name="Fabio Nunes", email="fabio.nunes@ufpel.edu.br", department="Computacao"),
        ]
        db.add_all(professors)
        db.flush()

        for professor in professors:
            db.add(ProfessorContract(professor_id=professor.id, min_hours=2, max_hours=10, regime="DE"))

        borrowed_professor = Professor(
            name="Gustavo Pires",
            email="gustavo.pires@externo.edu.br",
            department="Computacao",
        )
        db.add(borrowed_professor)
        db.flush()
        db.add(
            ProfessorContract(
                professor_id=borrowed_professor.id,
                min_hours=0,
                max_hours=4,
                regime="emprestado",
                semester="2026/2",
                is_borrowed=True,
                borrowed_from_department="Departamento de Estatistica",
                loan_notes="Disponivel apenas no semestre 2026/2 em horario reduzido.",
            )
        )

        course_by_code = {course.code: course for course in courses if course.code}
        all_professors = professors + [borrowed_professor]
        professor_by_name = {professor.name: professor for professor in all_professors}
        qualifications = {
            "Ana Ribeiro": ["COMP-ALGPROG", "COMP-ED", "COMP-IA-TOP"],
            "Bruno Lima": ["COMP-BD", "COMP-SD", "COMP-ES"],
            "Carla Mendes": ["COMP-ES", "COMP-PO", "COMP-IA-TOP"],
            "Diego Souza": ["MAT-CALC-A-EP", "MAT-ALG-LIN", "COMP-PO"],
            "Elisa Torres": ["COMP-ED", "COMP-BD", "COMP-SD"],
            "Fabio Nunes": ["MAT-CALC-A-EC", "MAT-ALG-LIN", "COMP-ALGPROG"],
            "Gustavo Pires": ["COMP-IA-TOP", "COMP-PO"],
        }
        for professor_name, course_codes in qualifications.items():
            professor = professor_by_name[professor_name]
            for course_code in course_codes:
                db.add(
                    ProfessorQualification(
                        professor_id=professor.id,
                        course_id=course_by_code[course_code].id,
                        strength=ConstraintStrength.hard,
                    )
                )

        preferences = {
            "Ana Ribeiro": {"COMP-ALGPROG": 5, "COMP-IA-TOP": 4},
            "Bruno Lima": {"COMP-BD": 5, "COMP-SD": 3},
            "Carla Mendes": {"COMP-PO": 4, "COMP-ES": 5},
            "Diego Souza": {"MAT-CALC-A-EP": 4, "MAT-ALG-LIN": 5},
            "Elisa Torres": {"COMP-ED": 4, "COMP-BD": 3},
            "Fabio Nunes": {"MAT-CALC-A-EC": 3, "COMP-ALGPROG": 2},
            "Gustavo Pires": {"COMP-IA-TOP": 5, "COMP-PO": 2},
        }
        for professor_name, course_scores in preferences.items():
            professor = professor_by_name[professor_name]
            for course_code, score in course_scores.items():
                db.add(
                    ProfessorCoursePreference(
                        professor_id=professor.id,
                        course_id=course_by_code[course_code].id,
                        preference=score,
                        strength=ConstraintStrength.soft,
                    )
                )

        db.add_all(
            [
                CourseRestriction(
                    course_id=course_by_code["COMP-ED"].id,
                    required_course_id=course_by_code["COMP-ALGPROG"].id,
                    kind=CourseRestrictionKind.prerequisite,
                    strength=ConstraintStrength.hard,
                    minimum_grade=6,
                ),
                CourseRestriction(
                    course_id=course_by_code["COMP-BD"].id,
                    required_course_id=course_by_code["COMP-ED"].id,
                    kind=CourseRestrictionKind.prerequisite,
                    strength=ConstraintStrength.hard,
                    minimum_grade=6,
                ),
            ]
        )

        demo_student = Student(
            name="Aluno Demo",
            email="aluno.demo@ufpel.edu.br",
            registration_number="20260001",
            degree_program_id=program_by_code["CC"].id,
            current_semester=2,
        )
        db.add(demo_student)
        db.flush()
        db.add(
            StudentCourseHistory(
                student_id=demo_student.id,
                course_id=course_by_code["COMP-ALGPROG"].id,
                status=StudentCourseStatus.completed,
                semester="2026/1",
                grade=8.5,
            )
        )
        for course_code in ["COMP-ED", "MAT-ALG-LIN"]:
            db.add(
                StudentCourseRequest(
                    student_id=demo_student.id,
                    course_id=course_by_code[course_code].id,
                    target_semester="2026/2",
                    priority=4,
                )
            )

        for professor in professors:
            db.add_all(
                [
                    ProfessorAvailability(
                        professor_id=professor.id,
                        day=0,
                        start_minute=8 * 60,
                        end_minute=18 * 60,
                        kind=AvailabilityKind.available,
                        strength=ConstraintStrength.hard,
                    ),
                    ProfessorAvailability(
                        professor_id=professor.id,
                        day=2,
                        start_minute=8 * 60,
                        end_minute=18 * 60,
                        kind=AvailabilityKind.available,
                        strength=ConstraintStrength.hard,
                    ),
                    ProfessorAvailability(
                        professor_id=professor.id,
                        day=4,
                        start_minute=8 * 60,
                        end_minute=18 * 60,
                        kind=AvailabilityKind.preferred,
                        strength=ConstraintStrength.soft,
                    ),
                ]
            )

        db.add(
            ProfessorAvailability(
                professor_id=borrowed_professor.id,
                day=1,
                start_minute=8 * 60,
                end_minute=12 * 60,
                kind=AvailabilityKind.available,
                strength=ConstraintStrength.hard,
                source="coordinator",
            )
        )

        rooms = [
            Room(name="Auditório CC", campus_id=campus_capao.id, capacity=100, kind=RoomKind.lecture),
            Room(name="Sala 201", campus_id=campus_anglo.id, capacity=60, kind=RoomKind.lecture),
            Room(name="Sala 305", campus_id=campus_anglo.id, capacity=45, kind=RoomKind.lecture),
            Room(name="Lab 1", campus_id=campus_capao.id, capacity=72, kind=RoomKind.lab),
            Room(name="Lab 2", campus_id=campus_capao.id, capacity=40, kind=RoomKind.lab),
        ]
        db.add_all(rooms)

        slots = []
        labels = [(8 * 60, 10 * 60), (10 * 60, 12 * 60), (14 * 60, 16 * 60), (16 * 60, 18 * 60)]
        for day in range(5):
            for start, end in labels:
                slots.append(TimeSlot(day=day, start_minute=start, end_minute=end, label=format_slot(day, start, end)))
        db.add_all(slots)
        db.commit()
        print("Seed completed.")
    finally:
        db.close()


def format_slot(day: int, start: int, end: int) -> str:
    days = ["Seg", "Ter", "Qua", "Qui", "Sex"]
    return f"{days[day]} {start // 60:02d}:{start % 60:02d}-{end // 60:02d}:{end % 60:02d}"


if __name__ == "__main__":
    main()
