from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta

from app.database import get_db
from app.schemas import schemas
from app.services import loss_service, crud

router = APIRouter(prefix="/loss", tags=["损耗管理"])


@router.get("/rate/store/{store_id}", response_model=schemas.StoreLossRate, summary="按门店计算损耗率")
def get_store_loss_rate(
    store_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    try:
        return loss_service.calculate_store_loss_rate(db, store_id, start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/rate/stores", response_model=List[schemas.StoreLossRate], summary="获取所有门店损耗率")
def get_all_stores_loss_rate(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    region: Optional[str] = None,
    db: Session = Depends(get_db)
):
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    return loss_service.calculate_all_stores_loss_rate(db, start_date, end_date, region)


@router.get("/high-frequency", response_model=List[schemas.HighFreqProduct], summary="识别高频报损商品")
def get_high_frequency_products(
    store_id: Optional[int] = None,
    days: int = Query(30, ge=1, le=365),
    min_count: int = Query(3, ge=1),
    db: Session = Depends(get_db)
):
    return loss_service.identify_high_frequency_products(db, store_id, days, min_count)


@router.get("/risk-score/{product_id}", response_model=schemas.ProductRiskScore, summary="商品损耗评分")
def get_product_risk_score(
    product_id: int,
    store_id: Optional[int] = None,
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db)
):
    try:
        return loss_service.calculate_product_risk_score(db, product_id, store_id, days)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/risk-scores", response_model=List[schemas.ProductRiskScore], summary="批量商品损耗评分")
def get_products_risk_scores(
    store_id: Optional[int] = None,
    category: Optional[str] = None,
    min_score: float = Query(0.0, ge=0.0, le=100.0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    return loss_service.calculate_all_products_risk_score(db, store_id, category, min_score, limit)


@router.get("/categories", response_model=List[schemas.LossCategoryStat], summary="原因归类统计")
def get_loss_categories(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    store_id: Optional[int] = None,
    region: Optional[str] = None,
    db: Session = Depends(get_db)
):
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    return loss_service.get_loss_categories_statistics(db, start_date, end_date, store_id, region)


@router.get("/trend", response_model=List[schemas.TrendDataPoint], summary="查询历史趋势")
def get_trend_data(
    store_id: Optional[int] = None,
    region: Optional[str] = None,
    period: str = Query("monthly", regex="^(daily|weekly|monthly)$"),
    days: int = Query(180, ge=7, le=730),
    db: Session = Depends(get_db)
):
    return loss_service.get_trend_data(db, store_id, region, period, days)


@router.get("/regional-ranking", response_model=List[schemas.RegionalRanking], summary="输出区域排行榜")
def get_regional_ranking(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    return loss_service.get_regional_ranking(db, start_date, end_date)


@router.get("/store-comparison", response_model=List[schemas.StoreComparison], summary="门店对比")
def get_store_comparison(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    region: Optional[str] = None,
    db: Session = Depends(get_db)
):
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    return loss_service.get_stores_comparison(db, start_date, end_date, region)


@router.get("/correction-list", response_model=List[schemas.CorrectionItem], summary="返回可执行的整改清单")
def get_correction_list(
    store_id: Optional[int] = None,
    region: Optional[str] = None,
    priority: Optional[str] = Query(None, regex="^(high|medium|low)$"),
    db: Session = Depends(get_db)
):
    return loss_service.generate_correction_list(db, store_id, region, priority)


@router.post("/report", response_model=schemas.LossReport, summary="报损提交")
def create_loss_report(
    report_in: schemas.LossReportCreate,
    db: Session = Depends(get_db)
):
    return crud.loss_report.create(db, obj_in=report_in)


@router.get("/reports", response_model=List[schemas.LossReport], summary="查询报损记录")
def get_loss_reports(
    store_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(models.LossReport)
    
    if store_id:
        query = query.filter(models.LossReport.store_id == store_id)
    if status:
        query = query.filter(models.LossReport.status == status)
    if start_date:
        query = query.filter(models.LossReport.report_time >= start_date)
    if end_date:
        query = query.filter(models.LossReport.report_time <= end_date)
    
    return query.order_by(models.LossReport.report_time.desc()).offset(skip).limit(limit).all()


@router.put("/report/{report_id}/review", response_model=schemas.LossReport, summary="接收人工复核结果")
def review_loss_report(
    report_id: int,
    review_in: schemas.LossReportReview,
    db: Session = Depends(get_db)
):
    report = crud.loss_report.get(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报损记录不存在")
    
    return crud.loss_report.review(db, db_obj=report, obj_in=review_in)


from app import models
