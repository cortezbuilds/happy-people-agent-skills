#!/usr/bin/env python3
"""Verify exact local files against unauthenticated GitHub public main reads."""

import argparse
import base64
import binascii
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


API_ROOT = "https://api.github.com"
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


def fetch_json(url):
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "release-evidence-public-main-check",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def public_main_sha(repo, fetch):
    branch = fetch(f"{API_ROOT}/repos/{repo}/branches/main")
    commit = branch.get("commit") if isinstance(branch, dict) else None
    sha = commit.get("sha") if isinstance(commit, dict) else None
    if not isinstance(sha, str) or not SHA_PATTERN.fullmatch(sha):
        raise ValueError("Public main response did not contain a valid commit SHA")
    return sha


def verify(repo, root, paths, fetch=fetch_json):
    if not REPO_PATTERN.fullmatch(repo):
        raise ValueError("--repo must be OWNER/REPO")
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("--root must be a directory")
    if not paths:
        raise ValueError("Specify at least one --file")

    checked = []
    for relative in paths:
        path = Path(relative)
        if path.is_absolute() or not relative or any(part in (".", "..") for part in path.parts):
            raise ValueError(f"Invalid repository-relative file path: {relative!r}")
        local = root / path
        if not local.is_file() or local.is_symlink() or not local.resolve().is_relative_to(root):
            raise ValueError(f"Local file is missing, linked, or outside root: {relative!r}")
        checked.append((relative, local))

    commit = public_main_sha(repo, fetch)
    files = []
    for relative, local in checked:
        url = f"{API_ROOT}/repos/{repo}/contents/{quote(relative, safe='/')}?ref={commit}"
        try:
            item = fetch(url)
        except HTTPError as error:
            if error.code == 404:
                files.append({"path": relative, "status": "missing_on_public_main"})
                continue
            raise

        if not isinstance(item, dict) or item.get("type") != "file" or item.get("path") != relative:
            raise ValueError(f"Unexpected public file response for {relative!r}")
        if item.get("encoding") != "base64" or not isinstance(item.get("content"), str):
            raise ValueError(f"Public file bytes unavailable for {relative!r}")
        try:
            public_bytes = base64.b64decode(item["content"].replace("\n", ""), validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError(f"Invalid public file encoding for {relative!r}") from error
        local_bytes = local.read_bytes()
        files.append(
            {
                "path": relative,
                "status": "match" if local_bytes == public_bytes else "different_on_public_main",
                "local_sha256": hashlib.sha256(local_bytes).hexdigest(),
                "public_sha256": hashlib.sha256(public_bytes).hexdigest(),
            }
        )

    if public_main_sha(repo, fetch) != commit:
        return {
            "status": "inconclusive",
            "reason": "Public main moved during verification; rerun the check",
            "repo": repo,
            "branch": "main",
            "files": files,
        }
    return {
        "status": "verified_public_main" if all(item["status"] == "match" for item in files) else "not_on_public_main",
        "repo": repo,
        "branch": "main",
        "public_main_commit": commit,
        "files": files,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Public GitHub OWNER/REPO")
    parser.add_argument("--root", required=True, help="Local repository root")
    parser.add_argument("--file", action="append", dest="files", required=True, help="Repository-relative file; repeat as needed")
    args = parser.parse_args(argv)
    try:
        result = verify(args.repo, args.root, args.files)
    except (HTTPError, URLError, OSError, ValueError, json.JSONDecodeError) as error:
        result = {"status": "inconclusive", "reason": str(error), "repo": args.repo, "branch": "main"}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "verified_public_main" else 2 if result["status"] == "inconclusive" else 1


if __name__ == "__main__":
    sys.exit(main())
