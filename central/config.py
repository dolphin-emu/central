"""Configuration system for Dolphin Central.

Loads a single configuration file at initialization time and provides access to
the configuration as a global 'cfg' object.
"""

from . import utils

import yaml

cfg = utils.ObjectLike({})


def load(fp):
    """Loads the configuration from a file-like object."""
    cfg.reset(yaml.full_load(fp))
