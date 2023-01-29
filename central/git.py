"""Library to maintain a local Git repository clone in order to extract metadata and enrich
information received from GitHub."""

from . import events, utils
from .config import cfg

import logging
import os.path
import queue
import shutil
import subprocess


def find_in_path(binary):
    path = shutil.which(binary)
    if path is None:
        raise RuntimeError("Could not find 'git' binary in $PATH")
    return path


class GitRepository:
    def __init__(self, path):
        super().__init__()
        self.path = path
        if cfg.git and cfg.git.git_path is not None:
            self.git_path = cfg.git.git_path
        else:
            self.git_path = find_in_path("git")

    def git_cli(self, *args):
        env = {
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "Dolphin Central",
            "GIT_AUTHOR_EMAIL": "central@dolphin-emu.org",
            "GIT_COMMITTER_NAME": "Dolphin Central",
            "GIT_COMMITTER_EMAIL": "central@dolphin-emu.org",
        }
        logging.debug("[%s] running git command: %s", self.path, args)
        out = subprocess.run(
            (self.git_path,) + args,
            cwd=self.path,
            check=True,
            env=env,
            capture_output=True,
        )
        return out.stdout.decode("utf-8").strip()

    def clone(self, origin):
        self.git_cli("clone", "--bare", "--filter=tree:0", origin, ".")

    def fetch(self):
        self.git_cli("fetch", "--all", "--prune")
        self.git_cli("update-ref", "HEAD", "FETCH_HEAD")

    def commit_log(self, hash, format):
        return self.git_cli("log", "-1", f"--format=format:{format}", hash)

    def show_ref(self, ref):
        return self.git_cli("show-ref", "--hash", ref)


class RepoManager:
    def __init__(self, repo_name):
        self.repo_name = repo_name
        self.path = os.path.join(cfg.git.repos_path, repo_name)
        self.repo_url = f"https://github.com/{repo_name}"
        self.repo = GitRepository(self.path)

        self.queue = queue.Queue()

    def handle_push(self, push_evt):
        self.queue.put(push_evt)

    def reset_repo(self):
        logging.info("[%s] cloning from %s", self.repo_name, self.repo_url)
        if os.path.isdir(self.path):
            shutil.rmtree(self.path)
        os.makedirs(self.path)
        self.repo.clone(self.repo_url)
        logging.info("[%s] repo cloned successfully", self.repo_name)

    def determine_branch(self, commit):
        out = self.repo.git_cli("branch", "-a", "--contains", commit.hash)
        candidates = [c.strip().removeprefix("* ") for c in out.split("\n")]

        for candidate in candidates:
            all_parents = self.repo.git_cli("rev-list", "--first-parent", candidate)
            if commit.hash in all_parents:
                return candidate

        return None

    def run(self):
        self.reset_repo()

        while True:
            evt = self.queue.get()

            self.repo.fetch()

            commits = [utils.ObjectLike(c) for c in evt.commits]
            distinct_commits = [c for c in commits if c.distinct and c.message.strip()]
            logging.info(
                "[%s] push received with %d commits",
                self.repo_name,
                len(distinct_commits),
            )

            for commit in distinct_commits:
                branch = self.determine_branch(commit)
                if branch is None:
                    logging.info(
                        "[%s] skipping commit %s, not on a named branch",
                        self.repo_name,
                        commit.hash,
                    )
                    continue

                desc = self.repo.git_cli("describe", "--always", "--long", commit.hash)
                shortrev = desc.rsplit("-", 1)[0]

                author = self.repo.commit_log(commit.hash, "%an")
                comment = self.repo.commit_log(commit.hash, "%s\n\n%b")
                url = f"https://github.com/{self.repo_name}/commit/{commit.hash}"

                logging.info(
                    "[%s] commit %s: (%s) %s from %s",
                    self.repo_name,
                    commit.hash[:8],
                    branch,
                    shortrev,
                    author,
                )

                dev_ver_evt = events.NewDevVersion(
                    commit.hash, branch, shortrev, author, comment, url
                )
                events.dispatcher.dispatch("repomanager", dev_ver_evt)


class NewDevVersionListener(events.EventTarget):
    def __init__(self, repos):
        super().__init__()
        self.repos = repos

    def accept_event(self, evt):
        return evt.type == events.GHPush.TYPE

    def push_event(self, evt):
        if evt.repo in self.repos:
            self.repos[evt.repo].handle_push(evt)


def start():
    """Starts all the Git related services."""
    if not cfg.git or not cfg.git.repos_path:
        logging.warning("Skipping Git module: no repos path configured")
        return

    os.makedirs(cfg.git.repos_path, exist_ok=True)

    repos = {r: RepoManager(r) for r in (cfg.github.maintain or [])}
    for manager in repos.values():
        utils.DaemonThread(target=manager.run).start()

    events.dispatcher.register_target(NewDevVersionListener(repos))
