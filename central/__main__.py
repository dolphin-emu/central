"""Main module for Dolphin Central.

Initializes and registers the required components then starts the main event
loop of the process.
"""

from . import (
    admin,
    buildbot,
    config,
    discord,
    events,
    git,
    github,
    ircclient,
    notifications,
    redmine,
    webserver,
    wiki,
)

import argparse
import functools
import logging
import logging.handlers
import signal
import time


class EventLoggingHandler(logging.Handler):
    """Emits internal_log events to the internal event dispatcher when a log
    message is received."""

    def emit(self, record):
        evt = events.InternalLog(
            record.levelname,
            record.pathname,
            record.lineno,
            record.msg,
            str(record.args),
        )
        events.dispatcher.dispatch("logging", evt)


def setup_logging(program, verbose=False, local=True):
    """Sets up the default Python logger.

    Always log to syslog, optionaly log to stdout.

    Args:
      program: Name of the program logging informations.
      verbose: If true, log more messages (DEBUG instead of INFO).
      local: If true, log to stdout as well as syslog.
    """
    loggers = []
    loggers.append(logging.handlers.SysLogHandler("/dev/log"))
    loggers.append(EventLoggingHandler())
    if local:
        loggers.append(logging.StreamHandler())
    for logger in loggers:
        logger.setFormatter(
            logging.Formatter(program + ": [%(levelname)s] %(message)s")
        )
        logging.getLogger("").addHandler(logger)
    logging.getLogger("").setLevel(logging.DEBUG if verbose else logging.INFO)


def reload_config(path, *, sighup=False):
    with open(path) as fp:
        config.load(fp)
    if sighup:
        logging.info("SIGHUP received, reloaded config")
        events.dispatcher.dispatch("sighup", events.ConfigReload())


def main():
    # Parse command line flags.
    parser = argparse.ArgumentParser(
        description="Dolphin Central event " "dispatching server."
    )
    parser.add_argument(
        "--verbose", help="Increases logging level.", action="store_true", default=False
    )
    parser.add_argument(
        "--no_local_logging",
        help="Disable stderr logging.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--config",
        help="Path to configuration file.",
        required=True,
    )
    args = parser.parse_args()

    # Initialize logging.
    setup_logging("central", args.verbose, not args.no_local_logging)

    logging.info("Starting Dolphin Central.")

    # Load configuration from disk.
    reload_config(args.config)
    signal.signal(
        signal.SIGHUP, lambda *a, **kw: reload_config(args.config, sighup=True)
    )

    logging.info("Configuration loaded, starting modules initialization.")

    # Start the modules.
    for mod in [
        admin,
        buildbot,
        discord,
        git,
        github,
        ircclient,
        notifications,
        redmine,
        webserver,
        wiki,
    ]:
        mod.start()

    logging.info("Modules started, waiting for events.")

    # Loop to wait for signals/exceptions.
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
