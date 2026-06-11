from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date


class StoreBase(BaseModel):
    name: str
    code: str
    region: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    manager: Optional[str] = None
    phone: Optional[str] = None


class StoreCreate(StoreBase):
    pass


class Store(StoreBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    sku: str
    name: str
    category: Optional[str] = None
    sub_category: Optional[str] = None
    brand: Optional[str] = None
    spec: Optional[str] = None
    unit: Optional[str] = None
    cost_price: Optional[float] = 0.0
    sale_price: Optional[float] = 0.0
    shelf_life_days: Optional[int] = None
    expiry_warning_days: Optional[int] = 7


class ProductCreate(ProductBase):
    pass


class Product(ProductBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class LossReasonBase(BaseModel):
    code: str
    name: str
    category: Optional[str] = None
    description: Optional[str] = None


class LossReasonCreate(LossReasonBase):
    pass


class LossReason(LossReasonBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class LossReportBase(BaseModel):
    store_id: int
    product_id: int
    reason_id: Optional[int] = None
    quantity: float
    amount: Optional[float] = 0.0
    batch_no: Optional[str] = None
    expiry_date: Optional[date] = None
    reporter: Optional[str] = None
    description: Optional[str] = None
    images: Optional[str] = None


class LossReportCreate(LossReportBase):
    pass


class LossReportReview(BaseModel):
    status: str
    reviewer: str
    review_comment: Optional[str] = None


class LossReport(LossReportBase):
    id: int
    report_no: str
    report_time: datetime
    status: str
    is_high_frequency: bool
    reviewer: Optional[str] = None
    review_time: Optional[datetime] = None
    review_comment: Optional[str] = None
    product: Optional[Product] = None
    store: Optional[Store] = None
    reason: Optional[LossReason] = None

    class Config:
        from_attributes = True


class InventoryCheckBase(BaseModel):
    store_id: int
    product_id: int
    check_date: date
    system_quantity: float
    actual_quantity: float
    checker: Optional[str] = None
    description: Optional[str] = None


class InventoryCheckCreate(InventoryCheckBase):
    pass


class InventoryCheck(InventoryCheckBase):
    id: int
    check_no: str
    shortage_quantity: float
    shortage_amount: float
    shortage_rate: float
    is_abnormal: bool
    status: str

    class Config:
        from_attributes = True


class WarningAlertBase(BaseModel):
    alert_type: str
    level: str
    title: str
    content: str
    risk_score: Optional[float] = 0.0


class WarningAlertHandle(BaseModel):
    status: str
    handled_by: str
    handle_comment: Optional[str] = None


class WarningAlert(WarningAlertBase):
    id: int
    alert_no: str
    store_id: Optional[int] = None
    product_id: Optional[int] = None
    related_data: Optional[str] = None
    status: str
    is_handled: bool
    handled_by: Optional[str] = None
    handled_time: Optional[datetime] = None
    handle_comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WarningSubscriptionBase(BaseModel):
    subscriber: str
    phone: Optional[str] = None
    email: Optional[str] = None
    alert_types: Optional[str] = None
    regions: Optional[str] = None
    store_ids: Optional[str] = None
    min_risk_level: Optional[str] = "medium"
    notify_method: Optional[str] = "email"


class WarningSubscriptionCreate(WarningSubscriptionBase):
    pass


class WarningSubscription(WarningSubscriptionBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class ActionRecordBase(BaseModel):
    action_type: str
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"
    responsible_person: Optional[str] = None
    deadline: Optional[date] = None
    created_by: Optional[str] = None


class ActionRecordCreate(ActionRecordBase):
    loss_report_id: Optional[int] = None
    alert_id: Optional[int] = None


class ActionRecordComplete(BaseModel):
    status: str
    result: str


class ActionRecord(ActionRecordBase):
    id: int
    action_no: str
    loss_report_id: Optional[int] = None
    alert_id: Optional[int] = None
    status: str
    completed_time: Optional[datetime] = None
    result: Optional[str] = None

    class Config:
        from_attributes = True


class ThresholdConfigBase(BaseModel):
    config_key: str
    config_value: float
    config_name: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    updated_by: Optional[str] = None


class ThresholdConfigCreate(ThresholdConfigBase):
    pass


class ThresholdConfig(ThresholdConfigBase):
    id: int

    class Config:
        from_attributes = True


class ProductRiskScore(BaseModel):
    product_id: int
    product_name: str
    sku: str
    category: str
    risk_score: float
    risk_level: str
    loss_rate: float
    report_count: int
    last_report_time: Optional[datetime] = None
    main_reasons: List[str]


class ExpiryReminder(BaseModel):
    inventory_id: int
    product_id: int
    product_name: str
    sku: str
    store_id: int
    store_name: str
    batch_no: str
    quantity: float
    expiry_date: date
    days_to_expiry: int
    suggested_action: str
    estimated_loss: float


class ShortageAbnormality(BaseModel):
    check_id: int
    check_no: str
    store_id: int
    store_name: str
    product_id: int
    product_name: str
    sku: str
    check_date: date
    system_quantity: float
    actual_quantity: float
    shortage_quantity: float
    shortage_amount: float
    shortage_rate: float
    threshold: float


class StoreComparison(BaseModel):
    store_id: int
    store_name: str
    region: str
    loss_amount: float
    loss_quantity: float
    loss_rate: float
    report_count: int
    high_freq_count: int
    ranking: int
    trend: str


class LossCategoryStat(BaseModel):
    reason_id: int
    reason_code: str
    reason_name: str
    category: str
    report_count: int
    total_quantity: float
    total_amount: float
    percentage: float


class HighFreqProduct(BaseModel):
    product_id: int
    product_name: str
    sku: str
    category: str
    report_count: int
    total_quantity: float
    total_amount: float
    avg_monthly_count: float
    risk_level: str


class TrendDataPoint(BaseModel):
    date: date
    loss_amount: float
    loss_quantity: float
    loss_rate: float
    report_count: int


class RegionalRanking(BaseModel):
    region: str
    store_count: int
    total_loss_amount: float
    avg_loss_rate: float
    best_store: str
    worst_store: str
    ranking: int


class WeeklyReportSummary(BaseModel):
    id: int
    report_no: str
    region: str
    week_start: date
    week_end: date
    total_loss_amount: float
    total_loss_quantity: float
    loss_rate: float
    week_over_week_change: float
    main_reasons: List[Dict[str, Any]]
    top_products: List[Dict[str, Any]]
    summary: str
    suggestions: List[str]


class CorrectionItem(BaseModel):
    id: Optional[int] = None
    action_no: Optional[str] = None
    title: str
    description: str
    priority: str
    category: str
    responsible_person: str
    deadline: date
    expected_effect: str
    related_product: Optional[str] = None
    related_store: Optional[str] = None


class StoreLossRate(BaseModel):
    store_id: int
    store_name: str
    region: str
    period: str
    start_date: date
    end_date: date
    total_sales: float
    total_loss_amount: float
    loss_rate: float
    loss_rate_trend: float
    threshold: float
    is_exceeded: bool


class Token(BaseModel):
    access_token: str
    token_type: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserBase(BaseModel):
    username: str
    full_name: Optional[str] = None
    role: Optional[str] = "user"
    store_id: Optional[int] = None


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True
