from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Campus, DegreeProgram
from app.schemas import CampusCreate, CampusRead, DegreeProgramCreate, DegreeProgramRead

router = APIRouter()


@router.get("/campuses", response_model=list[CampusRead])
def list_campuses(db: Session = Depends(get_db)) -> list[Campus]:
    return db.query(Campus).order_by(Campus.name).all()


@router.post("/campuses", response_model=CampusRead)
def create_campus(payload: CampusCreate, db: Session = Depends(get_db)) -> Campus:
    campus = Campus(**payload.model_dump())
    db.add(campus)
    db.commit()
    db.refresh(campus)
    return campus


@router.get("/campuses/{campus_id}", response_model=CampusRead)
def get_campus(campus_id: str, db: Session = Depends(get_db)) -> Campus:
    return require_campus(db, campus_id)


@router.put("/campuses/{campus_id}", response_model=CampusRead)
def update_campus(
    campus_id: str, payload: CampusCreate, db: Session = Depends(get_db)
) -> Campus:
    campus = require_campus(db, campus_id)
    for key, value in payload.model_dump().items():
        setattr(campus, key, value)
    db.commit()
    db.refresh(campus)
    return campus


@router.delete("/campuses/{campus_id}")
def delete_campus(campus_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    campus = require_campus(db, campus_id)
    db.delete(campus)
    db.commit()
    return {"ok": True}


@router.get("/degree-programs", response_model=list[DegreeProgramRead])
def list_degree_programs(db: Session = Depends(get_db)) -> list[DegreeProgram]:
    return db.query(DegreeProgram).order_by(DegreeProgram.name).all()


@router.post("/degree-programs", response_model=DegreeProgramRead)
def create_degree_program(
    payload: DegreeProgramCreate, db: Session = Depends(get_db)
) -> DegreeProgram:
    if payload.campus_id and not db.get(Campus, payload.campus_id):
        raise HTTPException(status_code=404, detail="Campus nao encontrado")
    degree_program = DegreeProgram(**payload.model_dump())
    db.add(degree_program)
    db.commit()
    db.refresh(degree_program)
    return degree_program


@router.get("/degree-programs/{degree_program_id}", response_model=DegreeProgramRead)
def get_degree_program(
    degree_program_id: str, db: Session = Depends(get_db)
) -> DegreeProgram:
    return require_degree_program(db, degree_program_id)


@router.put("/degree-programs/{degree_program_id}", response_model=DegreeProgramRead)
def update_degree_program(
    degree_program_id: str,
    payload: DegreeProgramCreate,
    db: Session = Depends(get_db),
) -> DegreeProgram:
    if payload.campus_id and not db.get(Campus, payload.campus_id):
        raise HTTPException(status_code=404, detail="Campus nao encontrado")
    degree_program = require_degree_program(db, degree_program_id)
    for key, value in payload.model_dump().items():
        setattr(degree_program, key, value)
    db.commit()
    db.refresh(degree_program)
    return degree_program


@router.delete("/degree-programs/{degree_program_id}")
def delete_degree_program(
    degree_program_id: str, db: Session = Depends(get_db)
) -> dict[str, bool]:
    degree_program = require_degree_program(db, degree_program_id)
    db.delete(degree_program)
    db.commit()
    return {"ok": True}


def require_campus(db: Session, campus_id: str) -> Campus:
    campus = db.get(Campus, campus_id)
    if not campus:
        raise HTTPException(status_code=404, detail="Campus nao encontrado")
    return campus


def require_degree_program(db: Session, degree_program_id: str) -> DegreeProgram:
    degree_program = db.get(DegreeProgram, degree_program_id)
    if not degree_program:
        raise HTTPException(status_code=404, detail="Curso nao encontrado")
    return degree_program
