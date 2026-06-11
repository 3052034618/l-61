from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional, Tuple
from datetime import datetime, date, timedelta
import json

from app import models
from app.schemas import schemas
from app.config import settings


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

    total_loss = db.query(
        func.sum(models.LossReport.amount)
    ).filter(
        models.LossReport.store_id == store_id,
        models.LossReport.report_time >= start_date,
        models.LossReport.report_time <= end_date,
        models.LossReport.status == "approved"
    ).scalar() or 0.0

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
        loss_rate = (total_loss / total_sales * 100)

    prev_start = start_date - timedelta(days=(end_date - start_date).days + 1)
    prev_end = start_date - timedelta(days=1)
    prev_loss = db.query(
        func.sum(models.LossReport.amount)
    ).filter(
        models.LossReport.store_id == store_id,
        models.LossReport.report_time >= prev_start,
        models.LossReport.report_time <= prev_end,
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

    return schemas.StoreLossRate(
        store_id=store_id,
        store_name=store.name,
        region=store.region or "",
        period="custom",
        start_date=start_date,
        end_date=end_date,
        total_sales=total_sales,
        total_loss_amount=total_loss,
        loss_rate=round(loss_rate, 2) if loss_rate is not None else None,
        loss_rate_trend=round(trend, 2) if trend is not None else None,
        threshold=threshold,
        is_exceeded=is_exceeded,
        has_sales_data=has_sales_data,
        note=note
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
        loss_rate = min(loss_amount / sales * 100, 100) if loss_amount > 0 else 0
    else:
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
        
        if store_id:
            total_sales = get_store_sales_amount(db, store_id, current_start, current_end)
        else:
            total_sales = get_region_sales_amount(db, region, current_start, current_end)
        
        has_sales_data = total_sales is not None and total_sales > 0
        
        loss_rate = None
        note = None
        if has_sales_data:
            loss_rate = (row.amount / total_sales * 100) if row.amount else 0.0
        else:
            note = f"{current_start}至{current_end}无销售额数据"
        
        results.append(schemas.TrendDataPoint(
            date=current_start,
            loss_amount=row.amount or 0.0,
            loss_quantity=row.quantity or 0.0,
            loss_rate=round(loss_rate, 2) if loss_rate is not None else None,
            report_count=row.count or 0,
            total_sales=total_sales,
            has_sales_data=has_sales_data,
            note=note
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
            models.LossReport.report_time >= start_date,
            models.LossReport.report_time <= end_date,
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
        
        total_sales = get_store_sales_amount(db, store.id, start_date, end_date)
        has_sales_data = total_sales is not None and total_sales > 0
        
        current_amount = current_data.amount or 0.0
        prev_amount = prev_data.amount or 0.0
        
        loss_rate = None
        note = None
        if has_sales_data:
            loss_rate = (current_amount / total_sales * 100)
        else:
            note = f"该时间段无销售额数据"
        
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
            total_sales=total_sales,
            loss_rate=round(loss_rate, 2) if loss_rate is not None else None,
            report_count=current_data.count or 0,
            high_freq_count=high_freq_count,
            ranking=0,
            trend=trend,
            has_sales_data=has_sales_data,
            note=note
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
