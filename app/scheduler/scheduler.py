from apscheduler.schedulers.background import BackgroundScheduler
from app.scheduler.jobs import daily_memory_job


def start_scheduler() -> BackgroundScheduler:
    """启动后台调度器并注册每日记忆汇总任务。"""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        daily_memory_job,
        "interval",
        hours=24,
        id="daily_memory_job",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
