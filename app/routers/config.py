from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.database import get_db
from app.schemas import schemas
from app.services import crud, report_service
from app import models

router = APIRouter(prefix="/config", tags=["配置管理"])


@router.get("/thresholds", response_model=List[schemas.ThresholdConfig], summary="获取所有阈值配置")
def get_thresholds(
    db: Session = Depends(get_db)
):
    return crud.threshold_config.get_all(db)


@router.get("/thresholds/{config_key}", response_model=schemas.ThresholdConfig, summary="获取单个阈值配置")
def get_threshold(
    config_key: str,
    db: Session = Depends(get_db)
):
    config = crud.threshold_config.get_by_key(db, config_key)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return config


@router.put("/thresholds/{config_key}", response_model=schemas.ThresholdConfig, summary="设置阈值")
def set_threshold(
    config_key: str,
    value: float = Query(..., gt=0),
    config_name: Optional[str] = None,
    description: Optional[str] = None,
    unit: Optional[str] = None,
    updated_by: Optional[str] = None,
    db: Session = Depends(get_db)
):
    return crud.threshold_config.set_value(
        db,
        key=config_key,
        value=value,
        name=config_name,
        description=description,
        unit=unit,
        updated_by=updated_by
    )


@router.post("/thresholds", response_model=schemas.ThresholdConfig, summary="创建阈值配置")
def create_threshold(
    config_in: schemas.ThresholdConfigCreate,
    db: Session = Depends(get_db)
):
    existing = crud.threshold_config.get_by_key(db, config_in.config_key)
    if existing:
        raise HTTPException(status_code=400, detail="配置键已存在")
    return crud.threshold_config.create(db, obj_in=config_in)
