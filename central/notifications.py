"""Module that formats events into nice, human-readable text."""

from . import events, utils
from .config import cfg

from pypeul import Tags

import logging
import queue


class EventSettler(utils.DaemonThread):
    SETTLE_TIMEOUT_SECS = 30.0

    def __init__(self, handler):
        super(EventSettler, self).__init__()
        self.handler = handler
        self.queue = queue.Queue()
        self.start()

    def push(self, item):
        self.queue.put(item)

    def run_daemonized(self):
        l = []
        while True:
            l = [self.queue.get()]
            try:
                while True:
                    l.append(self.queue.get(timeout=self.SETTLE_TIMEOUT_SECS))
            except queue.Empty:
                self.handler(l)


class EventTarget(events.EventTarget):
    def __init__(self):
        self.build_status_settler = EventSettler(self.handle_build_status_settled)
        self.queue = queue.Queue()

    def push_event(self, evt):
        self.queue.put(evt)

    def accept_event(self, evt):
        accepted_types = [
            events.Issue.TYPE,
            events.GHPush.TYPE,
            events.GHPullRequest.TYPE,
            events.GHPullRequestReview.TYPE,
            events.GHPullRequestComment.TYPE,
            events.GHIssueComment.TYPE,
            events.GHCommitComment.TYPE,
            events.BuildStatus.TYPE,
        ]
        return evt.type in accepted_types

    def run(self):
        while True:
            evt = self.queue.get()
            if evt.type == events.Issue.TYPE:
                self.handle_issue(evt)
            elif evt.type == events.GHPush.TYPE:
                self.handle_gh_push(evt)
            elif evt.type == events.GHPullRequest.TYPE:
                self.handle_gh_pull_request(evt)
            elif evt.type == events.GHPullRequestReview.TYPE:
                self.handle_gh_pull_request_review(evt)
            elif evt.type == events.GHPullRequestComment.TYPE:
                self.handle_gh_pull_request_comment(evt)
            elif evt.type == events.GHIssueComment.TYPE:
                self.handle_gh_issue_comment(evt)
            elif evt.type == events.GHCommitComment.TYPE:
                self.handle_gh_commit_comment(evt)
            elif evt.type == events.BuildStatus.TYPE:
                self.handle_build_status(evt)
            else:
                logging.error("Got unknown event for notifications: %r" % evt.type)

    def format_nickname(self, nickname, avoid_hl=True):
        # Add a unicode zero-width space in the nickname to avoid highlights on IRC.
        if avoid_hl and nickname:
            nickname = nickname[0] + "\ufeff" + nickname[1:]
        return Tags.Green(nickname)

    def handle_issue(self, evt):
        """Sends a notification for a new issue update."""
        author = self.format_nickname(evt.author)
        if evt.new:
            short_url = "https://dolp.in/i%d" % evt.issue
            url = Tags.UnderlineBlue(short_url)
            msg = 'Issue %d created: "%s" by %s - %s'
            msg = msg % (evt.issue, evt.title, author, url)
        else:
            short_url = "https://dolp.in/i%d/%d" % (evt.issue, evt.update)
            url = Tags.UnderlineBlue(short_url)
            msg = 'Update %d to issue %d ("%s") by %s - %s'
            msg = msg % (evt.update, evt.issue, evt.title, author, url)
        msg_evt = events.Notification(msg)
        events.dispatcher.dispatch("notifications", msg_evt)

    def handle_gh_push(self, evt):
        fmt_url = Tags.UnderlineBlue
        fmt_repo_name = Tags.UnderlinePink
        fmt_ref = Tags.Purple
        fmt_hash = lambda h: Tags.Grey(h[:6])

        commits = [utils.ObjectLike(c) for c in evt.commits]
        distinct_commits = [c for c in commits if c.distinct and c.message.strip()]
        num_commits = len(distinct_commits)

        parts = []
        parts.append("[" + fmt_repo_name(evt.repo) + "]")
        parts.append(self.format_nickname(evt.pusher))

        if evt.created:
            if evt.ref_type == "tags":
                parts.append("tagged " + fmt_ref(evt.ref_name) + " at")
                parts.append(
                    fmt_ref(evt.base_ref_name)
                    if evt.base_ref_name
                    else fmt_hash(evt.after_sha)
                )
            else:
                parts.append("created " + fmt_ref(evt.ref_name))
                if evt.base_ref_name:
                    parts.append("from " + fmt_ref(evt.base_ref_name))
                elif not distinct_commits:
                    parts.append("at " + fmt_hash(evt.after_sha))

                if distinct_commits:
                    parts.append("+" + Tags.Bold(str(num_commits)))
                    parts.append("new commit" + ("s" if num_commits > 1 else ""))
        elif evt.deleted:
            parts.append(Tags.Red("deleted ") + fmt_ref(evt.ref_name))
            parts.append("at " + fmt_hash(evt.before_sha))
        elif evt.forced:
            parts.append(Tags.Red("force-pushed ") + fmt_ref(evt.ref_name))
            parts.append(
                "from " + fmt_hash(evt.before_sha) + " to " + fmt_hash(evt.after_sha)
            )
        elif commits and not distinct_commits:
            if evt.base_ref_name:
                parts.append(
                    "merged "
                    + fmt_ref(evt.base_ref_name)
                    + " into "
                    + fmt_ref(evt.ref_name)
                )
            else:
                parts.append("fast-forwarded " + fmt_ref(evt.ref_name))
                parts.append(
                    "from "
                    + fmt_hash(evt.before_sha)
                    + " to "
                    + fmt_hash(evt.after_sha)
                )
        else:
            parts.append("pushed " + Tags.Bold(str(num_commits)))
            parts.append("new commit" + ("s" if num_commits > 1 else ""))
            parts.append("to " + fmt_ref(evt.ref_name))

        msg_evt = events.Notification(" ".join(str(p) for p in parts))
        events.dispatcher.dispatch("notifications", msg_evt)

        for commit in distinct_commits[:4]:
            firstline = commit.message.split("\n")[0]
            author = self.format_nickname(commit.author.name)
            added = Tags.LtGreen(str(len(commit.added)))
            modified = Tags.LtGreen(str(len(commit.modified)))
            removed = Tags.Red(str(len(commit.removed)))
            url = Tags.UnderlineBlue(utils.shorten_url(commit.url))
            commit_msg_evt = events.Notification(
                "%s by %s [%s|%s|%s] %s %s"
                % (commit.hash[:6], author, added, modified, removed, url, firstline)
            )
            events.dispatcher.dispatch("notifications", commit_msg_evt)

        if len(distinct_commits) > 4:
            more_commits_msg_evt = events.Notification(
                "... and %d more commits" % (len(distinct_commits) - 4)
            )
            events.dispatcher.dispatch("notifications", more_commits_msg_evt)

    def handle_gh_pull_request(self, evt):
        action = evt.action
        if action == "synchronize":
            action = "synchronized"
        elif action == "review_requested":
            action = "requested a review from %s for" % ", ".join(
                [user["login"] for user in evt.requested_reviewers]
            )
        elif action == "review_request_removed":
            action = "dismissed a review request on"
        elif action == "ready_for_review":
            action = "marked ready for review"
        elif action == "converted_to_draft":
            action = "converted to draft"
        elif action == "closed" and evt.merged:
            action = "merged"
        msg_evt = events.Notification(
            "[%s] %s %s pull request #%d: %s (%s...%s): %s"
            % (
                Tags.UnderlinePink(evt.repo),
                self.format_nickname(evt.author),
                action,
                evt.id,
                evt.title,
                Tags.Purple(evt.base_ref_name),
                Tags.Purple(evt.head_ref_name),
                Tags.UnderlineBlue(utils.shorten_url(evt.url)),
            )
        )
        events.dispatcher.dispatch("notifications", msg_evt)

    def handle_gh_pull_request_review(self, evt):
        # GitHub sends a review event in addition to a review comment event
        # when someone replies to an earlier comment or adds a single comment,
        # even when they didn't really submit a pull request review.
        # To prevent useless notifications, we skip any "review" which only has
        # one comment, since there is already a comment notification for those.
        if (
            len(evt.comments) == 1
            and evt.comments[0].created_at == evt.comments[0].updated_at
        ):
            return

        if evt.state == "pending" or evt.action == "edited":
            return

        if evt.action == "submitted" and evt.state == "approved":
            action = "approved"
            if len(evt.comments) != 0:
                action += " and commented on"
        elif evt.action == "submitted" and evt.state == "commented":
            action = "reviewed and commented on"
            # GitHub sends a review event when someone replies to a review comment.
            # Omit 'reviewed and' in this case.
            for comment in evt.comments:
                if "in_reply_to_id" in comment:
                    action = "commented on"
                    break
        elif evt.action == "submitted" and evt.state == "changes_requested":
            action = "requested changes to"
        elif evt.action == "dismissed":
            action = "dismissed their review on"
        else:
            action = "%s their review on" % evt.action
        msg_evt = events.Notification(
            "[%s] %s %s pull request #%s (%s): %s"
            % (
                Tags.UnderlinePink(evt.repo),
                self.format_nickname(evt.author),
                action,
                evt.pr_id,
                evt.pr_title,
                Tags.UnderlineBlue(utils.shorten_url(evt.url)),
            )
        )
        events.dispatcher.dispatch("notifications", msg_evt)

    def handle_gh_pull_request_comment(self, evt):
        if evt.is_part_of_review or evt.action != "created":
            return
        msg_evt = events.Notification(
            "[%s] %s commented on #%s %s: %s"
            % (
                Tags.UnderlinePink(evt.repo),
                self.format_nickname(evt.author),
                evt.id,
                evt.hash[:6],
                Tags.UnderlineBlue(utils.shorten_url(evt.url)),
            )
        )
        events.dispatcher.dispatch("notifications", msg_evt)

    def handle_gh_issue_comment(self, evt):
        if evt.author == cfg.github.app.username:
            return
        if evt.action == "created":
            action = "commented on"
        else:
            action = "%s a comment on" % evt.action
        msg_evt = events.Notification(
            "[%s] %s %s #%s (%s): %s"
            % (
                Tags.UnderlinePink(evt.repo),
                self.format_nickname(evt.author),
                action,
                evt.id,
                evt.title,
                Tags.UnderlineBlue(utils.shorten_url(evt.url)),
            )
        )
        events.dispatcher.dispatch("notifications", msg_evt)

    def handle_gh_commit_comment(self, evt):
        msg_evt = events.Notification(
            "[%s] %s commented on commit %s: %s"
            % (
                Tags.UnderlinePink(evt.repo),
                self.format_nickname(evt.author),
                evt.commit,
                Tags.UnderlineBlue(utils.shorten_url(evt.url)),
            )
        )
        events.dispatcher.dispatch("notifications", msg_evt)

    def handle_build_status(self, evt):
        if evt.success or evt.pending:
            return
        self.build_status_settler.push(evt)

    def handle_build_status_settled(self, evts):
        per_shortrev = {}
        for evt in evts:
            per_shortrev.setdefault(evt.shortrev, []).append(evt)
        for shortrev, evts in per_shortrev.items():
            builders = [evt.service for evt in evts]
            builders.sort()

            evt = evts[0]
            if evt.pr is not None:
                shortrev = "#%s" % evt.pr

            msg_evt = events.Notification(
                "[%s] build for %s %s on builders [%s]: %s"
                % (
                    Tags.UnderlinePink(evt.repo),
                    shortrev,
                    Tags.Red("failed"),
                    ", ".join(builders),
                    Tags.UnderlineBlue(utils.shorten_url(evt.url)),
                )
            )
            events.dispatcher.dispatch("notifications", msg_evt)


def start():
    evt_target = EventTarget()
    events.dispatcher.register_target(evt_target)
    utils.DaemonThread(target=evt_target.run).start()
