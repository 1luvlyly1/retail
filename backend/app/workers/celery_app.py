import asyncio

from celery import Celery
from celery.signals import worker_process_init
from app.core.config import settings


@worker_process_init.connect
def _setup_worker_event_loop(**kwargs):
    """
    Sau khi fork, child process kế thừa asyncio primitives từ parent loop
    → RuntimeError "attached to a different loop" khi dùng engine pool.
    Giải pháp: tạo event loop sạch và dispose engine pool của process cha.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Dispose inherited SQLAlchemy async engine pool (asyncio Locks từ parent loop)
    from app.db.database import engine
    loop.run_until_complete(engine.dispose())


celery_app = Celery(
    "sitevisit",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=settings.CELERY_TASK_TIMEOUT,
    task_time_limit=settings.CELERY_TASK_TIMEOUT + 60,
    task_max_retries=settings.CELERY_MAX_RETRIES,
    result_expires=86400,
    task_routes={
        "app.workers.tasks.process_photo_task":   {"queue": "photo_processing"},
        "app.workers.tasks.enrich_company_task":  {"queue": "enrichment"},
        "app.workers.tasks.generate_report_task": {"queue": "default"},
    },
    task_default_queue="default",
)
