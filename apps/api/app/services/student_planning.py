from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.entities import (
    ConstraintStrength,
    Course,
    CourseKind,
    CourseRestriction,
    CourseRestrictionKind,
    Student,
    StudentCourseHistory,
    StudentCourseRequest,
    StudentCourseStatus,
)


@dataclass(frozen=True)
class StudentDemandSummary:
    demand_by_course: dict[str, int]
    total_requests: int
    eligible_requests: int
    blocked_requests: int
    regular_requests: int
    reoffer_requests: int
    elective_requests: int


def student_demand_by_course(db: Session, semester: str) -> dict[str, int]:
    return student_demand_summary(db, semester).demand_by_course


def student_demand_summary(db: Session, semester: str) -> StudentDemandSummary:
    requests = (
        db.query(StudentCourseRequest)
        .filter(StudentCourseRequest.target_semester == semester)
        .all()
    )
    if not requests:
        return StudentDemandSummary({}, 0, 0, 0, 0, 0, 0)

    student_ids = {item.student_id for item in requests}
    course_ids = {item.course_id for item in requests}
    students = {
        item.id: item
        for item in db.query(Student).filter(Student.id.in_(student_ids)).all()
    }
    courses = {
        item.id: item
        for item in db.query(Course).filter(Course.id.in_(course_ids)).all()
    }

    demand: dict[str, int] = {}
    eligible = 0
    blocked = 0
    regular = 0
    reoffer = 0
    elective = 0

    for request in requests:
        student = students.get(request.student_id)
        course = courses.get(request.course_id)
        if not student or not course:
            blocked += 1
            continue

        eligibility_course = eligibility_course_for_student(db, student, course)
        if not eligibility_course or not course_eligible_for_student(db, student, course):
            blocked += 1
            continue

        demand_course = demand_course_for_student(db, student, course, eligibility_course)
        demand[demand_course.id] = demand.get(demand_course.id, 0) + 1
        eligible += 1
        relation = regular_relation_for_student(course, student, eligibility_course)
        if relation == "regular":
            regular += 1
        elif relation == "reoffer":
            reoffer += 1
        elif relation == "elective":
            elective += 1

    return StudentDemandSummary(
        demand_by_course=demand,
        total_requests=len(requests),
        eligible_requests=eligible,
        blocked_requests=blocked,
        regular_requests=regular,
        reoffer_requests=reoffer,
        elective_requests=elective,
    )


def raw_student_demand_by_course(db: Session, semester: str) -> dict[str, int]:
    rows = (
        db.query(StudentCourseRequest.course_id, func.count(StudentCourseRequest.id))
        .filter(StudentCourseRequest.target_semester == semester)
        .group_by(StudentCourseRequest.course_id)
        .all()
    )
    return {course_id: int(count) for course_id, count in rows}


def build_student_suggestions(
    db: Session, student: Student, target_semester: str
) -> list[dict[str, object]]:
    completed = completed_history_by_course(db, student.id)
    completed_contexts = completed_contexts_by_course(db, completed)
    requested = {
        item.course_id
        for item in db.query(StudentCourseRequest)
        .filter(
            StudentCourseRequest.student_id == student.id,
            StudentCourseRequest.target_semester == target_semester,
        )
        .all()
    }
    courses = suggestion_courses_for_student(db, student, completed_contexts)
    restrictions_by_course = restrictions_for_courses(db, [course.id for course in courses])
    course_by_id = {course.id: course for course in db.query(Course).all()}

    suggestions: list[dict[str, object]] = []
    for course in courses:
        if course.id in completed or course_completed_by_context(course, completed_contexts):
            continue

        eligibility_course = eligibility_course_for_student(db, student, course)
        if not eligibility_course:
            continue

        missing: list[Course] = []
        reasons: list[str] = []
        eligible = True
        for restriction in restrictions_by_course.get(eligibility_course.id, []):
            required_course = course_by_id.get(restriction.required_course_id)
            if restriction.kind == CourseRestrictionKind.corequisite:
                requirement_name = (
                    required_course.name if required_course else restriction.required_course_id
                )
                reasons.append(f"Corequisito: {requirement_name}")
                continue
            if requirement_satisfied(completed, restriction, required_course, completed_contexts):
                continue
            if required_course:
                missing.append(required_course)
            if restriction.strength == ConstraintStrength.hard:
                eligible = False
            reasons.append(
                f"Falta pre-requisito: {required_course.name if required_course else restriction.required_course_id}"
            )

        relation = regular_relation_for_student(course, student, eligibility_course)
        semester_distance = abs(eligibility_course.recommended_semester - student.current_semester)
        score = course.criticality * 10 - semester_distance * 2
        if course.kind == CourseKind.mandatory:
            score += 8
        if eligibility_course.recommended_semester <= student.current_semester + 1:
            score += 6
        if relation == "reoffer" and course.degree_program_id != student.degree_program_id:
            score += 5
            reasons.append("Reoferta equivalente disponivel em outro curso")
        if course.id in requested:
            score += 4
            reasons.append("Ja selecionada para o semestre alvo")
        if eligible and not reasons:
            reasons.append("Compativel com historico e semestre recomendado")

        suggestions.append(
            {
                "course": course,
                "eligible": eligible,
                "score": score,
                "reasons": reasons,
                "missing_requirements": missing,
                "already_requested": course.id in requested,
                "regular_relation": relation,
                "is_regular_for_student": is_regular_for_student(
                    course,
                    student,
                    eligibility_course,
                ),
            }
        )

    return sorted(suggestions, key=suggestion_sort_key)


def suggestion_sort_key(item: dict[str, object]) -> tuple[bool, int, int, str]:
    course = item["course"]
    if not isinstance(course, Course):
        return (True, 0, 99, "")
    return (
        not bool(item["eligible"]),
        -int(item["score"]),
        course.recommended_semester,
        course.name,
    )


def suggestion_courses_for_student(
    db: Session,
    student: Student,
    completed_contexts: dict[str, StudentCourseHistory],
) -> list[Course]:
    own_or_institutional = (
        db.query(Course)
        .filter(
            or_(
                Course.degree_program_id == student.degree_program_id,
                Course.degree_program_id.is_(None),
            )
        )
        .all()
    )
    reoffer_contexts = pending_reoffer_contexts(db, student, completed_contexts)
    equivalent_reoffers: list[Course] = []
    if reoffer_contexts:
        equivalent_reoffers = (
            db.query(Course)
            .filter(
                Course.shareable.is_(True),
                Course.context_key.in_(reoffer_contexts),
                Course.degree_program_id.is_not(None),
                Course.degree_program_id != student.degree_program_id,
            )
            .all()
        )
    deduped = {course.id: course for course in own_or_institutional + equivalent_reoffers}
    return sorted(
        deduped.values(),
        key=lambda course: (
            regular_relation_for_student(course, student),
            course.recommended_semester,
            course.kind.value,
            course.name,
        ),
    )


def pending_reoffer_contexts(
    db: Session,
    student: Student,
    completed_contexts: dict[str, StudentCourseHistory],
) -> set[str]:
    contexts = {
        context_key
        for course in db.query(Course)
        .filter(
            Course.degree_program_id == student.degree_program_id,
            Course.shareable.is_(True),
            Course.context_key.is_not(None),
            Course.recommended_semester < student.current_semester,
        )
        .all()
        if (context_key := normalize_context_key(course.context_key))
        and context_key not in completed_contexts
    }
    failed_course_ids = [
        item.course_id
        for item in db.query(StudentCourseHistory)
        .filter(
            StudentCourseHistory.student_id == student.id,
            StudentCourseHistory.status.in_(
                [StudentCourseStatus.failed, StudentCourseStatus.withdrawn]
            ),
        )
        .all()
    ]
    if failed_course_ids:
        failed_courses = db.query(Course).filter(Course.id.in_(failed_course_ids)).all()
        contexts.update(
            context_key
            for course in failed_courses
            if course.shareable
            and (context_key := normalize_context_key(course.context_key))
            and context_key not in completed_contexts
        )
    return contexts


def completed_history_by_course(
    db: Session, student_id: str
) -> dict[str, StudentCourseHistory]:
    rows = (
        db.query(StudentCourseHistory)
        .filter(
            StudentCourseHistory.student_id == student_id,
            StudentCourseHistory.status == StudentCourseStatus.completed,
        )
        .all()
    )
    return {item.course_id: item for item in rows}


def completed_contexts_by_course(
    db: Session, completed: dict[str, StudentCourseHistory]
) -> dict[str, StudentCourseHistory]:
    if not completed:
        return {}
    completed_courses = (
        db.query(Course)
        .filter(Course.id.in_(completed.keys()), Course.context_key.is_not(None), Course.shareable.is_(True))
        .all()
    )
    return {
        context_key: completed[course.id]
        for course in completed_courses
        if (context_key := normalize_context_key(course.context_key)) and course.id in completed
    }


def course_completed_by_context(
    course: Course, completed_contexts: dict[str, StudentCourseHistory]
) -> bool:
    context_key = normalize_context_key(course.context_key)
    return bool(course.shareable and context_key and context_key in completed_contexts)


def course_eligible_for_student(db: Session, student: Student, course: Course) -> bool:
    eligibility_course = eligibility_course_for_student(db, student, course)
    if not eligibility_course:
        return False
    completed = completed_history_by_course(db, student.id)
    if eligibility_course.id in completed:
        return False
    completed_contexts = completed_contexts_by_course(db, completed)
    if course_completed_by_context(eligibility_course, completed_contexts):
        return False

    restrictions = restrictions_for_courses(db, [eligibility_course.id]).get(eligibility_course.id, [])
    course_by_id = {item.id: item for item in db.query(Course).all()}
    for restriction in restrictions:
        if restriction.kind == CourseRestrictionKind.corequisite:
            continue
        required_course = course_by_id.get(restriction.required_course_id)
        if requirement_satisfied(completed, restriction, required_course, completed_contexts):
            continue
        if restriction.strength == ConstraintStrength.hard:
            return False
    return True


def course_belongs_to_student_program(db: Session, student: Student, course: Course) -> bool:
    if not course.degree_program_id or course.degree_program_id == student.degree_program_id:
        return True
    return eligibility_course_for_student(db, student, course) is not None


def canonical_course_for_student(db: Session, student: Student, course: Course) -> Course | None:
    return eligibility_course_for_student(db, student, course)


def eligibility_course_for_student(db: Session, student: Student, course: Course) -> Course | None:
    if not course.degree_program_id or course.degree_program_id == student.degree_program_id:
        return course
    context_key = normalize_context_key(course.context_key)
    if context_key and course.shareable:
        return (
            db.query(Course)
            .filter(
                Course.degree_program_id == student.degree_program_id,
                Course.context_key == context_key,
                Course.shareable.is_(True),
            )
            .first()
        )
    return None


def demand_course_for_student(
    db: Session,
    student: Student,
    requested_course: Course,
    eligibility_course: Course | None = None,
) -> Course:
    eligibility_course = eligibility_course or eligibility_course_for_student(
        db,
        student,
        requested_course,
    )
    if (
        eligibility_course
        and requested_course.degree_program_id
        and requested_course.degree_program_id != student.degree_program_id
        and requested_course.shareable
        and normalize_context_key(requested_course.context_key)
        == normalize_context_key(eligibility_course.context_key)
        and regular_relation_for_student(requested_course, student, eligibility_course) == "reoffer"
    ):
        return requested_course
    return eligibility_course or requested_course


def regular_relation_for_student(
    course: Course,
    student: Student,
    eligibility_course: Course | None = None,
) -> str:
    eligibility_course = eligibility_course or course
    if course.kind == CourseKind.elective:
        return "elective"
    if not course.degree_program_id or course.degree_program_id != student.degree_program_id:
        if eligibility_course.recommended_semester < student.current_semester:
            return "reoffer"
        return "institutional"
    if eligibility_course.recommended_semester == student.current_semester:
        return "regular"
    if eligibility_course.recommended_semester < student.current_semester:
        return "reoffer"
    return "future"


def is_regular_for_student(
    course: Course,
    student: Student,
    eligibility_course: Course | None = None,
) -> bool:
    return regular_relation_for_student(course, student, eligibility_course) == "regular"


def normalize_context_key(context_key: str | None) -> str | None:
    normalized = (context_key or "").strip().lower()
    return normalized or None


def restrictions_for_courses(
    db: Session, course_ids: list[str]
) -> dict[str, list[CourseRestriction]]:
    if not course_ids:
        return {}
    restrictions = (
        db.query(CourseRestriction)
        .filter(CourseRestriction.course_id.in_(course_ids))
        .all()
    )
    grouped: dict[str, list[CourseRestriction]] = {}
    for item in restrictions:
        grouped.setdefault(item.course_id, []).append(item)
    return grouped


def requirement_satisfied(
    completed: dict[str, StudentCourseHistory],
    restriction: CourseRestriction,
    required_course: Course | None = None,
    completed_contexts: dict[str, StudentCourseHistory] | None = None,
) -> bool:
    history = completed.get(restriction.required_course_id)
    if history and history_satisfies_minimum(history, restriction):
        return True
    if (
        required_course
        and required_course.shareable
        and required_course.context_key
        and completed_contexts
    ):
        equivalent_history = completed_contexts.get(normalize_context_key(required_course.context_key))
        if equivalent_history and history_satisfies_minimum(equivalent_history, restriction):
            return True
    return False


def history_satisfies_minimum(
    history: StudentCourseHistory, restriction: CourseRestriction
) -> bool:
    if restriction.minimum_grade is None:
        return True
    return history.grade is not None and history.grade >= restriction.minimum_grade
