from datetime import datetime
from pydantic import BaseModel


class WorkflowStatusSummary(BaseModel):
    total: int
    published: int
    paused: int
    draft: int
    needs_attention: int


class ExecutionMetricsSummary(BaseModel):
    total_runs: int
    successful_runs: int
    failed_runs: int
    running_runs: int
    success_rate: float
    avg_duration_seconds: float


class DailyRunMetric(BaseModel):
    date: str
    total: int
    success: int
    failed: int
    success_rate: float


class WorkflowMonitoringItem(BaseModel):
    id: int
    name: str
    status: str
    health_status: str
    health_message: str
    total_runs: int
    success_runs: int
    failed_runs: int
    success_rate: float | None = None
    tasks_this_month: int
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    created_at: datetime


class DashboardOverviewResponse(BaseModel):
    period_days: int
    workflow_summary: WorkflowStatusSummary
    execution_metrics: ExecutionMetricsSummary
    timeline: list[DailyRunMetric]
    workflows: list[WorkflowMonitoringItem]


class WorkflowUsageItem(BaseModel):
    workflow_id: int
    workflow_name: str
    status: str
    tasks_this_month: int
    successful_tasks_this_month: int
    failed_tasks_this_month: int
    percentage_of_total: float
    last_executed_at: datetime | None = None


class MonthlyUsageResponse(BaseModel):
    year: int
    month: int
    period_label: str
    total_tasks_this_month: int
    total_successful_tasks: int
    total_failed_tasks: int
    active_workflows_count: int
    workflow_usage: list[WorkflowUsageItem]
