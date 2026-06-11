from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta

from app.database import get_db
from app.schemas import schemas
from app.services import warning_service, crud
from app import models

router = APIRouter(prefix="/warning", tags=["预警管理"])


@router.get("/expiry-reminders", response_model=List[schemas.ExpiryReminder], summary="临期提醒")
def get_expiry_reminders(
    store_id: Optional[int] = None,
    region: Optional[str] = None,
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    return warning_service.get_expiry_reminders(db, store_id, region, days)


@router.get("/expiry-suggestions", summary="推送临期清理建议")
def get_expiry_suggestions(
    store_id: Optional[int] = None,
    days: int = Query(14, ge=1, le=60),
    db: Session = Depends(get_db)
):
    return warning_service.generate_expiry_suggestions(db, store_id, days)


@router.get("/shortage-abnormalities", response_model=List[schemas.ShortageAbnormality], summary="盘亏异常")
def get_shortage_abnormalities(
    store_id: Optional[int] = None,
    days: int = Query(30, ge=1, le=180),
    db: Session = Depends(get_db)
):
    return warning_service.get_shortage_abnormalities(db, store_id, days)


@router.post("/inventory-check", response_model=schemas.InventoryCheck, summary="提交盘点记录")
def create_inventory_check(
    check_in: schemas.InventoryCheckCreate,
    db: Session = Depends(get_db)
):
    return crud.inventory_check.create(db, obj_in=check_in)


@router.get("/alerts", response_model=List[schemas.WarningAlert], summary="查询预警列表")
def get_warning_alerts(
    alert_type: Optional[str] = None,
    level: Optional[str] = None,
    is_handled: Optional[bool] = None,
    store_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(models.WarningAlert)
    
    if alert_type:
        query = query.filter(models.WarningAlert.alert_type == alert_type)
    if level:
        query = query.filter(models.WarningAlert.level == level)
    if is_handled is not None:
        query = query.filter(models.WarningAlert.is_handled == is_handled)
    if store_id:
        query = query.filter(models.WarningAlert.store_id == store_id)
    if start_date:
        query = query.filter(models.WarningAlert.created_at >= start_date)
    if end_date:
        query = query.filter(models.WarningAlert.created_at <= end_date)
    
    return query.order_by(models.WarningAlert.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/alerts/{alert_id}", response_model=schemas.WarningAlert, summary="预警详情")
def get_alert_detail(
    alert_id: int,
    db: Session = Depends(get_db)
):
    alert = crud.warning_alert.get(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="预警不存在")
    return alert


@router.put("/alerts/{alert_id}/handle", response_model=schemas.WarningAlert, summary="处理预警")
def handle_alert(
    alert_id: int,
    handle_in: schemas.WarningAlertHandle,
    db: Session = Depends(get_db)
):
    alert = crud.warning_alert.get(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="预警不存在")
    
    return crud.warning_alert.handle(db, db_obj=alert, obj_in=handle_in)


@router.post("/run-checks", summary="立即执行预警检查")
def run_warning_checks(
    db: Session = Depends(get_db)
):
    return warning_service.run_all_alert_checks(db)


@router.get("/subscriptions", response_model=List[schemas.WarningSubscription], summary="获取预警订阅列表")
def get_subscriptions(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.WarningSubscription)
    if is_active is not None:
        query = query.filter(models.WarningSubscription.is_active == is_active)
    return query.all()


@router.post("/subscriptions", response_model=schemas.WarningSubscription, summary="预警订阅")
def create_subscription(
    sub_in: schemas.WarningSubscriptionCreate,
    db: Session = Depends(get_db)
):
    return crud.warning_subscription.create(db, obj_in=sub_in)


@router.put("/subscriptions/{sub_id}", response_model=schemas.WarningSubscription, summary="更新订阅")
def update_subscription(
    sub_id: int,
    sub_in: schemas.WarningSubscriptionCreate,
    db: Session = Depends(get_db)
):
    sub = crud.warning_subscription.get(db, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    return crud.warning_subscription.update(db, db_obj=sub, obj_in=sub_in)


@router.post("/subscriptions/{sub_id}/toggle", response_model=schemas.WarningSubscription, summary="启用/禁用订阅")
def toggle_subscription(
    sub_id: int,
    db: Session = Depends(get_db)
):
    sub = crud.warning_subscription.get(db, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    
    sub.is_active = not sub.is_active
    db.commit()
    db.refresh(sub)
    return sub
