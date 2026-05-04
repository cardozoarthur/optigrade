from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Campus, Room
from app.schemas import RoomCreate, RoomRead

router = APIRouter()


@router.get("", response_model=list[RoomRead])
def list_rooms(db: Session = Depends(get_db)) -> list[Room]:
    return db.query(Room).order_by(Room.name).all()


@router.post("", response_model=RoomRead)
def create_room(payload: RoomCreate, db: Session = Depends(get_db)) -> Room:
    validate_room_refs(db, payload)
    room = Room(**payload.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.put("/{room_id}", response_model=RoomRead)
def update_room(room_id: str, payload: RoomCreate, db: Session = Depends(get_db)) -> Room:
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Sala nao encontrada")
    validate_room_refs(db, payload)
    for key, value in payload.model_dump().items():
        setattr(room, key, value)
    db.commit()
    db.refresh(room)
    return room


@router.delete("/{room_id}")
def delete_room(room_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Sala nao encontrada")
    db.delete(room)
    db.commit()
    return {"ok": True}


def validate_room_refs(db: Session, payload: RoomCreate) -> None:
    if payload.campus_id and not db.get(Campus, payload.campus_id):
        raise HTTPException(status_code=404, detail="Campus nao encontrado")
