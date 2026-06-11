import sys
import os
from datetime import datetime, date, timedelta
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, Base, engine
from app import models
from app.services.auth import get_password_hash
from app.services.crud import threshold_config
from app.config import settings


def init_database():
    print("开始初始化数据库...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        if db.query(models.User).count() == 0:
            print("创建默认用户...")
            admin = models.User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                full_name="系统管理员",
                role="admin",
                is_active=True
            )
            db.add(admin)
            
            store_user = models.User(
                username="store",
                password_hash=get_password_hash("store123"),
                full_name="门店管理员",
                role="store_manager",
                store_id=1,
                is_active=True
            )
            db.add(store_user)
        
        if db.query(models.ThresholdConfig).count() == 0:
            print("创建默认阈值配置...")
            thresholds = [
                ("loss_rate_threshold", settings.DEFAULT_LOSS_RATE_THRESHOLD, "损耗率预警阈值", "门店月损耗率超过此值触发预警", "%"),
                ("shortage_rate_threshold", settings.DEFAULT_SHORTAGE_RATE_THRESHOLD, "盘亏率预警阈值", "盘点差异率超过此值判定为异常", "%"),
                ("expiry_warning_days", settings.DEFAULT_EXPIRY_DAYS, "临期预警天数", "距离保质期不足此天数触发临期预警", "天"),
                ("high_freq_report_count", 5, "高频报损判定次数", "30天内报损次数超过此值判定为高频", "次"),
                ("high_freq_amount_threshold", 1000, "高频报损金额阈值", "30天内报损金额超过此值判定为高频", "元")
            ]
            
            for key, value, name, desc, unit in thresholds:
                threshold_config.set_value(
                    db,
                    key=key,
                    value=value,
                    name=name,
                    description=desc,
                    unit=unit,
                    updated_by="system"
                )
        
        if db.query(models.LossReason).count() == 0:
            print("创建损耗原因...")
            reasons = [
                ("EXP_001", "过期变质", "过期", "商品超过保质期无法销售"),
                ("EXP_002", "临期报损", "过期", "临期商品无法售出"),
                ("DAM_001", "包装破损", "损耗", "运输或存储过程中包装损坏"),
                ("DAM_002", "磕碰损坏", "损耗", "商品物理损坏"),
                ("DAM_003", "解冻变质", "损耗", "冷链商品解冻后变质"),
                ("THE_001", "店内失窃", "失窃", "顾客盗窃"),
                ("THE_002", "员工内盗", "失窃", "员工偷盗行为"),
                ("THE_003", "供应商欺诈", "失窃", "供应商送货短少或作假"),
                ("OPE_001", "计量错误", "作业", "称重或计价错误"),
                ("OPE_002", "录入错误", "作业", "系统录入错误"),
                ("OPE_003", "盘点错误", "作业", "人工盘点误差"),
                ("WEA_001", "天气影响", "其他", "恶劣天气导致商品损坏"),
                ("WEA_002", "虫害鼠咬", "其他", "虫害鼠类造成的损失"),
                ("OTH_001", "其他原因", "其他", "无法归类的其他原因")
            ]
            
            for code, name, category, desc in reasons:
                reason = models.LossReason(
                    code=code,
                    name=name,
                    category=category,
                    description=desc,
                    is_active=True
                )
                db.add(reason)
        
        if db.query(models.Store).count() == 0:
            print("创建示例门店...")
            stores = [
                ("ST001", "朝阳路店", "华北区", "北京", "北京市朝阳区朝阳路188号", "张三", "13800138001"),
                ("ST002", "海淀店", "华北区", "北京", "北京市海淀区中关村大街56号", "李四", "13800138002"),
                ("ST003", "浦东店", "华东区", "上海", "上海市浦东新区陆家嘴环路100号", "王五", "13800138003"),
                ("ST004", "徐汇店", "华东区", "上海", "上海市徐汇区淮海中路200号", "赵六", "13800138004"),
                ("ST005", "天河店", "华南区", "广州", "广州市天河区天河路300号", "钱七", "13800138005"),
                ("ST006", "南山店", "华南区", "深圳", "深圳市南山区科技园路400号", "孙八", "13800138006")
            ]
            
            for code, name, region, city, address, manager, phone in stores:
                store = models.Store(
                    code=code,
                    name=name,
                    region=region,
                    city=city,
                    address=address,
                    manager=manager,
                    phone=phone,
                    is_active=True
                )
                db.add(store)
            db.flush()
        
        if db.query(models.Product).count() == 0:
            print("创建示例商品...")
            categories = ["生鲜蔬果", "肉类水产", "乳制品", "烘焙食品", "休闲零食", "饮料冲调", "粮油调味", "日用百货"]
            brands = ["伊利", "蒙牛", "光明", "三元", "双汇", "雨润", "旺旺", "康师傅", "统一", "农夫山泉"]
            units = ["袋", "盒", "瓶", "个", "kg", "g", "L", "ml"]
            
            products_data = [
                ("SKU001", "纯牛奶250ml", "乳制品", "液态奶", 2.5, 3.5, 180),
                ("SKU002", "原味酸奶1kg", "乳制品", "酸奶", 8.0, 12.5, 21),
                ("SKU003", "新鲜鸡蛋30枚", "生鲜蔬果", "蛋类", 15.0, 22.0, 30),
                ("SKU004", "五花肉500g", "肉类水产", "猪肉", 18.0, 28.0, 5),
                ("SKU005", "鸡胸肉400g", "肉类水产", "禽肉", 10.0, 15.0, 7),
                ("SKU006", "三文鱼200g", "肉类水产", "水产", 35.0, 55.0, 3),
                ("SKU007", "香蕉1kg", "生鲜蔬果", "水果", 5.0, 8.5, 7),
                ("SKU008", "草莓500g", "生鲜蔬果", "水果", 12.0, 19.8, 5),
                ("SKU009", "生菜500g", "生鲜蔬果", "蔬菜", 3.0, 5.5, 3),
                ("SKU010", "全麦面包500g", "烘焙食品", "面包", 6.0, 9.9, 7),
                ("SKU011", "巧克力蛋糕", "烘焙食品", "蛋糕", 15.0, 25.0, 3),
                ("SKU012", "薯片104g", "休闲零食", "膨化食品", 4.5, 7.9, 180),
                ("SKU013", "瓜子200g", "休闲零食", "坚果炒货", 5.0, 8.5, 365),
                ("SKU014", "矿泉水550ml", "饮料冲调", "饮用水", 0.8, 1.5, 365),
                ("SKU015", "橙汁1L", "饮料冲调", "果汁", 5.5, 9.9, 180),
                ("SKU016", "五常大米5kg", "粮油调味", "米面", 30.0, 49.9, 365),
                ("SKU017", "大豆油5L", "粮油调味", "食用油", 45.0, 69.9, 540),
                ("SKU018", "生抽500ml", "粮油调味", "调味品", 6.0, 10.5, 730),
                ("SKU019", "牙膏120g", "日用百货", "个人护理", 8.0, 14.5, 1095),
                ("SKU020", "卫生纸10卷", "日用百货", "家居清洁", 15.0, 23.9, 1095)
            ]
            
            for sku, name, category, sub_category, cost, sale, shelf_life in products_data:
                product = models.Product(
                    sku=sku,
                    name=name,
                    category=category,
                    sub_category=sub_category,
                    brand=random.choice(brands),
                    spec=f"{random.choice(['家庭装', '常规装', '优惠装'])}",
                    unit=random.choice(units),
                    cost_price=cost,
                    sale_price=sale,
                    shelf_life_days=shelf_life,
                    expiry_warning_days=max(3, min(shelf_life // 10, 14)),
                    is_active=True
                )
                db.add(product)
            db.flush()
        
        if db.query(models.Inventory).count() == 0:
            print("创建示例库存...")
            today = date.today()
            stores = db.query(models.Store).all()
            products = db.query(models.Product).all()
            
            for store in stores[:3]:
                for product in products:
                    expiry_date = today + timedelta(days=random.randint(2, product.shelf_life_days or 90))
                    if random.random() < 0.7:
                        inventory = models.Inventory(
                            store_id=store.id,
                            product_id=product.id,
                            batch_no=f"B{today.strftime('%Y%m%d')}{product.id:03d}",
                            quantity=random.randint(10, 200),
                            available_quantity=random.randint(5, 180),
                            production_date=today - timedelta(days=random.randint(1, 30)),
                            expiry_date=expiry_date,
                            warehouse_location=f"{random.choice(['A', 'B', 'C'])}-{random.randint(1, 10):02d}"
                        )
                        db.add(inventory)
        
        if db.query(models.LossReport).count() == 0:
            print("创建示例报损记录...")
            today = date.today()
            stores = db.query(models.Store).all()
            products = db.query(models.Product).all()
            reasons = db.query(models.LossReason).all()
            reporters = ["李理货", "王管库", "张店长", "赵员工", "孙收银"]
            
            for _ in range(200):
                store = random.choice(stores)
                product = random.choice(products)
                reason = random.choice(reasons)
                report_date = today - timedelta(days=random.randint(0, 90))
                quantity = round(random.uniform(1, 50), 1)
                amount = round(quantity * product.cost_price, 2)
                
                report = models.LossReport(
                    report_no=f"LOSS{report_date.strftime('%Y%m%d')}{random.randint(1000, 9999)}",
                    store_id=store.id,
                    product_id=product.id,
                    reason_id=reason.id,
                    quantity=quantity,
                    amount=amount,
                    batch_no=f"B{report_date.strftime('%Y%m%d')}{product.id:03d}",
                    expiry_date=report_date + timedelta(days=random.randint(0, 30)),
                    report_time=datetime.combine(report_date, datetime.min.time()) + timedelta(hours=random.randint(8, 20)),
                    reporter=random.choice(reporters),
                    description=f"{reason.name}导致{product.name}报损",
                    status=random.choice(["approved", "approved", "approved", "pending", "rejected"]),
                    is_high_frequency=random.random() < 0.15
                )
                if report.status in ["approved", "rejected"]:
                    report.reviewer = "运营主管"
                    report.review_time = datetime.combine(report_date, datetime.min.time()) + timedelta(days=1, hours=10)
                    report.review_comment = random.choice(["情况属实，同意报损", "已核实，准予处理", "驳回，需补充说明", "数据无误"])
                db.add(report)
        
        if db.query(models.InventoryCheck).count() == 0:
            print("创建示例盘点记录...")
            today = date.today()
            stores = db.query(models.Store).all()
            products = db.query(models.Product).all()
            checkers = ["王盘点", "李核对", "张主管"]
            
            for _ in range(100):
                store = random.choice(stores)
                product = random.choice(products)
                check_date = today - timedelta(days=random.randint(0, 60))
                system_qty = random.randint(50, 200)
                actual_qty = int(system_qty * random.uniform(0.85, 1.05))
                shortage_qty = max(0, system_qty - actual_qty)
                shortage_rate = (shortage_qty / system_qty * 100) if system_qty > 0 else 0
                
                check = models.InventoryCheck(
                    check_no=f"CHK{check_date.strftime('%Y%m%d')}{random.randint(1000, 9999)}",
                    store_id=store.id,
                    product_id=product.id,
                    check_date=check_date,
                    system_quantity=system_qty,
                    actual_quantity=actual_qty,
                    shortage_quantity=shortage_qty,
                    shortage_amount=round(shortage_qty * product.cost_price, 2),
                    shortage_rate=round(shortage_rate, 2),
                    is_abnormal=shortage_rate > settings.DEFAULT_SHORTAGE_RATE_THRESHOLD,
                    checker=random.choice(checkers),
                    description=random.choice(["正常盘点", "月度盘点", "专项抽查", "交接盘点"]),
                    status=random.choice(["completed", "completed", "pending"])
                )
                db.add(check)
        
        if db.query(models.StoreSales).count() == 0:
            print("创建示例销售额数据...")
            today = date.today()
            stores = db.query(models.Store).all()

            for store in stores:
                base_daily_sales = {
                    "华北区": 28000,
                    "华东区": 35000,
                    "华南区": 32000
                }.get(store.region, 25000)

                for days_ago in range(90):
                    sales_date = today - timedelta(days=days_ago)
                    weekday_factor = 1.0
                    if sales_date.weekday() >= 5:
                        weekday_factor = 1.25

                    season_factor = 1.0
                    if sales_date.month in [1, 2, 7, 8, 12]:
                        season_factor = 1.15

                    daily_sales = round(
                        base_daily_sales * weekday_factor * season_factor * random.uniform(0.85, 1.15),
                        2
                    )
                    transactions = int(daily_sales / random.uniform(45, 75))
                    customers = int(transactions * random.uniform(1.1, 1.5))

                    sales_record = models.StoreSales(
                        store_id=store.id,
                        sales_date=sales_date,
                        sales_amount=daily_sales,
                        transaction_count=transactions,
                        customer_count=customers,
                        remark=f"示例数据-{sales_date.isoformat()}",
                        created_by="system"
                    )
                    db.add(sales_record)
            db.flush()

        if db.query(models.WarningAlert).count() == 0:
            print("创建示例预警记录...")
            from app.services.warning_service import run_all_alert_checks
            run_all_alert_checks(db)
        
        if db.query(models.ActionRecord).count() == 0:
            print("创建示例处理动作...")
            today = date.today()
            loss_reports = db.query(models.LossReport).filter(models.LossReport.status == "approved").limit(10).all()
            alerts = db.query(models.WarningAlert).limit(10).all()
            action_types = ["price_adjustment", "promotion", "shelf_adjustment", "staff_training", "process_improvement", "security_enhance"]
            responsible = ["门店主管", "理货员", "防损员", "运营经理", "店长"]
            
            for i, (lr, alert) in enumerate(zip(loss_reports[:5], alerts[:5])):
                action = models.ActionRecord(
                    action_no=f"ACT{today.strftime('%Y%m%d')}{i+1:04d}",
                    loss_report_id=lr.id,
                    alert_id=alert.id,
                    action_type=random.choice(action_types),
                    title=f"整改动作 - {random.choice(['优化陈列', '促销活动', '加强培训', '完善流程'])}",
                    description=f"针对{lr.product.name}的高频损耗问题，采取相应整改措施以降低损耗率。",
                    priority=random.choice(["high", "medium", "medium", "low"]),
                    responsible_person=random.choice(responsible),
                    deadline=today + timedelta(days=random.randint(3, 14)),
                    status=random.choice(["pending", "in_progress", "completed"]),
                    created_by="system",
                    created_at=datetime.utcnow() - timedelta(days=random.randint(0, 7))
                )
                if action.status == "completed":
                    action.completed_time = datetime.utcnow()
                    action.result = "整改完成，损耗率有所下降"
                db.add(action)
        
        db.commit()
        print("数据库初始化完成！")
        print("\n默认账号:")
        print("  管理员: admin / admin123")
        print("  门店用户: store / store123")
        print("\n已创建示例数据:")
        print(f"  - {len(stores)} 家门店")
        print(f"  - {len(products)} 个商品")
        print(f"  - {len(reasons)} 种损耗原因")
        print(f"  - 200 条报损记录")
        print(f"  - 100 条盘点记录")
        
    except Exception as e:
        db.rollback()
        print(f"初始化失败: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
