from . import git

import contextlib
import pathlib
import tempfile
import unittest


@contextlib.contextmanager
def tmp_repo(*args, **kwargs):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = pathlib.Path(tmpdir)
        repo = git.GitRepository(tmpdir, *args, **kwargs)
        yield repo


class TestGit(unittest.TestCase):
    def test_init(self):
        with tmp_repo() as repo:
            repo.git_cli("init", "--bare")
            self.assertTrue((repo.path / "HEAD").is_file())

    def test_clone(self):
        with tmp_repo() as src_repo, tmp_repo() as dst_repo:
            src_repo.git_cli("init")
            with (src_repo.path / "test.txt").open("w") as f:
                f.write("hello")
            src_repo.git_cli("add", "test.txt")
            src_repo.git_cli("commit", "-m", "test commit")

            dst_repo.clone(src_repo.path)
            self.assertEqual(src_repo.show_ref("master"), dst_repo.show_ref("master"))
