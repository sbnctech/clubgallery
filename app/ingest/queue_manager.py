"""
SBNC Photo Gallery System - Processing Queue Manager
Manage the photo processing queue.
"""

import json
import uuid
from datetime import datetime
import logging

from app.database import get_db

logger = logging.getLogger(__name__)


class QueueManager:
    """Manage the photo processing queue."""

    @staticmethod
    def get_pending_items(limit=50):
        """Get pending items from the queue, ordered by priority."""
        with get_db() as conn:
            rows = conn.execute('''
                SELECT q.*, m.display_name as submitter_name
                FROM processing_queue q
                LEFT JOIN members m ON q.submitter_member_id = m.id
                WHERE q.status = 'pending'
                ORDER BY q.priority DESC, q.submitted_at ASC
                LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_item(queue_id):
        """Get a specific queue item."""
        with get_db() as conn:
            row = conn.execute(
                'SELECT * FROM processing_queue WHERE id = ?',
                (queue_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def mark_processing(queue_id):
        """Mark a queue item as being processed."""
        with get_db() as conn:
            conn.execute('''
                UPDATE processing_queue
                SET status = 'processing', started_at = ?, attempts = attempts + 1
                WHERE id = ?
            ''', (datetime.utcnow(), queue_id))

    @staticmethod
    def mark_completed(queue_id, photo_id=None):
        """Mark a queue item as completed."""
        with get_db() as conn:
            conn.execute('''
                UPDATE processing_queue
                SET status = 'completed', completed_at = ?
                WHERE id = ?
            ''', (datetime.utcnow(), queue_id))

    @staticmethod
    def mark_failed(queue_id, error_message):
        """Mark a queue item as failed."""
        with get_db() as conn:
            conn.execute('''
                UPDATE processing_queue
                SET status = 'failed', error_message = ?, completed_at = ?
                WHERE id = ?
            ''', (error_message, datetime.utcnow(), queue_id))

    @staticmethod
    def retry_failed(max_attempts=3):
        """Reset failed items for retry if under max attempts."""
        with get_db() as conn:
            result = conn.execute('''
                UPDATE processing_queue
                SET status = 'pending', error_message = NULL
                WHERE status = 'failed' AND attempts < ?
            ''', (max_attempts,))
            return result.rowcount

    @staticmethod
    def get_queue_stats():
        """Get statistics about the processing queue."""
        with get_db() as conn:
            stats = {}

            # Count by status
            rows = conn.execute('''
                SELECT status, COUNT(*) as count
                FROM processing_queue
                GROUP BY status
            ''').fetchall()

            for row in rows:
                stats[row['status']] = row['count']

            # Get oldest pending
            oldest = conn.execute('''
                SELECT submitted_at FROM processing_queue
                WHERE status = 'pending'
                ORDER BY submitted_at ASC
                LIMIT 1
            ''').fetchone()

            if oldest:
                stats['oldest_pending'] = oldest['submitted_at']

            return stats

    @staticmethod
    def cleanup_completed(days_old=7):
        """Remove completed queue items older than specified days."""
        with get_db() as conn:
            result = conn.execute('''
                DELETE FROM processing_queue
                WHERE status = 'completed'
                AND completed_at < datetime('now', ? || ' days')
            ''', (f'-{days_old}',))
            return result.rowcount
