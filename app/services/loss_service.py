from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional, Tuple
from datetime import datetime, date, timedelta
import json

from app import models
from app.schemas import schemas
from app.config import settings


def calculate_store_loss_rate(
    db: Session,
    store_id: int,
    start_date: date,
    end_date: date
) -> schemas.StoreLossRate:
    store = db.query(models.Store).filter(models.Store.id == store_id).first()
    if not store:
        raise ValueError("Store not found")

    total_loss = db.query(
        func.sum(models.LossReport.amount)
    ).filter(
        models.LossReport.store_id == store_id,
        models.LossReport.report_time >= start_date,
        models.LossReport.report_time <= end_date,
        models.LossReport.status == "approved"
    ).scalar() or 0.0

    total_sales = 100000.0

    loss_rate = (total_loss / total_sales * 100) if total_sales > 0 else 0.0

    prev_start = start_date - timedelta(days=30)
    prev_end = start_date - timedelta(days=1)
    prev_loss = db.query(
        func.sum(models.LossReport.amount)
    ).filter(
        models.LossReport.store_id == store_id,
        models.LossReport.report_time >= prev_start,
        models.LossReport.report_time <= prev_end,
        models.LossReport.status == "approved"
    ).scalar() or 0.0
    prev_loss_rate = (prev_loss / total_sales * 100) if total_sales > 0 else 0.0

    trend = loss_rate - prev_loss_rate
    threshold = get_threshold_value(db, "loss_rate_threshold", settings.DEFAULT_LOSS_RATE_THRESHOLD)

    return schemas.StoreLossRate(
        store_id=store_id,
        store_name=store.name,
        region=store.region or "",
        period="monthly",
        start_date=start_date,
        end_date=end_date,
        total_sales=total_sales,
        total_loss_amount=total_loss,
        loss_rate=round(loss_rate, 2),
        loss_rate_trend=round(trend, 2),
        threshold=threshold,
        is_exceeded=loss_rate > threshold
    )


def calculate_all_stores_loss_rate(
    db: Session,
    start_date: date,
    end_date: date,
    region: Optional[str] = None
) -> List[schemas.StoreLossRate]:
    query = db.query(models.Store).filter(models.Store.is_active == True)
    if region:
        query = query.filter(models.Store.region == region)
    
    stores = query.all()
    results = []
    for store in stores:
        try:
            result = calculate_store_loss_rate(db, store.id, start_date, end_date)
            results.append(result)
        except Exception:
            continue
    return results


def identify_high_frequency_products(
    db: Session,
    store_id: Optional[int] = None,
    days: int = 30,
    min_count: int = 5
) -> List[schemas.HighFreqProduct]:
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(
        models.LossReport.product_id,
        models.Product.name,
        models.Product.sku,
        models.Product.category,
        func.count(models.LossReport.id).label("report_count"),
        func.sum(models.LossReport.quantity).label("total_quantity"),
        func.sum(models.LossReport.amount).label("total_amount")
    ).join(
        models.Product, models.LossReport.product_id == models.Product.id
    ).filter(
        models.LossReport.report_time >= start_date,
        models.LossReport.status == "approved"
    )
    
    if store_id:
        query = query.filter(models.LossReport.store_id == store_id)
    
    query = query.group_by(
        models.LossReport.product_id,
        models.Product.name,
        models.Product.sku,
        models.Product.category
    ).having(
        func.count(models.LossReport.id) >= min_count
    ).order_by(
        func.count(models.LossReport.id).desc()
    ).limit(50).all()

    results = []
    months = days / 30.0
    for row in query:
        avg_monthly = row.report_count / months if months > 0 else 0
        
        if row.report_count >= 15:
            risk_level = "high"
        elif row.report_count >= 8:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        results.append(schemas.HighFreqProduct(
            product_id=row.product_id,
            product_name=row.name,
            sku=row.sku,
            category=row.category or "",
            report_count=row.report_count,
            total_quantity=row.total_quantity or 0.0,
            total_amount=row.total_amount or 0.0,
            avg_monthly_count=round(avg_monthly, 1),
            risk_level=risk_level
        ))
    
    return results


def calculate_product_risk_score(
    db: Session,
    product_id: int,
    store_id: Optional[int] = None,
    days: int = 90
) -> schemas.ProductRiskScore:
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise ValueError("Product not found")

    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(models.LossReport).filter(
        models.LossReport.product_id == product_id,
        models.LossReport.report_time >= start_date,
        models.LossReport.status == "approved"
    )
    
    if store_id:
        query = query.filter(models.LossReport.store_id == store_id)
    
    reports = query.all()
    report_count = len(reports)
    
    loss_amount = sum(r.amount for r in reports)
    loss_rate = min(loss_amount / 10000 * 100, 100) if loss_amount > 0 else 0
    
    reason_query = db.query(
        models.LossReason.name,
        func.count(models.LossReport.id).label("cnt")
    ).join(
        models.LossReport, models.LossReport.reason_id == models.LossReason.id
    ).filter(
        models.LossReport.product_id == product_id,
        models.LossReport.report_time >= start_date,
        models.LossReport.status == "approved"
    ).group_by(
        models.LossReason.name
    ).order_by(func.count(models.LossReport.id).desc()).limit(5).all()
    
    main_reasons = [r.name for r in reason_query]
    last_report = max((r.report_time for r in reports), default=None)
    
    frequency_score = min(report_count * 5, 40)
    amount_score = min(loss_rate * 3, 30)
    recency_score = 0
    if last_report:
        days_since = (datetime.utcnow() - last_report).days
        recency_score = max(0, 30 - days_since)
    variety_score = min(len(main_reasons) * 5, 10)
    
    risk_score = frequency_score + amount_score + recency_score + variety_score
    risk_score = min(risk_score, 100)
    
    if risk_score >= 70:
        risk_level = "high"
    elif risk_score >= 40:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    return schemas.ProductRiskScore(
        product_id=product_id,
        product_name=product.name,
        sku=product.sku,
        category=product.category or "",
        risk_score=round(risk_score, 1),
        risk_level=risk_level,
        loss_rate=round(loss_rate, 2),
        report_count=report_count,
        last_report_time=last_report,
        main_reasons=main_reasons
    )


def calculate_all_products_risk_score(
    db: Session,
    store_id: Optional[int] = None,
    category: Optional[str] = None,
    min_score: float = 0.0,
    limit: int = 100
) -> List[schemas.ProductRiskScore]:
    query = db.query(models.Product).filter(models.Product.is_active == True)
    if category:
        query = query.filter(models.Product.category == category)
    
    products = query.limit(limit).all()
    results = []
    for product in products:
        try:
            score = calculate_product_risk_score(db, product.id, store_id)
            if score.risk_score >= min_score:
                results.append(score)
        except Exception:
            continue
    
    results.sort(key=lambda x: x.risk_score, reverse=True)
    return results


def get_loss_categories_statistics(
    db: Session,
    start_date: date,
    end_date: date,
    store_id: Optional[int] = None,
    region: Optional[str] = None
) -> List[schemas.LossCategoryStat]:
    query = db.query(
        models.LossReason.id,
        models.LossReason.code,
        models.LossReason.name,
        models.LossReason.category,
        func.count(models.LossReport.id).label("report_count"),
        func.sum(models.LossReport.quantity).label("total_quantity"),
        func.sum(models.LossReport.amount).label("total_amount")
    ).join(
        models.LossReport, models.LossReport.reason_id == models.LossReason.id
    ).filter(
        models.LossReport.report_time >= start_date,
        models.LossReport.report_time <= end_date,
        models.LossReport.status == "approved"
    )
    
    if store_id:
        query = query.filter(models.LossReport.store_id == store_id)
    elif region:
        query = query.join(models.Store, models.LossReport.store_id == models.Store.id)
        query = query.filter(models.Store.region == region)
    
    query = query.group_by(
        models.LossReason.id,
        models.LossReason.code,
        models.LossReason.name,
        models.LossReason.category
    ).all()

    total_amount = sum(row.total_amount or 0 for row in query)
    
    results = []
    for row in query:
        percentage = (row.total_amount / total_amount * 100) if total_amount > 0 else 0.0
        results.append(schemas.LossCategoryStat(
            reason_id=row.id,
            reason_code=row.code,
            reason_name=row.name,
            category=row.category or "",
            report_count=row.report_count,
            total_quantity=row.total_quantity or 0.0,
            total_amount=row.total_amount or 0.0,
            percentage=round(percentage, 2)
        ))
    
    results.sort(key=lambda x: x.total_amount, reverse=True)
    return results


def get_trend_data(
    db: Session,
    store_id: Optional[int] = None,
    region: Optional[str] = None,
    period: str = "monthly",
    days: int = 180
) -> List[schemas.TrendDataPoint]:
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    if period == "daily":
        interval = 1
    elif period == "weekly":
        interval = 7
    else:
        interval = 30
    
    results = []
    current_start = start_date
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=interval - 1), end_date)
        
        query = db.query(
            func.sum(models.LossReport.amount).label("amount"),
            func.sum(models.LossReport.quantity).label("quantity"),
            func.count(models.LossReport.id).label("count")
        ).filter(
            models.LossReport.report_time >= current_start,
            models.LossReport.report_time <= current_end,
            models.LossReport.status == "approved"
        )
        
        if store_id:
            query = query.filter(models.LossReport.store_id == store_id)
        elif region:
            query = query.join(models.Store, models.LossReport.store_id == models.Store.id)
            query = query.filter(models.Store.region == region)
        
        row = query.first()
        
        total_sales = 100000.0
        loss_rate = (row.amount / total_sales * 100) if row.amount and total_sales > 0 else 0.0
        
        results.append(schemas.TrendDataPoint(
            date=current_start,
            loss_amount=row.amount or 0.0,
            loss_quantity=row.quantity or 0.0,
            loss_rate=round(loss_rate, 2),
            report_count=row.count or 0
        ))
        
        current_start = current_end + timedelta(days=1)
    
    return results


def get_regional_ranking(
    db: Session,
    start_date: date,
    end_date: date
) -> List[schemas.RegionalRanking]:
    query = db.query(
        models.Store.region,
        func.count(models.Store.id).label("store_count"),
        func.sum(models.LossReport.amount).label("total_loss")
    ).join(
        models.LossReport, models.Store.id == models.LossReport.store_id, isouter=True
    ).filter(
        models.Store.is_active == True,
        or_(
            models.LossReport.report_time.is_(None),
            and_(
                models.LossReport.report_time >= start_date,
                models.LossReport.report_time <= end_date,
                models.LossReport.status == "approved"
            )
        )
    ).group_by(models.Store.region).all()

    results = []
    for row in query:
        region = row.region or "未分配"
        store_loss_rates = []
        best_store = ""
        worst_store = ""
        best_rate = float('inf')
        worst_rate = float('-inf')
        
        stores = db.query(models.Store).filter(
            models.Store.region == (row.region or ""),
            models.Store.is_active == True
        ).all()
        
        for store in stores:
            try:
                lr = calculate_store_loss_rate(db, store.id, start_date, end_date)
                store_loss_rates.append(lr.loss_rate)
                if lr.loss_rate < best_rate:
                    best_rate = lr.loss_rate
                    best_store = store.name
                if lr.loss_rate > worst_rate:
                    worst_rate = lr.loss_rate
                    worst_store = store.name
            except Exception:
                continue
        
        avg_rate = sum(store_loss_rates) / len(store_loss_rates) if store_loss_rates else 0.0
        
        results.append(schemas.RegionalRanking(
            region=region,
            store_count=row.store_count,
            total_loss_amount=row.total_loss or 0.0,
            avg_loss_rate=round(avg_rate, 2),
            best_store=best_store,
            worst_store=worst_store,
            ranking=0
        ))
    
    results.sort(key=lambda x: x.avg_loss_rate)
    for i, r in enumerate(results):
        r.ranking = i + 1
    
    return results


def get_stores_comparison(
    db: Session,
    start_date: date,
    end_date: date,
    region: Optional[str] = None
) -> List[schemas.StoreComparison]:
    query = db.query(models.Store).filter(models.Store.is_active == True)
    if region:
        query = query.filter(models.Store.region == region)
    
    stores = query.all()
    
    prev_start = start_date - timedelta(days=(end_date - start_date).days + 1)
    prev_end = start_date - timedelta(days=1)
    
    results = []
    for store in stores:
        current_data = db.query(
            func.sum(models.LossReport.amount).label("amount"),
            func.sum(models.LossReport.quantity).label("quantity"),
            func.count(models.LossReport.id).label("count")
        ).filter(
            models.LossReport.store_id == store.id,
            models.LossReport.report_time >= start_date,
            models.LossReport.report_time <= end_date,
            models.LossReport.status == "approved"
        ).first()
        
        prev_data = db.query(
            func.sum(models.LossReport.amount).label("amount")
        ).filter(
            models.LossReport.store_id == store.id,
            models.LossReport.report_time >= prev_start,
            models.LossReport.report_time <= prev_end,
            models.LossReport.status == "approved"
        ).first()
        
        high_freq_count = db.query(func.count(func.distinct(models.LossReport.product_id))).filter(
            models.LossReport.store_id == store.id,
            models.LossReport.report_time >= start_date,
            models.LossReport.report_time <= end_date,
            models.LossReport.is_high_frequency == True,
            models.LossReport.status == "approved"
        ).scalar() or 0
        
        total_sales = 100000.0
        current_amount = current_data.amount or 0.0
        prev_amount = prev_data.amount or 0.0
        
        loss_rate = (current_amount / total_sales * 100) if total_sales > 0 else 0.0
        
        if prev_amount > 0:
            change_pct = (current_amount - prev_amount) / prev_amount * 100
            if change_pct > 10:
                trend = "up"
            elif change_pct < -10:
                trend = "down"
            else:
                trend = "stable"
        else:
            trend = "stable" if current_amount == 0 else "up"
        
        results.append(schemas.StoreComparison(
            store_id=store.id,
            store_name=store.name,
            region=store.region or "",
            loss_amount=current_amount,
            loss_quantity=current_data.quantity or 0.0,
            loss_rate=round(loss_rate, 2),
            report_count=current_data.count or 0,
            high_freq_count=high_freq_count,
            ranking=0,
            trend=trend
        ))
    
    results.sort(key=lambda x: x.loss_rate, reverse=True)
    for i, r in enumerate(results):
        r.ranking = i + 1
    
    return results


def generate_correction_list(
    db: Session,
    store_id: Optional[int] = None,
    region: Optional[str] = None,
    priority: Optional[str] = None
) -> List[schemas.CorrectionItem]:
    items = []
    
    high_freq_products = identify_high_frequency_products(db, store_id=store_id, days=30, min_count=3)
    
    for i, product in enumerate(high_freq_products[:5]):
        if product.risk_level == "high":
            prio = "high"
        elif product.risk_level == "medium":
            prio = "medium"
        else:
            prio = "low"
        
        if priority and prio != priority:
            continue
        
        items.append(schemas.CorrectionItem(
            action_no=f"CORR-HF-{i+1:04d}",
            title=f"高频损耗商品整改: {product.product_name}",
            description=f"该商品近30天报损{product.report_count}次，累计金额{product.total_amount:.2f}元。建议检查库存管理、陈列方式和保质期管控。",
            priority=prio,
            category="high_frequency",
            responsible_person="门店主管",
            deadline=date.today() + timedelta(days=7),
            expected_effect=f"预计降低{product.product_name}损耗率30%",
            related_product=product.sku,
            related_store=str(store_id) if store_id else None
        ))
    
    expiring_items = get_expiry_reminders(db, store_id=store_id, region=region, days=7)
    for i, item in enumerate(expiring_items[:5]):
        if priority and priority != "high":
            if item.days_to_expiry <= 3:
                prio = "high"
            elif item.days_to_expiry <= 7:
                prio = "medium"
            else:
                prio = "low"
            if prio != priority:
                continue
        else:
            prio = "high" if item.days_to_expiry <= 3 else "medium"
        
        items.append(schemas.CorrectionItem(
            action_no=f"CORR-EXP-{i+1:04d}",
            title=f"临期商品处理: {item.product_name}",
            description=f"批次{item.batch_no}共{item.quantity}件将于{str(item.expiry_date)}到期（还有{item.days_to_expiry}天）。{item.suggested_action}",
            priority=prio,
            category="expiry",
            responsible_person="理货员",
            deadline=date.today() + timedelta(days=min(item.days_to_expiry, 7)),
            expected_effect=f"预计减少损失{item.estimated_loss:.2f}元",
            related_product=item.sku,
            related_store=str(item.store_id)
        ))
    
    shortage_items = get_shortage_abnormalities(db, store_id=store_id, days=30)
    for i, item in enumerate(shortage_items[:5]):
        prio = "high" if item.shortage_rate >= 5 else "medium"
        
        if priority and prio != priority:
            continue
        
        items.append(schemas.CorrectionItem(
            action_no=f"CORR-SH-{i+1:04d}",
            title=f"盘亏异常核查: {item.product_name}",
            description=f"{item.store_name}盘点{item.product_name}，系统库存{item.system_quantity}，实际库存{item.actual_quantity}，盘亏{item.shortage_quantity}，盘亏率{item.shortage_rate:.2f}%（阈值{item.threshold}%）。",
            priority=prio,
            category="shortage",
            responsible_person="防损员",
            deadline=date.today() + timedelta(days=3),
            expected_effect="查明盘亏原因，完善库存管理流程",
            related_product=item.sku,
            related_store=str(item.store_id)
        ))
    
    items.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x.priority])
    return items


def get_threshold_value(db: Session, config_key: str, default: float) -> float:
    config = db.query(models.ThresholdConfig).filter(
        models.ThresholdConfig.config_key == config_key
    ).first()
    return config.config_value if config else default


def get_expiry_reminders(db, store_id=None, region=None, days=7):
    from app.services.warning_service import get_expiry_reminders as ger
    return ger(db, store_id, region, days)


def get_shortage_abnormalities(db, store_id=None, days=30):
    from app.services.warning_service import get_shortage_abnormalities as gsa
    return gsa(db, store_id, days)
