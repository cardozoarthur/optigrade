from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.entities import (
    AvailabilityKind,
    ConstraintStrength,
    CourseKind,
    CourseRestrictionKind,
    RoomKind,
    RunStatus,
    StudentCourseStatus,
)


class CampusCreate(BaseModel):
    name: str
    city: str | None = None


class CampusRead(CampusCreate):
    id: str

    model_config = ConfigDict(from_attributes=True)


class DegreeProgramCreate(BaseModel):
    name: str
    code: str | None = None
    department: str | None = None
    campus_id: str | None = None
    schedule_start_minute: int | None = Field(default=None, ge=0, le=1439)
    schedule_end_minute: int | None = Field(default=None, ge=1, le=1440)

    @model_validator(mode="after")
    def validate_schedule_window(self) -> "DegreeProgramCreate":
        has_start = self.schedule_start_minute is not None
        has_end = self.schedule_end_minute is not None
        if has_start != has_end:
            raise ValueError("Horario de inicio e fim do curso devem ser preenchidos juntos")
        if has_start and self.schedule_end_minute <= self.schedule_start_minute:
            raise ValueError("Horario final do curso deve ser posterior ao horario inicial")
        return self


class DegreeProgramRead(DegreeProgramCreate):
    id: str
    required_hours: int | None = None
    minimum_semesters: int | None = None
    maximum_semesters: int | None = None
    legal_notes: str | None = None
    source_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CourseCreate(BaseModel):
    code: str | None = None
    name: str
    campus_id: str | None = None
    degree_program_id: str | None = None
    workload_hours: int = Field(ge=1, le=120)
    theoretical_hours: int | None = Field(default=None, ge=0, le=120)
    practical_hours: int = Field(default=0, ge=0, le=120)
    kind: CourseKind
    recommended_semester: int = Field(ge=1, le=20)
    expected_demand: int = Field(ge=1)
    requires_lab: bool = False
    criticality: int = Field(default=3, ge=1, le=5)
    context_key: str | None = Field(default=None, max_length=160)
    shareable: bool = True

    @model_validator(mode="after")
    def normalize_hours(self) -> "CourseCreate":
        if self.theoretical_hours is None:
            self.theoretical_hours = max(0, self.workload_hours - self.practical_hours)
        if self.theoretical_hours + self.practical_hours > self.workload_hours:
            raise ValueError("Horas teoricas + praticas nao podem exceder a carga horaria")
        return self


class CourseRead(CourseCreate):
    id: str
    approval_grade: float | None = None
    approval_frequency_percent: int | None = None
    source_url: str | None = None
    official_period: str | None = None
    official_class: str | None = None
    official_schedule: list = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class CourseRestrictionCreate(BaseModel):
    course_id: str
    required_course_id: str
    kind: CourseRestrictionKind = CourseRestrictionKind.prerequisite
    strength: ConstraintStrength = ConstraintStrength.hard
    minimum_grade: float | None = Field(default=None, ge=0, le=10)
    note: str | None = None


class CourseRestrictionBatchCreate(BaseModel):
    course_id: str
    required_course_ids: list[str] = Field(min_length=1)
    kind: CourseRestrictionKind = CourseRestrictionKind.prerequisite
    strength: ConstraintStrength = ConstraintStrength.hard
    minimum_grade: float | None = Field(default=None, ge=0, le=10)
    note: str | None = None


class CourseRestrictionRead(CourseRestrictionCreate):
    id: str

    model_config = ConfigDict(from_attributes=True)


class StudentCreate(BaseModel):
    name: str
    email: str | None = None
    registration_number: str | None = None
    degree_program_id: str
    current_semester: int = Field(default=1, ge=1, le=20)


class StudentRead(StudentCreate):
    id: str

    model_config = ConfigDict(from_attributes=True)


class StudentCourseHistoryCreate(BaseModel):
    course_id: str
    status: StudentCourseStatus = StudentCourseStatus.completed
    semester: str | None = None
    grade: float | None = Field(default=None, ge=0, le=10)


class StudentCourseHistoryRead(StudentCourseHistoryCreate):
    id: str
    student_id: str

    model_config = ConfigDict(from_attributes=True)


class StudentCourseRequestCreate(BaseModel):
    course_id: str
    target_semester: str = "2026/2"
    priority: int = Field(default=3, ge=1, le=5)
    preference_order: int = Field(default=1, ge=1, le=50)
    alternative_group: str | None = None
    stage: str = "pre_enrollment"
    source: str = "student"
    note: str | None = None


class StudentCourseRequestRead(StudentCourseRequestCreate):
    id: str
    student_id: str

    model_config = ConfigDict(from_attributes=True)


class StudentCourseSelectionCreate(BaseModel):
    target_semester: str = "2026/2"
    course_ids: list[str] = Field(min_length=1)
    priority: int = Field(default=3, ge=1, le=5)
    alternative_group: str | None = None
    note: str | None = None


class StudentCourseChoiceCreate(BaseModel):
    course_id: str
    preference_order: int = Field(default=1, ge=1, le=50)
    alternative_group: str | None = None
    priority: int = Field(default=3, ge=1, le=5)
    note: str | None = None


class StudentCourseChoiceSelectionCreate(BaseModel):
    target_semester: str = "2026/2"
    choices: list[StudentCourseChoiceCreate] = Field(min_length=1)


class StudentCourseSuggestionRead(BaseModel):
    course: CourseRead
    eligible: bool
    score: int
    reasons: list[str]
    missing_requirements: list[CourseRead] = Field(default_factory=list)
    already_requested: bool = False
    regular_relation: str = "institutional"
    is_regular_for_student: bool = False


class StudentSuggestionsRead(BaseModel):
    student_id: str
    target_semester: str
    suggestions: list[StudentCourseSuggestionRead]


class EnrollmentRoundCreate(BaseModel):
    target_semester: str = "2026/2"
    stage: str = "pre_enrollment"
    run_id: str | None = None


class StudentEnrollmentRead(BaseModel):
    id: str
    student_id: str
    course_id: str
    request_id: str | None
    run_id: str | None
    target_semester: str
    stage: str
    status: str
    score: float
    score_breakdown: dict
    reason: str | None

    model_config = ConfigDict(from_attributes=True)


class EnrollmentRoundRead(BaseModel):
    target_semester: str
    stage: str
    run_id: str | None
    enrolled: int
    waitlisted: int
    superseded: int
    blocked: int
    unallocated_groups: int
    capacity_by_course: dict[str, int]


class ProfessorCreate(BaseModel):
    name: str
    email: str | None = None
    department: str = "UFPel"


class ProfessorContractCreate(BaseModel):
    min_hours: int = Field(ge=0, le=60)
    max_hours: int = Field(ge=1, le=80)
    regime: str = "DE"
    semester: str | None = None
    is_borrowed: bool = False
    borrowed_from_department: str | None = None
    legal_notes: str | None = None
    loan_notes: str | None = None


class ProfessorContractRead(ProfessorContractCreate):
    id: str
    professor_id: str

    model_config = ConfigDict(from_attributes=True)


class ProfessorQualificationCreate(BaseModel):
    course_id: str
    strength: ConstraintStrength = ConstraintStrength.hard
    source: str = "coordinator"


class ProfessorAvailabilityCreate(BaseModel):
    day: int = Field(ge=0, le=6)
    start_minute: int = Field(ge=0, le=1439)
    end_minute: int = Field(ge=1, le=1440)
    kind: AvailabilityKind
    strength: ConstraintStrength = ConstraintStrength.soft
    source: str = "teacher"


class ProfessorCoursePreferenceCreate(BaseModel):
    course_id: str
    preference: int = Field(ge=-5, le=5)
    strength: ConstraintStrength = ConstraintStrength.soft
    note: str | None = None


class ProfessorRead(ProfessorCreate):
    id: str
    contract: ProfessorContractRead | None = None

    model_config = ConfigDict(from_attributes=True)


class BorrowedProfessorCreate(BaseModel):
    name: str
    email: str | None = None
    department: str = "Computacao"
    borrowed_from_department: str
    semester: str = "2026/2"
    min_hours: int = Field(default=0, ge=0, le=20)
    max_hours: int = Field(default=4, ge=1, le=20)
    regime: str = "emprestado"
    legal_notes: str | None = None
    loan_notes: str | None = None
    availability: list[ProfessorAvailabilityCreate] = Field(default_factory=list)


class RoomCreate(BaseModel):
    name: str
    campus_id: str | None = None
    capacity: int = Field(ge=1)
    kind: RoomKind
    availability: dict = Field(default_factory=dict)


class RoomRead(RoomCreate):
    id: str

    model_config = ConfigDict(from_attributes=True)


class TimeSlotCreate(BaseModel):
    day: int = Field(ge=0, le=6)
    start_minute: int = Field(ge=0, le=1439)
    end_minute: int = Field(ge=1, le=1440)
    label: str


class TimeSlotRead(TimeSlotCreate):
    id: str

    model_config = ConfigDict(from_attributes=True)


class OptimizationRunCreate(BaseModel):
    semester: str = "2026/2"
    profile: str = "balanced"
    parameters: dict = Field(default_factory=dict)
    fixed_assignment_ids: list[str] = Field(default_factory=list)


class AssignmentRead(BaseModel):
    id: str
    run_id: str
    course_id: str
    professor_id: str
    room_id: str
    time_slot_id: str
    session_index: int
    fixed: bool
    hard_violations: list
    soft_violations: list
    origin: str

    model_config = ConfigDict(from_attributes=True)


class OptimizationRunRead(BaseModel):
    id: str
    status: RunStatus
    semester: str
    profile: str
    parameters: dict
    metrics: dict
    pareto_front: list
    explanation: str | None
    score: float | None
    created_at: datetime
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ManualAdjustmentCreate(BaseModel):
    assignment_id: str | None = None
    course_id: str
    professor_id: str
    room_id: str
    time_slot_id: str
    session_index: int = 0
    fixed: bool = True


class InvitationRead(BaseModel):
    id: str
    professor_id: str
    token: str
    semester: str
    expires_at: datetime
    submitted_at: datetime | None
    revoked: bool

    model_config = ConfigDict(from_attributes=True)


class TeacherPortalRead(BaseModel):
    professor_id: str
    professor_name: str
    semester: str
    courses: list[CourseRead]


class NaturalLanguageConstraintCreate(BaseModel):
    text: str
    strength: ConstraintStrength = ConstraintStrength.soft


class TeacherPortalSubmit(BaseModel):
    availability: list[ProfessorAvailabilityCreate] = Field(default_factory=list)
    course_preferences: list[ProfessorCoursePreferenceCreate] = Field(default_factory=list)
    natural_language_constraints: list[NaturalLanguageConstraintCreate] = Field(default_factory=list)


class PresentationLinkCreate(BaseModel):
    semester: str = "2026/2"
    professor_id: str | None = None
    degree_program_id: str | None = None


class PresentationLinkRead(BaseModel):
    token: str
    url: str
    expires_at: datetime
    kind: str


class PresentationStatsRead(BaseModel):
    campuses: int
    degree_programs: int
    courses: int
    professors: int
    students: int
    rooms: int
    threads: int
    cpu_count: int
    memory_total_mb: int | None = None


class PresentationStudentTokenRead(BaseModel):
    token: str
    semester: str
    degree_program: DegreeProgramRead
    courses: list[CourseRead]


class PresentationStudentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    email: str | None = Field(default=None, max_length=220)


class PresentationStudentCreatedRead(BaseModel):
    student: StudentRead
    suggestions: StudentSuggestionsRead


class PresentationStudentChoicesCreate(BaseModel):
    course_ids: list[str] = Field(min_length=1, max_length=12)
    queue_mode: bool = True


class PresentationStudentChoicesRead(BaseModel):
    requests: list[StudentCourseRequestRead]
