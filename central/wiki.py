"""Updates Dolphin's Wiki on various conditions, to e.g. keep the latest dev
build version up to date."""

from . import events, utils
from .config import cfg

import logging
import mwclient
import queue


class WikiUpdater:
    def __init__(self, settings):
        self.host = settings.host
        self.path = settings.path
        self.username = settings.username
        self.password = settings.password
        self.latest_dev_page = settings.latest_dev_page

        self.queue = queue.Queue()

    def handle_version(self, evt):
        self.queue.put(evt)

    def run(self):
        site = mwclient.Site(self.host, path=self.path)
        site.login(self.username, self.password)

        logging.info("Logged in to wiki %s (username %s)", self.host, self.username)

        while True:
            evt = self.queue.get()

            page = site.pages[self.latest_dev_page]
            page.edit(evt.shortrev, "Automatic update of the current git revision")


class NewDevVersionListener(events.EventTarget):
    def __init__(self, updater):
        super().__init__()
        self.updater = updater

    def accept_event(self, evt):
        return evt.type == events.NewDevVersion.TYPE

    def push_event(self, evt):
        self.updater.handle_version(evt)


def start():
    if not cfg.wiki:
        logging.warning("Skipping Wiki module: no configuration provided.")
        return

    updater = WikiUpdater(cfg.wiki)
    utils.DaemonThread(target=updater.run).start()

    events.dispatcher.register_target(NewDevVersionListener(updater))
