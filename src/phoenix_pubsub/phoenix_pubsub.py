import asyncio
from collections import defaultdict
from typing import Any

Topic = str
Subscriber = asyncio.Queue
Registry = dict[Topic, set[Subscriber]]


def try_put_message(subscriber: asyncio.Queue, topic: str, message: Any):
    try:
        subscriber.put_nowait((topic, message))
    except (asyncio.QueueFull, asyncio.QueueShutDown):
        # Handle slow consumers – you might want to drop or log
        pass


class PubSub:
    """
    A topic-based publish-subscribe system for asynchronous message passing.
    """

    def __init__(self):
        self._topics: Registry = defaultdict(set)
        "Dictionary mapping topics to sets of subscriber queues"
        self._lock = asyncio.Lock()
        "Lock for thread-safe operations on the registry"

    async def subscribe(self, subscriber: asyncio.Queue, *topics: str):
        """
        Subscribe a queue to one or more topics.

        Args:
            subscriber (asyncio.Queue): The queue that will receive messages.
                This queue will receive messages as (topic, message) tuples.
            *topics (str): Variable number of topic strings to subscribe to.
                The subscriber will receive messages published to any of these topics.

        Example:
            ```python
            queue = asyncio.Queue()

            # Subscribe to single topic
            await pubsub.subscribe(queue, "temperature")

            # Subscribe to multiple topics
            await pubsub.subscribe(queue, "news", "weather", "sports")
            ```
        """
        async with self._lock:
            for topic in topics:
                self._topics[topic].add(subscriber)

    async def unsubscribe(self, subscriber: asyncio.Queue, *topics: str):
        """
        Unsubscribe a queue from one or more topics.

        Args:
            subscriber (asyncio.Queue): The queue to unsubscribe.
            *topics (str): Topics to unsubscribe from.

        Example:
            ```python
            # Unsubscribe from a single topic
            await pubsub.unsubscribe(queue, "weather")

            # Unsubscribe from multiple topics
            await pubsub.unsubscribe(queue, "news", "sports")
            ```
        """
        async with self._lock:
            for topic in topics:
                if subscribers := self._topics.get(topic):
                    subscribers.discard(subscriber)
                    if not subscribers:
                        del self._topics[topic]

    async def broadcast(self, message: Any, *topics: str):
        """
        Broadcast a message to all subscribers of the specified topics.

        Args:
            message (Any): The message to broadcast.
            *topics (str): Topics to broadcast to.

        Example:
            ```python
            await pubsub.broadcast("Hello world!", "greetings")
            # Subscribers receive: ("greetings", "Hello world!")

            data = {"sensor": "temperature", "value": 23.5, "unit": "celsius"}
            await pubsub.broadcast(data, "telemetry", "monitoring")
            # Subscribers receive: ("telemetry", data)
            #                      ("monitoring", data)
            ```

        Note:
            - Slow consumers may miss messages if their queue is full
            - The broadcast is asynchronous - it doesn't wait for subscribers to process messages
        """
        pending: list[tuple[Topic, set[Subscriber]]] = []
        async with self._lock:
            for topic in topics:
                if subscribers := self._topics.get(topic, set()).copy():
                    pending.append((topic, subscribers))

        for topic, subscribers in pending:
            for subscriber in subscribers:
                try_put_message(subscriber, topic, message)

    async def broadcast_from(
        self, publisher: asyncio.Queue, message: Any, *topics: str
    ):
        """
        Broadcast a message to all subscribers except the publisher itself.

        Args:
            publisher (asyncio.Queue): The queue of the publisher to exclude.
                This subscriber will not receive the message.
            message (Any): The message to broadcast.
            *topics (str): Topics to broadcast to.

        Example:
            ```python
            publisher_queue = asyncio.Queue()
            chat_queue = asyncio.Queue()
            await pubsub.subscribe(publisher_queue, "chat")
            await pubsub.subscribe(chat, "chat")

            await pubsub.broadcast_from(
                publisher_queue,
                "User joined the channel",
                "chat"
            )
            # chat_queue receives ("chat", "User joined the channel")
            # publisher_queue doesn't receive this message
            ```
        """
        pending: list[tuple[Topic, set[Subscriber]]] = []
        async with self._lock:
            for topic in topics:
                subscribers = self._topics.get(topic, set())
                if peers := subscribers.difference({publisher}):
                    pending.append((topic, peers))

        for topic, peers in pending:
            for peer in peers:
                try_put_message(peer, topic, message)
