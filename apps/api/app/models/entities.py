from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CourseKind(str, enum.Enum):
    mandatory = "mandatory"
    elective = "elective"


class RoomKind(str, enum.Enum):
    lecture = "lecture"
    lab = "lab"


class ConstraintStrength(str, enum.Enum):
    hard = "hard"
    soft = "soft"
    manual_override = "manual_override"


class AvailabilityKind(str, enum.Enum):
    available = "available"
    unavailable = "unavailable"
    preferred = "preferred"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    feasible = "feasible"
    infeasible = "infeasible"
    failed = "failed"


class CourseRestrictionKind(str, enum.Enum):
    prerequisite = "prerequisite"
    corequisite = "corequisite"


class StudentCourseStatus(str, enum.Enum):
    completed = "completed"
    failed = "failed"
    enrolled = "enrolled"
    withdrawn = "withdrawn"


class EnrollmentStatus(str, enum.Enum):
    enrolled = "enrolled"
    waitlisted = "waitlisted"
    superseded = "superseded"
    blocked = "blocked"


class Campus(Base):
    __tablename__ = "campuses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    city: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    degree_programs: Mapped[list[DegreeProgram]] = relationship(back_populates="campus")
    courses: Mapped[list[Course]] = relationship(back_populates="campus")


class DegreeProgram(Base):
    __tablename__ = "degree_programs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campus_id: Mapped[str | None] = mapped_column(ForeignKey("campuses.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    code: Mapped[str | None] = mapped_column(String(40))
    department: Mapped[str | None] = mapped_column(String(120))
    schedule_start_minute: Mapped[int | None] = mapped_column(Integer)
    schedule_end_minute: Mapped[int | None] = mapped_column(Integer)
    required_hours: Mapped[int | None] = mapped_column(Integer)
    minimum_semesters: Mapped[int | None] = mapped_column(Integer)
    maximum_semesters: Mapped[int | None] = mapped_column(Integer)
    legal_notes: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    campus: Mapped[Campus | None] = relationship(back_populates="degree_programs")
    courses: Mapped[list[Course]] = relationship(back_populates="degree_program")
    students: Mapped[list[Student]] = relationship(back_populates="degree_program")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str | None] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    campus_id: Mapped[str | None] = mapped_column(ForeignKey("campuses.id", ondelete="SET NULL"))
    degree_program_id: Mapped[str | None] = mapped_column(
        ForeignKey("degree_programs.id", ondelete="SET NULL")
    )
    workload_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    theoretical_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    practical_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kind: Mapped[CourseKind] = mapped_column(Enum(CourseKind), nullable=False)
    recommended_semester: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_demand: Mapped[int] = mapped_column(Integer, nullable=False)
    requires_lab: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    criticality: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    context_key: Mapped[str | None] = mapped_column(String(160))
    shareable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approval_grade: Mapped[float | None] = mapped_column(Float, default=7)
    approval_frequency_percent: Mapped[int | None] = mapped_column(Integer, default=75)
    source_url: Mapped[str | None] = mapped_column(String(320))
    official_period: Mapped[str | None] = mapped_column(String(32))
    official_class: Mapped[str | None] = mapped_column(String(40))
    official_schedule: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    campus: Mapped[Campus | None] = relationship(back_populates="courses")
    degree_program: Mapped[DegreeProgram | None] = relationship(back_populates="courses")
    qualifications: Mapped[list[ProfessorQualification]] = relationship(back_populates="course")
    preferences: Mapped[list[ProfessorCoursePreference]] = relationship(back_populates="course")
    restrictions: Mapped[list[CourseRestriction]] = relationship(
        back_populates="course",
        foreign_keys="CourseRestriction.course_id",
        cascade="all, delete-orphan",
    )


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    email: Mapped[str | None] = mapped_column(String(220), unique=True)
    registration_number: Mapped[str | None] = mapped_column(String(80), unique=True)
    degree_program_id: Mapped[str] = mapped_column(
        ForeignKey("degree_programs.id", ondelete="CASCADE")
    )
    current_semester: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    degree_program: Mapped[DegreeProgram] = relationship(back_populates="students")
    history: Mapped[list[StudentCourseHistory]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    requests: Mapped[list[StudentCourseRequest]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    enrollments: Mapped[list[StudentEnrollment]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class CourseRestriction(Base):
    __tablename__ = "course_restrictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    required_course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    kind: Mapped[CourseRestrictionKind] = mapped_column(
        Enum(CourseRestrictionKind), default=CourseRestrictionKind.prerequisite
    )
    strength: Mapped[ConstraintStrength] = mapped_column(
        Enum(ConstraintStrength), default=ConstraintStrength.hard
    )
    minimum_grade: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)

    course: Mapped[Course] = relationship(back_populates="restrictions", foreign_keys=[course_id])
    required_course: Mapped[Course] = relationship(foreign_keys=[required_course_id])


class StudentCourseHistory(Base):
    __tablename__ = "student_course_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    status: Mapped[StudentCourseStatus] = mapped_column(
        Enum(StudentCourseStatus), default=StudentCourseStatus.completed
    )
    semester: Mapped[str | None] = mapped_column(String(32))
    grade: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    student: Mapped[Student] = relationship(back_populates="history")
    course: Mapped[Course] = relationship()


class StudentCourseRequest(Base):
    __tablename__ = "student_course_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    target_semester: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    preference_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    alternative_group: Mapped[str | None] = mapped_column(String(80))
    desired_day: Mapped[int | None] = mapped_column(Integer)
    desired_start_minute: Mapped[int | None] = mapped_column(Integer)
    desired_end_minute: Mapped[int | None] = mapped_column(Integer)
    time_preference_strength: Mapped[ConstraintStrength] = mapped_column(
        Enum(ConstraintStrength), default=ConstraintStrength.soft, nullable=False
    )
    stage: Mapped[str] = mapped_column(String(40), default="pre_enrollment", nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="student", nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    student: Mapped[Student] = relationship(back_populates="requests")
    course: Mapped[Course] = relationship()


class StudentEnrollment(Base):
    __tablename__ = "student_enrollments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    request_id: Mapped[str | None] = mapped_column(
        ForeignKey("student_course_requests.id", ondelete="SET NULL")
    )
    run_id: Mapped[str | None] = mapped_column(ForeignKey("optimization_runs.id", ondelete="SET NULL"))
    target_semester: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str] = mapped_column(String(40), default="pre_enrollment", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default=EnrollmentStatus.waitlisted.value)
    score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    score_breakdown: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    student: Mapped[Student] = relationship(back_populates="enrollments")
    course: Mapped[Course] = relationship()
    request: Mapped[StudentCourseRequest | None] = relationship()


class Professor(Base):
    __tablename__ = "professors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    email: Mapped[str | None] = mapped_column(String(220), unique=True)
    department: Mapped[str] = mapped_column(String(120), default="UFPel")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contract: Mapped[ProfessorContract | None] = relationship(
        back_populates="professor", uselist=False, cascade="all, delete-orphan", single_parent=True
    )
    qualifications: Mapped[list[ProfessorQualification]] = relationship(back_populates="professor")
    availability: Mapped[list[ProfessorAvailability]] = relationship(back_populates="professor")
    preferences: Mapped[list[ProfessorCoursePreference]] = relationship(back_populates="professor")
    constraints: Mapped[list[ProfessorConstraint]] = relationship(back_populates="professor")
    invitations: Mapped[list[InvitationLink]] = relationship(back_populates="professor")


class ProfessorContract(Base):
    __tablename__ = "professor_contracts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    professor_id: Mapped[str] = mapped_column(
        ForeignKey("professors.id", ondelete="CASCADE"), unique=True
    )
    min_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    max_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    regime: Mapped[str] = mapped_column(String(80), default="DE")
    semester: Mapped[str | None] = mapped_column(String(32))
    is_borrowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    borrowed_from_department: Mapped[str | None] = mapped_column(String(120))
    legal_notes: Mapped[str | None] = mapped_column(Text)
    loan_notes: Mapped[str | None] = mapped_column(Text)

    professor: Mapped[Professor] = relationship(back_populates="contract")


class ProfessorQualification(Base):
    __tablename__ = "professor_qualifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    professor_id: Mapped[str] = mapped_column(ForeignKey("professors.id", ondelete="CASCADE"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    strength: Mapped[ConstraintStrength] = mapped_column(
        Enum(ConstraintStrength), default=ConstraintStrength.hard
    )
    source: Mapped[str] = mapped_column(String(80), default="coordinator")

    professor: Mapped[Professor] = relationship(back_populates="qualifications")
    course: Mapped[Course] = relationship(back_populates="qualifications")


class ProfessorAvailability(Base):
    __tablename__ = "professor_availability"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    professor_id: Mapped[str] = mapped_column(ForeignKey("professors.id", ondelete="CASCADE"))
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[AvailabilityKind] = mapped_column(Enum(AvailabilityKind), nullable=False)
    strength: Mapped[ConstraintStrength] = mapped_column(
        Enum(ConstraintStrength), default=ConstraintStrength.soft
    )
    source: Mapped[str] = mapped_column(String(80), default="teacher")

    professor: Mapped[Professor] = relationship(back_populates="availability")


class ProfessorCoursePreference(Base):
    __tablename__ = "professor_course_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    professor_id: Mapped[str] = mapped_column(ForeignKey("professors.id", ondelete="CASCADE"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    preference: Mapped[int] = mapped_column(Integer, nullable=False)
    strength: Mapped[ConstraintStrength] = mapped_column(
        Enum(ConstraintStrength), default=ConstraintStrength.soft
    )
    note: Mapped[str | None] = mapped_column(Text)

    professor: Mapped[Professor] = relationship(back_populates="preferences")
    course: Mapped[Course] = relationship(back_populates="preferences")


class ProfessorConstraint(Base):
    __tablename__ = "professor_constraints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    professor_id: Mapped[str] = mapped_column(ForeignKey("professors.id", ondelete="CASCADE"))
    natural_language: Mapped[str] = mapped_column(Text, nullable=False)
    structured_rule: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    strength: Mapped[ConstraintStrength] = mapped_column(
        Enum(ConstraintStrength), default=ConstraintStrength.soft
    )
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    professor: Mapped[Professor] = relationship(back_populates="constraints")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    campus_id: Mapped[str | None] = mapped_column(ForeignKey("campuses.id", ondelete="SET NULL"))
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[RoomKind] = mapped_column(Enum(RoomKind), nullable=False)
    availability: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class TimeSlot(Base):
    __tablename__ = "time_slots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.pending)
    semester: Mapped[str] = mapped_column(String(32), default="2026/2", nullable=False)
    profile: Mapped[str] = mapped_column(String(32), default="balanced")
    parameters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    pareto_front: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assignments: Mapped[list[Assignment]] = relationship(back_populates="run")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("optimization_runs.id", ondelete="CASCADE"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    professor_id: Mapped[str] = mapped_column(ForeignKey("professors.id", ondelete="CASCADE"))
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    time_slot_id: Mapped[str] = mapped_column(ForeignKey("time_slots.id", ondelete="CASCADE"))
    session_index: Mapped[int] = mapped_column(Integer, default=0)
    fixed: Mapped[bool] = mapped_column(Boolean, default=False)
    hard_violations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    soft_violations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    origin: Mapped[str] = mapped_column(String(32), default="optimized")

    run: Mapped[OptimizationRun] = relationship(back_populates="assignments")
    course: Mapped[Course] = relationship()
    professor: Mapped[Professor] = relationship()
    room: Mapped[Room] = relationship()
    time_slot: Mapped[TimeSlot] = relationship()


class InvitationLink(Base):
    __tablename__ = "invitation_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    professor_id: Mapped[str] = mapped_column(ForeignKey("professors.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(96), unique=True, nullable=False)
    semester: Mapped[str] = mapped_column(String(32), default="2026/2")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    professor: Mapped[Professor] = relationship(back_populates="invitations")


class PresentationToken(Base):
    __tablename__ = "presentation_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token: Mapped[str] = mapped_column(String(96), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    semester: Mapped[str] = mapped_column(String(32), default="2026/2", nullable=False)
    degree_program_id: Mapped[str | None] = mapped_column(
        ForeignKey("degree_programs.id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


Index("ix_availability_professor_day", ProfessorAvailability.professor_id, ProfessorAvailability.day)
Index("ix_degree_programs_campus", DegreeProgram.campus_id)
Index("ix_courses_campus", Course.campus_id)
Index("ix_courses_degree_program", Course.degree_program_id)
Index("ix_courses_context_key", Course.context_key)
Index("ix_rooms_campus", Room.campus_id)
Index("ix_students_degree_program", Student.degree_program_id)
Index("ix_course_restrictions_course", CourseRestriction.course_id)
Index("ix_course_restrictions_required", CourseRestriction.required_course_id)
Index("ix_student_history_student", StudentCourseHistory.student_id)
Index("ix_student_history_course", StudentCourseHistory.course_id)
Index(
    "ix_student_requests_student_semester",
    StudentCourseRequest.student_id,
    StudentCourseRequest.target_semester,
)
Index(
    "ix_student_requests_course_semester",
    StudentCourseRequest.course_id,
    StudentCourseRequest.target_semester,
)
Index(
    "ix_student_enrollments_student_semester",
    StudentEnrollment.student_id,
    StudentEnrollment.target_semester,
)
Index(
    "ix_student_enrollments_course_semester",
    StudentEnrollment.course_id,
    StudentEnrollment.target_semester,
)
Index("ix_assignments_run_slot", Assignment.run_id, Assignment.time_slot_id)
Index("ix_assignments_run_professor", Assignment.run_id, Assignment.professor_id)
Index("ix_assignments_run_room", Assignment.run_id, Assignment.room_id)
Index("ix_presentation_tokens_token", PresentationToken.token)
