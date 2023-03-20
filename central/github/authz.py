from . import app

from .. import github, utils
from ..config import cfg

import logging


_TRUSTED_USERS = set()
_CORE_USERS = set()


def is_safe_author(login):
    return login in _TRUSTED_USERS


def sync_github_group(group, group_name):
    """Synchronizes the list of trusted users by querying a given group."""
    org = group_name.split("/")[0]
    team = group_name.split("/")[1]
    logging.info("Refreshing list of trusted users (from %s/%s)", org, team)

    team_info = github.request_get_all(
        "https://api.github.com/orgs/%s/teams/%s/members" % (org, team),
        auth=app.OrgAuth(org),
    )
    group.clear()
    for member in team_info:
        group.add(member["login"])
    logging.info("New GH %s: %s", group_name, ",".join(group))


def sync_trusted_users():
    sync_github_group(_TRUSTED_USERS, cfg.github.trusted_users.group)


def sync_core_users():
    sync_github_group(_CORE_USERS, cfg.github.core_users.group)


def start():
    utils.spawn_periodic_task(
        cfg.github.trusted_users.refresh_interval, sync_trusted_users
    )
    utils.spawn_periodic_task(cfg.github.core_users.refresh_interval, sync_core_users)
