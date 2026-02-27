"""Discord client module that sends notifications to a Discord channel."""

from . import events, utils
from .config import cfg

from pypeul import Tags

from discord import Client, Intents

import asyncio
import logging
import queue
import time


class Bot(Client):
    def __init__(self, cfg, intents):
        super(Bot, self).__init__(intents=intents)
        self.cfg = cfg

    def send_notification(self, message):
        stripped_msg = Tags.strip(message)

        for channel_id in self.cfg.channels:
            channel = self.get_channel(channel_id)
            f = asyncio.run_coroutine_threadsafe(channel.send(stripped_msg), self.loop)
            f.result()

    def format_wark_text(self, accepted):
        return "**WARK WARK WARK** (%s)" % ("accepted" if accepted else "denied")

    def send_dev_wark(self, accepted):
        # Artifical delay to ensure that chat-bridge sends the command message first
        time.sleep(1)

        text = self.format_wark_text(accepted)
        channel = self.get_channel(self.cfg.dev_channel)

        f = asyncio.run_coroutine_threadsafe(channel.send(text), self.loop)
        f.result()

    async def on_message(self, message):
        if message.author == self.user or not self.user.mentioned_in(message):
            return

        accepted = False

        if message.author.get_role(self.cfg.privileged_role) != None:
            evt = events.CommandMessage(message.author.name, message.content)
            events.dispatcher.dispatch("discord", evt)

            accepted = True

        if message.channel.id == self.cfg.dev_channel:
            wark_evt = events.DevWark(accepted)
            events.dispatcher.dispatch("discord", wark_evt)
        else:
            await message.channel.send(self.format_wark_text(accepted))


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
                self.bot.send_notification(evt.msg)
            elif evt.type == events.DevWark.TYPE:
                self.bot.send_dev_wark(evt.accepted)
            else:
                logging.error("Got unknown event for discord: %r" % evt.type)


def start():
    """Starts the Discord client."""
    if not cfg.discord:
        logging.warning("Skipping Discord module: no configuration provided")
        return

    logging.info("Starting Discord client")

    intents = Intents.default()
    intents.guilds = True
    intents.guild_messages = True

    bot = Bot(cfg.discord, intents)
    utils.DaemonThread(target=bot.run, kwargs={"token": cfg.discord.token}).start()

    evt_target = EventTarget(bot)
    events.dispatcher.register_target(evt_target)
    utils.DaemonThread(target=evt_target.run).start()
