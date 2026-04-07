"""
Reports router — daily and weekly generated reports (list, get, download, trigger).

Uses `import app as app_module` for `generate_daily_report_for_date` and
`generate_weekly_report_for_week` defined in app.py.
Stores from `database`.
"""
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

import app as app_module
from middleware import CurrentUser, get_current_user, require_admin
from adapters.driving.api.v1.dependencies import ReportRepositoryDep

from adapters.driving.api.v1.schemas.report_schemas import (
    DailyReportDetailResponse,
    DailyReportsListResponse,
    TriggerDailyReportResponse,
    TriggerWeeklyReportResponse,
    WeeklyReportDetailResponse,
    WeeklyReportsListResponse,
)

router = APIRouter()


@router.get("/daily", response_model=DailyReportsListResponse)
async def list_daily_reports(
    report_repository: ReportRepositoryDep,
    limit: int = 100,
    current_user: CurrentUser = Depends(get_current_user),
):
    """List daily reports (report_date, created_at, updated_at). All authenticated users."""
    reports = report_repository.list_daily_sync(limit=limit)
    result = []
    for r in reports:
        report_date = r["report_date"]
        if isinstance(report_date, datetime):
            report_date = report_date.isoformat()

        created_at = r.get("created_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        updated_at = r.get("updated_at")
        if isinstance(updated_at, datetime):
            updated_at = updated_at.isoformat()

        result.append({
            "report_date": report_date,
            "created_at": created_at,
            "updated_at": updated_at,
        })

    return {"reports": result}


@router.get("/daily/{report_date}", response_model=DailyReportDetailResponse)
async def get_daily_report(
    report_date: str,
    report_repository: ReportRepositoryDep,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get full content of a daily report by date (YYYY-MM-DD)."""
    report = report_repository.get_daily_by_date_sync(report_date)
    if not report:
        raise HTTPException(status_code=404, detail=f"No report for date {report_date}")
    return {
        "report_date": report["report_date"],
        "content": report["content"],
        "created_at": report.get("created_at"),
        "updated_at": report.get("updated_at"),
    }


@router.get("/daily/{report_date}/download", response_class=PlainTextResponse)
async def download_daily_report(
    report_date: str,
    report_repository: ReportRepositoryDep,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Download daily report as plain text/markdown."""
    report = report_repository.get_daily_by_date_sync(report_date)
    if not report:
        raise HTTPException(status_code=404, detail=f"No report for date {report_date}")
    return PlainTextResponse(
        content=report["content"],
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="reporte-{report_date}.md"'},
    )


@router.post("/daily/{report_date}/generate", response_model=TriggerDailyReportResponse)
async def trigger_daily_report_generation(
    report_date: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """Admin: trigger generation/regeneration of daily report for a date (YYYY-MM-DD)."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", report_date):
        raise HTTPException(status_code=400, detail="report_date must be YYYY-MM-DD")
    ok = app_module.generate_daily_report_for_date(report_date)
    if not ok:
        raise HTTPException(
            status_code=422,
            detail=f"No indexed documents with news_date={report_date} or generation failed",
        )
    return {"message": f"Report generated for {report_date}", "report_date": report_date}


@router.get("/weekly", response_model=WeeklyReportsListResponse)
async def list_weekly_reports(
    report_repository: ReportRepositoryDep,
    limit: int = 52,
    current_user: CurrentUser = Depends(get_current_user),
):
    """List weekly reports (week_start = Monday YYYY-MM-DD, created_at, updated_at). All authenticated users."""
    reports = report_repository.list_weekly_sync(limit=limit)
    result = []
    for r in reports:
        week_start = r["week_start"]
        if isinstance(week_start, datetime):
            week_start = week_start.isoformat()

        created_at = r.get("created_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        updated_at = r.get("updated_at")
        if isinstance(updated_at, datetime):
            updated_at = updated_at.isoformat()

        result.append({
            "week_start": week_start,
            "created_at": created_at,
            "updated_at": updated_at,
        })

    return {"reports": result}


@router.get("/weekly/{week_start}", response_model=WeeklyReportDetailResponse)
async def get_weekly_report(
    week_start: str,
    report_repository: ReportRepositoryDep,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get full content of a weekly report by week_start (Monday YYYY-MM-DD)."""
    report = report_repository.get_weekly_by_start_sync(week_start)
    if not report:
        raise HTTPException(status_code=404, detail=f"No report for week {week_start}")
    return {
        "week_start": report["week_start"],
        "content": report["content"],
        "created_at": report.get("created_at"),
        "updated_at": report.get("updated_at"),
    }


@router.get("/weekly/{week_start}/download", response_class=PlainTextResponse)
async def download_weekly_report(
    week_start: str,
    report_repository: ReportRepositoryDep,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Download weekly report as markdown."""
    report = report_repository.get_weekly_by_start_sync(week_start)
    if not report:
        raise HTTPException(status_code=404, detail=f"No report for week {week_start}")
    return PlainTextResponse(
        content=report["content"],
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="reporte-semanal-{week_start}.md"'},
    )


@router.post("/weekly/{week_start}/generate", response_model=TriggerWeeklyReportResponse)
async def trigger_weekly_report_generation(
    week_start: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """Admin: trigger generation/regeneration of weekly report (week_start = Monday YYYY-MM-DD)."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", week_start):
        raise HTTPException(status_code=400, detail="week_start must be YYYY-MM-DD")
    ok = app_module.generate_weekly_report_for_week(week_start)
    if not ok:
        raise HTTPException(
            status_code=422,
            detail=f"No indexed documents for that week or generation failed",
        )
    return {"message": f"Weekly report generated for {week_start}", "week_start": week_start}
