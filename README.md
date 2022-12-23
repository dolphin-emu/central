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
$ poetry install
$ poetry run black --check .
$ poetry run pytest
$ poetry run central
```
