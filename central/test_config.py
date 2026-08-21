from . import config
from .config import cfg

import io
import pathlib
import tempfile
import unittest


class TestConfig(unittest.TestCase):
    def test_basic(self):
        config.load(io.StringIO("""
        test:
            inner:
                val: 42
                foo: bar
        """))
        self.assertEqual(cfg.test.inner.val, 42)
        self.assertEqual(cfg.test.inner.foo, "bar")

    def test_file_include(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.txt"
            with open(path, "w") as fp:
                fp.write("hello")

            config.load(io.StringIO(f"""
                test: !FileInclude "{path}"
            """))
            self.assertEqual(cfg.test, "hello")
