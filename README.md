# 智慧零售损耗预警后端服务

## 项目概述

智慧零售损耗预警系统是一个面向零售行业的损耗管理平台，为门店系统、仓储系统和运营后台提供统一的商品损耗风险查询接口。

## 核心功能

### 业务接口（17个核心接口）

1. **商品损耗评分** - 基于多维度算法计算商品损耗风险评分
2. **临期提醒** - 监控即将到期商品，提前预警
3. **盘亏异常** - 识别盘点差异异常情况
4. **报损提交** - 门店提交商品报损申请
5. **门店对比** - 多维度门店损耗情况对比分析
6. **原因归类** - 损耗原因统计分析
7. **预警订阅** - 用户订阅关注的预警类型
8. **按门店计算损耗率** - 自动计算各门店损耗率
9. **识别高频报损商品** - 智能识别频繁报损的商品
10. **推送临期清理建议** - 根据临期情况给出处理建议
11. **接收人工复核结果** - 支持对报损单的人工审核
12. **记录处理动作** - 跟踪所有整改和处理动作
13. **输出区域排行榜** - 按区域统计损耗情况排名
14. **查询历史趋势** - 展示损耗数据的历史变化趋势
15. **设置阈值** - 灵活配置各类预警阈值
16. **生成周报摘要** - 自动生成周度分析报告
17. **返回可执行的整改清单** - 智能生成整改建议列表

## 技术栈

- **Web框架**: FastAPI 0.109.0
- **ASGI服务器**: Uvicorn 0.27.0
- **ORM**: SQLAlchemy 2.0.25
- **数据验证**: Pydantic 2.5.3
- **定时任务**: APScheduler 3.10.4
- **认证**: JWT + Passlib
- **数据库**: SQLite (可扩展至PostgreSQL/MySQL)

## 项目结构

```
loss-warning-system/
├── app/
│   ├── __init__.py
│   ├── main.py              # 应用入口
│   ├── config.py            # 配置管理
│   ├── database.py          # 数据库连接
│   ├── models.py            # 数据模型
│   ├── scheduler.py         # 定时任务调度
│   ├── init_data.py         # 数据初始化脚本
│   ├── routers/             # API路由
│   │   ├── __init__.py
│   │   ├── auth.py          # 认证接口
│   │   ├── loss.py          # 损耗管理接口
│   │   ├── warning.py       # 预警管理接口
│   │   ├── actions.py       # 动作管理接口
│   │   ├── config.py        # 配置管理接口
│   │   └── reports.py       # 报表管理接口
│   ├── schemas/             # Pydantic数据模型
│   │   ├── __init__.py
│   │   └── schemas.py
│   └── services/            # 业务逻辑服务
│       ├── __init__.py
│       ├── auth.py          # 认证服务
│       ├── crud.py          # 通用CRUD服务
│       ├── loss_service.py  # 损耗计算服务
│       ├── warning_service.py  # 预警分析服务
│       └── report_service.py   # 报表生成服务
├── requirements.txt         # 依赖清单
├── start.bat                # Windows启动脚本
├── start.sh                 # Linux/Mac启动脚本
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 初始化数据库

```bash
python -m app.init_data
```

### 3. 启动服务

Windows:
```bash
start.bat
```

Linux/Mac:
```bash
chmod +x start.sh
./start.sh
```

或直接运行:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 访问API文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 默认账号

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| admin | admin123 | admin | 系统管理员 |
| store | store123 | store_manager | 门店管理员 |

## API接口列表

### 认证接口 (`/api/v1/auth`)
- `POST /login` - 用户登录获取Token
- `POST /register` - 用户注册
- `GET /me` - 获取当前用户信息

### 损耗管理接口 (`/api/v1/loss`)
- `GET /rate/store/{store_id}` - 按门店计算损耗率
- `GET /rate/stores` - 获取所有门店损耗率
- `GET /high-frequency` - 识别高频报损商品
- `GET /risk-score/{product_id}` - 商品损耗评分
- `GET /risk-scores` - 批量商品损耗评分
- `GET /categories` - 原因归类统计
- `GET /trend` - 查询历史趋势
- `GET /regional-ranking` - 输出区域排行榜
- `GET /store-comparison` - 门店对比
- `GET /correction-list` - 返回可执行的整改清单
- `POST /report` - 报损提交
- `GET /reports` - 查询报损记录
- `PUT /report/{report_id}/review` - 接收人工复核结果

### 预警管理接口 (`/api/v1/warning`)
- `GET /expiry-reminders` - 临期提醒
- `GET /expiry-suggestions` - 推送临期清理建议
- `GET /shortage-abnormalities` - 盘亏异常
- `POST /inventory-check` - 提交盘点记录
- `GET /alerts` - 查询预警列表
- `GET /alerts/{alert_id}` - 预警详情
- `PUT /alerts/{alert_id}/handle` - 处理预警
- `POST /run-checks` - 立即执行预警检查
- `GET /subscriptions` - 获取预警订阅列表
- `POST /subscriptions` - 预警订阅
- `PUT /subscriptions/{sub_id}` - 更新订阅
- `POST /subscriptions/{sub_id}/toggle` - 启用/禁用订阅

### 动作管理接口 (`/api/v1/actions`)
- `POST /` - 记录处理动作
- `GET /` - 查询处理动作列表
- `GET /{action_id}` - 获取动作详情
- `PUT /{action_id}/complete` - 完成处理动作

### 配置管理接口 (`/api/v1/config`)
- `GET /thresholds` - 获取所有阈值配置
- `GET /thresholds/{config_key}` - 获取单个阈值配置
- `PUT /thresholds/{config_key}` - 设置阈值
- `POST /thresholds` - 创建阈值配置

### 报表管理接口 (`/api/v1/reports`)
- `GET /weekly` - 查询周报历史
- `POST /weekly/generate` - 生成周报摘要
- `POST /weekly/generate-all` - 批量生成所有周报
- `GET /stores` - 查询门店列表
- `GET /products` - 查询商品列表
- `GET /reasons` - 查询损耗原因列表
- `POST /stores` - 创建门店
- `POST /products` - 创建商品
- `POST /reasons` - 创建损耗原因

## 定时任务

系统内置两个定时任务：

1. **每日预警检查** - 每天凌晨2:00执行
   - 临期商品预警检查
   - 盘亏异常预警检查
   - 高频损耗预警检查
   - 损耗率超标预警检查

2. **每周报告生成** - 每周一凌晨2:30执行
   - 全区域周报生成
   - 各区域周报生成
   - 各门店周报生成

## 预警类型

| 类型 | 说明 | 触发条件 |
|------|------|----------|
| expiry | 临期预警 | 商品保质期小于配置的预警天数 |
| shortage | 盘亏异常 | 盘点差异率超过阈值 |
| high_loss | 高频损耗 | 商品30天内报损超过阈值 |
| loss_rate | 损耗率超标 | 门店月损耗率超过阈值 |

## 预警级别

| 级别 | 说明 | 风险评分范围 |
|------|------|-------------|
| critical | 紧急 | 90-100 |
| high | 高 | 70-89 |
| medium | 中 | 40-69 |
| low | 低 | 0-39 |

## 风险评分算法

商品损耗风险评分由以下四个维度加权计算：

1. **频次分 (40%)** - 近90天报损次数 × 5，最高40分
2. **金额分 (30%)** - 损失率 × 3，最高30分
3. **时效分 (30%)** - 距最近报损天数，最近最高30分
4. **多样性分 (10%)** - 不同原因数 × 5，最高10分

总分 = 频次分 + 金额分 + 时效分 + 多样性分（最高100分）

## 部署建议

### 生产环境配置

1. **数据库**: 建议使用 PostgreSQL 12+ 或 MySQL 8.0+
2. **进程管理**: 使用 systemd 或 supervisor 管理进程
3. **反向代理**: 使用 Nginx 作为反向代理
4. **日志**: 配置文件日志输出，建议接入 ELK 等日志分析系统

### 配置示例 (PostgreSQL)

修改 `app/config.py`:
```python
DATABASE_URL: str = "postgresql://user:password@localhost:5432/loss_warning"
```

### 环境变量配置

支持通过环境变量覆盖配置：
```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/loss_warning"
export SECRET_KEY="your-production-secret-key"
```

## 数据字典

### stores (门店表)
- id, name, code, region, city, address, manager, phone, is_active

### products (商品表)
- id, sku, name, category, sub_category, brand, spec, unit, cost_price, sale_price, shelf_life_days, expiry_warning_days

### inventories (库存表)
- id, store_id, product_id, batch_no, quantity, available_quantity, production_date, expiry_date, warehouse_location

### loss_reports (报损表)
- id, report_no, store_id, product_id, reason_id, quantity, amount, batch_no, expiry_date, report_time, reporter, status, reviewer, is_high_frequency

### warning_alerts (预警表)
- id, alert_no, store_id, product_id, alert_type, level, title, content, risk_score, status, is_handled, handled_by, handled_time

### weekly_reports (周报表)
- id, report_no, region, store_id, week_start, week_end, total_loss_amount, total_loss_quantity, loss_rate, summary, suggestions

## 运营系统集成指南

运营系统只需按接口调用即可展示所有结果，以下是推荐的页面接口映射：

### 1. 首页仪表盘
- `/api/v1/loss/rate/stores` - 门店损耗率概览
- `/api/v1/loss/regional-ranking` - 区域排名
- `/api/v1/loss/categories` - 损耗原因分布
- `/api/v1/loss/trend` - 趋势图

### 2. 商品损耗页面
- `/api/v1/loss/risk-scores` - 商品风险评分列表
- `/api/v1/loss/high-frequency` - 高频损耗商品
- `/api/v1/loss/risk-score/{product_id}` - 商品详情

### 3. 临期管理页面
- `/api/v1/warning/expiry-reminders` - 临期商品列表
- `/api/v1/warning/expiry-suggestions` - 清理建议

### 4. 盘点管理页面
- `/api/v1/warning/shortage-abnormalities` - 盘亏异常
- `/api/v1/warning/inventory-check` - 提交盘点

### 5. 报损管理页面
- `/api/v1/loss/reports` - 报损记录列表
- `/api/v1/loss/report` - 提交报损
- `/api/v1/loss/report/{id}/review` - 审核报损

### 6. 预警中心
- `/api/v1/warning/alerts` - 预警列表
- `/api/v1/warning/alerts/{id}/handle` - 处理预警
- `/api/v1/warning/subscriptions` - 订阅管理

### 7. 整改追踪
- `/api/v1/actions` - 整改动作列表
- `/api/v1/loss/correction-list` - 整改清单
- `/api/v1/actions/{id}/complete` - 完成整改

### 8. 分析报告
- `/api/v1/reports/weekly` - 周报历史
- `/api/v1/reports/weekly/generate` - 生成周报
- `/api/v1/loss/store-comparison` - 门店对比

## 许可证

MIT License
