import asyncio
from collections import defaultdict
from typing import Any, Optional, Callable

type Topic = str
type Message = Any
type Peer = asyncio.Queue
type Subscribers = dict[Peer, dict]
type Registry = dict[Topic, Subscribers]
type Dispatcher = Callable[[Topic, Message, Subscribers, Optional[Peer]], None]


def synchronous_dispatcher(
    topic: Topic,
    message: Message,
    subscribers: Subscribers,
    publisher: Optional[Peer] = None,
):
    """
    Blocks the caller until all put attempts are made.
    """

    def try_put_message(peer: asyncio.Queue, topic: str, message: Message):
        try:
            peer.put_nowait((topic, message))
        except (asyncio.QueueFull, asyncio.QueueShutDown):
            # Handle slow consumers – you might want to drop or log
            pass

    if publisher:  # broadcast_from
        for peer, _metadata in subscribers.items():
            if peer is not publisher:
                try_put_message(peer, topic, message)
    else:  # broadcast
        for peer in subscribers.keys():
            try_put_message(peer, topic, message)


def concurrent_dispatcher(
    topic: Topic,
    message: Message,
    subscribers: Subscribers,
    publisher: Optional[Peer] = None,
):
    """
    Spawns one background put attempt task per subscriber.
    """

    async def try_put_message(peer: asyncio.Queue, topic: str, message: Message):
        try:
            peer.put_nowait((topic, message))
        except (asyncio.QueueFull, asyncio.QueueShutDown):
            pass

    for peer in subscribers.keys():
        if publisher and peer is publisher:
            continue
        asyncio.create_task(try_put_message(peer, topic, message))


class PubSub:
    """
    A topic-based publish-subscribe system for asynchronous message passing.

    Supports attaching arbitrary metadata to subscriptions, allowing custom
    dispatcher logic for flexible message routing.
    """

    def __init__(self):
        self._topics: Registry = defaultdict(dict)
        "Dictionary mapping Topics to Subscribers"
        self._lock = asyncio.Lock()
        "Lock for thread-safe operations on the registry"

    async def subscribe(
        self, peer: Peer, *topics: str, metadata: Optional[dict] = None
    ):
        """
        Subscribe a queue to one or more topics.

        Args:
            peer: The queue that will receive messages.
                This queue will receive messages as (topic, message) tuples.
            *topics: Variable number of topic strings to subscribe to.
                The subscriber will receive messages published to any of these topics.
            metadata: Arbitrary data attached to this subscription.
                The dispatcher can use it for custom delivery logic (e.g., filtering,
                prioritisation).

        Example:
            ```
            queue = asyncio.Queue()

            # Subscribe to single topic
            await pubsub.subscribe(queue, "temperature")

            # Subscribe to multiple topics
            await pubsub.subscribe(queue, "news", "weather", "sports")

            # Provide metadata
            await pubsub.subscribe(queue, "stock", metadata={"priority": 10})
            ```
        """
        metadata = metadata or {}
        async with self._lock:
            for topic in topics:
                self._topics[topic][peer] = metadata

    async def unsubscribe(self, peer: Peer, *topics: str):
        """
        Unsubscribe a queue from one or more topics.

        Args:
            peer: The queue to unsubscribe.
            *topics: Topics to unsubscribe from.

        Example:
            ```
            # Unsubscribe from a single topic
            await pubsub.unsubscribe(queue, "weather")

            # Unsubscribe from multiple topics
            await pubsub.unsubscribe(queue, "news", "sports")
            ```
        """
        async with self._lock:
            for topic in topics:
                if subscribers := self._topics.get(topic):
                    subscribers.pop(peer, None)
                    if not subscribers:
                        del self._topics[topic]

    async def broadcast(
        self,
        message: Message,
        *topics: str,
        dispatcher: Dispatcher = synchronous_dispatcher,
    ):
        """
        Broadcast a message to all subscribers of the specified topics.

        Args:
            message: The message to broadcast.
            *topics: Topics to broadcast to.
            dispatcher: A callable that handles the actual message delivery.
                Custom dispatchers can implement filtering, transformation,
                or prioritisation using the metadata stored with each subscriber.

        Example:
            ```
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
        pending: list[tuple[Topic, Subscribers]] = []
        async with self._lock:
            for topic in topics:
                if subscribers := self._topics.get(topic):
                    pending.append((topic, subscribers.copy()))

        for topic, subscribers in pending:
            dispatcher(topic, message, subscribers, None)

    async def broadcast_from(
        self,
        publisher: Peer,
        message: Message,
        *topics: str,
        dispatcher: Dispatcher = synchronous_dispatcher,
    ):
        """
        Broadcast a message to all subscribers except the publisher itself.

        Args:
            publisher: The queue of the publisher to exclude.
                This peer (the publisher) will not receive the message.
            message: The message to broadcast.
            *topics: Topics to broadcast to.
            dispatcher: A callable that handles the actual message delivery.
                Custom dispatchers can implement filtering, transformation,
                or prioritisation using the metadata stored with each subscriber.

        Example:
            ```
            publisher_queue = asyncio.Queue()
            chat_queue = asyncio.Queue()
            await pubsub.subscribe(publisher_queue, "chat")
            await pubsub.subscribe(chat_queue, "chat")

            await pubsub.broadcast_from(
                publisher_queue,
                "User joined the channel",
                "chat"
            )
            # chat_queue receives ("chat", "User joined the channel")
            # publisher_queue doesn't receive this message
            ```
        """
        pending: list[tuple[Topic, Subscribers]] = []
        async with self._lock:
            for topic in topics:
                subscribers = self._topics.get(topic)
                if subscribers:
                    pending.append((topic, subscribers.copy()))

        for topic, subscribers in pending:
            dispatcher(topic, message, subscribers, publisher)
