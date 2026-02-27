"""IRC client module that sends events to an IRC channel with nice,
human-readable formatting. Also receives events from registered users."""

from . import events, utils
from .config import cfg

from pypeul import IRC, Tags

import logging
import queue
import time


class Bot(IRC):
    def __init__(self, cfg):
        super(Bot, self).__init__()
        self.cfg = cfg

    def start(self):
        self.connect(self.cfg.server, self.cfg.port, self.cfg.ssl)
        self.ident(
            self.cfg.nick,
            sasl_username=self.cfg.sasl_username,
            sasl_password=self.cfg.sasl_password,
        )
        self.set_reconnect(lambda n: 10 * n)
        self.run()

    def on_ready(self):
        for chan in self.cfg.channels:
            self.join(chan)

    def say(self, what):
        for chan in self.cfg.channels:
            self.message(chan, what)

    def wark(self, channel, accepted):
        if accepted:
            text = Tags.BoldLtGreen("WARK WARK WARK")
        else:
            text = Tags.BoldRed("WARK WARK WARK")

        self.message(channel, text)

    def dev_wark(self, accepted):
        # Artifical delay to ensure that chat-bridge sends the command message first
        time.sleep(1)

        self.wark(self.cfg.dev_channel, accepted)

    def on_channel_message(self, who, channel, msg):
        direct = msg.startswith(self.cfg.nick)
        modes = who.user.modes_in(channel)

        if direct:
            trusted = "o" in modes
            if trusted:
                evt = events.CommandMessage(str(who), msg)
                events.dispatcher.dispatch("ircclient", evt)

            if channel == self.cfg.dev_channel:
                wark_evt = events.DevWark(trusted)
                events.dispatcher.dispatch("ircclient", wark_evt)
            else:
                self.wark(channel, trusted)


class EventTarget(events.EventTarget):
    def __init__(self, bot):
        self.bot = bot
        self.queue = queue.Queue()

    def push_event(self, evt):
        self.queue.put(evt)

    def accept_event(self, evt):
        accepted_types = [
            events.Notification.TYPE,
            events.DevWark.TYPE,
        ]
        return evt.type in accepted_types

    def run(self):
        while True:
            evt = self.queue.get()
            if evt.type == events.Notification.TYPE:
                self.bot.say(evt.msg)
            elif evt.type == events.DevWark.TYPE:
                self.bot.dev_wark(evt.accepted)
            else:
                logging.error("Got unknown event for irc: %r" % evt.type)


def start():
    """Starts the IRC client."""
    if not cfg.irc:
        logging.warning("Skipping IRC module: no configuration provided")
        return

    server = cfg.irc.server
    port = cfg.irc.port
    ssl = cfg.irc.ssl
    nick = cfg.irc.nick
    channels = cfg.irc.channels

    logging.info(
        "Starting IRC client: server=%r port=%d ssl=%s nick=%r sasl=%s channels=%r",
        server,
        port,
        ssl,
        nick,
        cfg.irc.sasl_username is not None and cfg.irc.sasl_password is not None,
        channels,
    )

    bot = Bot(cfg.irc)
    utils.DaemonThread(target=bot.start).start()

    evt_target = EventTarget(bot)
    events.dispatcher.register_target(evt_target)
    utils.DaemonThread(target=evt_target.run).start()
