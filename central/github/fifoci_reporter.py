from .. import events, github
from ..config import cfg

import requests
import textwrap


class GHFifoCIEditer(events.EventTarget):
    MAGIC_WORDS = "automated-fifoci-reporter"

    def accept_event(self, evt):
        return evt.type == events.PullRequestFifoCIStatus.TYPE

    def push_event(self, evt):
        # Get FifoCI side status
        url = cfg.fifoci.url + "/version/%s/json/" % evt.hash
        diff_data = requests.get(url).json()
        owner, repo = evt.repo.split("/")
        pr = github.get_pull_request(owner, repo, evt.pr)
        comments = github.get_pull_request_comments(pr)
        comments = [
            c for c in comments if c["user"]["login"] == cfg.github.app.username
        ]

        body = textwrap.dedent(
            """\
            [FifoCI](%s/about/) detected that this change impacts graphical \
            rendering. Here are the [behavior differences](%s/version/%s/) \
            detected by the system:

        """
            % (cfg.fifoci.url, cfg.fifoci.url, evt.hash)
        )
        for diff in diff_data:
            l = "* `%s` on `%s`: " % (diff["dff"], diff["type"])
            if diff["failure"]:
                l += "[failed to render]"
            else:
                l += "[diff]"
            l += "(%s%s)" % (cfg.fifoci.url, diff["url"])
            body += l + "\n"
        body += "\n<sub><sup>" + self.MAGIC_WORDS + "</sup></sub>"

        if comments and comments[-1]["body"] == body:
            return

        for c in comments:
            if self.MAGIC_WORDS in c["body"]:
                github.delete_comment(owner, repo, c["id"])

        if not diff_data:
            return

        github.post_comment(owner, repo, evt.pr, body)


def start():
    events.dispatcher.register_target(GHFifoCIEditer())
