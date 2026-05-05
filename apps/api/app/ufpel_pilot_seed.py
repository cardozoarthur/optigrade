from __future__ import annotations

import re
from math import ceil
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
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
    Student,
    StudentCourseHistory,
    StudentCourseRequest,
    StudentCourseStatus,
    TimeSlot,
)
from app.services.optimizer import run_optimization
from app.services.student_planning import build_student_suggestions, student_demand_summary

INSTITUTIONAL_BASE = "https://institucional.ufpel.edu.br"
PILOT_SEMESTER = "2026/1"
PILOT_STUDENT_TARGET_SEMESTER = "2026/2"
PILOT_SOURCE = "ufpel_official_2026_1"
PILOT_STUDENT_SOURCE = "ufpel_pilot_student_form"
PILOT_STUDENTS_PER_PROGRAM = 180
MIN_STUDENT_PROFESSOR_RATIO = 10
REGULAR_ROOM_MIN_CAPACITY = 10
REGULAR_ROOM_MAX_CAPACITY = 50
AUDITORIUM_CAPACITY = 200

ENGINEERING_CODES = [
    700,
    6200,
    6300,
    6900,
    6500,
    6700,
    7000,
    5600,
    5200,
    6100,
    6400,
    3910,
]
COMPUTING_CODES = [3900, 3910]
COURSE_CODES = list(dict.fromkeys(ENGINEERING_CODES + COMPUTING_CODES))

DAY_TO_INDEX = {"SEG": 0, "TER": 1, "QUA": 2, "QUI": 3, "SEX": 4, "SAB": 5, "DOM": 6}

LEGAL_NOTES = (
    "Dados importados do Portal Institucional UFPel. Frequencia minima de aprovacao: "
    "75%. Nota media padrao de aprovacao: 7,0. Ingresso por ampla concorrencia e "
    "reservas conforme Lei 12.711/2012. Contratos docentes modelados no piloto com "
    "limite operacional de 40h semanais, alinhado aos regimes da Lei 12.772/2012."
)


@dataclass(frozen=True)
class CoursePage:
    code: int
    name: str
    turn: str
    unit: str
    coordinator: str | None
    source_url: str
    curriculum: dict[str, dict[str, object]]
    offerings: list[dict[str, object]]


def main() -> None:
    db = SessionLocal()
    try:
        pages = [fetch_course_page(code) for code in COURSE_CODES]
        seed_ufpel_pilot(db, pages)
    finally:
        db.close()


def seed_ufpel_pilot(db: Session, pages: list[CoursePage]) -> None:
    campus = upsert_campus(
        db,
        "UFPel - Campus Porto",
        "Pelotas",
    )
    degree_programs = {
        page.code: upsert_degree_program(db, page, campus.id)
        for page in pages
    }

    offering_records: list[tuple[CoursePage, dict[str, object], Course]] = []
    for page in pages:
        program = degree_programs[page.code]
        for offering in page.offerings:
            if not offering["schedule"]:
                continue
            course = upsert_course(db, page, program, campus.id, offering)
            offering_records.append((page, offering, course))

    update_degree_program_windows(db, degree_programs, offering_records)
    seed_time_slots(db, offering_records)
    seed_rooms(db, campus.id, offering_records)
    seed_professors(db, offering_records)
    student_stats = seed_students(db, degree_programs)
    db.commit()

    run = OptimizationRun(
        semester=PILOT_SEMESTER,
        profile="official_ufpel",
        parameters={"source": PILOT_SOURCE, "generated_at": datetime.now(timezone.utc).isoformat()},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    result = run_optimization(db, run)
    if result.metrics.get("hard_conflicts"):
        raise RuntimeError(f"Grade oficial importada com conflitos: {result.metrics}")
    print(
        "UFPel pilot seeded:",
        {
            "degree_programs": len(degree_programs),
            "courses": len(offering_records),
            "students": student_stats["students"],
            "student_history": student_stats["history"],
            "student_requests": student_stats["requests"],
            "assignments": result.metrics.get("assigned_sessions"),
            "hard_conflicts": result.metrics.get("hard_conflicts"),
        },
    )


def fetch_course_page(code: int) -> CoursePage:
    source_url = f"{INSTITUTIONAL_BASE}/cursos/cod/{code}"
    soup = BeautifulSoup(fetch_url(source_url), "html.parser")
    name = clean((soup.title.string or "").replace("| UFPel", "")) if soup.title else str(code)
    turn = ficha_value(soup, "Turno") or "INTEGRAL"
    unit = ficha_value(soup, "Unidade") or "UFPel"
    coordinator = ficha_value(soup, "Coordenador")
    curriculum = parse_curriculum(soup)
    offerings = parse_offerings(soup)
    return CoursePage(code, name, turn, unit, coordinator, source_url, curriculum, offerings)


def fetch_url(url: str) -> str:
    request = Request(url, headers={"User-Agent": "OptiGradePilot/1.0"})
    with urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", errors="replace")


def ficha_value(soup: BeautifulSoup, label: str) -> str | None:
    node = soup.find(string=lambda value: bool(value and clean(value) == label))
    if not node or not node.parent:
        return None
    value_node = node.parent.find_next_sibling()
    if not value_node:
        return None
    return clean(value_node.get_text(" ", strip=True))


def parse_curriculum(soup: BeautifulSoup) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for accordion in soup.select("#curriculo .accordion"):
        header = accordion.find("h3")
        semester_match = re.search(r"(\d+)º Semestre", header.get_text(" ", strip=True) if header else "")
        if not semester_match:
            continue
        semester = int(semester_match.group(1))
        for tr in accordion.select("table.tabela-dados > tr")[1:]:
            cells = tr.find_all("td", recursive=False)
            if len(cells) < 5:
                continue
            code = clean(cells[0].get_text())
            rows[code] = {
                "semester": semester,
                "name": clean(cells[1].get_text()),
                "kind": clean(cells[2].get_text()),
                "credits": safe_int(clean(cells[3].get_text())),
                "hours": safe_int(clean(cells[4].get_text())),
            }
    return rows


def parse_offerings(soup: BeautifulSoup) -> list[dict[str, object]]:
    period = PILOT_SEMESTER
    period_header = soup.select_one("#turmas > h3")
    if period_header:
        period_match = re.search(r"(\d{4})\s*/\s*(\d)", period_header.get_text(" ", strip=True))
        if period_match:
            period = f"{period_match.group(1)}/{period_match.group(2)}"

    offerings: list[dict[str, object]] = []
    for accordion in soup.select("#turmas .accordion"):
        header = accordion.find("h3")
        semester_match = re.search(r"(\d+)º Semestre", header.get_text(" ", strip=True) if header else "")
        if not semester_match:
            continue
        semester = int(semester_match.group(1))
        table = accordion.find("table", class_="tabela-dados")
        if not table:
            continue
        for tr in table.find_all("tr", recursive=False)[1:]:
            cells = tr.find_all("td", recursive=False)
            if len(cells) < 4:
                continue
            first = cells[0]
            link = first.find("a", href=re.compile("/disciplinas/cod/"))
            if not link:
                continue
            discipline = clean(link.get_text(" ", strip=True))
            discipline_match = re.match(r"([^ ]+)\s*-\s*(.*)", discipline)
            if not discipline_match:
                continue
            schedule_blocks = parse_schedule_blocks(first)
            offerings.append(
                {
                    "semester": semester,
                    "discipline_code": discipline_match.group(1),
                    "name": discipline_match.group(2),
                    "professors": parse_professors(first),
                    "schedule": pair_schedule_blocks(schedule_blocks),
                    "schedule_blocks": schedule_blocks,
                    "class": clean(cells[1].get_text()),
                    "seats": safe_int(clean(cells[2].get_text())) or 1,
                    "enrolled": safe_int(clean(cells[3].get_text())) or 1,
                    "period": period,
                }
            )
    return offerings


def parse_professors(node) -> list[str]:
    professors: list[str] = []
    for span in node.select(".tabela-detalhe-info"):
        text = span.get_text("\n", strip=True)
        for match in re.finditer(r"Professor (?:responsável pela turma|Regente):\s*([^\n]+)", text):
            professor = clean(match.group(1))
            if professor and professor not in professors:
                professors.append(professor)
    return professors


def parse_schedule_blocks(node) -> list[dict[str, int]]:
    table = node.select_one("table.grade-horarios")
    if not table:
        return []
    blocks: list[dict[str, int]] = []
    for cell in table.select("td"):
        last_day: str | None = None
        cell_html = str(cell)
        for match in re.finditer(
            r'grade-horarios-dia">(.*?)</span>\s*([0-9]{2}:[0-9]{2})\s*-\s*([0-9]{2}:[0-9]{2})',
            cell_html,
            re.S,
        ):
            day_label = clean(unescape(match.group(1))) or last_day
            if not day_label:
                continue
            last_day = day_label
            blocks.append(
                {
                    "day": DAY_TO_INDEX[day_label],
                    "start_minute": to_minutes(match.group(2)),
                    "end_minute": to_minutes(match.group(3)),
                }
            )
    return sorted(blocks, key=lambda item: (item["day"], item["start_minute"], item["end_minute"]))


def pair_schedule_blocks(blocks: list[dict[str, int]]) -> list[dict[str, int]]:
    paired: list[dict[str, int]] = []
    by_day: dict[int, list[dict[str, int]]] = {}
    for block in blocks:
        by_day.setdefault(block["day"], []).append(block)
    for day, day_blocks in by_day.items():
        ordered = sorted(day_blocks, key=lambda item: item["start_minute"])
        index = 0
        while index < len(ordered):
            current = ordered[index]
            end = current["end_minute"]
            if index + 1 < len(ordered) and ordered[index + 1]["start_minute"] == end:
                end = ordered[index + 1]["end_minute"]
                index += 1
            paired.append({"day": day, "start_minute": current["start_minute"], "end_minute": end})
            index += 1
    return sorted(paired, key=lambda item: (item["day"], item["start_minute"], item["end_minute"]))


def upsert_campus(db: Session, name: str, city: str) -> Campus:
    campus = db.query(Campus).filter(Campus.name == name).first()
    if not campus:
        campus = Campus(name=name)
        db.add(campus)
    campus.city = city
    db.flush()
    return campus


def upsert_degree_program(db: Session, page: CoursePage, campus_id: str) -> DegreeProgram:
    code = f"UFPEL-{page.code}"
    program = db.query(DegreeProgram).filter(DegreeProgram.code == code).first()
    if not program:
        program = DegreeProgram(name=page.name, code=code)
        db.add(program)
    program.name = page.name
    program.department = page.unit
    program.campus_id = campus_id
    program.legal_notes = LEGAL_NOTES
    program.source_url = page.source_url
    program.required_hours = sum(
        int(item.get("hours") or 0)
        for item in page.curriculum.values()
        if str(item.get("kind", "")).lower().startswith("obrig")
    ) or None
    program.minimum_semesters = 8 if page.code == 3900 else 10
    program.maximum_semesters = 18
    db.flush()
    return program


def upsert_course(
    db: Session,
    page: CoursePage,
    program: DegreeProgram,
    campus_id: str,
    offering: dict[str, object],
) -> Course:
    discipline_code = str(offering["discipline_code"])
    official_class = str(offering["class"])
    code = f"UFPEL-{page.code}-{discipline_code}-{official_class}"
    curriculum_item = page.curriculum.get(discipline_code, {})
    course = (
        db.query(Course)
        .filter(Course.code == code, Course.degree_program_id == program.id)
        .first()
    )
    if not course:
        course = Course(code=code, name=str(offering["name"]))
        db.add(course)
    schedule_blocks = list(offering["schedule_blocks"])
    workload_hours = int(curriculum_item.get("credits") or len(schedule_blocks) or 1)
    course.name = f"{offering['name']} ({official_class})"
    course.campus_id = campus_id
    course.degree_program_id = program.id
    course.workload_hours = max(1, min(20, workload_hours))
    course.theoretical_hours = max(0, min(course.workload_hours, course.workload_hours))
    course.practical_hours = 0
    course.kind = (
        CourseKind.elective
        if "opt" in str(curriculum_item.get("kind", "")).lower()
        else CourseKind.mandatory
    )
    course.recommended_semester = int(offering["semester"])
    course.expected_demand = max(int(offering["seats"]), int(offering["enrolled"]), 1)
    course.requires_lab = str(official_class).upper().startswith("P") or "LABORAT" in str(offering["name"]).upper()
    course.criticality = 5 if course.kind == CourseKind.mandatory and course.recommended_semester <= 2 else 3
    course.context_key = f"ufpel:{discipline_code}:{official_class}".lower()
    course.shareable = True
    course.approval_grade = 7
    course.approval_frequency_percent = 75
    course.source_url = f"{INSTITUTIONAL_BASE}/disciplinas/cod/{discipline_code}"
    course.official_period = str(offering["period"])
    course.official_class = official_class
    course.official_schedule = list(offering["schedule"])
    db.flush()
    return course


def update_degree_program_windows(
    db: Session,
    degree_programs: dict[int, DegreeProgram],
    offering_records: list[tuple[CoursePage, dict[str, object], Course]],
) -> None:
    windows: dict[int, list[tuple[int, int]]] = {code: [] for code in degree_programs}
    for page, offering, _course in offering_records:
        for item in offering["schedule"]:
            windows[page.code].append((int(item["start_minute"]), int(item["end_minute"])))
    for code, program in degree_programs.items():
        if windows[code]:
            program.schedule_start_minute = min(start for start, _end in windows[code])
            program.schedule_end_minute = max(end for _start, end in windows[code])
        else:
            program.schedule_start_minute, program.schedule_end_minute = turn_window(program.name)
    db.flush()


def seed_time_slots(db: Session, offering_records: list[tuple[CoursePage, dict[str, object], Course]]) -> None:
    existing = {
        (slot.day, slot.start_minute, slot.end_minute)
        for slot in db.query(TimeSlot).all()
    }
    windows = sorted(
        {
            (int(item["day"]), int(item["start_minute"]), int(item["end_minute"]))
            for _page, offering, _course in offering_records
            for item in offering["schedule"]
        }
    )
    for day, start, end in windows:
        if (day, start, end) in existing:
            continue
        label = f"{day_label(day)} {format_minutes(start)}-{format_minutes(end)}"
        db.add(TimeSlot(day=day, start_minute=start, end_minute=end, label=label))
        existing.add((day, start, end))
    db.flush()


def seed_rooms(
    db: Session,
    campus_id: str,
    offering_records: list[tuple[CoursePage, dict[str, object], Course]],
) -> None:
    max_parallel = max_parallel_sessions(offering_records)
    max_parallel_labs = max_parallel_sessions(
        [record for record in offering_records if record[2].requires_lab]
    )
    max_parallel_auditoriums = max_parallel_sessions(
        [
            record
            for record in offering_records
            if not record[2].requires_lab and record[2].expected_demand > REGULAR_ROOM_MAX_CAPACITY
        ]
    )
    max_parallel_lab_auditoriums = max_parallel_sessions(
        [
            record
            for record in offering_records
            if record[2].requires_lab and record[2].expected_demand > REGULAR_ROOM_MAX_CAPACITY
        ]
    )
    room_count = max(80, max_parallel + 20)
    lab_count = max(40, max_parallel_labs + 20)
    auditorium_count = max(4, max_parallel_auditoriums + 2)
    lab_auditorium_count = max(2, max_parallel_lab_auditoriums + 1)

    for index in range(1, auditorium_count + 1):
        upsert_seed_room(
            db,
            name=f"UFPel Porto - Auditório piloto {index:03d}",
            campus_id=campus_id,
            kind=RoomKind.lecture,
            capacity=AUDITORIUM_CAPACITY,
        )
    for index in range(1, room_count + 1):
        upsert_seed_room(
            db,
            name=f"UFPel Porto - Sala piloto {index:03d}",
            campus_id=campus_id,
            kind=RoomKind.lecture,
            capacity=regular_room_capacity(index),
        )
    for index in range(1, lab_auditorium_count + 1):
        upsert_seed_room(
            db,
            name=f"UFPel Porto - Auditório técnico piloto {index:03d}",
            campus_id=campus_id,
            kind=RoomKind.lab,
            capacity=AUDITORIUM_CAPACITY,
        )
    for index in range(1, lab_count + 1):
        upsert_seed_room(
            db,
            name=f"UFPel Porto - Laboratório piloto {index:03d}",
            campus_id=campus_id,
            kind=RoomKind.lab,
            capacity=regular_room_capacity(index),
        )
    db.flush()


def upsert_seed_room(
    db: Session,
    *,
    name: str,
    campus_id: str,
    kind: RoomKind,
    capacity: int,
) -> Room:
    room = db.query(Room).filter(Room.name == name).first()
    if not room:
        room = Room(name=name, availability={})
        db.add(room)
    room.campus_id = campus_id
    room.kind = kind
    room.capacity = capacity
    return room


def regular_room_capacity(index: int) -> int:
    span = REGULAR_ROOM_MAX_CAPACITY - REGULAR_ROOM_MIN_CAPACITY
    return REGULAR_ROOM_MIN_CAPACITY + ((index - 1) * 5 % (span + 1))


def seed_professors(
    db: Session,
    offering_records: list[tuple[CoursePage, dict[str, object], Course]],
) -> None:
    professor_windows: dict[str, list[dict[str, int]]] = {}
    professor_courses: dict[str, list[Course]] = {}
    for page, offering, course in offering_records:
        professors = list(offering["professors"]) or [f"Professor a definir - {page.name}"]
        for professor_name in professors:
            professor = upsert_professor(db, professor_name, page.unit)
            professor_courses.setdefault(professor.id, []).append(course)
            for item in offering["schedule"]:
                professor_windows.setdefault(professor.id, []).append(item)

    for professor_id, courses in professor_courses.items():
        for course in courses:
            exists = (
                db.query(ProfessorQualification)
                .filter(
                    ProfessorQualification.professor_id == professor_id,
                    ProfessorQualification.course_id == course.id,
                )
                .first()
            )
            if not exists:
                db.add(ProfessorQualification(professor_id=professor_id, course_id=course.id))

    for professor_id, windows in professor_windows.items():
        db.query(ProfessorAvailability).filter(
            ProfessorAvailability.professor_id == professor_id,
            ProfessorAvailability.source == PILOT_SOURCE,
        ).delete()
        for item in unique_windows(windows):
            db.add(
                ProfessorAvailability(
                    professor_id=professor_id,
                    day=int(item["day"]),
                    start_minute=int(item["start_minute"]),
                    end_minute=int(item["end_minute"]),
                    kind=AvailabilityKind.available,
                    strength=ConstraintStrength.hard,
                    source=PILOT_SOURCE,
                )
            )
    db.flush()


def upsert_professor(db: Session, name: str, department: str) -> Professor:
    professor = db.query(Professor).filter(Professor.name == name).first()
    if not professor:
        professor = Professor(name=name)
        db.add(professor)
        db.flush()
    professor.department = department or "UFPel"
    contract = (
        professor.contract
        or db.query(ProfessorContract).filter(ProfessorContract.professor_id == professor.id).first()
    )
    if not contract:
        contract = ProfessorContract(professor_id=professor.id, min_hours=0, max_hours=40)
        professor.contract = contract
        db.add(contract)
    contract.min_hours = 0
    contract.max_hours = 40
    contract.regime = "DE/40h"
    contract.semester = None
    contract.is_borrowed = False
    contract.legal_notes = LEGAL_NOTES
    db.flush()
    return professor


def seed_students(db: Session, degree_programs: dict[int, DegreeProgram]) -> dict[str, int]:
    students_per_program = target_pilot_students_per_program(db, degree_programs)
    stats = {
        "students": 0,
        "history": 0,
        "requests": 0,
        "students_per_program": students_per_program,
    }
    for program_code, program in sorted(degree_programs.items()):
        program_courses = official_courses_for_program(db, program.id)
        if not program_courses:
            continue
        max_semester = max(course.recommended_semester for course in program_courses)
        for index in range(1, students_per_program + 1):
            current_semester = pilot_current_semester(index, max_semester, program)
            student = upsert_pilot_student(db, program_code, program, index, current_semester)
            completed_courses, failed_courses = pilot_student_history_courses(
                program_courses,
                current_semester,
                index,
            )
            reset_pilot_student_history(db, student)
            stats["history"] += seed_student_history(
                db,
                student,
                completed_courses,
                failed_courses,
            )
            db.flush()
            stats["requests"] += seed_student_requests(db, student)
            stats["students"] += 1

    summary = student_demand_summary(db, PILOT_STUDENT_TARGET_SEMESTER)
    if stats["students"] and summary.eligible_requests == 0:
        raise RuntimeError("Seed de alunos UFPel nao gerou demandas elegiveis")
    db.flush()
    return stats


def target_pilot_students_per_program(
    db: Session,
    degree_programs: dict[int, DegreeProgram],
) -> int:
    program_count = max(1, len(degree_programs))
    minimum_total = db.query(Professor).count() * MIN_STUDENT_PROFESSOR_RATIO
    return max(PILOT_STUDENTS_PER_PROGRAM, ceil(minimum_total / program_count))


def official_courses_for_program(db: Session, degree_program_id: str) -> list[Course]:
    return (
        db.query(Course)
        .filter(
            Course.degree_program_id == degree_program_id,
            Course.source_url.like(f"{INSTITUTIONAL_BASE}/%"),
        )
        .order_by(Course.recommended_semester, Course.kind, Course.name, Course.official_class)
        .all()
    )


def pilot_current_semester(
    student_index: int,
    max_semester: int,
    program: DegreeProgram,
) -> int:
    planned_semesters = program.minimum_semesters or max_semester or 10
    upper_bound = max(1, min(max_semester or planned_semesters, planned_semesters, 10))
    return 1 + ((student_index - 1) % upper_bound)


def upsert_pilot_student(
    db: Session,
    program_code: int,
    program: DegreeProgram,
    student_index: int,
    current_semester: int,
) -> Student:
    registration = f"PILOTO-UFPEL-{program_code}-{student_index:03d}"
    email = f"aluno.piloto.ufpel.{program_code}.{student_index:03d}@optigrade.local"
    student = (
        db.query(Student)
        .filter(or_(Student.registration_number == registration, Student.email == email))
        .first()
    )
    if not student:
        student = Student(
            name=f"Aluno Piloto {program.code}-{student_index:02d}",
            registration_number=registration,
            email=email,
            degree_program_id=program.id,
            current_semester=current_semester,
        )
        db.add(student)
    student.name = f"Aluno Piloto {program.code}-{student_index:02d}"
    student.registration_number = registration
    student.email = email
    student.degree_program_id = program.id
    student.current_semester = current_semester
    db.flush()
    return student


def pilot_student_history_courses(
    courses: list[Course],
    current_semester: int,
    student_index: int,
) -> tuple[list[Course], list[Course]]:
    completed = [
        course
        for course in courses
        if course.kind == CourseKind.mandatory and course.recommended_semester < current_semester
    ]
    if current_semester >= 6:
        completed.extend([
            course
            for course in courses
            if course.kind == CourseKind.elective and course.recommended_semester < current_semester
        ][:2])
    failed: list[Course] = []
    if student_index % 4 == 0 and completed:
        backlog = [
            course
            for course in completed
            if course.recommended_semester == max(1, current_semester - 1)
        ] or completed[-3:]
        failed_course = backlog[(student_index // 4) % len(backlog)]
        completed = [course for course in completed if course.id != failed_course.id]
        failed.append(failed_course)
    return completed, failed


def reset_pilot_student_history(db: Session, student: Student) -> None:
    db.query(StudentCourseHistory).filter(StudentCourseHistory.student_id == student.id).delete()
    db.query(StudentCourseRequest).filter(
        StudentCourseRequest.student_id == student.id,
        StudentCourseRequest.target_semester == PILOT_STUDENT_TARGET_SEMESTER,
        StudentCourseRequest.source == PILOT_STUDENT_SOURCE,
    ).delete()


def seed_student_history(
    db: Session,
    student: Student,
    completed_courses: list[Course],
    failed_courses: list[Course],
) -> int:
    count = 0
    for course in completed_courses:
        db.add(
            StudentCourseHistory(
                student_id=student.id,
                course_id=course.id,
                status=StudentCourseStatus.completed,
                semester=history_semester_label(
                    student.current_semester,
                    course.recommended_semester,
                ),
                grade=pilot_grade(student.current_semester, course.recommended_semester),
            )
        )
        count += 1
    for course in failed_courses:
        db.add(
            StudentCourseHistory(
                student_id=student.id,
                course_id=course.id,
                status=StudentCourseStatus.failed,
                semester=history_semester_label(student.current_semester, course.recommended_semester),
                grade=4.5,
            )
        )
        count += 1
    return count


def seed_student_requests(db: Session, student: Student) -> int:
    suggestions = build_student_suggestions(db, student, PILOT_STUDENT_TARGET_SEMESTER)
    selected: list[Course] = []
    max_requests = 5 if student.current_semester >= 3 else 4
    for relation in ("regular", "reoffer", "elective", "future"):
        for item in suggestions:
            course = item["course"]
            if not isinstance(course, Course):
                continue
            if not item["eligible"] or item["regular_relation"] != relation:
                continue
            if any(selected_course.id == course.id for selected_course in selected):
                continue
            selected.append(course)
            if len(selected) >= max_requests:
                break
        if len(selected) >= max_requests:
            break

    for priority, course in enumerate(selected, start=1):
        db.add(
            StudentCourseRequest(
                student_id=student.id,
                course_id=course.id,
                target_semester=PILOT_STUDENT_TARGET_SEMESTER,
                priority=max(1, min(5, 6 - priority)),
                source=PILOT_STUDENT_SOURCE,
                note="Demanda sintetica do piloto UFPel para demonstracao do fluxo discente",
            )
        )
    return len(selected)


def history_semester_label(current_semester: int, recommended_semester: int) -> str:
    distance = max(1, current_semester - recommended_semester)
    absolute_index = 2026 * 2 + 1 - distance
    year = absolute_index // 2
    period = 1 if absolute_index % 2 else 2
    return f"{year}/{period}"


def pilot_grade(current_semester: int, recommended_semester: int) -> float:
    return round(6.8 + ((current_semester + recommended_semester) % 7) * 0.35, 1)


def max_parallel_sessions(records: list[tuple[CoursePage, dict[str, object], Course]]) -> int:
    counts: dict[tuple[int, int, int], int] = {}
    seen: set[tuple[str, str, tuple[int, int, int]]] = set()
    for _page, offering, _course in records:
        for item in offering["schedule"]:
            key = (str(offering["discipline_code"]), str(offering["class"]), (item["day"], item["start_minute"], item["end_minute"]))
            if key in seen:
                continue
            seen.add(key)
            counts[key[2]] = counts.get(key[2], 0) + 1
    return max(counts.values(), default=1)


def unique_windows(windows: list[dict[str, int]]) -> list[dict[str, int]]:
    return [
        {"day": day, "start_minute": start, "end_minute": end}
        for day, start, end in sorted(
            {
                (int(item["day"]), int(item["start_minute"]), int(item["end_minute"]))
                for item in windows
            }
        )
    ]


def turn_window(name: str) -> tuple[int, int]:
    if "Noturno" in name:
        return 19 * 60, 22 * 60 + 20
    return 8 * 60, 18 * 60


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def safe_int(value: str | None) -> int | None:
    digits = re.sub(r"[^0-9]", "", value or "")
    return int(digits) if digits else None


def to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def format_minutes(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def day_label(day: int) -> str:
    return ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"][day]


if __name__ == "__main__":
    main()
