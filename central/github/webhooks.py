from .. import events, github, utils
from ..config import cfg

import json
import logging
import requests

GH_WEBHOOK_EVENTS = [
    "check_run",
    "commit_comment",
    "issue_comment",
    "pull_request",
    "pull_request_review",
    "pull_request_review_comment",
    "push",
]


def watched_repositories():
    return (cfg.github.maintain or []) + (cfg.github.notify or [])


def webhook_url():
    return cfg.web.external_url + "/gh/hook/"


def periodic_hook_maintainer():
    """Function that checks watched repositories for presence of a webhook that
    points to us. If not present, installs the hook."""

    logging.info("Checking watched repositories for webhook presence")
    for repo in watched_repositories():
        hs = github.request_get_all("https://api.github.com/repos/%s/hooks" % repo)
        hook_present = False
        for h in hs:
            if "config" not in h:
                continue
            config = h["config"]
            if "url" not in config:
                continue
            if config["url"] != webhook_url():
                continue
            hook_present = True
            break

        hook_data = {
            "name": "web",
            "active": True,
            "events": GH_WEBHOOK_EVENTS,
            "config": {
                "url": webhook_url(),
                "content_type": "json",
                "secret": cfg.github.hook_hmac_secret,
                "insecure_ssl": "0",
            },
        }

        if hook_present:
            logging.info("Watched repo %r has our hook installed" % repo)
            url = h["url"]
            method = requests.patch
        else:
            logging.warning("Repo %r is missing our hook, installing" % repo)
            url = "https://api.github.com/repos/%s/hooks" % repo
            method = requests.post

        method(
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(hook_data),
            auth=github.basic_auth(),
        )


class GHHookEventParser(events.EventTarget):
    def accept_event(self, evt):
        return evt.type == events.RawGHHook.TYPE

    def convert_commit(self, commit):
        commit = utils.ObjectLike(commit)
        return {
            "author": commit.author,
            "distinct": commit.distinct,
            "added": commit.added,
            "modified": commit.modified,
            "removed": commit.removed,
            "message": commit.message,
            "url": commit.url,
            "hash": commit.id,
        }

    def convert_push_event(self, raw):
        repo = raw.repository.owner.name + "/" + raw.repository.name
        pusher = raw.pusher.name
        before_sha = raw.before
        after_sha = raw.after
        commits = [self.convert_commit(c) for c in raw.commits]
        base_ref = raw.base_ref
        base_ref_name = base_ref.split("/", 2)[2] if base_ref else None
        ref_name = raw.ref.split("/", 2)[2]
        ref_type = raw.ref.split("/", 2)[1]
        created = raw.created
        deleted = raw.deleted
        forced = raw.forced

        return events.GHPush(
            repo,
            pusher,
            before_sha,
            after_sha,
            commits,
            base_ref_name,
            ref_name,
            ref_type,
            created,
            deleted,
            forced,
        )

    def convert_pull_request_event(self, raw):
        repo = raw.repository.owner.login + "/" + raw.repository.name
        author = raw.sender.login
        base_ref_name = raw.pull_request.base.label.split(":")[-1]
        head_ref_name = raw.pull_request.head.label.split(":")[-1]
        base_sha = raw.pull_request.base.sha
        head_sha = raw.pull_request.head.sha
        return events.GHPullRequest(
            repo,
            author,
            raw.action,
            raw.pull_request.number,
            raw.pull_request.title,
            base_ref_name,
            head_ref_name,
            base_sha,
            head_sha,
            raw.pull_request.html_url,
            github.authz.is_safe_author(author),
            raw.pull_request.merged,
            raw.pull_request.requested_reviewers,
        )

    def convert_pull_request_review(self, raw):
        repo = raw.repository.owner.login + "/" + raw.repository.name
        pr_id = raw.pull_request.number
        comments = github.get_pr_review_comments(repo, pr_id, raw.review.id)
        return events.GHPullRequestReview(
            repo,
            raw.sender.login,
            raw.action,
            pr_id,
            raw.pull_request.title,
            raw.review.state,
            raw.review.html_url,
            comments,
        )

    def convert_pull_request_comment_event(self, raw):
        repo = raw.repository.owner.login + "/" + raw.repository.name
        id = int(raw.comment.pull_request_url.split("/")[-1])
        # Comments submitted as part of a review can be detected by their
        # action, the presence of a review ID, and a difference between
        # created_at and updated_at (because the comment is initially pending).
        is_part_of_review = (
            raw.action == "created"
            and "pull_request_review_id" in raw.comment
            and raw.comment.created_at != raw.comment.updated_at
        )
        return events.GHPullRequestComment(
            repo,
            raw.sender.login,
            raw.action,
            id,
            raw.comment.commit_id,
            raw.comment.html_url,
            is_part_of_review,
        )

    def convert_issue_comment_event(self, raw):
        author = raw.sender.login
        repo = raw.repository.owner.login + "/" + raw.repository.name
        id = int(raw.issue.html_url.split("/")[-1])
        return events.GHIssueComment(
            repo,
            author,
            raw.action,
            id,
            raw.issue.title,
            raw.comment.html_url,
            github.authz.is_safe_author(author),
            raw.comment.body,
            raw,
        )

    def convert_commit_comment_event(self, raw):
        repo = raw.repository.owner.login + "/" + raw.repository.name
        return events.GHCommitComment(
            repo, raw.sender.login, raw.comment.commit_id, raw.comment.html_url
        )

    def push_event(self, evt):
        if evt.gh_type == "push":
            obj = self.convert_push_event(evt.raw)
        elif evt.gh_type == "pull_request":
            obj = self.convert_pull_request_event(evt.raw)
        elif evt.gh_type == "pull_request_review":
            obj = self.convert_pull_request_review(evt.raw)
        elif evt.gh_type == "pull_request_review_comment":
            obj = self.convert_pull_request_comment_event(evt.raw)
        elif evt.gh_type == "issue_comment":
            obj = self.convert_issue_comment_event(evt.raw)
        elif evt.gh_type == "commit_comment":
            obj = self.convert_commit_comment_event(evt.raw)
        else:
            logging.error("Unhandled event type %r in GH parser" % evt.gh_type)
            return
        events.dispatcher.dispatch("ghhookparser", obj)


def start():
    events.dispatcher.register_target(GHHookEventParser())

    utils.spawn_periodic_task(600, periodic_hook_maintainer)
