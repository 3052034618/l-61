from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, date

from app.database import Base


class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    region = Column(String(100), index=True)
    city = Column(String(100))
    address = Column(String(255))
    manager = Column(String(50))
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    inventories = relationship("Inventory", back_populates="store")
    loss_reports = relationship("LossReport", back_populates="store")
    inventory_checks = relationship("InventoryCheck", back_populates="store")
    alerts = relationship("WarningAlert", back_populates="store")
    sales_records = relationship("StoreSales", back_populates="store")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False, index=True)
    category = Column(String(100), index=True)
    sub_category = Column(String(100))
    brand = Column(String(100))
    spec = Column(String(100))
    unit = Column(String(20))
    cost_price = Column(Float, default=0.0)
    sale_price = Column(Float, default=0.0)
    shelf_life_days = Column(Integer)
    expiry_warning_days = Column(Integer, default=7)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    inventories = relationship("Inventory", back_populates="product")
    loss_reports = relationship("LossReport", back_populates="product")
    inventory_checks = relationship("InventoryCheck", back_populates="product")


class Inventory(Base):
    __tablename__ = "inventories"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    batch_no = Column(String(50), index=True)
    quantity = Column(Float, default=0.0)
    available_quantity = Column(Float, default=0.0)
    production_date = Column(Date)
    expiry_date = Column(Date, index=True)
    warehouse_location = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = relationship("Store", back_populates="inventories")
    product = relationship("Product", back_populates="inventories")


class LossReason(Base):
    __tablename__ = "loss_reasons"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    category = Column(String(50), index=True)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    loss_reports = relationship("LossReport", back_populates="reason")


class LossReport(Base):
    __tablename__ = "loss_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_no = Column(String(50), unique=True, index=True, nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    reason_id = Column(Integer, ForeignKey("loss_reasons.id"))
    quantity = Column(Float, nullable=False)
    amount = Column(Float, default=0.0)
    batch_no = Column(String(50))
    expiry_date = Column(Date)
    report_time = Column(DateTime, default=datetime.utcnow, index=True)
    reporter = Column(String(50))
    description = Column(Text)
    images = Column(Text)
    status = Column(String(20), default="pending")
    reviewer = Column(String(50))
    review_time = Column(DateTime)
    review_comment = Column(Text)
    is_high_frequency = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = relationship("Store", back_populates="loss_reports")
    product = relationship("Product", back_populates="loss_reports")
    reason = relationship("LossReason", back_populates="loss_reports")
    actions = relationship("ActionRecord", back_populates="loss_report")


class InventoryCheck(Base):
    __tablename__ = "inventory_checks"

    id = Column(Integer, primary_key=True, index=True)
    check_no = Column(String(50), unique=True, index=True, nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    check_date = Column(Date, index=True)
    system_quantity = Column(Float, default=0.0)
    actual_quantity = Column(Float, default=0.0)
    shortage_quantity = Column(Float, default=0.0)
    shortage_amount = Column(Float, default=0.0)
    shortage_rate = Column(Float, default=0.0)
    is_abnormal = Column(Boolean, default=False, index=True)
    checker = Column(String(50))
    description = Column(Text)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = relationship("Store", back_populates="inventory_checks")
    product = relationship("Product", back_populates="inventory_checks")


class WarningAlert(Base):
    __tablename__ = "warning_alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_no = Column(String(50), unique=True, index=True, nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"))
    product_id = Column(Integer)
    alert_type = Column(String(50), index=True)
    level = Column(String(20), index=True)
    title = Column(String(200))
    content = Column(Text)
    risk_score = Column(Float, default=0.0)
    related_data = Column(Text)
    status = Column(String(20), default="pending")
    is_handled = Column(Boolean, default=False, index=True)
    handled_by = Column(String(50))
    handled_time = Column(DateTime)
    handle_comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    store = relationship("Store", back_populates="alerts")
    actions = relationship("ActionRecord", back_populates="alert")


class WarningSubscription(Base):
    __tablename__ = "warning_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    subscriber = Column(String(100), nullable=False)
    phone = Column(String(20))
    email = Column(String(100))
    alert_types = Column(String(255))
    regions = Column(String(255))
    store_ids = Column(String(255))
    min_risk_level = Column(String(20), default="medium")
    is_active = Column(Boolean, default=True)
    notify_method = Column(String(20), default="email")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ActionRecord(Base):
    __tablename__ = "action_records"

    id = Column(Integer, primary_key=True, index=True)
    action_no = Column(String(50), unique=True, index=True, nullable=False)
    loss_report_id = Column(Integer, ForeignKey("loss_reports.id"))
    alert_id = Column(Integer, ForeignKey("warning_alerts.id"))
    action_type = Column(String(50), index=True)
    title = Column(String(200))
    description = Column(Text)
    priority = Column(String(20), default="medium")
    responsible_person = Column(String(50))
    deadline = Column(Date)
    status = Column(String(20), default="pending", index=True)
    completed_time = Column(DateTime)
    result = Column(Text)
    created_by = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    loss_report = relationship("LossReport", back_populates="actions")
    alert = relationship("WarningAlert", back_populates="actions")


class ThresholdConfig(Base):
    __tablename__ = "threshold_configs"

    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), unique=True, index=True, nullable=False)
    config_value = Column(Float, nullable=False)
    config_name = Column(String(100))
    description = Column(Text)
    unit = Column(String(20))
    updated_by = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_no = Column(String(50), unique=True, index=True, nullable=False)
    region = Column(String(100), index=True)
    store_id = Column(Integer)
    week_start = Column(Date, index=True)
    week_end = Column(Date)
    total_loss_amount = Column(Float, default=0.0)
    total_loss_quantity = Column(Float, default=0.0)
    total_sales_amount = Column(Float)
    loss_rate = Column(Float)
    prev_total_loss_amount = Column(Float)
    prev_total_sales_amount = Column(Float)
    prev_loss_rate = Column(Float)
    week_over_week_change = Column(Float)
    loss_amount_change = Column(Float)
    has_sales_data = Column(Boolean, default=False)
    high_freq_products = Column(Text)
    main_reasons = Column(Text)
    regional_ranking = Column(Text)
    regional_ranking_change = Column(Text)
    correction_items = Column(Text)
    summary = Column(Text)
    suggestions = Column(Text)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    role = Column(String(50), default="user")
    store_id = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class StoreSales(Base):
    __tablename__ = "store_sales"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    sales_date = Column(Date, nullable=False, index=True)
    sales_amount = Column(Float, nullable=False, default=0.0)
    transaction_count = Column(Integer, default=0)
    customer_count = Column(Integer, default=0)
    remark = Column(String(255))
    created_by = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = relationship("Store", back_populates="sales_records")

    __table_args__ = ()
