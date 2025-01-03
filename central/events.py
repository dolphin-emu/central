"""Events module, including all the supported event constructors and the global
event dispatcher."""

from . import utils

import functools
import logging


class EventTarget:
    def push_event(self, evt):
        logging.error("push_event not redefined in EventTarget subclass")

    def accept_event(self, evt):
        return False


class Dispatcher:
    def __init__(self, targets=None):
        self.targets = targets or []

    def register_target(self, target):
        self.targets.append(target)

    def dispatch(self, source, evt):
        transmitted = {"source": source}
        transmitted.update(evt)
        transmitted = utils.ObjectLike(transmitted)
        for tgt in self.targets:
            try:
                if tgt.accept_event(transmitted):
                    tgt.push_event(transmitted)
            except Exception:
                logging.exception("Failed to pass event to %r" % tgt)
                continue


dispatcher = Dispatcher()

# Event constructors. Events are dictionaries, with the following keys being
# mandatory:
#   - type: The event type (string).
#   - source: The event source (string).


def event(type):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            evt = f(*args, **kwargs)
            evt["type"] = type
            return evt

        wrapper.TYPE = type
        return wrapper

    return decorator


@event("internal_log")
def InternalLog(level: str, pathname: str, lineno: int, msg: str, args: str):
    return {
        "level": level,
        "pathname": pathname,
        "lineno": lineno,
        "msg": msg,
        "args": args,
    }


@event("config_reload")
def ConfigReload():
    return {}


@event("notification")
def Notification(msg: str):
    return {"msg": msg}


@event("command_message")
def CommandMessage(who: str, what: str):
    return {"who": who, "what": what}


@event("issue")
def Issue(new: bool, update: int, issue: int, title: str, author: str):
    return {
        "new": new,
        "update": update,
        "issue": issue,
        "title": title,
        "author": author,
    }


@event("raw_gh_hook")
def RawGHHook(gh_type: str, raw: dict):
    return {"gh_type": gh_type, "raw": raw}


@event("gh_push")
def GHPush(
    repo: str,
    pusher: str,
    before_sha: str,
    after_sha: str,
    commits: list,
    base_ref_name: str,
    ref_name: str,
    ref_type: str,
    created: bool,
    deleted: bool,
    forced: bool,
):
    return {
        "repo": repo,
        "pusher": pusher,
        "before_sha": before_sha,
        "after_sha": after_sha,
        "commits": commits,
        "base_ref_name": base_ref_name,
        "ref_name": ref_name,
        "ref_type": ref_type,
        "created": created,
        "deleted": deleted,
        "forced": forced,
    }


@event("gh_pull_request")
def GHPullRequest(
    repo: str,
    author: str,
    action: str,
    id: int,
    title: str,
    base_ref_name: str,
    head_ref_name: str,
    base_sha: str,
    head_sha: str,
    url: str,
    safe_author: bool,
    merged: bool,
    requested_reviewers: list,
):
    return {
        "repo": repo,
        "author": author,
        "action": action,
        "id": id,
        "title": title,
        "base_ref_name": base_ref_name,
        "url": url,
        "head_ref_name": head_ref_name,
        "safe_author": safe_author,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "merged": merged,
        "requested_reviewers": requested_reviewers,
    }


@event("gh_pull_request_review")
def GHPullRequestReview(
    repo: str,
    author: str,
    action: str,
    pr_id: int,
    pr_title: str,
    state: str,
    url: str,
    comments: list,
):
    """This event is triggered when a GitHub review is submitted."""
    return {
        "repo": repo,
        "author": author,
        "action": action,
        "pr_id": pr_id,
        "pr_title": pr_title,
        "state": state,
        "url": url,
        "comments": comments,
    }


@event("gh_pull_request_comment")
def GHPullRequestComment(
    repo: str,
    author: str,
    action: str,
    id: int,
    hash: str,
    url: str,
    is_part_of_review: bool,
):
    return {
        "repo": repo,
        "author": author,
        "action": action,
        "id": id,
        "hash": hash,
        "url": url,
        "is_part_of_review": is_part_of_review,
    }


@event("gh_issue_comment")
def GHIssueComment(
    repo: str,
    author: str,
    action: str,
    id: int,
    title: str,
    url: str,
    safe_author: bool,
    body: str,
    raw: dict,
):
    return {
        "repo": repo,
        "author": author,
        "action": action,
        "id": id,
        "title": title,
        "url": url,
        "safe_author": safe_author,
        "body": body,
        "raw": raw,
    }


@event("gh_commit_comment")
def GHCommitComment(repo: str, author: str, commit: str, url: str):
    return {"repo": repo, "author": author, "commit": commit, "url": url}


@event("build_status")
def BuildStatus(
    repo: str,
    hash: str,
    shortrev: str,
    service: str,
    pr: int,
    success: bool,
    pending: bool,
    url: str,
    description: str,
):
    return {
        "repo": repo,
        "hash": hash,
        "shortrev": shortrev,
        "service": service,
        "pr": pr,
        "success": success,
        "pending": pending,
        "url": url,
        "description": description,
    }


@event("pull_request_fifoci_status")
def PullRequestFifoCIStatus(repo: str, hash: str, service: str, pr: int):
    return {"repo": repo, "hash": hash, "service": service, "pr": pr}


@event("raw_bb_hook")
def RawBBHook(raw: dict):
    return {"raw": raw}


@event("raw_redmine_hook")
def RawRedmineHook(rm_type: str, raw: dict):
    return {"rm_type": rm_type, "raw": raw}


@event("new_dev_version")
def NewDevVersion(
    hash: str, branch: str, shortrev: str, author: str, message: str, url: str
):
    return {
        "hash": hash,
        "branch": branch,
        "shortrev": shortrev,
        "author": author,
        "message": message,
        "url": url,
    }


@event("new_release_version")
def NewReleaseVersion(hash: str, tag: str, author: str):
    return {
        "hash": hash,
        "tag": tag,
        "author": author,
    }
