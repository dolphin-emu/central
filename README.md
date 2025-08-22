# Dolphin Central

Central is the infrastructure component receiving webhooks and coordinating
builds, status updates, notifications, etc. for Dolphin's CI/CD infrastructure.

It provides plumbing to connect the following systems together:
- GitHub
- IRC
- Buildbot
- FifoCI

This is not meant as a general purpose system, it is custom made for Dolphin's
needs and likely not directly usable for other projects.

## Setup

```bash
$ nix run
```

## Development

```bash
$ nix develop
$ uv sync
$ uv run black --check .
$ uv run pytest
$ uv run central
```
