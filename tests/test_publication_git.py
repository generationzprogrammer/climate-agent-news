"""Offline regression of the exact CI dirty-cache/rebase failure."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which("git"), "git is required for publication regression")
class PublicationGitTests(unittest.TestCase):
    def test_generated_caches_do_not_block_rebase_or_replace_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args, check=True):
                return subprocess.run(["git", *args], cwd=root, check=check, capture_output=True, text=True, encoding="utf-8", timeout=20)
            def write(name, data):
                file = root / name; file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(data, encoding="utf-8")
            git("init", "-b", "main")
            git("config", "user.name", "Publication regression")
            git("config", "user.email", "test@example.invalid")
            git("config", "commit.gpgsign", "false")
            git("config", "core.autocrlf", "false")
            write("data/news_archive.json", '{"records":[{"id":"old"}]}')
            write("static/data/bth_assistant_config.json", '{"endpoint":""}')
            write("app.py", "original\n")
            git("add", "."); git("commit", "-m", "baseline")
            git("switch", "-c", "upstream")
            write("app.py", "new upstream code\n")
            git("add", "app.py"); git("commit", "-m", "code update")
            git("switch", "main")
            archive = '{"records":[{"id":"old"},{"id":"new"}]}'
            write("data/news_archive.json", archive)
            git("add", "data/news_archive.json"); git("commit", "-m", "daily archive")
            write("static/data/bth_assistant_config.json", '{"endpoint":"https://assistant.example.com"}')
            write("static/data/bth_policy_archive.json", '{"records":[{"id":"policy"}]}')
            write("site/data/dashboard.json", archive)
            write("src/package.egg-info/PKG-INFO", "generated installation metadata")
            failed = git("rebase", "upstream", check=False)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("unstaged changes", failed.stderr)
            git("stash", "push", "--include-untracked", "--message", "ci-generated-static-data", "--", "static/data")
            git("rebase", "upstream")
            self.assertEqual((root / "data/news_archive.json").read_text(), archive)
            self.assertEqual((root / "site/data/dashboard.json").read_text(), archive)
            self.assertEqual((root / "app.py").read_text(), "new upstream code\n")
            self.assertEqual(json.loads((root / "static/data/bth_assistant_config.json").read_text())["endpoint"], "")
            self.assertIn("ci-generated-static-data", git("stash", "list").stdout)
            git("stash", "apply", "--index")
            self.assertEqual(json.loads((root / "static/data/bth_assistant_config.json").read_text())["endpoint"], "https://assistant.example.com")
            self.assertTrue((root / "static/data/bth_policy_archive.json").exists())

    def test_workflow_uses_scoped_cache_stash_before_rebase(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        command = "git stash push --include-untracked --message ci-generated-static-data -- static/data"
        self.assertIn(command, workflow)
        self.assertLess(workflow.index(command), workflow.index("git rebase origin/main"))
        self.assertIn("test -f site/data/dashboard.json", workflow)
        self.assertNotIn("git push --force", workflow)


if __name__ == "__main__": unittest.main()
