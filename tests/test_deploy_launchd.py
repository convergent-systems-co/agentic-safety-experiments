"""The launchd installer renders a valid, agent-named wake job."""
from __future__ import annotations

import platform
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from experiment4.harness import IdentityApprenticeship
from experiment4.repository import SQLiteIdentityRepository

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "deploy" / "launchd" / "install-wake-agent.sh"


class WakeAgentInstallerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        if platform.system() != "Darwin" or shutil.which("plutil") is None:
            self.skipTest("launchd installer is macOS only")
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "agent.db"
        harness = IdentityApprenticeship(SQLiteIdentityRepository(self.database))
        self.experiment_id = harness.initialize(
            experiment_id="installer-test",
            model_config={"provider": "test", "model": "genesis", "tools": []},
        )["experiment_id"]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def dry_run(self, *extra: str) -> str:
        completed = subprocess.run(
            [
                str(INSTALLER),
                "--agent", "test-agent",
                "--db", str(self.database),
                "--experiment-id", self.experiment_id,
                "--log-dir", str(Path(self.temporary.name) / "logs"),
                "--dry-run",
                *extra,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        return completed.stdout

    def test_dry_run_renders_a_valid_job_named_for_the_agent(self):
        rendered = self.dry_run()
        plist = rendered.split("\n# dry run", 1)[0]
        self.assertIn("com.convergent-systems.test-agent-wake", plist)
        self.assertIn(str(self.database), plist)
        self.assertIn("execute-wake-intents", plist)
        # No UNFILLED PLACEHOLDER may remain. Asserting on a bare "__"
        # instead conflated placeholders with substituted values: macOS temp
        # paths contain a double underscore (/var/folders/67/w__hpdvj.../T/),
        # so this failed on a correctly rendered plist.
        self.assertIsNone(
            re.search(r"__[A-Z][A-Z0-9_]*__", plist.split("-->", 1)[1])
        )
        self.assertNotIn("--model-command", plist)
        lint = Path(self.temporary.name) / "job.plist"
        lint.write_text(plist)
        self.assertEqual(
            0, subprocess.run(["plutil", "-lint", str(lint)], capture_output=True).returncode
        )

    def test_model_command_is_forwarded_as_one_argument(self):
        rendered = self.dry_run("--model-command", "claude -p --output-format json")
        self.assertIn("<string>--model-command</string>", rendered)
        self.assertIn("<string>claude -p --output-format json</string>", rendered)

    def test_installer_rejects_unsafe_agent_names_and_repo_logs(self):
        for bad in (["--agent", "Bad Name"], ["--agent", "x", "--log-dir", str(REPO_ROOT / "logs")]):
            completed = subprocess.run(
                [str(INSTALLER), *bad, "--db", str(self.database), "--experiment-id", self.experiment_id, "--dry-run"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(2, completed.returncode, bad)


if __name__ == "__main__":
    unittest.main()
