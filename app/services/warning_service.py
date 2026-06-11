from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional
from datetime import datetime, date, timedelta
import uuid
import json

from app import models
from app.schemas import schemas
from app.config import settings
from app.services.loss_service import get_threshold_value


def generate_alert_no() -> str:
    return f"ALT{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"


def get_expiry_reminders(
    db: Session,
    store_id: Optional[int] = None,
    region: Optional[str] = None,
    days: Optional[int] = None
) -> List[schemas.ExpiryReminder]:
    warning_days = days or settings.DEFAULT_EXPIRY_DAYS
    today = date.today()
    expiry_cutoff = today + timedelta(days=warning_days)
    
    query = db.query(
        models.Inventory,
        models.Product,
        models.Store
    ).join(
        models.Product, models.Inventory.product_id == models.Product.id
    ).join(
        models.Store, models.Inventory.store_id == models.Store.id
    ).filter(
        models.Inventory.quantity > 0,
        models.Inventory.expiry_date.isnot(None),
        models.Inventory.expiry_date <= expiry_cutoff,
        models.Inventory.expiry_date >= today,
        models.Store.is_active == True
    )
    
    if store_id:
        query = query.filter(models.Inventory.store_id == store_id)
    elif region:
        query = query.filter(models.Store.region == region)
    
    inventories = query.order_by(models.Inventory.expiry_date.asc()).all()
    
    results = []
    for inv, product, store in inventories:
        days_to_expiry = (inv.expiry_date - today).days
        estimated_loss = inv.quantity * product.cost_price
        
        if days_to_expiry <= 1:
            suggested_action = "立即下架，启动报损流程"
        elif days_to_expiry <= 3:
            suggested_action = "建议打折促销，捆绑销售清理库存"
        elif days_to_expiry <= 7:
            suggested_action = "设置临期专区，开展买一送一活动"
        else:
            suggested_action = "加强陈列展示，优先销售"
        
        results.append(schemas.ExpiryReminder(
            inventory_id=inv.id,
            product_id=product.id,
            product_name=product.name,
            sku=product.sku,
            store_id=store.id,
            store_name=store.name,
            batch_no=inv.batch_no or "",
            quantity=inv.quantity,
            expiry_date=inv.expiry_date,
            days_to_expiry=days_to_expiry,
            suggested_action=suggested_action,
            estimated_loss=round(estimated_loss, 2)
        ))
    
    return results


def get_shortage_abnormalities(
    db: Session,
    store_id: Optional[int] = None,
    days: int = 30
) -> List[schemas.ShortageAbnormality]:
    start_date = date.today() - timedelta(days=days)
    threshold = get_threshold_value(db, "shortage_rate_threshold", settings.DEFAULT_SHORTAGE_RATE_THRESHOLD)
    
    query = db.query(
        models.InventoryCheck,
        models.Product,
        models.Store
    ).join(
        models.Product, models.InventoryCheck.product_id == models.Product.id
    ).join(
        models.Store, models.InventoryCheck.store_id == models.Store.id
    ).filter(
        models.InventoryCheck.check_date >= start_date,
        models.InventoryCheck.is_abnormal == True,
        models.InventoryCheck.shortage_rate > threshold
    )
    
    if store_id:
        query = query.filter(models.InventoryCheck.store_id == store_id)
    
    checks = query.order_by(models.InventoryCheck.shortage_rate.desc()).all()
    
    results = []
    for check, product, store in checks:
        results.append(schemas.ShortageAbnormality(
            check_id=check.id,
            check_no=check.check_no,
            store_id=store.id,
            store_name=store.name,
            product_id=product.id,
            product_name=product.name,
            sku=product.sku,
            check_date=check.check_date,
            system_quantity=check.system_quantity,
            actual_quantity=check.actual_quantity,
            shortage_quantity=check.shortage_quantity,
            shortage_amount=check.shortage_amount,
            shortage_rate=check.shortage_rate,
            threshold=threshold
        ))
    
    return results


def create_expiry_alerts(db: Session) -> int:
    reminders = get_expiry_reminders(db)
    count = 0
    
    for reminder in reminders:
        existing = db.query(models.WarningAlert).filter(
            models.WarningAlert.alert_type == "expiry",
            models.WarningAlert.store_id == reminder.store_id,
            models.WarningAlert.product_id == reminder.product_id,
            func.date(models.WarningAlert.created_at) == date.today()
        ).first()
        
        if existing:
            continue
        
        if reminder.days_to_expiry <= 1:
            level = "critical"
            risk_score = 90
        elif reminder.days_to_expiry <= 3:
            level = "high"
            risk_score = 70
        elif reminder.days_to_expiry <= 7:
            level = "medium"
            risk_score = 50
        else:
            level = "low"
            risk_score = 30
        
        alert = models.WarningAlert(
            alert_no=generate_alert_no(),
            store_id=reminder.store_id,
            product_id=reminder.product_id,
            alert_type="expiry",
            level=level,
            title=f"商品临期预警: {reminder.product_name}",
            content=f"{reminder.store_name} - {reminder.product_name} (批次: {reminder.batch_no}) 还有{reminder.days_to_expiry}天到期，库存{reminder.quantity}件。建议: {reminder.suggested_action}",
            risk_score=risk_score,
            related_data=json.dumps({
                "inventory_id": reminder.inventory_id,
                "batch_no": reminder.batch_no,
                "quantity": reminder.quantity,
                "expiry_date": str(reminder.expiry_date),
                "days_to_expiry": reminder.days_to_expiry,
                "estimated_loss": reminder.estimated_loss
            }, ensure_ascii=False),
            status="pending",
            is_handled=False
        )
        db.add(alert)
        count += 1
    
    db.commit()
    return count


def create_shortage_alerts(db: Session) -> int:
    abnormalities = get_shortage_abnormalities(db, days=7)
    count = 0
    
    for abnormal in abnormalities:
        existing = db.query(models.WarningAlert).filter(
            models.WarningAlert.alert_type == "shortage",
            models.WarningAlert.store_id == abnormal.store_id,
            models.WarningAlert.product_id == abnormal.product_id,
            func.date(models.WarningAlert.created_at) == date.today()
        ).first()
        
        if existing:
            continue
        
        if abnormal.shortage_rate >= 10:
            level = "critical"
            risk_score = 95
        elif abnormal.shortage_rate >= 5:
            level = "high"
            risk_score = 75
        else:
            level = "medium"
            risk_score = 55
        
        alert = models.WarningAlert(
            alert_no=generate_alert_no(),
            store_id=abnormal.store_id,
            product_id=abnormal.product_id,
            alert_type="shortage",
            level=level,
            title=f"盘亏异常预警: {abnormal.product_name}",
            content=f"{abnormal.store_name} 盘点发现 {abnormal.product_name} 盘亏{abnormal.shortage_quantity}件，金额{abnormal.shortage_amount:.2f}元，盘亏率{abnormal.shortage_rate:.2f}%（阈值{abnormal.threshold}%）。请立即核查原因。",
            risk_score=risk_score,
            related_data=json.dumps({
                "check_id": abnormal.check_id,
                "check_no": abnormal.check_no,
                "check_date": str(abnormal.check_date),
                "system_quantity": abnormal.system_quantity,
                "actual_quantity": abnormal.actual_quantity,
                "shortage_quantity": abnormal.shortage_quantity,
                "shortage_amount": abnormal.shortage_amount,
                "shortage_rate": abnormal.shortage_rate,
                "threshold": abnormal.threshold
            }, ensure_ascii=False),
            status="pending",
            is_handled=False
        )
        db.add(alert)
        count += 1
    
    db.commit()
    return count


def create_high_loss_alerts(db: Session) -> int:
    from app.services.loss_service import identify_high_frequency_products
    
    high_freq = identify_high_frequency_products(db, days=15, min_count=3)
    count = 0
    today = date.today()
    
    for product in high_freq:
        existing = db.query(models.WarningAlert).filter(
            models.WarningAlert.alert_type == "high_loss",
            models.WarningAlert.product_id == product.product_id,
            func.date(models.WarningAlert.created_at) >= today - timedelta(days=7)
        ).first()
        
        if existing:
            continue
        
        if product.risk_level == "high":
            level = "high"
            risk_score = 80
        else:
            level = "medium"
            risk_score = 60
        
        alert = models.WarningAlert(
            alert_no=generate_alert_no(),
            product_id=product.product_id,
            alert_type="high_loss",
            level=level,
            title=f"高频损耗预警: {product.product_name}",
            content=f"商品 {product.product_name} ({product.sku}) 近30天报损{product.report_count}次，累计金额{product.total_amount:.2f}元，月均{product.avg_monthly_count:.1f}次。风险等级: {product.risk_level}",
            risk_score=risk_score,
            related_data=json.dumps({
                "product_id": product.product_id,
                "sku": product.sku,
                "category": product.category,
                "report_count": product.report_count,
                "total_quantity": product.total_quantity,
                "total_amount": product.total_amount,
                "avg_monthly_count": product.avg_monthly_count,
                "risk_level": product.risk_level
            }, ensure_ascii=False),
            status="pending",
            is_handled=False
        )
        db.add(alert)
        count += 1
    
    db.commit()
    return count


def create_loss_rate_alerts(db: Session) -> int:
    from app.services.loss_service import calculate_all_stores_loss_rate
    
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    threshold = get_threshold_value(db, "loss_rate_threshold", settings.DEFAULT_LOSS_RATE_THRESHOLD)
    
    store_rates = calculate_all_stores_loss_rate(db, start_date, end_date)
    count = 0
    
    for rate in store_rates:
        if not rate.is_exceeded:
            continue
        
        existing = db.query(models.WarningAlert).filter(
            models.WarningAlert.alert_type == "loss_rate",
            models.WarningAlert.store_id == rate.store_id,
            func.date(models.WarningAlert.created_at) >= date.today() - timedelta(days=7)
        ).first()
        
        if existing:
            continue
        
        if rate.loss_rate >= threshold * 2:
            level = "critical"
            risk_score = 90
        else:
            level = "high"
            risk_score = 70
        
        alert = models.WarningAlert(
            alert_no=generate_alert_no(),
            store_id=rate.store_id,
            alert_type="loss_rate",
            level=level,
            title=f"损耗率超标预警: {rate.store_name}",
            content=f"门店 {rate.store_name} 本月损耗率 {rate.loss_rate:.2f}%，超过阈值 {threshold}%。较上月{'上升' if rate.loss_rate_trend > 0 else '下降'} {abs(rate.loss_rate_trend):.2f}个百分点。",
            risk_score=risk_score,
            related_data=json.dumps({
                "store_id": rate.store_id,
                "store_name": rate.store_name,
                "region": rate.region,
                "total_sales": rate.total_sales,
                "total_loss_amount": rate.total_loss_amount,
                "loss_rate": rate.loss_rate,
                "loss_rate_trend": rate.loss_rate_trend,
                "threshold": threshold
            }, ensure_ascii=False),
            status="pending",
            is_handled=False
        )
        db.add(alert)
        count += 1
    
    db.commit()
    return count


def run_all_alert_checks(db: Session) -> dict:
    results = {
        "expiry_alerts": create_expiry_alerts(db),
        "shortage_alerts": create_shortage_alerts(db),
        "high_loss_alerts": create_high_loss_alerts(db),
        "loss_rate_alerts": create_loss_rate_alerts(db)
    }
    return results


def generate_expiry_suggestions(
    db: Session,
    store_id: Optional[int] = None,
    days: int = 14
) -> List[dict]:
    reminders = get_expiry_reminders(db, store_id=store_id, days=days)
    
    suggestions_by_category = {}
    
    for reminder in reminders:
        category = "其他"
        if reminder.days_to_expiry <= 1:
            category = "紧急处理"
        elif reminder.days_to_expiry <= 3:
            category = "促销清理"
        elif reminder.days_to_expiry <= 7:
            category = "优先销售"
        else:
            category = "关注预警"
        
        if category not in suggestions_by_category:
            suggestions_by_category[category] = {
                "category": category,
                "priority": "high" if "紧急" in category else "medium",
                "total_items": 0,
                "total_quantity": 0.0,
                "estimated_loss": 0.0,
                "suggestion": "",
                "items": []
            }
        
        suggestions_by_category[category]["total_items"] += 1
        suggestions_by_category[category]["total_quantity"] += reminder.quantity
        suggestions_by_category[category]["estimated_loss"] += reminder.estimated_loss
        
        suggestions_by_category[category]["items"].append({
            "product_name": reminder.product_name,
            "sku": reminder.sku,
            "store_name": reminder.store_name,
            "quantity": reminder.quantity,
            "expiry_date": str(reminder.expiry_date),
            "days_to_expiry": reminder.days_to_expiry,
            "suggested_action": reminder.suggested_action
        })
    
    suggestion_texts = {
        "紧急处理": "立即下架所有1天内到期商品，启动紧急报损流程，避免过期商品流入市场。",
        "促销清理": "对3-7天内到期商品设置临期专区，开展买一送一、捆绑销售等促销活动快速清理库存。",
        "优先销售": "将7-14天内到期商品调整到显眼陈列位置，安排导购优先推荐。",
        "关注预警": "关注近期将到期商品的销售情况，提前制定促销计划。"
    }
    
    result = []
    for category in ["紧急处理", "促销清理", "优先销售", "关注预警"]:
        if category in suggestions_by_category:
            data = suggestions_by_category[category]
            data["suggestion"] = suggestion_texts.get(category, "")
            data["estimated_loss"] = round(data["estimated_loss"], 2)
            data["total_quantity"] = round(data["total_quantity"], 2)
            result.append(data)
    
    return result
