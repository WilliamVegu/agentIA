import asyncio
from app.services.queue_service import ConcurrencyQueueManager


def test_cancelled_waiter_never_claims_or_releases_an_active_worker():
    async def scenario():
        queue=ConcurrencyQueueManager(1)
        await queue.enqueue('active')
        assert await queue.acquire_slot('active') is True
        await queue.enqueue('waiting')
        waiting=asyncio.create_task(queue.acquire_slot('waiting'))
        await asyncio.sleep(.02)
        queue.cancel_waiting('waiting')
        assert await asyncio.wait_for(waiting,timeout=2) is False
        assert queue.active_sessions=={'active'}
        assert not queue.waiting_queue
        await queue.release_slot('active')
        assert not queue.active_sessions
    asyncio.run(scenario())


def test_queue_preserves_fifo_without_overbooking_capacity():
    async def scenario():
        queue=ConcurrencyQueueManager(1)
        assert await queue.acquire_slot('first') is True
        await queue.enqueue('second');await queue.enqueue('third')
        second=asyncio.create_task(queue.acquire_slot('second'))
        third=asyncio.create_task(queue.acquire_slot('third'))
        await asyncio.sleep(.02)
        assert not second.done() and not third.done()
        await queue.release_slot('first')
        assert await asyncio.wait_for(second,timeout=2) is True
        assert queue.active_sessions=={'second'} and not third.done()
        await queue.release_slot('second')
        assert await asyncio.wait_for(third,timeout=2) is True
        assert queue.active_sessions=={'third'}
        await queue.release_slot('third')
    asyncio.run(scenario())
