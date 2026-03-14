# phoenix-pubsub

A topic-based publish‑subscribe system for `asyncio` applications, inspired by the [Phoenix PubSub](https://hexdocs.pm/phoenix_pubsub/Phoenix.PubSub.html) library from the Elixir Phoenix framework.

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

