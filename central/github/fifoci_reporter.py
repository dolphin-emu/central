from .. import events, github
from ..config import cfg

import collections
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

            <details>
            <summary>Detected differences</summary>

        """
            % (cfg.fifoci.url, cfg.fifoci.url, evt.hash)
        )

        system_types = sorted(set(entry["type"] for entry in diff_data))

        table_header = "||"
        table_divider = "|-|"

        for system_type in system_types:
            table_header += "%s|" % system_type
            table_divider += "-|"

        body += "%s\n%s\n" % (table_header, table_divider)

        dff_dict = collections.defaultdict(dict)
        for entry in diff_data:
            replay = entry["dff"]

            if entry["failure"]:
                value = "❌ fail"
            else:
                value = "🔍 diff"

            dff_dict[replay][entry["type"]] = "[%s](%s%s)" % (
                value,
                cfg.fifoci.url,
                entry["url"],
            )

        table_rows = []

        for replay in sorted(dff_dict.keys()):
            row = "|%s|" % replay

            for system_type in system_types:
                row += "%s|" % dff_dict[replay].get(system_type, "-")

            table_rows.append(row)

        body += "%s\n</details>" % "\n".join(table_rows)
        body += "\n<sub><sup>%s</sup></sub>" % self.MAGIC_WORDS

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
