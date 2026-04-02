"""
Pydantic models for daily/weekly report list, detail, and generate responses.
"""
from datetime import date, datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class DailyReportSummaryItem(BaseModel):
    report_date: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DailyReportsListResponse(BaseModel):
    reports: List[DailyReportSummaryItem] = Field(default_factory=list)


class DailyReportDetailResponse(BaseModel):
    report_date: Union[str, date, datetime]
    content: str
    created_at: Optional[Union[str, datetime, date]] = None
    updated_at: Optional[Union[str, datetime, date]] = None


class WeeklyReportSummaryItem(BaseModel):
    week_start: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WeeklyReportsListResponse(BaseModel):
    reports: List[WeeklyReportSummaryItem] = Field(default_factory=list)


class WeeklyReportDetailResponse(BaseModel):
    week_start: Union[str, date, datetime]
    content: str
    created_at: Optional[Union[str, datetime, date]] = None
    updated_at: Optional[Union[str, datetime, date]] = None


class TriggerDailyReportResponse(BaseModel):
    message: str
    report_date: str


class TriggerWeeklyReportResponse(BaseModel):
    message: str
    week_start: str
