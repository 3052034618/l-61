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
    get_regional_ranking,
    get_store_sales_amount,
    get_region_sales_amount,
    generate_correction_list
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

    loss_query = db.query(
        func.sum(models.LossReport.amount).label("amount"),
        func.sum(models.LossReport.quantity).label("quantity")
    ).filter(
        models.LossReport.report_time >= week_start,
        models.LossReport.report_time <= week_end,
        models.LossReport.status == "approved"
    )

    if store_id:
        loss_query = loss_query.filter(models.LossReport.store_id == store_id)
    elif region:
        loss_query = loss_query.join(models.Store, models.LossReport.store_id == models.Store.id)
        loss_query = loss_query.filter(models.Store.region == region)

    current_data = loss_query.first()
    current_amount = current_data.amount or 0.0
    current_quantity = current_data.quantity or 0.0

    prev_loss_query = db.query(
        func.sum(models.LossReport.amount).label("amount"),
        func.sum(models.LossReport.quantity).label("quantity")
    ).filter(
        models.LossReport.report_time >= prev_week_start,
        models.LossReport.report_time <= prev_week_end,
        models.LossReport.status == "approved"
    )

    if store_id:
        prev_loss_query = prev_loss_query.filter(models.LossReport.store_id == store_id)
    elif region:
        prev_loss_query = prev_loss_query.join(models.Store, models.LossReport.store_id == models.Store.id)
        prev_loss_query = prev_loss_query.filter(models.Store.region == region)

    prev_data = prev_loss_query.first()
    prev_amount = prev_data.amount or 0.0
    prev_quantity = prev_data.quantity or 0.0

    if store_id:
        current_sales = get_store_sales_amount(db, store_id, week_start, week_end)
        prev_sales = get_store_sales_amount(db, store_id, prev_week_start, prev_week_end)
    else:
        current_sales = get_region_sales_amount(db, region, week_start, week_end)
        prev_sales = get_region_sales_amount(db, region, prev_week_start, prev_week_end)

    has_sales_data = current_sales is not None and current_sales > 0
    prev_has_sales_data = prev_sales is not None and prev_sales > 0

    loss_rate = None
    prev_loss_rate = None
    week_over_week_change = None
    loss_amount_change = None
    note = None

    if has_sales_data and current_sales > 0:
        loss_rate = round((current_amount / current_sales * 100), 2)
    else:
        note = "本期无有效销售额数据，损耗率暂无法计算"

    if prev_has_sales_data and prev_sales > 0:
        prev_loss_rate = round((prev_amount / prev_sales * 100), 2)

    if prev_amount > 0:
        week_over_week_change = round(((current_amount - prev_amount) / prev_amount * 100), 1)
    elif current_amount > 0:
        week_over_week_change = 100.0
    else:
        week_over_week_change = 0.0

    loss_amount_change = round(current_amount - prev_amount, 2)

    loss_categories = get_loss_categories_statistics(
        db, week_start, week_end, store_id=store_id, region=region
    )

    main_reasons = []
    for cat in loss_categories[:5]:
        main_reasons.append({
            "reason_id": cat.reason_id,
            "reason_name": cat.reason_name,
            "category": cat.category,
            "report_count": cat.report_count,
            "total_amount": cat.total_amount,
            "percentage": cat.percentage
        })

    high_freq = identify_high_frequency_products(
        db, store_id=store_id, region=region, days=7, min_count=1
    )

    top_products = []
    for prod in high_freq[:5]:
        top_products.append({
            "product_id": prod.product_id,
            "product_name": prod.product_name,
            "sku": prod.sku,
            "category": prod.category,
            "report_count": prod.report_count,
            "total_amount": prod.total_amount,
            "risk_level": prod.risk_level
        })

    regional_ranking = []
    regional_ranking_change = []
    if not store_id:
        current_ranking = get_regional_ranking(db, week_start, week_end, region_filter=region)
        prev_ranking = get_regional_ranking(db, prev_week_start, prev_week_end, region_filter=region)

        for r in current_ranking:
            regional_ranking.append({
                "region": r.region,
                "store_count": r.store_count,
                "total_loss_amount": r.total_loss_amount,
                "total_sales_amount": r.total_sales_amount,
                "avg_loss_rate": r.avg_loss_rate,
                "has_sales_data": r.has_sales_data,
                "ranking": r.ranking,
                "best_store": {
                    "store_id": r.best_store.store_id if r.best_store else None,
                    "store_name": r.best_store.store_name if r.best_store else None,
                    "loss_amount": r.best_store.loss_amount if r.best_store else 0,
                    "loss_rate": r.best_store.loss_rate if r.best_store else None
                } if r.best_store else None,
                "worst_store": {
                    "store_id": r.worst_store.store_id if r.worst_store else None,
                    "store_name": r.worst_store.store_name if r.worst_store else None,
                    "loss_amount": r.worst_store.loss_amount if r.worst_store else 0,
                    "loss_rate": r.worst_store.loss_rate if r.worst_store else None
                } if r.worst_store else None
            })

        prev_rank_map = {}
        for r in prev_ranking:
            prev_rank_map[r.region] = r.ranking

        for r in current_ranking:
            prev_rank = prev_rank_map.get(r.region)
            change = None
            if prev_rank is not None:
                change = prev_rank - r.ranking
            regional_ranking_change.append({
                "region": r.region,
                "current_ranking": r.ranking,
                "prev_ranking": prev_rank,
                "ranking_change": change
            })

    correction_list = generate_correction_list(db, store_id=store_id, region=region)
    correction_items = []
    for item in correction_list[:10]:
        correction_items.append({
            "title": item.title,
            "description": item.description,
            "priority": item.priority,
            "category": item.category,
            "responsible_person": item.responsible_person,
            "deadline": item.deadline.isoformat() if item.deadline else None,
            "expected_effect": item.expected_effect,
            "related_product": item.related_product,
            "related_store": item.related_store
        })

    region_name = region or "全区域"
    if store_id:
        store = db.query(models.Store).filter(models.Store.id == store_id).first()
        if store:
            region_name = store.name

    summary_parts = []
    summary_parts.append(f"{region_name}本周（{week_start}至{week_end}）")
    summary_parts.append(f"累计损耗金额 {current_amount:.2f} 元")
    if has_sales_data:
        summary_parts.append(f"，销售额 {current_sales:.2f} 元，损耗率 {loss_rate:.2f}%。")
    else:
        summary_parts.append("。无有效销售额数据，损耗率暂无法计算。")

    if week_over_week_change is not None:
        if week_over_week_change > 10:
            summary_parts.append(f"损耗金额较上周上升 {week_over_week_change:.1f}%（增加{loss_amount_change:.2f}元），呈恶化趋势，需重点关注。")
        elif week_over_week_change < -10:
            summary_parts.append(f"损耗金额较上周下降 {abs(week_over_week_change):.1f}%（减少{abs(loss_amount_change):.2f}元），管控措施初见成效。")
        else:
            summary_parts.append(f"损耗金额较上周变化不大（{week_over_week_change:+.1f}%），保持稳定。")

    if loss_rate is not None and prev_loss_rate is not None:
        rate_diff = loss_rate - prev_loss_rate
        if rate_diff > 0.5:
            summary_parts.append(f"损耗率较上周上升 {rate_diff:+.2f} 个百分点，需警惕。")
        elif rate_diff < -0.5:
            summary_parts.append(f"损耗率较上周下降 {abs(rate_diff):.2f} 个百分点，趋势向好。")

    if main_reasons:
        top_reason = main_reasons[0]
        summary_parts.append(f"主要损耗原因：{top_reason['reason_name']}（占比{top_reason['percentage']:.1f}%，{top_reason['total_amount']:.2f}元）。")

    if top_products:
        top_prod = top_products[0]
        summary_parts.append(f"高频损耗商品：{top_prod['product_name']}（{top_prod['report_count']}次报损，{top_prod['total_amount']:.2f}元）。")

    summary = "".join(summary_parts)

    suggestions = []
    if not has_sales_data:
        suggestions.append("请尽快补录本期销售额数据，以便准确计算损耗率。")

    suggestions.append("加强临期商品管理，提前7天启动促销清理流程，严格执行先进先出原则。")
    suggestions.append("针对高频损耗商品，优化库存周转和陈列方式，考虑调整订货量。")

    if loss_rate is not None and loss_rate > 3:
        suggestions.append("损耗率超标（>3%），建议开展专项盘点和全体员工防损培训。")

    if week_over_week_change is not None and week_over_week_change > 10:
        suggestions.append("损耗上升明显，建议排查管理漏洞，加强安防监控和重点区域巡视。")

    if main_reasons:
        top_category = main_reasons[0].get("category", "")
        if top_category == "过期":
            suggestions.append("临期损耗占比过高，建议优化订货周期，加强先进先出执行检查。")
        elif top_category == "损耗":
            suggestions.append("作业损耗占比较高，建议加强员工操作规范培训，优化作业流程。")
        elif top_category == "失窃":
            suggestions.append("失窃损耗较多，建议升级安防系统，加强高峰时段巡视。")
        elif top_category == "盘亏":
            suggestions.append("盘亏异常突出，建议加强库存出入库管理，定期抽查盘点。")

    report = models.WeeklyReport(
        report_no=generate_report_no(),
        region=region or "",
        store_id=store_id,
        week_start=week_start,
        week_end=week_end,
        total_loss_amount=current_amount,
        total_loss_quantity=current_quantity,
        total_sales_amount=current_sales,
        loss_rate=loss_rate,
        prev_total_loss_amount=prev_amount,
        prev_total_sales_amount=prev_sales,
        prev_loss_rate=prev_loss_rate,
        week_over_week_change=week_over_week_change,
        loss_amount_change=loss_amount_change,
        has_sales_data=has_sales_data,
        high_freq_products=json.dumps(top_products, ensure_ascii=False),
        main_reasons=json.dumps(main_reasons, ensure_ascii=False),
        regional_ranking=json.dumps(regional_ranking, ensure_ascii=False),
        regional_ranking_change=json.dumps(regional_ranking_change, ensure_ascii=False),
        correction_items=json.dumps(correction_items, ensure_ascii=False),
        summary=summary,
        suggestions=json.dumps(suggestions, ensure_ascii=False),
        note=note
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
        total_loss_quantity=current_quantity,
        total_sales_amount=current_sales,
        loss_rate=loss_rate,
        prev_total_loss_amount=prev_amount,
        prev_total_sales_amount=prev_sales,
        prev_loss_rate=prev_loss_rate,
        week_over_week_change=week_over_week_change,
        loss_amount_change=loss_amount_change,
        has_sales_data=has_sales_data,
        main_reasons=main_reasons,
        top_products=top_products,
        regional_ranking=regional_ranking if regional_ranking else None,
        regional_ranking_change=regional_ranking_change if regional_ranking_change else None,
        summary=summary,
        suggestions=suggestions,
        correction_items=correction_items if correction_items else None,
        note=note
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
    else:
        query = query.filter(
            (models.WeeklyReport.store_id.is_(None)) | (models.WeeklyReport.store_id == 0),
            models.WeeklyReport.region == ""
        )

    reports = query.order_by(models.WeeklyReport.week_start.desc()).limit(limit).all()

    results = []
    for rpt in reports:
        try:
            main_reasons = json.loads(rpt.main_reasons) if rpt.main_reasons else []
            top_products = json.loads(rpt.high_freq_products) if rpt.high_freq_products else []
            suggestions = json.loads(rpt.suggestions) if rpt.suggestions else []
            regional_ranking = json.loads(rpt.regional_ranking) if rpt.regional_ranking else None
            regional_ranking_change = json.loads(rpt.regional_ranking_change) if rpt.regional_ranking_change else None
            correction_items = json.loads(rpt.correction_items) if rpt.correction_items else None

            region_name = rpt.region or "全区域"
            if rpt.store_id:
                store = db.query(models.Store).filter(models.Store.id == rpt.store_id).first()
                if store:
                    region_name = store.name

            results.append(schemas.WeeklyReportSummary(
                id=rpt.id,
                report_no=rpt.report_no,
                region=region_name,
                week_start=rpt.week_start,
                week_end=rpt.week_end,
                total_loss_amount=rpt.total_loss_amount or 0.0,
                total_loss_quantity=rpt.total_loss_quantity or 0.0,
                total_sales_amount=rpt.total_sales_amount,
                loss_rate=rpt.loss_rate,
                prev_total_loss_amount=rpt.prev_total_loss_amount,
                prev_total_sales_amount=rpt.prev_total_sales_amount,
                prev_loss_rate=rpt.prev_loss_rate,
                week_over_week_change=rpt.week_over_week_change,
                loss_amount_change=rpt.loss_amount_change,
                has_sales_data=rpt.has_sales_data or False,
                main_reasons=main_reasons,
                top_products=top_products,
                regional_ranking=regional_ranking,
                regional_ranking_change=regional_ranking_change,
                summary=rpt.summary or "",
                suggestions=suggestions,
                correction_items=correction_items,
                note=rpt.note
            ))
        except Exception:
            continue

    return results
