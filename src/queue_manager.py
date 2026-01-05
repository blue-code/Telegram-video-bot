"""
Background job queue system for playlist downloads.
"""
import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status enumeration."""
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadTask:
    """Represents a download task in the queue."""
    task_id: str
    user_id: int
    video_url: str
    video_title: str
    format_id: str
    quality: str
    status: TaskStatus = TaskStatus.QUEUED
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    progress: float = 0.0


class QueueManager:
    """Manages download queue for users."""
    
    def __init__(self):
        self.queues: Dict[int, asyncio.Queue] = {}
        self.tasks: Dict[str, DownloadTask] = {}
        self.running_tasks: Dict[int, Optional[str]] = {}
        self._lock = asyncio.Lock()
    
    async def add_task(self, task: DownloadTask) -> bool:
        """
        Add a task to the user's queue.
        
        Args:
            task: DownloadTask object
            
        Returns:
            True if task was added successfully
        """
        async with self._lock:
            user_id = task.user_id
            
            # Create queue for user if doesn't exist
            if user_id not in self.queues:
                self.queues[user_id] = asyncio.Queue()
            
            # Store task
            self.tasks[task.task_id] = task
            
            # Add to queue
            await self.queues[user_id].put(task.task_id)
            
            logger.info(f"Added task {task.task_id} to queue for user {user_id}")
            return True
    
    async def get_next_task(self, user_id: int) -> Optional[DownloadTask]:
        """
        Get the next task from user's queue.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Next DownloadTask or None if queue is empty
        """
        if user_id not in self.queues:
            return None
        
        queue = self.queues[user_id]
        
        if queue.empty():
            return None
        
        task_id = await queue.get()
        task = self.tasks.get(task_id)
        
        if task:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self.running_tasks[user_id] = task_id
        
        return task
    
    async def complete_task(self, task_id: str, success: bool = True, error: Optional[str] = None):
        """
        Mark a task as completed or failed.
        
        Args:
            task_id: Task ID
            success: Whether task completed successfully
            error: Error message if failed
        """
        async with self._lock:
            task = self.tasks.get(task_id)
            
            if not task:
                return
            
            task.completed_at = datetime.now()
            
            if success:
                task.status = TaskStatus.COMPLETED
                task.progress = 100.0
            else:
                task.attempts += 1
                
                if task.attempts >= task.max_attempts:
                    task.status = TaskStatus.FAILED
                    task.error = error
                else:
                    # Retry - add back to queue
                    task.status = TaskStatus.QUEUED
                    task.started_at = None
                    await self.queues[task.user_id].put(task_id)
                    logger.info(f"Retrying task {task_id} (attempt {task.attempts + 1}/{task.max_attempts})")
            
            # Clear running task
            if self.running_tasks.get(task.user_id) == task_id:
                self.running_tasks[task.user_id] = None
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.
        
        Args:
            task_id: Task ID
            
        Returns:
            True if task was cancelled
        """
        async with self._lock:
            task = self.tasks.get(task_id)
            
            if not task:
                return False
            
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            
            # Clear from running tasks
            if self.running_tasks.get(task.user_id) == task_id:
                self.running_tasks[task.user_id] = None
            
            logger.info(f"Cancelled task {task_id}")
            return True
    
    async def pause_task(self, task_id: str) -> bool:
        """
        Pause a task.
        
        Args:
            task_id: Task ID
            
        Returns:
            True if task was paused
        """
        async with self._lock:
            task = self.tasks.get(task_id)
            
            if not task or task.status != TaskStatus.RUNNING:
                return False
            
            task.status = TaskStatus.PAUSED
            logger.info(f"Paused task {task_id}")
            return True
    
    async def resume_task(self, task_id: str) -> bool:
        """
        Resume a paused task.
        
        Args:
            task_id: Task ID
            
        Returns:
            True if task was resumed
        """
        async with self._lock:
            task = self.tasks.get(task_id)
            
            if not task or task.status != TaskStatus.PAUSED:
                return False
            
            # Add back to queue
            task.status = TaskStatus.QUEUED
            task.started_at = None
            await self.queues[task.user_id].put(task_id)
            
            logger.info(f"Resumed task {task_id}")
            return True
    
    async def get_user_queue(self, user_id: int) -> List[DownloadTask]:
        """
        Get all tasks in user's queue.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of DownloadTask objects
        """
        user_tasks = [
            task for task in self.tasks.values()
            if task.user_id == user_id
        ]
        
        # Sort by created_at
        user_tasks.sort(key=lambda t: t.created_at)
        
        return user_tasks
    
    async def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """
        Get a task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            DownloadTask or None
        """
        return self.tasks.get(task_id)
    
    async def update_progress(self, task_id: str, progress: float):
        """
        Update task progress.
        
        Args:
            task_id: Task ID
            progress: Progress percentage (0-100)
        """
        task = self.tasks.get(task_id)
        if task:
            task.progress = min(100.0, max(0.0, progress))


# Global queue manager instance
queue_manager = QueueManager()


async def get_queue_status(user_id: int) -> Optional[Dict]:
    """
    Get queue status for a user.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        Dictionary with current download and queue items, or None
    """
    user_tasks = await queue_manager.get_user_queue(user_id)
    
    if not user_tasks:
        return None
    
    # Find currently running task
    running_task_id = queue_manager.running_tasks.get(user_id)
    current_task = None
    
    if running_task_id:
        current_task = await queue_manager.get_task(running_task_id)
    
    # Get queued tasks
    queued_tasks = [
        task for task in user_tasks
        if task.status == TaskStatus.QUEUED
    ]
    
    result = {}
    
    if current_task and current_task.status == TaskStatus.RUNNING:
        result['current'] = {
            'task_id': current_task.task_id,
            'title': current_task.video_title,
            'progress': current_task.progress,
            'quality': current_task.quality
        }
    
    if queued_tasks:
        result['queue'] = [
            {
                'task_id': task.task_id,
                'title': task.video_title,
                'quality': task.quality
            }
            for task in queued_tasks
        ]
    
    return result if result else None

