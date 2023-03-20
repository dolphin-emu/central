from . import app
from .. import events

import json
import requests


class GHPRStatusUpdater(events.EventTarget):
    def accept_event(self, evt):
        return evt.type == events.BuildStatus.TYPE

    def push_event(self, evt):
        if evt.pr is None:
            return

        if evt.pending:
            state = "pending"
        elif evt.success:
            state = "success"
        else:
            state = "failure"

        url = "https://api.github.com/repos/" + evt.repo + "/statuses/" + evt.hash
        data = {
            "state": state,
            "target_url": evt.url,
            "description": evt.description,
            "context": evt.service,
        }
        requests.post(
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(data),
            auth=app.OrgAuth(evt.repo.split("/")[0]),
        )


def start():
    events.dispatcher.register_target(GHPRStatusUpdater())
