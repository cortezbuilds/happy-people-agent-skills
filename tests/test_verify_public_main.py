import base64
import importlib.util
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError


SCRIPT = Path(__file__).resolve().parents[1] / "skills/release-evidence/scripts/verify_public_main.py"
SPEC = importlib.util.spec_from_file_location("verify_public_main", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
COMMIT = "a" * 40
NEW_COMMIT = "b" * 40


class PublicMainVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "assets").mkdir()
        (self.root / "assets/icon.png").write_bytes(b"\x89PNG\r\nexample")

    def public_file(self, data, path="assets/icon.png"):
        return {
            "type": "file",
            "path": path,
            "encoding": "base64",
            "content": base64.b64encode(data).decode("ascii"),
        }

    def test_exact_binary_bytes_on_pinned_public_main(self):
        calls = []

        def fetch(url):
            calls.append(url)
            if url.endswith("/branches/main"):
                return {"commit": {"sha": COMMIT}}
            self.assertIn(f"?ref={COMMIT}", url)
            return self.public_file(b"\x89PNG\r\nexample")

        result = MODULE.verify("example/project", self.root, ["assets/icon.png"], fetch)
        self.assertEqual(result["status"], "verified_public_main")
        self.assertEqual(result["public_main_commit"], COMMIT)
        self.assertEqual(len(calls), 3)

    def test_changed_bytes_do_not_count_as_shipped(self):
        def fetch(url):
            return {"commit": {"sha": COMMIT}} if url.endswith("/branches/main") else self.public_file(b"older icon")

        result = MODULE.verify("example/project", self.root, ["assets/icon.png"], fetch)
        self.assertEqual(result["status"], "not_on_public_main")
        self.assertEqual(result["files"][0]["status"], "different_on_public_main")

    def test_every_named_file_must_match(self):
        (self.root / "README.md").write_bytes(b"current explanation")

        def fetch(url):
            if url.endswith("/branches/main"):
                return {"commit": {"sha": COMMIT}}
            if "/contents/README.md?" in url:
                return self.public_file(b"old explanation", "README.md")
            return self.public_file(b"\x89PNG\r\nexample")

        result = MODULE.verify("example/project", self.root, ["assets/icon.png", "README.md"], fetch)
        self.assertEqual(result["status"], "not_on_public_main")
        self.assertEqual([item["status"] for item in result["files"]], ["match", "different_on_public_main"])

    def test_missing_public_file_does_not_count_as_shipped(self):
        def fetch(url):
            if url.endswith("/branches/main"):
                return {"commit": {"sha": COMMIT}}
            raise HTTPError(url, 404, "Not Found", {}, None)

        result = MODULE.verify("example/project", self.root, ["assets/icon.png"], fetch)
        self.assertEqual(result["status"], "not_on_public_main")
        self.assertEqual(result["files"][0]["status"], "missing_on_public_main")

    def test_main_moving_during_read_is_inconclusive(self):
        reads = 0

        def fetch(url):
            nonlocal reads
            if url.endswith("/branches/main"):
                reads += 1
                return {"commit": {"sha": COMMIT if reads == 1 else NEW_COMMIT}}
            return self.public_file(b"\x89PNG\r\nexample")

        result = MODULE.verify("example/project", self.root, ["assets/icon.png"], fetch)
        self.assertEqual(result["status"], "inconclusive")

    def test_rejects_file_outside_repository_root(self):
        with self.assertRaises(ValueError):
            MODULE.verify("example/project", self.root, ["../outside.png"], lambda url: None)


if __name__ == "__main__":
    unittest.main()
