"""Configuration system for Dolphin Central.

Loads a single configuration file at initialization time and provides access to
the configuration as a global 'cfg' object.
"""

from . import utils

import yaml

cfg = utils.ObjectLike({})


def file_include_constructor(loader, node):
    value = str(loader.construct_scalar(node))
    with open(value) as fp:
        return fp.read()


def load(fp):
    """Loads the configuration from a file-like object."""
    loader = yaml.SafeLoader
    loader.add_constructor("!FileInclude", file_include_constructor)
    cfg.reset(yaml.load(fp, Loader=loader))
