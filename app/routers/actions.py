from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta

from app.database import get_db
from app.schemas import schemas
from app.services import crud, report_service
from app import models

router = APIRouter(prefix="/actions", tags=["动作管理"])


@router.post("", response_model=schemas.ActionRecord, summary="记录处理动作")
def create_action(
    action_in: schemas.ActionRecordCreate,
    db: Session = Depends(get_db)
):
    return crud.action_record.create(db, obj_in=action_in)


@router.get("", response_model=List[schemas.ActionRecord], summary="查询处理动作列表")
def get_actions(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    action_type: Optional[str] = None,
    responsible_person: Optional[str] = None,
    deadline_from: Optional[date] = None,
    deadline_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(models.ActionRecord)
    
    if status:
        query = query.filter(models.ActionRecord.status == status)
    if priority:
        query = query.filter(models.ActionRecord.priority == priority)
    if action_type:
        query = query.filter(models.ActionRecord.action_type == action_type)
    if responsible_person:
        query = query.filter(models.ActionRecord.responsible_person == responsible_person)
    if deadline_from:
        query = query.filter(models.ActionRecord.deadline >= deadline_from)
    if deadline_to:
        query = query.filter(models.ActionRecord.deadline <= deadline_to)
    
    return query.order_by(models.ActionRecord.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{action_id}", response_model=schemas.ActionRecord, summary="获取动作详情")
def get_action(
    action_id: int,
    db: Session = Depends(get_db)
):
    action = crud.action_record.get(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="动作记录不存在")
    return action


@router.put("/{action_id}/complete", response_model=schemas.ActionRecord, summary="完成处理动作")
def complete_action(
    action_id: int,
    complete_in: schemas.ActionRecordComplete,
    db: Session = Depends(get_db)
):
    action = crud.action_record.get(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="动作记录不存在")
    
    return crud.action_record.complete(db, db_obj=action, obj_in=complete_in)
