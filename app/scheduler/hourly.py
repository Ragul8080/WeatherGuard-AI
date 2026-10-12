"""Hourly autonomous scheduler for WeatherGuard AI."""

import argparse
import signal
import sys
from typing import Optional
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database.connection import init_db
from app.graph.workflow import run_workflow
from app.logging_config import logger


def scheduled_weather_check_job() -> None:
    """Invoked periodically by APScheduler to trigger the LangGraph workflow."""
    logger.info("================ SCHEDULER EXECUTION TRIGGERED ================")
    try:
        result = run_workflow()
        status = result.get("workflow_status", "UNKNOWN")
        alerts_count = len(result.get("saved_alert_ids", []))
        logger.info(
            f"Scheduler execution completed. Status: {status}. "
            f"Alerts triggered: {alerts_count}."
        )
    except Exception as exc:
        logger.error(
            f"Scheduled workflow execution encountered an error: {exc}",
            exc_info=True,
        )
        # Continue running: do not crash the scheduler
    logger.info("================================================================")


def create_scheduler(interval_minutes: Optional[int] = None) -> BlockingScheduler:
    """Create and configure the APScheduler instance with non-overlapping execution."""
    minutes = interval_minutes or settings.WEATHER_CHECK_INTERVAL_MINUTES
    scheduler = BlockingScheduler(timezone=settings.TIMEZONE)

    scheduler.add_job(
        func=scheduled_weather_check_job,
        trigger=IntervalTrigger(minutes=minutes),
        id="hourly_weather_guard_job",
        name="Hourly Autonomous Weather Check",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    logger.info(
        f"Scheduler initialized: checks configured every {minutes} minute(s) "
        f"in timezone {settings.TIMEZONE}."
    )
    return scheduler


def run_scheduler_daemon(
    interval_minutes: Optional[int] = None,
    interval_seconds: Optional[int] = None,
    run_immediately: bool = True,
) -> None:
    """Run the standalone scheduler daemon until interrupted."""
    logger.info("Starting WeatherGuard Autonomous Scheduler daemon...")
    init_db()

    if run_immediately:
        logger.info("Executing initial startup check immediately...")
        scheduled_weather_check_job()

    if interval_seconds:
        scheduler = BlockingScheduler(timezone=settings.TIMEZONE)
        scheduler.add_job(
            func=scheduled_weather_check_job,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id="test_weather_guard_job",
            max_instances=1,
            coalesce=True,
        )
        logger.info(f"Test mode active: checking every {interval_seconds} seconds.")
    else:
        scheduler = create_scheduler(interval_minutes)

    def handle_shutdown(signum, frame):
        logger.info(f"Received termination signal {signum}. Shutting down scheduler gracefully...")
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler daemon stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WeatherGuard Autonomous Scheduler")
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=None,
        help="Override interval in minutes (default from config: 60)",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=None,
        help="Dev/test override interval in seconds",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Execute a single check and exit immediately",
    )
    args = parser.parse_args()

    if args.run_once:
        init_db()
        scheduled_weather_check_job()
        sys.exit(0)

    run_scheduler_daemon(
        interval_minutes=args.interval_minutes,
        interval_seconds=args.interval_seconds,
    )
