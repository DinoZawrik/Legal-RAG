"""Маршруты для работы с Task Queue."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:  # pragma: no cover
    from services.gateway.app import APIGateway


def register(gateway: "APIGateway") -> None:
    app = gateway.app

    @app.get("/api/tasks/{task_id}/status")
    async def get_task_status(task_id: str):
        try:
            from core.task_queue import get_task_queue

            task_queue = await get_task_queue()
            task_status = await task_queue.get_task_status(task_id)
            if not task_status:
                raise HTTPException(status_code=404, detail="Task not found")

            return {
                "success": True,
                "task_id": task_id,
                "status": task_status.get("status"),
                "progress": task_status.get("progress", 0),
                "created_at": task_status.get("created_at"),
                "started_at": task_status.get("started_at"),
                "completed_at": task_status.get("completed_at"),
                "error_message": task_status.get("error_message"),
                "result": task_status.get("result"),
                "worker_id": task_status.get("worker_id"),
                "retry_count": task_status.get("retry_count", 0),
                "progress_messages": task_status.get("progress_messages", []),
            }
        except HTTPException:
            raise
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Error getting task status: {exc}")
            raise HTTPException(status_code=500, detail="Failed to get task status")

    @app.delete("/api/tasks/{task_id}")
    async def cancel_task(task_id: str):
        try:
            from core.task_queue import get_task_queue

            task_queue = await get_task_queue()
            cancelled = await task_queue.cancel_task(task_id)
            if not cancelled:
                raise HTTPException(status_code=404, detail="Task not found or cannot be cancelled")

            return {"success": True, "message": f"Task {task_id} has been cancelled", "task_id": task_id}
        except HTTPException:
            raise
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Error cancelling task: {exc}")
            raise HTTPException(status_code=500, detail="Failed to cancel task")

    @app.get("/api/tasks/queue/stats")
    async def get_queue_stats():
        try:
            from core.task_queue import get_task_queue

            task_queue = await get_task_queue()
            stats = await task_queue.get_queue_stats()
            return {"success": True, "stats": stats}
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Error getting queue stats: {exc}")
            raise HTTPException(status_code=500, detail="Failed to get queue stats")

    @app.post("/api/tasks/cleanup")
    async def cleanup_old_tasks(hours: int = 24):
        try:
            from core.task_queue import get_task_queue

            task_queue = await get_task_queue()
            cleaned_count = await task_queue.cleanup_old_tasks(hours)
            return {
                "success": True,
                "message": f"Cleaned up {cleaned_count} old tasks",
                "cleaned_count": cleaned_count,
            }
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Error cleaning up tasks: {exc}")
            raise HTTPException(status_code=500, detail="Failed to cleanup tasks")
