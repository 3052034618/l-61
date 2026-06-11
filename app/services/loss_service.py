from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional, Tuple
from datetime import datetime, date, timedelta, time
import json

from app import models
from app.schemas import schemas
from app.config import settings


def _to_datetime_start(d: date) -> datetime:
    return datetime.combine(d, time.min)


def _to_datetime_end(d: date) -> datetime:
    return datetime.combine(d, time.max)


def get_store_sales_amount(
    db: Session,
    store_id: int,
    start_date: date,
    end_date: date
) -> Optional[float]:
    result = db.query(
        func.sum(models.StoreSales.sales_amount)
    ).filter(
        models.StoreSales.store_id == store_id,
        models.StoreSales.sales_date >= start_date,
        models.StoreSales.sales_date <= end_date
    ).scalar()
    return result


def get_region_sales_amount(
    db: Session,
    region: Optional[str],
    start_date: date,
    end_date: date
) -> Optional[float]:
    query = db.query(
        func.sum(models.StoreSales.sales_amount)
    ).join(
        models.Store, models.StoreSales.store_id == models.Store.id
    ).filter(
        models.StoreSales.sales_date >= start_date,
        models.StoreSales.sales_date <= end_date,
        models.Store.is_active == True
    )
    
    if region:
        query = query.filter(models.Store.region == region)
    
    result = query.scalar()
    return result


def calculate_store_loss_rate(
    db: Session,
    store_id: int,
    start_date: date,
    end_date: date
) -> schemas.StoreLossRate:
    store = db.query(models.Store).filter(models.Store.id == store_id).first()
    if not store:
        raise ValueError("Store not found")

    base_query = db.query(
        func.sum(models.LossReport.amount).label("amount"),
        func.count(models.LossReport.id).label("count")
    ).filter(
        models.LossReport.store_id == store_id,
        models.LossReport.report_time >= _to_datetime_start(start_date),
        models.LossReport.report_time <= _to_datetime_end(end_date)
    )

    approved_data = base_query.filter(
        models.LossReport.status == "approved"
    ).first()

    pending_data = base_query.filter(
        models.LossReport.status == "pending"
    ).first()

    approved_loss = approved_data.amount or 0.0
    pending_loss = pending_data.amount or 0.0
    total_loss = approved_loss + pending_loss
    approved_count = approved_data.count or 0
    pending_count = pending_data.count or 0

    total_sales = get_store_sales_amount(db, store_id, start_date, end_date)
    has_sales_data = total_sales is not None and total_sales > 0

    note = None
    loss_rate = None
    is_exceeded = None

    if not has_sales_data:
        note = f"该时间段({start_date}至{end_date})无销售额数据，损耗率暂无法计算"
        if total_sales == 0:
            note = f"该时间段销售额为0，损耗率无法计算"
    else:
        loss_rate = (approved_loss / total_sales * 100)

    prev_start = start_date - timedelta(days=(end_date - start_date).days + 1)
    prev_end = start_date - timedelta(days=1)
    prev_loss = db.query(
        func.sum(models.LossReport.amount)
    ).filter(
        models.LossReport.store_id == store_id,
        models.LossReport.report_time >= _to_datetime_start(prev_start),
        models.LossReport.report_time <= _to_datetime_end(prev_end),
        models.LossReport.status == "approved"
    ).scalar() or 0.0

    prev_sales = get_store_sales_amount(db, store_id, prev_start, prev_end)
    prev_has_sales = prev_sales is not None and prev_sales > 0

    prev_loss_rate = None
    trend = None

    if prev_has_sales:
        prev_loss_rate = (prev_loss / prev_sales * 100)

    if loss_rate is not None and prev_loss_rate is not None:
        trend = loss_rate - prev_loss_rate

    threshold = get_threshold_value(db, "loss_rate_threshold", settings.DEFAULT_LOSS_RATE_THRESHOLD)

    if loss_rate is not None:
        is_exceeded = loss_rate > threshold

    data_note_parts = []
    data_note_parts.append(f"已纳入已审核报损{approved_count}笔，金额{approved_loss:.2f}元")
    if pending_count > 0:
        data_note_parts.append(f"待审核报损{pending_count}笔，金额{pending_loss:.2f}元（暂未纳入损耗率计算）")
    data_note = "；".join(data_note_parts)

    return schemas.StoreLossRate(
        store_id=store_id,
        store_name=store.name,
        region=store.region or "",
        period="custom",
        start_date=start_date,
        end_date=end_date,
        total_sales=total_sales,
        total_loss_amount=total_loss,
        approved_loss_amount=approved_loss,
        pending_loss_amount=pending_loss,
        loss_rate=round(loss_rate, 2) if loss_rate is not None else None,
        loss_rate_trend=round(trend, 2) if trend is not None else None,
        threshold=threshold,
        is_exceeded=is_exceeded,
        has_sales_data=has_sales_data,
        approved_report_count=approved_count,
        pending_report_count=pending_count,
        note=note,
        data_note=data_note
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
    region: Optional[str] = None,
    days: int = 30,
    min_count: int = 5
) -> List[schemas.HighFreqProduct]:
    start_date = datetime.utcnow() - timedelta(days=days)

    approved_query = db.query(
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
        approved_query = approved_query.filter(models.LossReport.store_id == store_id)
    elif region:
        approved_query = approved_query.join(models.Store, models.LossReport.store_id == models.Store.id)
        approved_query = approved_query.filter(models.Store.region == region)

    approved_query = approved_query.group_by(
        models.LossReport.product_id,
        models.Product.name,
        models.Product.sku,
        models.Product.category
    ).having(
        func.count(models.LossReport.id) >= min_count
    ).order_by(
        func.count(models.LossReport.id).desc()
    ).limit(50).all()

    product_ids = [row.product_id for row in approved_query]

    pending_stats = {}
    if product_ids:
        pending_query = db.query(
            models.LossReport.product_id,
            func.count(models.LossReport.id).label("count"),
            func.sum(models.LossReport.quantity).label("quantity"),
            func.sum(models.LossReport.amount).label("amount")
        ).filter(
            models.LossReport.product_id.in_(product_ids),
            models.LossReport.report_time >= start_date,
            models.LossReport.status == "pending"
        )
        if store_id:
            pending_query = pending_query.filter(models.LossReport.store_id == store_id)
        elif region:
            pending_query = pending_query.join(models.Store, models.LossReport.store_id == models.Store.id)
            pending_query = pending_query.filter(models.Store.region == region)

        pending_query = pending_query.group_by(models.LossReport.product_id).all()

        for row in pending_query:
            pending_stats[row.product_id] = {
                "count": row.count or 0,
                "quantity": row.quantity or 0.0,
                "amount": row.amount or 0.0
            }

    results = []
    months = days / 30.0
    for row in approved_query:
        avg_monthly = row.report_count / months if months > 0 else 0

        if row.report_count >= 15:
            risk_level = "high"
        elif row.report_count >= 8:
            risk_level = "medium"
        else:
            risk_level = "low"

        pending = pending_stats.get(row.product_id, {"count": 0, "quantity": 0.0, "amount": 0.0})
        approved_count = row.report_count
        approved_qty = row.total_quantity or 0.0
        approved_amt = row.total_amount or 0.0
        total_count = approved_count + pending["count"]
        total_qty = approved_qty + pending["quantity"]
        total_amt = approved_amt + pending["amount"]

        data_note_parts = []
        data_note_parts.append(f"已纳入已审核{approved_count}笔")
        if pending["count"] > 0:
            data_note_parts.append(f"待审核{pending['count']}笔（暂未纳入高频统计）")
        data_note = "；".join(data_note_parts)

        results.append(schemas.HighFreqProduct(
            product_id=row.product_id,
            product_name=row.name,
            sku=row.sku,
            category=row.category or "",
            report_count=total_count,
            approved_report_count=approved_count,
            pending_report_count=pending["count"],
            total_quantity=total_qty,
            approved_quantity=approved_qty,
            pending_quantity=pending["quantity"],
            total_amount=total_amt,
            approved_amount=approved_amt,
            pending_amount=pending["amount"],
            avg_monthly_count=round(avg_monthly, 1),
            risk_level=risk_level,
            data_note=data_note
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

    base_query = db.query(models.LossReport).filter(
        models.LossReport.product_id == product_id,
        models.LossReport.report_time >= start_date
    )

    if store_id:
        base_query = base_query.filter(models.LossReport.store_id == store_id)

    approved_reports = base_query.filter(models.LossReport.status == "approved").all()
    pending_reports = base_query.filter(models.LossReport.status == "pending").all()

    approved_count = len(approved_reports)
    pending_count = len(pending_reports)
    total_count = approved_count + pending_count

    approved_loss = sum(r.amount for r in approved_reports)
    pending_loss = sum(r.amount for r in pending_reports)
    total_loss = approved_loss + pending_loss

    all_reports = approved_reports + pending_reports

    if store_id:
        sales = get_store_sales_amount(
            db, store_id,
            (datetime.utcnow() - timedelta(days=days)).date(),
            datetime.utcnow().date()
        )
    else:
        sales = get_region_sales_amount(
            db, None,
            (datetime.utcnow() - timedelta(days=days)).date(),
            datetime.utcnow().date()
        )

    if sales and sales > 0:
        loss_rate = min(approved_loss / sales * 100, 100) if approved_loss > 0 else 0
    else:
        loss_rate = min(approved_loss / 10000 * 100, 100) if approved_loss > 0 else 0

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
    last_report = max((r.report_time for r in all_reports), default=None)

    frequency_score = min(approved_count * 5, 40)
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

    data_note_parts = []
    data_note_parts.append(f"风险评分基于已审核报损{approved_count}笔，金额{approved_loss:.2f}元计算")
    if pending_count > 0:
        data_note_parts.append(f"待审核报损{pending_count}笔，金额{pending_loss:.2f}元（暂未纳入评分）")
    if sales is None or sales <= 0:
        data_note_parts.append("无有效销售额数据，损耗率采用估算值")
    data_note = "；".join(data_note_parts)

    return schemas.ProductRiskScore(
        product_id=product_id,
        product_name=product.name,
        sku=product.sku,
        category=product.category or "",
        risk_score=round(risk_score, 1),
        risk_level=risk_level,
        loss_rate=round(loss_rate, 2),
        report_count=total_count,
        approved_report_count=approved_count,
        pending_report_count=pending_count,
        approved_loss_amount=approved_loss,
        pending_loss_amount=pending_loss,
        last_report_time=last_report,
        main_reasons=main_reasons,
        data_note=data_note
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
    approved_query = db.query(
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
        models.LossReport.report_time >= _to_datetime_start(start_date),
        models.LossReport.report_time <= _to_datetime_end(end_date),
        models.LossReport.status == "approved"
    )

    if store_id:
        approved_query = approved_query.filter(models.LossReport.store_id == store_id)
    elif region:
        approved_query = approved_query.join(models.Store, models.LossReport.store_id == models.Store.id)
        approved_query = approved_query.filter(models.Store.region == region)

    approved_query = approved_query.group_by(
        models.LossReason.id,
        models.LossReason.code,
        models.LossReason.name,
        models.LossReason.category
    ).all()

    reason_ids = [row.id for row in approved_query]

    pending_stats = {}
    if reason_ids:
        pending_query = db.query(
            models.LossReport.reason_id,
            func.count(models.LossReport.id).label("count"),
            func.sum(models.LossReport.quantity).label("quantity"),
            func.sum(models.LossReport.amount).label("amount")
        ).filter(
            models.LossReport.reason_id.in_(reason_ids),
            models.LossReport.report_time >= _to_datetime_start(start_date),
            models.LossReport.report_time <= _to_datetime_end(end_date),
            models.LossReport.status == "pending"
        )

        if store_id:
            pending_query = pending_query.filter(models.LossReport.store_id == store_id)
        elif region:
            pending_query = pending_query.join(models.Store, models.LossReport.store_id == models.Store.id)
            pending_query = pending_query.filter(models.Store.region == region)

        pending_query = pending_query.group_by(models.LossReport.reason_id).all()

        for row in pending_query:
            pending_stats[row.reason_id] = {
                "count": row.count or 0,
                "quantity": row.quantity or 0.0,
                "amount": row.amount or 0.0
            }

    total_amount = sum(row.total_amount or 0 for row in approved_query)

    results = []
    for row in approved_query:
        percentage = (row.total_amount / total_amount * 100) if total_amount > 0 else 0.0

        pending = pending_stats.get(row.id, {"count": 0, "quantity": 0.0, "amount": 0.0})

        approved_count = row.report_count
        approved_qty = row.total_quantity or 0.0
        approved_amt = row.total_amount or 0.0
        total_count = approved_count + pending["count"]
        total_qty = approved_qty + pending["quantity"]
        total_amt = approved_amt + pending["amount"]

        data_note_parts = []
        data_note_parts.append(f"已纳入已审核{approved_count}笔")
        if pending["count"] > 0:
            data_note_parts.append(f"待审核{pending['count']}笔（暂未纳入统计）")
        data_note = "；".join(data_note_parts)

        results.append(schemas.LossCategoryStat(
            reason_id=row.id,
            reason_code=row.code,
            reason_name=row.name,
            category=row.category or "",
            report_count=total_count,
            approved_report_count=approved_count,
            pending_report_count=pending["count"],
            total_quantity=total_qty,
            approved_quantity=approved_qty,
            pending_quantity=pending["quantity"],
            total_amount=total_amt,
            approved_amount=approved_amt,
            pending_amount=pending["amount"],
            percentage=round(percentage, 2),
            data_note=data_note
        ))

    results.sort(key=lambda x: x.approved_amount, reverse=True)
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

        base_query = db.query(
            func.sum(models.LossReport.amount).label("amount"),
            func.sum(models.LossReport.quantity).label("quantity"),
            func.count(models.LossReport.id).label("count")
        ).filter(
            models.LossReport.report_time >= _to_datetime_start(current_start),
            models.LossReport.report_time <= _to_datetime_end(current_end)
        )

        if store_id:
            base_query = base_query.filter(models.LossReport.store_id == store_id)
        elif region:
            base_query = base_query.join(models.Store, models.LossReport.store_id == models.Store.id)
            base_query = base_query.filter(models.Store.region == region)

        approved_row = base_query.filter(models.LossReport.status == "approved").first()
        pending_row = base_query.filter(models.LossReport.status == "pending").first()

        approved_amt = approved_row.amount or 0.0
        approved_qty = approved_row.quantity or 0.0
        approved_cnt = approved_row.count or 0
        pending_amt = pending_row.amount or 0.0
        pending_qty = pending_row.quantity or 0.0
        pending_cnt = pending_row.count or 0
        total_amt = approved_amt + pending_amt
        total_qty = approved_qty + pending_qty
        total_cnt = approved_cnt + pending_cnt

        if store_id:
            total_sales = get_store_sales_amount(db, store_id, current_start, current_end)
        else:
            total_sales = get_region_sales_amount(db, region, current_start, current_end)

        has_sales_data = total_sales is not None and total_sales > 0

        loss_rate = None
        note = None
        if has_sales_data:
            loss_rate = (approved_amt / total_sales * 100) if approved_amt else 0.0
        else:
            note = f"{current_start}至{current_end}无销售额数据"

        data_note_parts = []
        data_note_parts.append(f"已纳入已审核{approved_cnt}笔，金额{approved_amt:.2f}元")
        if pending_cnt > 0:
            data_note_parts.append(f"待审核{pending_cnt}笔，金额{pending_amt:.2f}元（暂未纳入趋势计算）")
        data_note = "；".join(data_note_parts)

        results.append(schemas.TrendDataPoint(
            date=current_start,
            loss_amount=total_amt,
            loss_quantity=total_qty,
            approved_loss_amount=approved_amt,
            pending_loss_amount=pending_amt,
            loss_rate=round(loss_rate, 2) if loss_rate is not None else None,
            report_count=total_cnt,
            approved_report_count=approved_cnt,
            pending_report_count=pending_cnt,
            total_sales=total_sales,
            has_sales_data=has_sales_data,
            note=note,
            data_note=data_note
        ))

        current_start = current_end + timedelta(days=1)

    return results


def get_regional_ranking(
    db: Session,
    start_date: date,
    end_date: date,
    region_filter: Optional[str] = None
) -> List[schemas.RegionalRanking]:
    prev_days = (end_date - start_date).days + 1
    prev_start = start_date - timedelta(days=prev_days)
    prev_end = start_date - timedelta(days=1)
    
    region_query = db.query(models.Store.region).distinct()
    region_query = region_query.filter(models.Store.is_active == True)
    if region_filter:
        region_query = region_query.filter(models.Store.region == region_filter)
    regions = [r[0] for r in region_query.all() if r[0]]
    
    if not regions and not region_filter:
        regions = [None]
    
    results = []
    for region in regions:
        region_name = region or "未分配"
        
        stores_query = db.query(models.Store).filter(
            models.Store.is_active == True
        )
        if region:
            stores_query = stores_query.filter(models.Store.region == region)
        else:
            stores_query = stores_query.filter(
                or_(models.Store.region.is_(None), models.Store.region == "")
            )
        stores = stores_query.all()
        
        if not stores:
            continue
        
        store_count = len(stores)
        store_ids = [s.id for s in stores]
        
        total_loss = db.query(
            func.sum(models.LossReport.amount)
        ).filter(
            models.LossReport.store_id.in_(store_ids),
            models.LossReport.report_time >= _to_datetime_start(start_date),
            models.LossReport.report_time <= _to_datetime_end(end_date),
            models.LossReport.status == "approved"
        ).scalar() or 0.0
        
        total_sales = db.query(
            func.sum(models.StoreSales.sales_amount)
        ).filter(
            models.StoreSales.store_id.in_(store_ids),
            models.StoreSales.sales_date >= start_date,
            models.StoreSales.sales_date <= end_date
        ).scalar()
        
        has_sales_data = total_sales is not None and total_sales > 0
        
        store_loss_rates = []
        best_store_detail = None
        worst_store_detail = None
        best_rate = float('inf')
        worst_rate = float('-inf')
        
        for store in stores:
            lr = calculate_store_loss_rate(db, store.id, start_date, end_date)
            if lr.loss_rate is not None:
                store_loss_rates.append(lr.loss_rate)
                if lr.loss_rate < best_rate:
                    best_rate = lr.loss_rate
                    best_store_detail = schemas.RegionalRankingStoreDetail(
                        store_id=store.id,
                        store_name=store.name,
                        loss_amount=lr.total_loss_amount,
                        sales_amount=lr.total_sales,
                        loss_rate=lr.loss_rate,
                        has_sales_data=lr.has_sales_data
                    )
                if lr.loss_rate > worst_rate:
                    worst_rate = lr.loss_rate
                    worst_store_detail = schemas.RegionalRankingStoreDetail(
                        store_id=store.id,
                        store_name=store.name,
                        loss_amount=lr.total_loss_amount,
                        sales_amount=lr.total_sales,
                        loss_rate=lr.loss_rate,
                        has_sales_data=lr.has_sales_data
                    )
        
        avg_loss_rate = None
        if store_loss_rates:
            avg_loss_rate = sum(store_loss_rates) / len(store_loss_rates)
        
        results.append(schemas.RegionalRanking(
            region=region_name,
            store_count=store_count,
            total_loss_amount=total_loss,
            total_sales_amount=total_sales,
            avg_loss_rate=round(avg_loss_rate, 2) if avg_loss_rate is not None else None,
            has_sales_data=has_sales_data,
            best_store=best_store_detail,
            worst_store=worst_store_detail,
            ranking=0
        ))
    
    if results:
        results.sort(key=lambda x: (x.avg_loss_rate is None, x.avg_loss_rate if x.avg_loss_rate is not None else float('inf')))
        for i, r in enumerate(results):
            r.ranking = i + 1
    
    if len(results) > 1:
        prev_results = []
        for region in regions:
            region_name = region or "未分配"
            
            stores_query = db.query(models.Store).filter(
                models.Store.is_active == True
            )
            if region:
                stores_query = stores_query.filter(models.Store.region == region)
            else:
                stores_query = stores_query.filter(
                    or_(models.Store.region.is_(None), models.Store.region == "")
                )
            stores = stores_query.all()
            store_ids = [s.id for s in stores] if stores else []
            
            prev_store_loss_rates = []
            for store in stores:
                prev_lr = calculate_store_loss_rate(db, store.id, prev_start, prev_end)
                if prev_lr.loss_rate is not None:
                    prev_store_loss_rates.append(prev_lr.loss_rate)
            
            prev_avg = sum(prev_store_loss_rates) / len(prev_store_loss_rates) if prev_store_loss_rates else None
            prev_results.append((region_name, prev_avg))
        
        prev_results.sort(key=lambda x: (x[1] is None, x[1] if x[1] is not None else float('inf')))
        prev_rank_map = {name: i + 1 for i, (name, _) in enumerate(prev_results)}
        
        for r in results:
            prev_rank = prev_rank_map.get(r.region)
            r.prev_ranking = prev_rank
            if prev_rank is not None:
                r.ranking_change = prev_rank - r.ranking
    
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
        base_query = db.query(
            func.sum(models.LossReport.amount).label("amount"),
            func.sum(models.LossReport.quantity).label("quantity"),
            func.count(models.LossReport.id).label("count")
        ).filter(
            models.LossReport.store_id == store.id,
            models.LossReport.report_time >= _to_datetime_start(start_date),
            models.LossReport.report_time <= _to_datetime_end(end_date)
        )

        current_approved = base_query.filter(models.LossReport.status == "approved").first()
        current_pending = base_query.filter(models.LossReport.status == "pending").first()

        approved_amt = current_approved.amount or 0.0
        approved_qty = current_approved.quantity or 0.0
        approved_cnt = current_approved.count or 0
        pending_amt = current_pending.amount or 0.0
        pending_qty = current_pending.quantity or 0.0
        pending_cnt = current_pending.count or 0
        total_amt = approved_amt + pending_amt
        total_qty = approved_qty + pending_qty
        total_cnt = approved_cnt + pending_cnt

        prev_data = db.query(
            func.sum(models.LossReport.amount).label("amount")
        ).filter(
            models.LossReport.store_id == store.id,
            models.LossReport.report_time >= _to_datetime_start(prev_start),
            models.LossReport.report_time <= _to_datetime_end(prev_end),
            models.LossReport.status == "approved"
        ).first()

        high_freq_count = db.query(func.count(func.distinct(models.LossReport.product_id))).filter(
            models.LossReport.store_id == store.id,
            models.LossReport.report_time >= _to_datetime_start(start_date),
            models.LossReport.report_time <= _to_datetime_end(end_date),
            models.LossReport.is_high_frequency == True,
            models.LossReport.status == "approved"
        ).scalar() or 0

        total_sales = get_store_sales_amount(db, store.id, start_date, end_date)
        has_sales_data = total_sales is not None and total_sales > 0

        approved_amount = approved_amt
        prev_amount = prev_data.amount or 0.0

        loss_rate = None
        note = None
        if has_sales_data:
            loss_rate = (approved_amount / total_sales * 100)
        else:
            note = f"该时间段无销售额数据"

        if prev_amount > 0:
            change_pct = (approved_amount - prev_amount) / prev_amount * 100
            if change_pct > 10:
                trend = "up"
            elif change_pct < -10:
                trend = "down"
            else:
                trend = "stable"
        else:
            trend = "stable" if approved_amount == 0 else "up"

        data_note_parts = []
        data_note_parts.append(f"已纳入已审核{approved_cnt}笔，金额{approved_amt:.2f}元")
        if pending_cnt > 0:
            data_note_parts.append(f"待审核{pending_cnt}笔，金额{pending_amt:.2f}元（暂未纳入对比）")
        data_note = "；".join(data_note_parts)

        results.append(schemas.StoreComparison(
            store_id=store.id,
            store_name=store.name,
            region=store.region or "",
            loss_amount=total_amt,
            loss_quantity=total_qty,
            approved_loss_amount=approved_amt,
            pending_loss_amount=pending_amt,
            total_sales=total_sales,
            loss_rate=round(loss_rate, 2) if loss_rate is not None else None,
            report_count=total_cnt,
            approved_report_count=approved_cnt,
            pending_report_count=pending_cnt,
            high_freq_count=high_freq_count,
            ranking=0,
            trend=trend,
            has_sales_data=has_sales_data,
            note=note,
            data_note=data_note
        ))

    results.sort(key=lambda x: (x.loss_rate is None, -(x.loss_rate if x.loss_rate is not None else -1)))
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

    high_freq_products = identify_high_frequency_products(db, store_id=store_id, region=region, days=30, min_count=3)
    
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


def create_store_sales(
    db: Session,
    sales_in: schemas.StoreSalesCreate
) -> models.StoreSales:
    store = db.query(models.Store).filter(models.Store.id == sales_in.store_id).first()
    if not store:
        raise ValueError(f"门店ID {sales_in.store_id} 不存在")

    if sales_in.sales_amount < 0:
        raise ValueError("销售额不能为负数")

    existing = db.query(models.StoreSales).filter(
        models.StoreSales.store_id == sales_in.store_id,
        models.StoreSales.sales_date == sales_in.sales_date
    ).first()

    if existing:
        existing.sales_amount = sales_in.sales_amount
        existing.transaction_count = sales_in.transaction_count or 0
        existing.customer_count = sales_in.customer_count or 0
        existing.remark = sales_in.remark
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    sales = models.StoreSales(
        store_id=sales_in.store_id,
        sales_date=sales_in.sales_date,
        sales_amount=sales_in.sales_amount,
        transaction_count=sales_in.transaction_count or 0,
        customer_count=sales_in.customer_count or 0,
        remark=sales_in.remark,
        created_by=sales_in.created_by
    )
    db.add(sales)
    db.commit()
    db.refresh(sales)
    return sales


def get_store_sales_records(
    db: Session,
    store_id: Optional[int] = None,
    region: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100
) -> List[models.StoreSales]:
    query = db.query(models.StoreSales).join(
        models.Store, models.StoreSales.store_id == models.Store.id
    )
    
    if store_id:
        query = query.filter(models.StoreSales.store_id == store_id)
    if region:
        query = query.filter(models.Store.region == region)
    if start_date:
        query = query.filter(models.StoreSales.sales_date >= start_date)
    if end_date:
        query = query.filter(models.StoreSales.sales_date <= end_date)
    
    return query.order_by(
        models.StoreSales.sales_date.desc(),
        models.StoreSales.store_id
    ).offset(skip).limit(limit).all()


def get_dashboard_summary(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    region: Optional[str] = None,
    store_id: Optional[int] = None
) -> schemas.DashboardSummary:
    today = date.today()
    if not end_date:
        end_date = today
    if not start_date:
        start_date = end_date - timedelta(days=30)

    period_days = (end_date - start_date).days + 1
    prev_start = start_date - timedelta(days=period_days)
    prev_end = start_date - timedelta(days=1)

    store_name = None
    if store_id:
        store = db.query(models.Store).filter(models.Store.id == store_id).first()
        if store:
            store_name = store.name

    base_loss_query = db.query(
        func.sum(models.LossReport.amount).label("amount"),
        func.count(models.LossReport.id).label("count")
    ).filter(
        models.LossReport.report_time >= _to_datetime_start(start_date),
        models.LossReport.report_time <= _to_datetime_end(end_date)
    )

    if store_id:
        base_loss_query = base_loss_query.filter(models.LossReport.store_id == store_id)
    elif region:
        base_loss_query = base_loss_query.join(models.Store, models.LossReport.store_id == models.Store.id)
        base_loss_query = base_loss_query.filter(models.Store.region == region)

    approved_data = base_loss_query.filter(models.LossReport.status == "approved").first()
    pending_data = base_loss_query.filter(models.LossReport.status == "pending").first()

    approved_loss = approved_data.amount or 0.0
    pending_loss = pending_data.amount or 0.0
    total_loss = approved_loss + pending_loss
    approved_count = approved_data.count or 0
    pending_count = pending_data.count or 0

    prev_loss_query = db.query(
        func.sum(models.LossReport.amount).label("amount")
    ).filter(
        models.LossReport.report_time >= _to_datetime_start(prev_start),
        models.LossReport.report_time <= _to_datetime_end(prev_end),
        models.LossReport.status == "approved"
    )

    if store_id:
        prev_loss_query = prev_loss_query.filter(models.LossReport.store_id == store_id)
    elif region:
        prev_loss_query = prev_loss_query.join(models.Store, models.LossReport.store_id == models.Store.id)
        prev_loss_query = prev_loss_query.filter(models.Store.region == region)

    prev_loss = prev_loss_query.scalar() or 0.0

    if store_id:
        current_sales = get_store_sales_amount(db, store_id, start_date, end_date)
        prev_sales = get_store_sales_amount(db, store_id, prev_start, prev_end)
    else:
        current_sales = get_region_sales_amount(db, region, start_date, end_date)
        prev_sales = get_region_sales_amount(db, region, prev_start, prev_end)

    has_sales_data = current_sales is not None and current_sales > 0
    prev_has_sales = prev_sales is not None and prev_sales > 0

    loss_rate = None
    prev_loss_rate = None
    sales_wow = None
    loss_wow = None
    loss_rate_wow = None

    if has_sales_data and current_sales > 0:
        loss_rate = round(approved_loss / current_sales * 100, 2)

    if prev_has_sales and prev_sales > 0:
        prev_loss_rate = round(prev_loss / prev_sales * 100, 2)

    if prev_sales and prev_sales > 0:
        sales_wow = round(((current_sales - prev_sales) / prev_sales * 100), 2) if current_sales else None
    if prev_loss > 0:
        loss_wow = round(((approved_loss - prev_loss) / prev_loss * 100), 2)
    if loss_rate is not None and prev_loss_rate is not None:
        loss_rate_wow = round(loss_rate - prev_loss_rate, 2)

    warning_query = db.query(
        models.WarningAlert.level,
        func.count(models.WarningAlert.id).label("cnt")
    ).filter(
        models.WarningAlert.created_at >= _to_datetime_start(start_date),
        models.WarningAlert.created_at <= _to_datetime_end(end_date)
    )

    if store_id:
        warning_query = warning_query.filter(models.WarningAlert.store_id == store_id)
    elif region:
        warning_query = warning_query.join(models.Store, models.WarningAlert.store_id == models.Store.id)
        warning_query = warning_query.filter(models.Store.region == region)

    warning_data = warning_query.group_by(models.WarningAlert.level).all()

    warning_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for level, cnt in warning_data:
        if level in warning_counts:
            warning_counts[level] = cnt

    total_warnings = sum(warning_counts.values())

    unhandled_query = db.query(func.count(models.WarningAlert.id)).filter(
        models.WarningAlert.status == "pending",
        models.WarningAlert.created_at >= _to_datetime_start(start_date),
        models.WarningAlert.created_at <= _to_datetime_end(end_date)
    )

    if store_id:
        unhandled_query = unhandled_query.filter(models.WarningAlert.store_id == store_id)
    elif region:
        unhandled_query = unhandled_query.join(models.Store, models.WarningAlert.store_id == models.Store.id)
        unhandled_query = unhandled_query.filter(models.Store.region == region)

    unhandled_warnings = unhandled_query.scalar() or 0

    regional_ranking = []
    if not store_id:
        ranking_data = get_regional_ranking(db, start_date, end_date, region_filter=region)
        for r in ranking_data:
            regional_ranking.append(schemas.DashboardRankingItem(
                region=r.region,
                avg_loss_rate=r.avg_loss_rate,
                total_loss_amount=r.total_loss_amount,
                store_count=r.store_count,
                ranking=r.ranking
            ))

    data_note_parts = []
    data_note_parts.append(f"统计周期：{start_date}至{end_date}")
    data_note_parts.append(f"已纳入已审核报损{approved_count}笔，金额{approved_loss:.2f}元")
    if pending_count > 0:
        data_note_parts.append(f"待审核报损{pending_count}笔，金额{pending_loss:.2f}元（暂未纳入损耗率计算）")
    if not has_sales_data:
        data_note_parts.append("无有效销售额数据，损耗率暂无法计算")
    data_note = "；".join(data_note_parts)

    return schemas.DashboardSummary(
        period_start=start_date,
        period_end=end_date,
        region=region,
        store_id=store_id,
        store_name=store_name,
        total_sales=current_sales,
        total_loss_amount=total_loss,
        approved_loss_amount=approved_loss,
        pending_loss_amount=pending_loss,
        loss_rate=loss_rate,
        prev_total_sales=prev_sales,
        prev_total_loss_amount=prev_loss,
        prev_loss_rate=prev_loss_rate,
        sales_wow_change=sales_wow,
        loss_wow_change=loss_wow,
        loss_rate_wow_change=loss_rate_wow,
        total_warnings=total_warnings,
        critical_warnings=warning_counts["critical"],
        high_warnings=warning_counts["high"],
        medium_warnings=warning_counts["medium"],
        low_warnings=warning_counts["low"],
        unhandled_warnings=unhandled_warnings,
        approved_report_count=approved_count,
        pending_report_count=pending_count,
        regional_ranking=regional_ranking if regional_ranking else None,
        has_sales_data=has_sales_data,
        data_note=data_note
    )


def batch_create_store_sales(
    db: Session,
    items: List[schemas.StoreSalesBatchItem]
) -> schemas.StoreSalesBatchResult:
    inserted = []
    updated = []
    failed = []

    for idx, item in enumerate(items):
        try:
            store = db.query(models.Store).filter(models.Store.id == item.store_id).first()
            if not store:
                failed.append({
                    "index": idx,
                    "store_id": item.store_id,
                    "sales_date": item.sales_date.isoformat(),
                    "error": f"门店ID {item.store_id} 不存在"
                })
                continue

            if item.sales_amount < 0:
                failed.append({
                    "index": idx,
                    "store_id": item.store_id,
                    "sales_date": item.sales_date.isoformat(),
                    "sales_amount": item.sales_amount,
                    "error": "销售额不能为负数"
                })
                continue

            existing = db.query(models.StoreSales).filter(
                models.StoreSales.store_id == item.store_id,
                models.StoreSales.sales_date == item.sales_date
            ).first()

            if existing:
                existing.sales_amount = item.sales_amount
                existing.transaction_count = item.transaction_count or 0
                existing.customer_count = item.customer_count or 0
                existing.remark = item.remark
                existing.updated_at = datetime.utcnow()
                db.flush()

                updated.append({
                    "index": idx,
                    "store_id": item.store_id,
                    "store_name": store.name,
                    "sales_date": item.sales_date.isoformat(),
                    "sales_amount": item.sales_amount,
                    "transaction_count": item.transaction_count,
                    "customer_count": item.customer_count
                })
            else:
                sales = models.StoreSales(
                    store_id=item.store_id,
                    sales_date=item.sales_date,
                    sales_amount=item.sales_amount,
                    transaction_count=item.transaction_count or 0,
                    customer_count=item.customer_count or 0,
                    remark=item.remark,
                    created_by=item.created_by
                )
                db.add(sales)
                db.flush()

                inserted.append({
                    "index": idx,
                    "store_id": item.store_id,
                    "store_name": store.name,
                    "sales_date": item.sales_date.isoformat(),
                    "sales_amount": item.sales_amount,
                    "transaction_count": item.transaction_count,
                    "customer_count": item.customer_count
                })

        except Exception as e:
            failed.append({
                "index": idx,
                "store_id": item.store_id,
                "sales_date": item.sales_date.isoformat(),
                "error": str(e)
            })

    db.commit()

    return schemas.StoreSalesBatchResult(
        total_items=len(items),
        success_count=len(inserted) + len(updated),
        inserted_count=len(inserted),
        updated_count=len(updated),
        failed_count=len(failed),
        inserted=inserted,
        updated=updated,
        failed=failed
    )
