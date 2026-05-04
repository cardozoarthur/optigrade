from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Campus, Course, DegreeProgram
from app.schemas import CourseCreate, CourseRead

router = APIRouter()


@router.get("", response_model=list[CourseRead])
def list_courses(db: Session = Depends(get_db)) -> list[Course]:
    return db.query(Course).order_by(Course.recommended_semester, Course.name).all()


@router.post("", response_model=CourseRead)
def create_course(payload: CourseCreate, db: Session = Depends(get_db)) -> Course:
    validate_academic_refs(db, payload)
    course = Course(**payload.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("/{course_id}", response_model=CourseRead)
def get_course(course_id: str, db: Session = Depends(get_db)) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Disciplina nao encontrada")
    return course


@router.put("/{course_id}", response_model=CourseRead)
def update_course(course_id: str, payload: CourseCreate, db: Session = Depends(get_db)) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Disciplina nao encontrada")
    validate_academic_refs(db, payload)
    for key, value in payload.model_dump().items():
        setattr(course, key, value)
    db.commit()
    db.refresh(course)
    return course


@router.delete("/{course_id}")
def delete_course(course_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Disciplina nao encontrada")
    db.delete(course)
    db.commit()
    return {"ok": True}


def validate_academic_refs(db: Session, payload: CourseCreate) -> None:
    if payload.campus_id and not db.get(Campus, payload.campus_id):
        raise HTTPException(status_code=404, detail="Campus nao encontrado")
    if payload.degree_program_id:
        degree_program = db.get(DegreeProgram, payload.degree_program_id)
        if not degree_program:
            raise HTTPException(status_code=404, detail="Curso nao encontrado")
        if payload.campus_id and degree_program.campus_id and degree_program.campus_id != payload.campus_id:
            raise HTTPException(status_code=400, detail="Curso nao pertence ao campus informado")
