from . import app, authz, build_status, fifoci_reporter, webhooks

from .. import utils
from ..config import cfg

import json
import requests


def get_pull_request(owner, repo, pr_id):
    return requests.get(
        "https://api.github.com/repos/%s/%s/pulls/%s" % (owner, repo, pr_id)
    ).json()


def get_pull_request_comments(pr):
    comments = []
    url = pr["_links"]["comments"]["href"]
    while True:
        r = requests.get(url)
        comments.extend(r.json())
        if "link" in r.headers and "next" in r.links:
            url = r.links["next"]["url"]
        else:
            break
    return comments


def delete_comment(owner, repo, cmt_id):
    requests.delete(
        "https://api.github.com/repos/%s/%s/issues/comments/%d" % (owner, repo, cmt_id),
        auth=app.OrgAuth(owner),
    )


def post_comment(owner, repo, pr_id, body):
    requests.post(
        "https://api.github.com/repos/%s/%s/issues/%s/comments" % (owner, repo, pr_id),
        data=json.dumps({"body": body}),
        headers={"Content-Type": "application/json"},
        auth=app.OrgAuth(owner),
    )


def get_pr_review_comments(owner, repo, pr_id, review_id):
    json = requests.get(
        "https://api.github.com/repos/%s/%s/pulls/%d/reviews/%d/comments"
        % (owner, repo, pr_id, review_id),
        headers={
            "Content-Type": "application/json",
            # This API is currently in preview so we need to specify this,
            # but it will continue to work after the preview period ends.
            "Accept": "application/vnd.github.black-cat-preview+json",
        },
        auth=app.OrgAuth(owner),
    ).json()
    return [utils.ObjectLike(c) for c in json]


def request_get_all(url, **kwargs):
    """Github uses Link header for pagination, this loops through all pages."""
    data = []
    r = requests.get(url, **kwargs)
    data += r.json()
    while "next" in r.links:
        r = requests.get(r.links["next"]["url"], **kwargs)
        data += r.json()
    return data


def start():
    """Starts all the GitHub related services."""

    # Start first to ensure app-based authorization is available to all other
    # modules.
    app.start()

    for mod in [authz, build_status, fifoci_reporter, webhooks]:
        mod.start()
