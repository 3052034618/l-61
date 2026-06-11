from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional
from datetime import datetime, date, timedelta
import uuid
import json

from app import models
from app.schemas import schemas
from app.services.loss_service import (
    calculate_store_loss_rate,
    identify_high_frequency_products,
    get_loss_categories_statistics,
    get_regional_ranking
)


def generate_report_no() -> str:
    return f"RPT{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"


def generate_weekly_summary(
    db: Session,
    region: Optional[str] = None,
    store_id: Optional[int] = None,
    week_offset: int = 0
) -> schemas.WeeklyReportSummary:
    today = date.today()
    weekday = today.weekday()
    
    week_end = today - timedelta(days=weekday + 1 + week_offset * 7)
    week_start = week_end - timedelta(days=6)
    
    prev_week_end = week_start - timedelta(days=1)
    prev_week_start = prev_week_end - timedelta(days=6)
    
    query = db.query(
        func.sum(models.LossReport.amount).label("amount"),
        func.sum(models.LossReport.quantity).label("quantity")
    ).filter(
        models.LossReport.report_time >= week_start,
        models.LossReport.report_time <= week_end,
        models.LossReport.status == "approved"
    )
    
    if store_id:
        query = query.filter(models.LossReport.store_id == store_id)
    elif region:
        query = query.join(models.Store, models.LossReport.store_id == models.Store.id)
        query = query.filter(models.Store.region == region)
    
    current_data = query.first()
    
    prev_query = db.query(
        func.sum(models.LossReport.amount).label("amount")
    ).filter(
        models.LossReport.report_time >= prev_week_start,
        models.LossReport.report_time <= prev_week_end,
        models.LossReport.status == "approved"
    )
    
    if store_id:
        prev_query = prev_query.filter(models.LossReport.store_id == store_id)
    elif region:
        prev_query = prev_query.join(models.Store, models.LossReport.store_id == models.Store.id)
        prev_query = prev_query.filter(models.Store.region == region)
    
    prev_data = prev_query.first()
    
    total_sales = 700000.0
    current_amount = current_data.amount or 0.0
    prev_amount = prev_data.amount or 0.0
    
    loss_rate = (current_amount / total_sales * 100) if total_sales > 0 else 0.0
    
    if prev_amount > 0:
        wow_change = (current_amount - prev_amount) / prev_amount * 100
    else:
        wow_change = 100.0 if current_amount > 0 else 0.0
    
    loss_categories = get_loss_categories_statistics(
        db, week_start, week_end, store_id=store_id, region=region
    )
    
    main_reasons = []
    for cat in loss_categories[:5]:
        main_reasons.append({
            "reason_name": cat.reason_name,
            "category": cat.category,
            "amount": cat.total_amount,
            "percentage": cat.percentage
        })
    
    high_freq = identify_high_frequency_products(
        db, store_id=store_id, days=7, min_count=1
    )
    
    top_products = []
    for prod in high_freq[:5]:
        top_products.append({
            "product_name": prod.product_name,
            "sku": prod.sku,
            "category": prod.category,
            "report_count": prod.report_count,
            "total_amount": prod.total_amount,
            "risk_level": prod.risk_level
        })
    
    region_name = region or "全区域"
    if store_id:
        store = db.query(models.Store).filter(models.Store.id == store_id).first()
        if store:
            region_name = store.name
    
    summary_parts = []
    summary_parts.append(f"{region_name}本周（{week_start}至{week_end}）")
    summary_parts.append(f"累计损耗金额 {current_amount:.2f} 元，损耗率 {loss_rate:.2f}%。")
    
    if wow_change > 10:
        summary_parts.append(f"较上周上升 {wow_change:.1f}%，损耗情况呈恶化趋势，需重点关注。")
    elif wow_change < -10:
        summary_parts.append(f"较上周下降 {abs(wow_change):.1f}%，管控措施初见成效。")
    else:
        summary_parts.append(f"较上周变化不大，保持稳定。")
    
    if main_reasons:
        top_reason = main_reasons[0]
        summary_parts.append(f"主要损耗原因：{top_reason['reason_name']}（占比{top_reason['percentage']:.1f}%）。")
    
    if top_products:
        top_prod = top_products[0]
        summary_parts.append(f"高频损耗商品：{top_prod['product_name']}（{top_prod['report_count']}次，{top_prod['total_amount']:.2f}元）。")
    
    summary = "".join(summary_parts)
    
    suggestions = []
    suggestions.append("加强临期商品管理，提前7天启动促销清理流程。")
    suggestions.append("针对高频损耗商品，优化库存周转和陈列方式。")
    
    if loss_rate > 3:
        suggestions.append("损耗率超标，建议开展专项盘点和员工培训。")
    
    if wow_change > 10:
        suggestions.append("损耗上升明显，建议排查管理漏洞，加强防损措施。")
    
    if main_reasons and main_reasons[0]["category"] == "过期":
        suggestions.append("临期损耗占比过高，建议优化订货周期和先进先出执行。")
    elif main_reasons and main_reasons[0]["category"] == "损耗":
        suggestions.append("作业损耗占比较高，建议加强员工操作规范培训。")
    elif main_reasons and main_reasons[0]["category"] == "失窃":
        suggestions.append("失窃损耗较多，建议加强安防监控和重点区域巡视。")
    
    report = models.WeeklyReport(
        report_no=generate_report_no(),
        region=region or "",
        store_id=store_id,
        week_start=week_start,
        week_end=week_end,
        total_loss_amount=current_amount,
        total_loss_quantity=current_data.quantity or 0.0,
        loss_rate=loss_rate,
        high_freq_products=json.dumps(top_products, ensure_ascii=False),
        main_reasons=json.dumps(main_reasons, ensure_ascii=False),
        summary=summary,
        suggestions=json.dumps(suggestions, ensure_ascii=False)
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    
    return schemas.WeeklyReportSummary(
        id=report.id,
        report_no=report.report_no,
        region=region_name,
        week_start=week_start,
        week_end=week_end,
        total_loss_amount=current_amount,
        total_loss_quantity=current_data.quantity or 0.0,
        loss_rate=round(loss_rate, 2),
        week_over_week_change=round(wow_change, 1),
        main_reasons=main_reasons,
        top_products=top_products,
        summary=summary,
        suggestions=suggestions
    )


def generate_all_weekly_reports(db: Session) -> dict:
    results = {}
    
    overall = generate_weekly_summary(db)
    results["overall"] = overall.report_no
    
    regions = db.query(models.Store.region).distinct().all()
    for (region,) in regions:
        if region:
            try:
                rpt = generate_weekly_summary(db, region=region)
                results[f"region_{region}"] = rpt.report_no
            except Exception as e:
                results[f"region_{region}_error"] = str(e)
    
    stores = db.query(models.Store).filter(models.Store.is_active == True).all()
    for store in stores:
        try:
            rpt = generate_weekly_summary(db, store_id=store.id)
            results[f"store_{store.id}"] = rpt.report_no
        except Exception as e:
            results[f"store_{store.id}_error"] = str(e)
    
    return results


def get_weekly_report_history(
    db: Session,
    region: Optional[str] = None,
    store_id: Optional[int] = None,
    limit: int = 12
) -> List[schemas.WeeklyReportSummary]:
    query = db.query(models.WeeklyReport)
    
    if store_id:
        query = query.filter(models.WeeklyReport.store_id == store_id)
    elif region:
        query = query.filter(models.WeeklyReport.region == region)
    
    reports = query.order_by(models.WeeklyReport.week_start.desc()).limit(limit).all()
    
    results = []
    for rpt in reports:
        try:
            main_reasons = json.loads(rpt.main_reasons) if rpt.main_reasons else []
            top_products = json.loads(rpt.high_freq_products) if rpt.high_freq_products else []
            suggestions = json.loads(rpt.suggestions) if rpt.suggestions else []
            
            results.append(schemas.WeeklyReportSummary(
                id=rpt.id,
                report_no=rpt.report_no,
                region=rpt.region or "全区域",
                week_start=rpt.week_start,
                week_end=rpt.week_end,
                total_loss_amount=rpt.total_loss_amount,
                total_loss_quantity=rpt.total_loss_quantity,
                loss_rate=rpt.loss_rate,
                week_over_week_change=0.0,
                main_reasons=main_reasons,
                top_products=top_products,
                summary=rpt.summary or "",
                suggestions=suggestions
            ))
        except Exception:
            continue
    
    return results
