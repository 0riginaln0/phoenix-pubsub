import asyncio
from phoenix_pubsub import PubSub, Topic, Message, Subscribers, Peer
from typing import Optional


async def test_pubsub():
    pubsub = PubSub()

    # Create subscriber queues
    queue_alerts = asyncio.Queue()
    queue_news = asyncio.Queue()
    queue_all = asyncio.Queue()  # listens to multiple topics
    queue_publisher = asyncio.Queue()
    queue_slow = asyncio.Queue(maxsize=1)  # will demonstrate dropped messages

    # Subscribe to topics
    await pubsub.subscribe(queue_alerts, "alerts")
    await pubsub.subscribe(queue_news, "news")
    await pubsub.subscribe(queue_all, "alerts", "news", "sports", "chat")
    await pubsub.subscribe(queue_publisher, "chat")
    await pubsub.subscribe(queue_slow, "alerts")

    # 1. Broadcast to a single topic
    await pubsub.broadcast("System alert!", "alerts")

    # queue_alerts should receive it
    topic, msg = await queue_alerts.get()
    assert topic == "alerts"
    assert msg == "System alert!"

    # queue_all should receive it
    topic, msg = await queue_all.get()
    assert topic == "alerts"
    assert msg == "System alert!"

    # queue_slow should receive it
    topic, msg = await queue_slow.get()
    assert topic == "alerts"
    assert msg == "System alert!"

    # 2. Broadcast to multiple topics
    await pubsub.broadcast("Score update", "news", "sports")

    # queue_news receives the news message
    topic, msg = await queue_news.get()
    assert topic == "news"
    assert msg == "Score update"

    # queue_all receives both messages
    received = []
    for _ in range(2):
        topic, msg = await queue_all.get()
        received.append((topic, msg))
    expected_msgs = {("news", "Score update"), ("sports", "Score update")}
    assert set(received) == expected_msgs

    # 3. Broadcast from a publisher (exclude itself)
    await pubsub.broadcast_from(queue_publisher, "Hello everyone!", "chat")

    # queue_all receives it
    topic, msg = await queue_all.get()
    assert topic == "chat"
    assert msg == "Hello everyone!"

    # queue_publisher should NOT receive it
    try:
        await asyncio.wait_for(queue_publisher.get(), timeout=0.1)
        # If we reach here, a message was unexpectedly received
        assert False, "queue_publisher should not have received the message"
    except asyncio.TimeoutError:
        pass  # Expected – no message arrived

    # 4. Unsubscribe and verify no further messages
    await pubsub.unsubscribe(queue_news, "news")
    await pubsub.broadcast("Late news", "news")

    # queue_news should NOT receive anything
    try:
        await asyncio.wait_for(queue_news.get(), timeout=0.1)
        assert False, (
            "queue_news should not have received the message after unsubscribe"
        )
    except asyncio.TimeoutError:
        pass  # Correct

    # queue_all still receives because it's still subscribed
    topic, msg = await queue_all.get()
    assert topic == "news"
    assert msg == "Late news"

    # 5. Slow consumer misses messages
    await pubsub.broadcast("System alert 1", "alerts")
    await pubsub.broadcast("System alert 2", "alerts")
    await pubsub.broadcast("System alert 3", "alerts")

    # queue_alerts receives all three
    for i in range(1, 4):
        topic, msg = await asyncio.wait_for(queue_alerts.get(), timeout=0.1)
        assert topic == "alerts"
        assert msg == f"System alert {i}"

    # queue_slow receives only the first alert (the rest are dropped because its queue is full)
    topic, msg = await queue_slow.get()
    assert topic == "alerts"
    assert msg == "System alert 1"

    # No second message arrives
    try:
        await asyncio.wait_for(queue_slow.get(), timeout=0.1)
        assert False, "queue_slow should not have received a second message"
    except asyncio.TimeoutError:
        pass  # Expected

    # 6. Custom dispatcher
    def catagory_filter_dispatcher(
        topic: Topic,
        message: Message,
        subscribers: Subscribers,
        publisher: Optional[Peer] = None,
    ) -> None:
        """
        Deliver message only to subscribers whose 'interests' metadata list
        contains the message's 'category' field.
        """

        def try_put_message(peer: asyncio.Queue, topic: str, message: Message):
            try:
                peer.put_nowait((topic, message))
            except (asyncio.QueueFull, asyncio.QueueShutDown):
                pass

        if not isinstance(message, dict) or "category" not in message:
            return

        category = message["category"]

        if publisher:  # broadcast_from
            for peer, metadata in subscribers.items():
                interests = metadata.get("interests", [])
                if category in interests:
                    if peer != publisher:
                        try_put_message(peer, topic, message)
        else:  # broadcast
            for peer, metadata in subscribers.items():
                interests = metadata.get("interests", [])
                if category in interests:
                    try_put_message(peer, topic, message)

    queue1 = asyncio.Queue()
    await pubsub.subscribe(
        queue1, "news", metadata={"interests": ["sports", "politics"]}
    )
    queue2 = asyncio.Queue()
    await pubsub.subscribe(queue2, "news", metadata={"interests": ["sports"]})
    queue3 = asyncio.Queue()
    await pubsub.subscribe(queue3, "news", metadata={"interests": ["technology"]})

    sports_msg = {"category": "sports", "content": "Game result 3-2"}
    await pubsub.broadcast(sports_msg, "news", dispatcher=catagory_filter_dispatcher)
    politics_msg = {"category": "politics", "content": "Election update"}
    await pubsub.broadcast(politics_msg, "news", dispatcher=catagory_filter_dispatcher)

    msgs1 = []
    while not queue1.empty():
        msgs1.append(await queue1.get())
    assert msgs1 == [
        ("news", sports_msg),
        ("news", politics_msg),
    ]

    msgs2 = []
    while not queue2.empty():
        msgs2.append(await queue2.get())
    assert msgs2 == [
        ("news", sports_msg),
    ]

    assert queue3.empty()

    print("All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_pubsub())
