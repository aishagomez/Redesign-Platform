import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models import ExecutionLog, Notification, Pipeline, Project, ServiceExecution, StageExecution, User
from services.file_storage import GENERATED_ROOT, PERSISTENT_STORAGE_ROOT, UPLOADS_ROOT
from services.reports import REPORTS_ROOT

logger = logging.getLogger(__name__)
GUEST_DATA_RETENTION_DAYS = max(1, int(os.environ.get("GUEST_DATA_RETENTION_DAYS", "90")))
ACTIVE_PIPELINE_STATUSES = {"pending", "running", "retrying", "waiting_for_approval"}


def cleanup_expired_guest_data(db: Session) -> dict[str, int]:
    """Delete guest projects, pipelines, and uploaded files past the retention window."""
    cutoff_aware = datetime.now(timezone.utc) - timedelta(days=GUEST_DATA_RETENTION_DAYS)
    cutoff_naive = cutoff_aware.replace(tzinfo=None)
    guest = db.query(User).filter(User.role == "guest", User.email == "guest@example.com").first()
    if guest is None:
        return {"projects": 0, "pipelines": 0, "files": 0}

    active_project_ids = {
        row.project_id
        for row in (
            db.query(Pipeline.project_id)
            .filter(Pipeline.status.in_(ACTIVE_PIPELINE_STATUSES))
            .all()
        )
    }
    expired_projects = (
        db.query(Project)
        .filter(Project.user_id == guest.id, Project.created_at < cutoff_naive)
        .all()
    )
    expired_project_ids = [
        project.id
        for project in expired_projects
        if not db.query(Pipeline.id)
        .filter(Pipeline.project_id == project.id, Pipeline.created_at >= cutoff_aware)
        .first()
        and not _contains_recent_file(
            UPLOADS_ROOT / f"user_{guest.id}" / f"project_{project.id}", cutoff_aware
        )
        and not _contains_recent_file(
            REPORTS_ROOT / f"user_{guest.id}" / f"project_{project.id}", cutoff_aware
        )
    ]
    projects_to_delete = [
        project_id for project_id in expired_project_ids
        if project_id not in active_project_ids
    ]

    project_pipeline_ids: dict[int, list[int]] = {}
    for project_id in projects_to_delete:
        project_pipeline_ids[project_id] = [
            row.id for row in db.query(Pipeline.id).filter(Pipeline.project_id == project_id).all()
        ]

    expired_pipeline_rows = (
        db.query(Pipeline.id, Pipeline.project_id)
        .join(Project, Project.id == Pipeline.project_id)
        .filter(
            Project.user_id == guest.id,
            Pipeline.created_at < cutoff_aware,
            ~Pipeline.status.in_(ACTIVE_PIPELINE_STATUSES),
        )
        .all()
    )
    pipeline_ids_to_delete = {
        row.id for row in expired_pipeline_rows
        if row.project_id not in projects_to_delete
    }
    for pipeline_ids in project_pipeline_ids.values():
        pipeline_ids_to_delete.update(pipeline_ids)

    files_removed = 0
    for project in db.query(Project).filter(Project.user_id == guest.id).all():
        project_uploads = UPLOADS_ROOT / f"user_{guest.id}" / f"project_{project.id}"
        if project.id in projects_to_delete:
            _remove_tree(UPLOADS_ROOT, project_uploads)
        else:
            files_removed += _remove_expired_files(project_uploads, cutoff_aware)

    guest_reports = REPORTS_ROOT / f"user_{guest.id}"
    files_removed += _remove_expired_files(guest_reports, cutoff_aware)

    for pipeline_id in pipeline_ids_to_delete:
        _remove_tree(GENERATED_ROOT, GENERATED_ROOT / f"pipeline_{pipeline_id}")
        stage_ids = [
            row.id for row in db.query(StageExecution.id)
            .filter(StageExecution.pipeline_id == pipeline_id).all()
        ]
        runs_root = PERSISTENT_STORAGE_ROOT / "runs"
        for stage_id in stage_ids:
            _remove_tree(runs_root, runs_root / f"stage_{stage_id}")
        guest_reports = REPORTS_ROOT / f"user_{guest.id}"
        if guest_reports.exists():
            for report_dir in guest_reports.rglob(f"pipeline_{pipeline_id}"):
                _remove_tree(guest_reports, report_dir)
        output_root = PERSISTENT_STORAGE_ROOT / "outputs" / guest.username
        if output_root.exists():
            for output_dir in output_root.glob(f"*/pipeline_{pipeline_id}"):
                _remove_tree(output_root, output_dir)

    if pipeline_ids_to_delete:
        _delete_pipeline_records(db, pipeline_ids_to_delete)

    if projects_to_delete:
        db.query(Project).filter(Project.id.in_(projects_to_delete)).delete(synchronize_session=False)

    db.query(Notification).filter(
        Notification.user_id == guest.id,
        Notification.sent_at < cutoff_naive,
    ).delete(synchronize_session=False)
    db.commit()

    return {
        "projects": len(projects_to_delete),
        "pipelines": len(pipeline_ids_to_delete),
        "files": files_removed,
    }


def _delete_pipeline_records(db: Session, pipeline_ids: set[int]) -> None:
    stage_ids = [
        row.id for row in db.query(StageExecution.id)
        .filter(StageExecution.pipeline_id.in_(pipeline_ids)).all()
    ]
    service_ids = [
        row.id for row in db.query(ServiceExecution.id)
        .filter(ServiceExecution.pipeline_id.in_(pipeline_ids)).all()
    ]
    log_filters = []
    if stage_ids:
        log_filters.append(ExecutionLog.stage_execution_id.in_(stage_ids))
    if service_ids:
        log_filters.append(ExecutionLog.service_execution_id.in_(service_ids))
    if log_filters:
        db.query(ExecutionLog).filter(or_(*log_filters)).delete(synchronize_session=False)
    if stage_ids:
        db.query(StageExecution).filter(StageExecution.id.in_(stage_ids)).delete(synchronize_session=False)
    if service_ids:
        db.query(ServiceExecution).filter(ServiceExecution.id.in_(service_ids)).delete(synchronize_session=False)
    db.query(Pipeline).filter(Pipeline.id.in_(pipeline_ids)).delete(synchronize_session=False)


def _remove_tree(root: Path, target: Path) -> None:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    if target_resolved != root_resolved and root_resolved in target_resolved.parents:
        if target_resolved.exists():
            shutil.rmtree(target_resolved, ignore_errors=True)


def _remove_expired_files(root: Path, cutoff: datetime) -> int:
    if not root.exists():
        return 0
    removed = 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            logger.exception("Could not remove expired guest file %s", path)
    return removed


def _contains_recent_file(root: Path, cutoff: datetime) -> bool:
    if not root.exists():
        return False
    for path in root.rglob("*"):
        try:
            if path.is_file() and datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) >= cutoff:
                return True
        except OSError:
            logger.exception("Could not inspect guest file %s", path)
    return False
