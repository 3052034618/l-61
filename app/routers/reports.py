from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.database import get_db
from app.schemas import schemas
from app.services import report_service, loss_service, crud
from app import models

router = APIRouter(prefix="/reports", tags=["报表管理"])


@router.get("/weekly", response_model=List[schemas.WeeklyReportSummary], summary="查询周报历史")
def get_weekly_reports(
    region: Optional[str] = None,
    store_id: Optional[int] = None,
    limit: int = Query(12, ge=1, le=52),
    db: Session = Depends(get_db)
):
    return report_service.get_weekly_report_history(db, region, store_id, limit)


@router.post("/weekly/generate", response_model=schemas.WeeklyReportSummary, summary="生成周报摘要")
def generate_weekly_report(
    region: Optional[str] = None,
    store_id: Optional[int] = None,
    week_offset: int = Query(0, ge=0, le=12),
    db: Session = Depends(get_db)
):
    return report_service.generate_weekly_summary(db, region, store_id, week_offset)


@router.post("/weekly/generate-all", summary="批量生成所有周报")
def generate_all_weekly_reports(
    db: Session = Depends(get_db)
):
    return report_service.generate_all_weekly_reports(db)


@router.post("/sales", response_model=schemas.StoreSales, summary="录入门店销售额")
def create_store_sales(
    sales_in: schemas.StoreSalesCreate,
    db: Session = Depends(get_db)
):
    try:
        return loss_service.create_store_sales(db, sales_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sales", response_model=List[schemas.StoreSales], summary="查询门店销售额")
def get_store_sales(
    store_id: Optional[int] = None,
    region: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    return loss_service.get_store_sales_records(db, store_id, region, start_date, end_date, skip, limit)


@router.get("/stores", response_model=List[schemas.Store], summary="查询门店列表")
def get_stores(
    region: Optional[str] = None,
    is_active: Optional[bool] = True,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(models.Store)
    if region:
        query = query.filter(models.Store.region == region)
    if is_active is not None:
        query = query.filter(models.Store.is_active == is_active)
    return query.offset(skip).limit(limit).all()


@router.get("/products", response_model=List[schemas.Product], summary="查询商品列表")
def get_products(
    category: Optional[str] = None,
    sku: Optional[str] = None,
    is_active: Optional[bool] = True,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(models.Product)
    if category:
        query = query.filter(models.Product.category == category)
    if sku:
        query = query.filter(models.Product.sku.contains(sku))
    if is_active is not None:
        query = query.filter(models.Product.is_active == is_active)
    return query.offset(skip).limit(limit).all()


@router.get("/reasons", response_model=List[schemas.LossReason], summary="查询损耗原因列表")
def get_loss_reasons(
    category: Optional[str] = None,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    query = db.query(models.LossReason)
    if category:
        query = query.filter(models.LossReason.category == category)
    if is_active is not None:
        query = query.filter(models.LossReason.is_active == is_active)
    return query.all()


@router.post("/stores", response_model=schemas.Store, summary="创建门店")
def create_store(
    store_in: schemas.StoreCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(models.Store).filter(models.Store.code == store_in.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="门店编码已存在")
    return crud.store.create(db, obj_in=store_in)


@router.post("/products", response_model=schemas.Product, summary="创建商品")
def create_product(
    product_in: schemas.ProductCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(models.Product).filter(models.Product.sku == product_in.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="商品SKU已存在")
    return crud.product.create(db, obj_in=product_in)


@router.post("/reasons", response_model=schemas.LossReason, summary="创建损耗原因")
def create_loss_reason(
    reason_in: schemas.LossReasonCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(models.LossReason).filter(models.LossReason.code == reason_in.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="原因编码已存在")
    return crud.loss_reason.create(db, obj_in=reason_in)
