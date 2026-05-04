from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import TimeSlot
from app.schemas import TimeSlotCreate, TimeSlotRead

router = APIRouter()


@router.get("", response_model=list[TimeSlotRead])
def list_time_slots(db: Session = Depends(get_db)) -> list[TimeSlot]:
    return db.query(TimeSlot).order_by(TimeSlot.day, TimeSlot.start_minute).all()


@router.post("", response_model=TimeSlotRead)
def create_time_slot(payload: TimeSlotCreate, db: Session = Depends(get_db)) -> TimeSlot:
    slot = TimeSlot(**payload.model_dump())
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


@router.put("/{slot_id}", response_model=TimeSlotRead)
def update_time_slot(slot_id: str, payload: TimeSlotCreate, db: Session = Depends(get_db)) -> TimeSlot:
    slot = db.get(TimeSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot nao encontrado")
    for key, value in payload.model_dump().items():
        setattr(slot, key, value)
    db.commit()
    db.refresh(slot)
    return slot


@router.delete("/{slot_id}")
def delete_time_slot(slot_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    slot = db.get(TimeSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot nao encontrado")
    db.delete(slot)
    db.commit()
    return {"ok": True}

