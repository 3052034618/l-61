from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import logging

from app.config import settings
from app.database import SessionLocal
from app.services.warning_service import run_all_alert_checks
from app.services.report_service import generate_all_weekly_reports

logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.WARNING)


def check_warnings_job():
    db = SessionLocal()
    try:
        results = run_all_alert_checks(db)
        print(f"[{datetime.utcnow()}] 预警检查完成: {results}")
    except Exception as e:
        print(f"[{datetime.utcnow()}] 预警检查失败: {str(e)}")
    finally:
        db.close()


def generate_weekly_report_job():
    db = SessionLocal()
    try:
        results = generate_all_weekly_reports(db)
        print(f"[{datetime.utcnow()}] 周报告生成完成: 共生成 {len(results)} 份报告")
    except Exception as e:
        print(f"[{datetime.utcnow()}] 周报告生成失败: {str(e)}")
    finally:
        db.close()


def start_scheduler():
    scheduler = BackgroundScheduler()
    
    scheduler.add_job(
        check_warnings_job,
        'cron',
        hour=settings.SCHEDULER_HOUR,
        minute=settings.SCHEDULER_MINUTE,
        id='daily_warning_check',
        replace_existing=True
    )
    
    scheduler.add_job(
        generate_weekly_report_job,
        'cron',
        day_of_week='mon',
        hour=settings.SCHEDULER_HOUR,
        minute=settings.SCHEDULER_MINUTE + 30,
        id='weekly_report_generation',
        replace_existing=True
    )
    
    scheduler.start()
    print(f"定时任务调度器已启动，配置时间: 每天 {settings.SCHEDULER_HOUR:02d}:{settings.SCHEDULER_MINUTE:02d} 执行预警检查，每周一 {settings.SCHEDULER_HOUR:02d}:{settings.SCHEDULER_MINUTE + 30:02d} 生成周报")
    
    return scheduler


def shutdown_scheduler(scheduler):
    if scheduler and scheduler.running:
        scheduler.shutdown()
        print("定时任务调度器已停止")
