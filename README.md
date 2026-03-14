# phoenix-pubsub

A topic-based publish‑subscribe system for `asyncio` applications, inspired by the [Phoenix PubSub](https://hexdocs.pm/phoenix_pubsub/Phoenix.PubSub.html) library from the Elixir Phoenix framework.

- [Online API Documentation](https://0riginaln0.github.io/phoenix-pubsub/phoenix_pubsub.html) 
- [PyPi](https://pypi.org/project/phoenix-pubsub/)
- [Source code](https://github.com/0riginaln0/phoenix-pubsub)

## Features

- Subscribe to one or more topics
- Broadcast messages to all subscribers of a topic
- Broadcast messages while excluding the publisher itself
- Graceful handling of slow consumers (messages are dropped when a subscriber’s queue is full)

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
