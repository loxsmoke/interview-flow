"""Tests for process-local AI queue state."""

import asyncio

from app.queue_manager import QueueManager


def run(coro):
    return asyncio.run(coro)


def test_enqueue_promotes_first_item_and_dedupes_same_section():
    async def scenario():
        manager = QueueManager()

        first = await manager.enqueue("state-1", "pitch", "Pitch")
        duplicate = await manager.enqueue("state-1", "pitch", "Pitch")
        snapshot = await manager.snapshot()

        assert first.id == duplicate.id
        assert snapshot["running"]["section_key"] == "pitch"
        assert snapshot["queued"] == []

    run(scenario())


def test_waiting_items_are_sorted_by_sidebar_order_not_click_order():
    async def scenario():
        manager = QueueManager()

        running = await manager.enqueue("state-1", "pitch", "Pitch")
        assert running.status == "running"

        await manager.enqueue("state-1", "salary", "Salary")
        await manager.enqueue("state-1", "jd_decode", "Job Decoder")
        await manager.enqueue("state-1", "concerns", "Concerns")
        snapshot = await manager.snapshot()

        assert snapshot["running"]["section_key"] == "pitch"
        assert [item["section_key"] for item in snapshot["queued"]] == [
            "jd_decode",
            "concerns",
            "salary",
        ]

    run(scenario())


def test_unqueue_then_requeue_returns_item_to_sidebar_order_position():
    async def scenario():
        manager = QueueManager()

        await manager.enqueue("state-1", "pitch", "Pitch")
        salary = await manager.enqueue("state-1", "salary", "Salary")
        await manager.enqueue("state-1", "jd_decode", "Job Decoder")

        await manager.unqueue(salary.id)
        await manager.enqueue("state-1", "salary", "Salary")
        snapshot = await manager.snapshot()

        assert [item["section_key"] for item in snapshot["queued"]] == [
            "jd_decode",
            "salary",
        ]

    run(scenario())


def test_completion_starts_next_waiting_item():
    async def scenario():
        manager = QueueManager()

        first = await manager.enqueue("state-1", "research", "Research")
        await manager.enqueue("state-1", "pitch", "Pitch")

        await manager.mark_completed(first.id)
        snapshot = await manager.snapshot()

        assert snapshot["running"]["section_key"] == "pitch"
        assert snapshot["queued"] == []
        assert snapshot["failed"] == []

    run(scenario())


def test_failure_is_reported_and_next_item_starts():
    async def scenario():
        manager = QueueManager()

        first = await manager.enqueue("state-1", "research", "Research")
        await manager.enqueue("state-1", "salary", "Salary")

        await manager.mark_failed(first.id, "Boom", "Stack trace")
        snapshot = await manager.snapshot()

        assert snapshot["running"]["section_key"] == "salary"
        assert snapshot["failed"][0]["section_key"] == "research"
        assert snapshot["failed"][0]["error"] == "Boom"
        assert snapshot["failed"][0]["error_detail"] == "Stack trace"

    run(scenario())


def test_cancel_running_item_sets_cancel_event_and_can_mark_canceled():
    async def scenario():
        manager = QueueManager()

        running = await manager.enqueue("state-1", "research", "Research")
        await manager.enqueue("state-1", "salary", "Salary")

        canceled = await manager.cancel(running.id)
        assert canceled.status == "canceling"
        assert canceled.cancel_event.is_set()

        await manager.mark_canceled(running.id)
        snapshot = await manager.snapshot()

        assert snapshot["running"]["section_key"] == "salary"
        assert snapshot["queued"] == []

    run(scenario())


def test_cleanup_custom_action_removes_waiting_item_and_cancels_running_item():
    async def scenario():
        manager = QueueManager()

        running = await manager.enqueue("state-1", "custom:cover", "Cover Letter")
        await manager.enqueue("state-1", "custom:followup", "Follow-up")

        await manager.cleanup_custom_action("cover")
        snapshot = await manager.snapshot()

        assert snapshot["running"]["status"] == "canceling"
        assert running.cancel_event.is_set()

        await manager.cleanup_custom_action("followup")
        snapshot = await manager.snapshot()
        assert snapshot["queued"] == []

    run(scenario())
