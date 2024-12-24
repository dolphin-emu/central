"""Admin module that handles some central management and administration related
commands."""

from . import events

import os
import os.path
import sys
import time


class RebootListener(events.EventTarget):
    def accept_event(self, evt):
        return evt.type == events.CommandMessage.TYPE

    def push_event(self, evt):
        if not evt.what.endswith("reboot"):
            return

        main_file = os.path.join(os.path.dirname(__file__), "central.py")
        argv = [sys.executable, main_file] + sys.argv[1:]
        if os.fork():
            os._exit(0)
        else:
            time.sleep(1)
            os.execv(sys.executable, argv)


def start():
    """Starts all the Admin related services."""
    events.dispatcher.register_target(RebootListener())
