[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/0riginaln0/phoenix-pubsub)

# phoenix-pubsub

A topic-based publish‑subscribe system for `asyncio` applications, inspired by the [Phoenix PubSub](https://hexdocs.pm/phoenix_pubsub/Phoenix.PubSub.html) library from the Elixir Phoenix framework.

- [Online API Documentation](https://0riginaln0.github.io/phoenix-pubsub) 
- [PyPi](https://pypi.org/project/phoenix-pubsub/)
- [Source code](https://github.com/0riginaln0/phoenix-pubsub)

## Features

- Subscribe to one or more topics
- Broadcast messages to all subscribers of a topic
- Broadcast messages while excluding the publisher itself
- Subscribers metadata & Custom dispatchers – attach metadata to subscriptions and implement your own delivery logic by passing a dispatcher function into `broadcast` / `broadcast_from`

## Installation

```bash
pip install phoenix-pubsub
uv add phoenix-pubsub
```

## Examples


### Basic: Subscribe, Broadcast, Unsubscribe

```python
import asyncio
from phoenix_pubsub import PubSub

async def main():
    pubsub = PubSub()
    queue = asyncio.Queue()

    # Subscribe to a topic
    await pubsub.subscribe(queue, "alerts")

    # Broadcast a message
    await pubsub.broadcast("System alert!", "alerts")

    # Receive the message
    topic, msg = await queue.get()
    print(topic, msg) # alerts System alert!

    # Unsubscribe from the topic
    await pubsub.unsubscribe(queue, "alerts")

    # Broadcast another message – this one should not be received
    await pubsub.broadcast("Another alert", "alerts")

    try:
        await asyncio.wait_for(queue.get(), timeout=0.1)
        print("Unexpected message received after unsubscribe")
    except asyncio.TimeoutError:
        print("No message received after unsubscribe (as expected)")

asyncio.run(main())
```

### Subscribing to multiple topics

```python
import asyncio
from phoenix_pubsub import PubSub

async def main():
    pubsub = PubSub()
    queue = asyncio.Queue()

    await pubsub.subscribe(queue, "alerts", "news", "sports")
    await pubsub.broadcast("Earthquake!", "alerts")
    await pubsub.broadcast("Score update", "sports")

    topic, msg = await queue.get()
    print(topic, msg)  # alerts Earthquake!
    topic, msg = await queue.get()
    print(topic, msg)  # sports Score update

asyncio.run(main())
```

### Broadcasting to multiple topics

```python
import asyncio
from phoenix_pubsub import PubSub


async def main():
    pubsub = PubSub()
    queue_news = asyncio.Queue()
    queue_sports = asyncio.Queue()

    await pubsub.subscribe(queue_news, "news")
    await pubsub.subscribe(queue_sports, "sports")

    await pubsub.broadcast("Breaking news!", "news", "sports")

    topic, msg = await queue_news.get()
    print(topic, msg)  # news Breaking news!
    topic, msg = await queue_sports.get()
    print(topic, msg)  # sports Breaking news!


asyncio.run(main())

```

### Excluding the publisher from broadcast

```python
import asyncio
from phoenix_pubsub import PubSub

async def main():
    pubsub = PubSub()
    publisher = asyncio.Queue()
    other = asyncio.Queue()

    await pubsub.subscribe(publisher, "chat")
    await pubsub.subscribe(other, "chat")

    await pubsub.broadcast_from(publisher, "Hello everyone!", "chat")

    topic, msg = await other.get()
    print(topic, msg)  # chat Hello everyone!

    try:
        await asyncio.wait_for(publisher.get(), timeout=0.1)
        print("Unexpected message")
    except asyncio.TimeoutError:
        print("Publisher received nothing (as expected)")

asyncio.run(main())
```


### Slow consumer - Messages are dropped

```python
import asyncio
from phoenix_pubsub import PubSub

async def main():
    pubsub = PubSub()
    slow = asyncio.Queue(maxsize=1)  # can hold only one message
    fast = asyncio.Queue()

    await pubsub.subscribe(slow, "alerts")
    await pubsub.subscribe(fast, "alerts")

    await pubsub.broadcast("Alert 1", "alerts")
    await pubsub.broadcast("Alert 2", "alerts")
    await pubsub.broadcast("Alert 3", "alerts")

    # Fast consumer receives all three
    topic, msg = await fast.get()
    print(topic, msg)  # alerts Alert 1
    topic, msg = await fast.get()
    print(topic, msg)  # alerts Alert 2
    topic, msg = await fast.get()
    print(topic, msg)  # alerts Alert 3

    # Slow consumer receives only the first (others are dropped)
    topic, msg = await slow.get()
    print(topic, msg)  # alerts Alert 1

    try:
        await asyncio.wait_for(slow.get(), timeout=0.1)
        print("Unexpected second message")
    except asyncio.TimeoutError:
        print("Slow queue received no further messages (as expected)")

asyncio.run(main())
```

### Metadata & Custom dispatcher

The library provides two dispatchers: `synchronous_dispatcher`, `concurrent_dispatcher`. The default one is synchronous.

You can create and pass your own dispatchers like that:


#### Filter dispatcher

```python
import asyncio
from phoenix_pubsub import PubSub, Topic, Message, Subscribers, Peer
from typing import Optional

async def main():
    pubsub = PubSub()

    def category_filter_dispatcher(
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

        peers = []
        for peer, metadata in subscribers.items():
            interests = metadata.get("interests", [])
            if category in interests:
                peers.append(peer)

        if publisher:  # broadcast_from
            for peer in peers:
                if peer != publisher:
                    try_put_message(peer, topic, message)
        else:  # broadcast
            for peer in peers:
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
    await pubsub.broadcast(sports_msg, "news", dispatcher=category_filter_dispatcher)
    politics_msg = {"category": "politics", "content": "Election update"}
    await pubsub.broadcast(politics_msg, "news", dispatcher=category_filter_dispatcher)

    for i, q in enumerate([queue1, queue2, queue3], 1):
        received = []
        while not q.empty():
            received.append(await q.get())
        print(f"Subscriber {i} received: {received}")
        # Subscriber 1 received: [('news', {'category': 'sports', 'content': 'Game result 3-2'}), ('news', {'category': 'politics', 'content': 'Election update'})]
        # Subscriber 2 received: [('news', {'category': 'sports', 'content': 'Game result 3-2'})]
        # Subscriber 3 received: []        


asyncio.run(main())
```

#### Batched dispatcher

```python
import asyncio
from phoenix_pubsub import PubSub, Topic, Message, Subscribers, Peer
from typing import Optional
from functools import partial


def batched_dispatcher(
    topic: Topic,
    message: Message,
    subscribers: Subscribers,
    publisher: Optional[Peer] = None,
    *,
    batch_size: int = 5,
) -> None:
    """
    Groups subscribers into batches and spawns one background task per batch.
    """

    async def process_batch(
        batch_peers: list[Peer], topic: str, message: Message
    ) -> None:
        for peer in batch_peers:
            try:
                peer.put_nowait((topic, message))
            except (asyncio.QueueFull, asyncio.QueueShutDown):
                pass

    if publisher:  # broadcast_from
        peers = [peer for peer in subscribers.keys() if peer is not publisher]
    else:  # broadcast
        peers = [peer for peer in subscribers.keys()]

    for i in range(0, len(peers), batch_size):
        batch = peers[i : i + batch_size]
        asyncio.create_task(process_batch(batch, topic, message))


async def main():
    pubsub = PubSub()

    queues = [asyncio.Queue() for _ in range(7)]

    for q in queues:
        await pubsub.subscribe(q, "notifications")

    await pubsub.broadcast(
        "Important notification 1",
        "notifications",
        dispatcher=batched_dispatcher,
    )
    getters = [q.get() for q in queues]
    await asyncio.gather(*getters)

    await pubsub.broadcast(
        "Important notification 2",
        "notifications",
        dispatcher=partial(batched_dispatcher, batch_size=10),
    )
    getters = [q.get() for q in queues]
    await asyncio.gather(*getters)


if __name__ == "__main__":
    asyncio.run(main())
```
