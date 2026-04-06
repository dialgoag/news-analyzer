"""
Admin router — reindex, memory, stats, logging, insights pipeline, data integrity, backup.

Uses `import app as app_module` for globals and helpers defined in app.py.
"""
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

import app as app_module
from adapters.driving.api.v1.dependencies import AdminDataIntegrityServiceDep
from adapters.driving.api.v1.schemas.admin_schemas import InsightsPipelineUpdate
from backup_models import (
    BackupProviderCreate,
    BackupRestoreRequest,
    BackupRunRequest,
    BackupScheduleRequest,
)
from backup_service import backup_service
from middleware import CurrentUser, require_admin

router = APIRouter()


# ---------------------------------------------------------------------------
# Reindex
# ---------------------------------------------------------------------------


@router.post("/reindex-all")
async def reindex_all(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Reindex all documents (re-embed with current model/prefix).
    Use after changing EMBEDDING_MODEL or instruction prefix.
    Requires: Admin
    """
    if not app_module.qdrant_connector:
        raise HTTPException(status_code=503, detail="Qdrant not initialized")
    app_module.logger.info("🔄 Starting reindexing of all documents...")
    background_tasks.add_task(app_module._run_reindex_all)
    return {"message": "Reindexing in progress. Check logs for progress."}


# ---------------------------------------------------------------------------
# Memory management
# ---------------------------------------------------------------------------


@router.delete("/memory/{user_id}")
async def clear_user_memory(
    user_id: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """Clear conversational memory for a specific user"""
    if user_id in app_module.user_conversations:
        num_exchanges = len(app_module.user_conversations[user_id])
        del app_module.user_conversations[user_id]
        app_module.logger.info(
            f"🧹 Memory cleared for user '{user_id}' ({num_exchanges} exchanges removed)"
        )
        return {
            "message": f"Memory cleared for user '{user_id}'",
            "exchanges_removed": num_exchanges,
        }
    return {
        "message": f"No memory found for user '{user_id}'",
        "exchanges_removed": 0,
    }


@router.delete("/memory")
async def clear_all_memory(current_user: CurrentUser = Depends(require_admin)):
    """Clear ALL conversational memory for all users"""
    total_users = len(app_module.user_conversations)
    total_exchanges = sum(len(conv) for conv in app_module.user_conversations.values())
    app_module.user_conversations.clear()
    app_module.logger.info(
        f"🧹 Global memory cleared: {total_users} users, {total_exchanges} total exchanges"
    )
    return {
        "message": "Global memory cleared",
        "users_removed": total_users,
        "exchanges_removed": total_exchanges,
    }


@router.get("/memory")
async def get_memory_stats(current_user: CurrentUser = Depends(require_admin)):
    """Conversational memory statistics"""
    stats = {"total_users": len(app_module.user_conversations), "users": {}}
    for user_id, history in app_module.user_conversations.items():
        stats["users"][user_id] = {
            "exchanges": len(history),
            "last_questions": [msg["user"] for msg in history[-3:]],
        }
    return stats


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats")
async def get_stats(current_user: CurrentUser = Depends(require_admin)):
    """System statistics"""
    if not app_module.qdrant_connector:
        raise HTTPException(status_code=503, detail="Qdrant not connected")

    try:
        return app_module.qdrant_connector.get_stats()
    except Exception as e:
        app_module.logger.error(f"Statistics error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


@router.get("/logging")
async def get_logging_config(current_user: CurrentUser = Depends(require_admin)):
    """Get current logging configuration"""
    return {
        "current_level": app_module.get_effective_log_level(),
        "default_level": app_module.LOG_LEVEL,
        "has_override": app_module._log_level_override is not None,
        "available_levels": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    }


@router.put("/logging")
async def update_logging_config(
    level: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """Change log level at runtime without restarting"""
    try:
        app_module.set_log_level(level)
        return {
            "success": True,
            "new_level": level.upper(),
            "message": f"Log level changed to {level.upper()} (no restart required)",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Insights pipeline
# ---------------------------------------------------------------------------


@router.get("/insights-pipeline")
async def get_insights_pipeline_settings(current_user: CurrentUser = Depends(require_admin)):
    """Runtime insights controls: pause steps, provider order vs .env chain."""
    import insights_pipeline_control as _ipc

    return _ipc.get_snapshot()


@router.put("/insights-pipeline")
async def put_insights_pipeline_settings(
    body: InsightsPipelineUpdate,
    current_user: CurrentUser = Depends(require_admin),
):
    import insights_pipeline_control as _ipc

    try:
        patch = body.model_dump(exclude_unset=True)
        ollama_kw = {}
        if "ollama_model" in patch:
            ollama_kw["ollama_model"] = patch["ollama_model"]
        snap = _ipc.update_settings(
            pause_generation=body.pause_generation,
            pause_indexing_insights=body.pause_indexing_insights,
            pause_steps=body.pause_steps,
            pause_all=body.pause_all,
            resume_all=body.resume_all,
            provider_mode=body.provider_mode,
            provider_order=body.provider_order,
            **ollama_kw,
        )
        return {"success": True, **snap}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Data integrity
# ---------------------------------------------------------------------------


@router.get("/data-integrity")
async def get_data_integrity(
    current_user: CurrentUser = Depends(require_admin),
    integrity_service: AdminDataIntegrityServiceDep = Depends(),
):
    """Data integrity metrics: files vs DB, insights linkage, schema validation."""
    try:
        return integrity_service.get_data_integrity()
    except Exception as e:
        app_module.logger.error(f"Data integrity error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Backup & restore
# ---------------------------------------------------------------------------


@router.get("/backup/status")
async def get_backup_status(current_user: CurrentUser = Depends(require_admin)):
    """Get backup system status"""
    return backup_service.get_status()


@router.get("/backup/providers")
async def list_backup_providers(current_user: CurrentUser = Depends(require_admin)):
    """List configured cloud providers and supported types"""
    return {
        "providers": backup_service.list_providers(),
        "supported_types": backup_service.get_supported_providers(),
    }


@router.post("/backup/providers")
async def add_backup_provider(
    provider: BackupProviderCreate,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Add a new cloud provider for backup.

    Example configurations:
    - Mega: {"name": "mega", "type": "mega", "config": {"user": "email", "pass": "password"}}
    - S3: {"name": "aws", "type": "s3", "config": {"provider": "AWS", "access_key_id": "...", "secret_access_key": "...", "region": "eu-west-1"}}
    - Google Drive: {"name": "gdrive", "type": "drive", "config": {"token": "{...}"}}
    - WebDAV/Nextcloud: {"name": "nextcloud", "type": "webdav", "config": {"url": "https://...", "user": "...", "pass": "..."}}
    """
    return backup_service.add_provider(
        name=provider.name,
        provider_type=provider.type,
        config=provider.config,
    )


@router.delete("/backup/providers/{name}")
async def remove_backup_provider(
    name: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """Remove a configured cloud provider"""
    backup_service.remove_provider(name)
    return {"message": f"Provider '{name}' removed"}


@router.post("/backup/providers/{name}/test")
async def test_backup_provider(
    name: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """Test connection to a cloud provider"""
    return backup_service.test_provider(name)


@router.post("/backup/run")
async def run_backup(
    request: BackupRunRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Trigger a manual backup.

    If 'provider' is specified, the backup will be uploaded to that cloud provider.
    Otherwise, it will be stored locally only.
    """
    background_tasks.add_task(
        app_module._execute_manual_backup,
        request.provider,
        request.remote_path,
    )
    return {"message": "Backup started", "status": "running"}


@router.get("/backup/schedule")
async def get_backup_schedule(current_user: CurrentUser = Depends(require_admin)):
    """Get current backup schedule"""
    return app_module.backup_scheduler.get_schedule()


@router.post("/backup/schedule")
async def set_backup_schedule(
    request: BackupScheduleRequest,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Set or update the backup schedule.

    Cron expression examples:
    - "0 2 * * *"     → Daily at 2:00 AM
    - "0 3 * * 0"     → Weekly on Sunday at 3:00 AM
    - "0 1 1 * *"     → Monthly on the 1st at 1:00 AM
    - "0 */6 * * *"   → Every 6 hours
    """
    return app_module.backup_scheduler.set_schedule(
        cron_expression=request.cron,
        provider=request.provider,
        remote_path=request.remote_path,
        retention=request.retention,
        enabled=request.enabled,
    )


@router.get("/backup/history")
async def get_backup_history(current_user: CurrentUser = Depends(require_admin)):
    """Get backup execution history"""
    return {"history": backup_service.get_history()}


@router.get("/backup/local")
async def list_local_backups(current_user: CurrentUser = Depends(require_admin)):
    """List local backup files"""
    return {"backups": backup_service.list_local_backups()}


@router.delete("/backup/local/{filename}")
async def delete_local_backup(
    filename: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """Delete a local backup file"""
    if backup_service.delete_local_backup(filename):
        return {"message": f"Backup '{filename}' deleted"}
    raise HTTPException(status_code=404, detail="Backup not found")


@router.get("/backup/cloud/{provider}")
async def list_cloud_backups(
    provider: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """List backups stored on a cloud provider"""
    return {"backups": backup_service.list_cloud_backups(provider)}


@router.post("/backup/cloud/{provider}/download")
async def download_cloud_backup(
    provider: str,
    filename: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """Download a backup from cloud to local storage"""
    local_path = backup_service.download_from_cloud(provider, filename)
    return {"message": f"Downloaded to {local_path}", "local_path": local_path}


@router.post("/backup/restore")
async def restore_backup(
    request: BackupRestoreRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Restore from a local backup archive.

    WARNING: This will overwrite current data. Use with caution.
    """
    archive_path = os.path.join(app_module.BACKUP_DIR, request.filename)
    if not os.path.exists(archive_path):
        raise HTTPException(status_code=404, detail="Backup file not found")

    background_tasks.add_task(
        app_module._execute_restore,
        archive_path,
        request.restore_db,
        request.restore_uploads,
        request.restore_qdrant,
    )
    return {"message": "Restore started", "status": "running"}
