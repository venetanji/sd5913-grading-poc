import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from grading_poc.cli import make_packet
from grading_poc.core import collect_evidence, read_urls, repo_id
from grading_poc.laya_local import state_for_criterion


class EvidenceTests(unittest.TestCase):
    def test_url_parser_rejects_non_github_input(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as f:
            f.write("https://example.com/not-a-repo\n")
            f.flush()
            with self.assertRaises(ValueError):
                read_urls(f.name)

    def test_evidence_packet_omits_url_and_uses_source_rubric(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "README.md").write_text("# Essay\nA short test README.\n", encoding="utf-8")
            (repo / "PROCESS.md").write_text("Used tool X, kept A, rejected B.\n", encoding="utf-8")
            (repo / "main.py").write_text("print('ok')\n", encoding="utf-8")
            (repo / "data").mkdir()
            (repo / "data" / "raw.csv").write_text("v\n1\n", encoding="utf-8")
            env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                   "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
                   "GIT_AUTHOR_DATE": "2026-09-01T12:00:00Z", "GIT_COMMITTER_DATE": "2026-09-01T12:00:00Z"}
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True, env=env)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "test"], check=True, env=env)
            source = repo.as_uri()
            evidence = collect_evidence(source, 1, str(Path(root) / "clone"))
            packet = make_packet(evidence)
            self.assertEqual(evidence["submission_id"], repo_id(source))
            self.assertNotIn(source, json.dumps(packet))
            self.assertEqual(packet["rubric"]["criteria"][0]["name"], "Argument")
            self.assertTrue(any(row["check"] == "PROCESS.md present and non-empty" and row["result"] for row in packet["preflight"]))

    def test_laya_builds_criterion_specific_evidence_context(self):
        packet = {
            "assignment": 1,
            "rubric": {"title": "Test essay", "criteria": [{"name": "Argument", "description": "claim"}]},
            "preflight": [],
            "history": {},
            "inventory": {},
            "evidence": [
                {"path": "README.md", "text": "Essay body"},
                {"path": "PROCESS.md", "text": "Process"},
                {"path": "irrelevant.py", "text": "not argument evidence"},
            ],
        }
        state = json.loads(state_for_criterion(packet, "Argument"))
        self.assertEqual([item["path"] for item in state["files"]], ["README.md"])


if __name__ == "__main__":
    unittest.main()
