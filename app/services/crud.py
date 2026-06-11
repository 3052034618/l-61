from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from datetime import datetime, date, timedelta
import uuid
import json

from pydantic import BaseModel
from app.database import Base
from app import models
from app.schemas import schemas
from app.services.loss_service import get_threshold_value

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        return db.query(self.model).filter(self.model.id == id).first()

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        return db.query(self.model).offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: int) -> ModelType:
        obj = db.query(self.model).get(id)
        db.delete(obj)
        db.commit()
        return obj


class CRUDLossReport(CRUDBase[models.LossReport, schemas.LossReportCreate, schemas.LossReportReview]):
    def generate_report_no(self) -> str:
        return f"LOSS{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"

    def create(self, db: Session, *, obj_in: schemas.LossReportCreate) -> models.LossReport:
        obj_in_data = obj_in.model_dump()
        
        if obj_in_data.get("amount") in [0, None] and obj_in_data.get("quantity"):
            product = db.query(models.Product).filter(models.Product.id == obj_in.product_id).first()
            if product:
                obj_in_data["amount"] = obj_in.quantity * product.cost_price
        
        obj_in_data["report_no"] = self.generate_report_no()
        
        product_id = obj_in.product_id
        store_id = obj_in.store_id
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_count = db.query(func.count(models.LossReport.id)).filter(
            models.LossReport.product_id == product_id,
            models.LossReport.store_id == store_id,
            models.LossReport.report_time >= thirty_days_ago
        ).scalar() or 0
        obj_in_data["is_high_frequency"] = recent_count >= 3
        
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def review(
        self,
        db: Session,
        *,
        db_obj: models.LossReport,
        obj_in: schemas.LossReportReview
    ) -> models.LossReport:
        update_data = obj_in.model_dump()
        update_data["review_time"] = datetime.utcnow()
        return self.update(db, db_obj=db_obj, obj_in=update_data)


class CRUDInventoryCheck(CRUDBase[models.InventoryCheck, schemas.InventoryCheckCreate, Any]):
    def generate_check_no(self) -> str:
        return f"CHK{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"

    def create(self, db: Session, *, obj_in: schemas.InventoryCheckCreate) -> models.InventoryCheck:
        obj_in_data = obj_in.model_dump()
        
        shortage_qty = obj_in.system_quantity - obj_in.actual_quantity
        obj_in_data["shortage_quantity"] = max(0, shortage_qty)
        
        product = db.query(models.Product).filter(models.Product.id == obj_in.product_id).first()
        cost_price = product.cost_price if product else 0.0
        obj_in_data["shortage_amount"] = obj_in_data["shortage_quantity"] * cost_price
        
        if obj_in.system_quantity > 0:
            obj_in_data["shortage_rate"] = (obj_in_data["shortage_quantity"] / obj_in.system_quantity) * 100
        else:
            obj_in_data["shortage_rate"] = 0.0
        
        threshold = get_threshold_value(db, "shortage_rate_threshold", 2.0)
        obj_in_data["is_abnormal"] = obj_in_data["shortage_rate"] > threshold
        
        obj_in_data["check_no"] = self.generate_check_no()
        
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


class CRUDActionRecord(CRUDBase[models.ActionRecord, schemas.ActionRecordCreate, schemas.ActionRecordComplete]):
    def generate_action_no(self) -> str:
        return f"ACT{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"

    def create(self, db: Session, *, obj_in: schemas.ActionRecordCreate) -> models.ActionRecord:
        obj_in_data = obj_in.model_dump()
        obj_in_data["action_no"] = self.generate_action_no()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def complete(
        self,
        db: Session,
        *,
        db_obj: models.ActionRecord,
        obj_in: schemas.ActionRecordComplete
    ) -> models.ActionRecord:
        update_data = obj_in.model_dump()
        update_data["completed_time"] = datetime.utcnow()
        return self.update(db, db_obj=db_obj, obj_in=update_data)


class CRUDWarningAlert(CRUDBase[models.WarningAlert, schemas.WarningAlertBase, schemas.WarningAlertHandle]):
    def handle(
        self,
        db: Session,
        *,
        db_obj: models.WarningAlert,
        obj_in: schemas.WarningAlertHandle
    ) -> models.WarningAlert:
        update_data = obj_in.model_dump()
        update_data["handled_time"] = datetime.utcnow()
        update_data["is_handled"] = True
        return self.update(db, db_obj=db_obj, obj_in=update_data)


class CRUDThresholdConfig(CRUDBase[models.ThresholdConfig, schemas.ThresholdConfigCreate, schemas.ThresholdConfigCreate]):
    def get_by_key(self, db: Session, key: str) -> Optional[models.ThresholdConfig]:
        return db.query(self.model).filter(self.model.config_key == key).first()

    def get_all(self, db: Session) -> List[models.ThresholdConfig]:
        return db.query(self.model).all()

    def set_value(
        self,
        db: Session,
        *,
        key: str,
        value: float,
        name: Optional[str] = None,
        description: Optional[str] = None,
        unit: Optional[str] = None,
        updated_by: Optional[str] = None
    ) -> models.ThresholdConfig:
        existing = self.get_by_key(db, key)
        if existing:
            update_data = {
                "config_value": value,
                "updated_by": updated_by,
                "updated_at": datetime.utcnow()
            }
            if name:
                update_data["config_name"] = name
            if description:
                update_data["description"] = description
            if unit:
                update_data["unit"] = unit
            return self.update(db, db_obj=existing, obj_in=update_data)
        else:
            obj_in = schemas.ThresholdConfigCreate(
                config_key=key,
                config_value=value,
                config_name=name or key,
                description=description,
                unit=unit,
                updated_by=updated_by
            )
            return self.create(db, obj_in=obj_in)


class CRUDWarningSubscription(CRUDBase[models.WarningSubscription, schemas.WarningSubscriptionCreate, schemas.WarningSubscriptionCreate]):
    def get_active_subscriptions(
        self,
        db: Session,
        alert_type: Optional[str] = None,
        region: Optional[str] = None
    ) -> List[models.WarningSubscription]:
        query = db.query(self.model).filter(self.model.is_active == True)
        if alert_type:
            query = query.filter(self.model.alert_types.contains(alert_type))
        if region:
            query = query.filter(self.model.regions.contains(region))
        return query.all()


loss_report = CRUDLossReport(models.LossReport)
inventory_check = CRUDInventoryCheck(models.InventoryCheck)
action_record = CRUDActionRecord(models.ActionRecord)
warning_alert = CRUDWarningAlert(models.WarningAlert)
threshold_config = CRUDThresholdConfig(models.ThresholdConfig)
warning_subscription = CRUDWarningSubscription(models.WarningSubscription)
store = CRUDBase[models.Store, schemas.StoreCreate, schemas.StoreCreate](models.Store)
product = CRUDBase[models.Product, schemas.ProductCreate, schemas.ProductCreate](models.Product)
loss_reason = CRUDBase[models.LossReason, schemas.LossReasonCreate, schemas.LossReasonCreate](models.LossReason)
