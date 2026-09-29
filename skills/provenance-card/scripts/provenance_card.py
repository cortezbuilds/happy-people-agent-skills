#!/usr/bin/env python3
"""Build and verify a deterministic, offline provenance card package."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET


DOMAIN = b"provenance-card/1\0"
SCHEMA = "provenance-card/1"
CLASSES = {
    "source": ("SOURCE", "#75B7FF"),
    "observed": ("OBSERVED", "#69DEB4"),
    "decision": ("DECISION", "#D1A9FF"),
    "inference": ("INFERENCE", "#FFD08A"),
    "unknown": ("UNKNOWN", "#BCC9D7"),
}
STAGES = ("local", "checked_main", "release")
STATES = {"verified", "proposed", "unknown"}
KINDS = {"text", "image", "audio", "transcript", "other"}
PINS = {"immutable", "mutable", "local"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
UTC_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$"
)


def fail(message: str) -> None:
    raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def no_float(value: str) -> None:
    fail(f"floating point or non-finite JSON value is not allowed: {value}")


def load_json(path: Path) -> dict:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_keys,
        parse_float=no_float,
        parse_constant=no_float,
    )
    if not isinstance(value, dict):
        fail(f"{path} must contain a JSON object")
    return value


def canonical_subset(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or not key.isascii():
                fail("JSON object keys must be ASCII strings")
            canonical_subset(child)
    elif isinstance(value, list):
        for child in value:
            canonical_subset(child)
    elif isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            fail("all strings must be NFC normalized")
    elif value is None or isinstance(value, (bool, int)):
        return
    else:
        fail(f"unsupported JSON value: {type(value).__name__}")


def canonical_bytes(value: dict) -> bytes:
    canonical_subset(value)
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def string(value: object, name: str, maximum: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (not allow_empty and not value.strip()):
        fail(f"{name} must be a nonempty string of at most {maximum} characters")
    if "\n" in value or "\r" in value:
        fail(f"{name} must be one line")
    return value


def identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        fail(f"{name} must be a short ASCII identifier")
    return value


def exact_keys(value: object, required: set[str], optional: set[str], name: str) -> dict:
    if not isinstance(value, dict):
        fail(f"{name} must be an object")
    missing = required - value.keys()
    extra = value.keys() - required - optional
    if missing or extra:
        fail(f"{name} fields: missing={sorted(missing)}, extra={sorted(extra)}")
    return value


def check_sha(value: object, name: str) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        fail(f"{name} must be a lowercase 64-character SHA-256 hex digest")
    return value


def timestamp(value: object, name: str) -> str:
    value = string(value, name, 40)
    if not UTC_DATETIME.fullmatch(value):
        fail(f"{name} must use an ISO 8601 UTC date-time with seconds ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        fail(f"{name} must be a valid ISO 8601 UTC timestamp")
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        fail(f"{name} must be a UTC-aware date-time")
    return value


def check_ids(value: object, name: str, known: set[str]) -> list[str]:
    if not isinstance(value, list):
        fail(f"{name} must be an array")
    ids = [identifier(item, name) for item in value]
    if len(ids) != len(set(ids)) or any(item not in known for item in ids):
        fail(f"{name} contains duplicate or unknown IDs")
    return ids


def validate(manifest: dict) -> None:
    canonical_subset(manifest)
    exact_keys(
        manifest,
        {"schema", "title", "summary", "as_of", "claims", "evidence", "inputs", "stages"},
        {"similarity_candidates"},
        "manifest",
    )
    if manifest["schema"] != SCHEMA:
        fail(f"schema must be {SCHEMA}")
    string(manifest["title"], "title", 70)
    string(manifest["summary"], "summary", 180)
    timestamp(manifest["as_of"], "as_of")
    if not isinstance(manifest["inputs"], list) or len(manifest["inputs"]) > 40:
        fail("inputs must be an array with at most 40 entries")
    input_ids = set()
    for item in manifest["inputs"]:
        exact_keys(item, {"id", "kind", "label", "sha256"}, {"derived_from"}, "input")
        name = identifier(item["id"], "input.id")
        if name in input_ids:
            fail("duplicate input ID")
        if "derived_from" in item:
            parent = identifier(item["derived_from"], "input.derived_from")
            if parent not in input_ids:
                fail("input.derived_from must name an earlier input")
        input_ids.add(name)
        if item["kind"] not in KINDS:
            fail(f"invalid input kind: {item['kind']}")
        string(item["label"], "input.label", 100)
        check_sha(item["sha256"], "input.sha256")
    if not isinstance(manifest["evidence"], list) or len(manifest["evidence"]) > 40:
        fail("evidence must be an array with at most 40 entries")
    evidence_ids = set()
    for item in manifest["evidence"]:
        exact_keys(item, {"id", "label", "pin", "url", "note"}, {"sha256", "observed_at"}, "evidence")
        name = identifier(item["id"], "evidence.id")
        if name in evidence_ids:
            fail("duplicate evidence ID")
        evidence_ids.add(name)
        string(item["label"], "evidence.label", 100)
        string(item["note"], "evidence.note", 200, allow_empty=True)
        if item["pin"] not in PINS:
            fail("evidence.pin must be immutable, mutable, or local")
        if item["pin"] == "local":
            if item["url"] is not None:
                fail("local evidence must have a null URL")
            check_sha(item.get("sha256"), "local evidence.sha256")
        else:
            url = string(item["url"], "evidence.url", 500)
            parsed = urlparse(url)
            if (
                parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password
                or re.search(r"[\s<>()\\]", url)
            ):
                fail("public evidence URLs must be HTTPS with a host and no credentials")
            hostname = parsed.hostname or ""
            github_alias = unquote(hostname).rstrip(".") in {"github.com", "www.github.com"}
            if github_alias and hostname != "github.com":
                fail("GitHub evidence must use canonical github.com host")
            decoded_path = parsed.path
            for _ in range(8):
                if any(piece in {".", ".."} for piece in decoded_path.split("/")):
                    fail("public evidence URL must not contain dot path segments")
                next_path = unquote(decoded_path)
                if next_path == decoded_path:
                    break
                decoded_path = next_path
            else:
                fail("public evidence URL has excessive nested percent encoding")
            if item["pin"] == "immutable" and hostname == "github.com":
                pieces = decoded_path.strip("/").split("/")
                commit_ref = (
                    len(pieces) >= 4
                    and pieces[2] in {"blob", "tree", "commit"}
                    and re.fullmatch(r"[0-9a-f]{40}", pieces[3]) is not None
                )
                if not commit_ref:
                    fail("immutable GitHub evidence must use a full commit SHA in its URL")
            if "sha256" in item:
                check_sha(item["sha256"], "evidence.sha256")
        if "observed_at" in item:
            timestamp(item["observed_at"], "evidence.observed_at")
    if not isinstance(manifest["claims"], list) or not 1 <= len(manifest["claims"]) <= 12:
        fail("claims must contain 1 to 12 entries")
    claim_ids = set()
    for item in manifest["claims"]:
        exact_keys(item, {"id", "class", "text", "evidence_ids", "limit"}, set(), "claim")
        name = identifier(item["id"], "claim.id")
        if name in claim_ids:
            fail("duplicate claim ID")
        claim_ids.add(name)
        if item["class"] not in CLASSES:
            fail(f"invalid claim class: {item['class']}")
        string(item["text"], "claim.text", 200)
        string(item["limit"], "claim.limit", 180)
        refs = check_ids(item["evidence_ids"], "claim.evidence_ids", evidence_ids)
        if item["class"] != "unknown" and not refs:
            fail(f"{name} needs at least one evidence reference")
    exact_keys(manifest["stages"], set(STAGES), set(), "stages")
    for stage in STAGES:
        item = exact_keys(manifest["stages"][stage], {"state", "evidence_ids"}, set(), stage)
        if item["state"] not in STATES:
            fail(f"invalid {stage} state")
        refs = check_ids(item["evidence_ids"], f"{stage}.evidence_ids", evidence_ids)
        if item["state"] == "verified" and not refs:
            fail(f"verified {stage} requires evidence")
        if item["state"] == "verified" and stage == "checked_main":
            found = [source for source in manifest["evidence"]
                     if source["id"] in refs and source["pin"] == "immutable"
                     and source["url"] is not None]
            if not found:
                fail("verified checked_main requires a public immutable locator")
        if item["state"] == "verified" and stage == "release":
            found = [source for source in manifest["evidence"]
                     if source["id"] in refs and source["url"] is not None
                     and "observed_at" in source]
            if not found:
                fail("verified release requires a public URL with observed_at")
    candidates = manifest.get("similarity_candidates", [])
    if not isinstance(candidates, list) or len(candidates) > 20:
        fail("similarity_candidates must be an array with at most 20 entries")
    candidate_ids = set()
    for item in candidates:
        exact_keys(
            item,
            {"id", "input_id", "algorithm", "version", "candidate", "score_text"},
            set(),
            "similarity candidate",
        )
        name = identifier(item["id"], "similarity candidate.id")
        if name in candidate_ids:
            fail("duplicate similarity candidate ID")
        candidate_ids.add(name)
        if item["input_id"] not in input_ids:
            fail("similarity candidate refers to unknown input")
        for field in ("algorithm", "version", "candidate", "score_text"):
            string(item[field], f"similarity candidate.{field}", 120)


def manifest_id(manifest: dict) -> str:
    return digest(DOMAIN + canonical_bytes(manifest))


def glyph_milli_em(char: str) -> int:
    """Conservative advance budget for the SVG's sans-serif fonts."""
    if char in {"\u200c", "\u200d"}:
        return 0
    if unicodedata.combining(char):
        # A standalone combining mark can display a dotted-circle glyph.
        return 1000
    if char == " ":
        return 450
    if char in "W":
        return 1150
    if char in "Mm@%":
        return 1100
    if char == "w":
        return 1000
    if char in "ilI!|.,:;'`":
        return 600
    if char.isascii():
        if char.isupper():
            return 950
        if char.isdigit():
            return 800
        return 850 if char.islower() else 950
    # DejaVu Sans Bold's widest printable mapped glyph is about 2.017 em
    # (U+1676). Reserve 2.25 em for other non-ASCII symbols, including U+2031.
    # Common CJK letters use square fallback glyphs; keep them near one em.
    # Other fallback fonts and emoji still require a visual check at phone width.
    if (unicodedata.east_asian_width(char) in {"F", "W"}
            and unicodedata.category(char).startswith(("L", "N"))):
        return 1250
    return 2250


def fits_pixels(value: str, size: int, width_px: int) -> bool:
    return sum(glyph_milli_em(char) for char in value) * size <= width_px * 1000


def wrap(value: str, width_px: int, size: int) -> list[str]:
    """Wrap to a conservative pixel budget, including broad ASCII glyphs."""
    lines: list[str] = []
    current = ""
    for word in " ".join(value.split()).split(" "):
        if current and fits_pixels(current + " " + word, size, width_px):
            current += " " + word
            continue
        if current:
            lines.append(current)
            current = ""
        piece = ""
        for char in word:
            if piece and not fits_pixels(piece + char, size, width_px):
                lines.append(piece)
                piece = ""
            piece += char
        current = piece
    if current:
        lines.append(current)
    return lines or [""]


def shorten_pixels(value: str, width_px: int, size: int) -> str:
    value = " ".join(value.split())
    if fits_pixels(value, size, width_px):
        return value
    result = ""
    for char in value:
        if not fits_pixels(result + char + "…", size, width_px):
            break
        result += char
    return result.rstrip() + "…"


def svg_text(x: int, y: int, value: str, *, size: int = 14, color: str = "#E7EFF9",
             weight: int = 400, family: str = "DejaVu Sans, sans-serif") -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-family="{family}" '
        f'font-size="{size}" font-weight="{weight}">{html.escape(value)}</text>'
    )


def render_svg(manifest: dict, record_id: str) -> bytes:
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="360" height="1" viewBox="0 0 360 1" '
        'role="img" aria-labelledby="card-title card-desc">',
        '<title id="card-title">Provenance card: ' + html.escape(manifest["title"]) + '</title>',
        '<desc id="card-desc">A visual index of evidence classes and deployment states. '
        'Use sources.md for accessible deep links. An unsigned local receipt does not prove execution.</desc>',
        '<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#081421"/>'
        '<stop offset="1" stop-color="#13283B"/></linearGradient></defs>',
    ]
    y = 0
    out.append('<rect width="360" height="100%" fill="url(#bg)"/>')
    out.append('<path d="M0 12 Q135 57 360 2" stroke="#386C88" stroke-width="1" opacity=".6" fill="none"/>')
    out.append(svg_text(22, 40, "PROVENANCE / 01", size=11, color="#72D9C5", weight=700))
    y = 72
    for line in wrap(manifest["title"], 316, 22):
        out.append(svg_text(22, y, line, size=22, weight=700))
        y += 29
    y += 10
    for line in wrap(manifest["summary"], 316, 13):
        out.append(svg_text(22, y, line, size=13, color="#C3D1E1"))
        y += 20
    y += 13
    out.append(svg_text(22, y, f"AS OF  {manifest['as_of']}", size=10, color="#95AFC3", weight=700))
    y += 25
    out.append('<path d="M22 ' + str(y) + ' H338" stroke="#426377" stroke-width="1"/>')
    y += 24
    evidence = {item["id"]: item for item in manifest["evidence"]}
    for claim in manifest["claims"]:
        label, color = CLASSES[claim["class"]]
        text_lines = wrap(claim["text"], 296, 14)
        limit_lines = wrap(claim["limit"], 296, 11)
        refs = claim["evidence_ids"]
        height = 61 + 21 * len(text_lines) + 17 * len(limit_lines) + 20 * len(refs)
        out.append(f'<rect x="16" y="{y}" width="328" height="{height}" rx="15" '
                   'fill="#152C40" stroke="#36546B"/>')
        out.append(f'<rect x="16" y="{y}" width="4" height="{height}" rx="2" fill="{color}"/>')
        out.append(svg_text(32, y + 29, f"{label}  /  {claim['id']}", size=11, color=color, weight=700))
        cursor = y + 54
        for line in text_lines:
            out.append(svg_text(32, cursor, line, size=14, weight=600))
            cursor += 21
        cursor += 1
        for line in limit_lines:
            out.append(svg_text(32, cursor, line, size=11, color="#AABDD0"))
            cursor += 17
        for ref in refs:
            source = evidence[ref]
            cursor += 3
            citation = f"↗ {ref}  {source['label']}"
            citation = shorten_pixels(citation, 296, 11)
            if source["url"]:
                out.append(f'<a href="{html.escape(source["url"], quote=True)}" '
                           f'aria-label="{html.escape(source["label"], quote=True)}">')
                out.append(svg_text(32, cursor, citation, size=11, color="#9ED1FF"))
                out.append("</a>")
            else:
                out.append(svg_text(32, cursor,
                                    shorten_pixels(f"{ref}  local digest in sources.md", 296, 11),
                                    size=11, color="#B5C7D8"))
            cursor += 17
        y += height + 12
    y += 14
    out.append(svg_text(22, y, "DEPLOYMENT STATES", size=11, color="#72D9C5", weight=700))
    y += 20
    labels = {"local": "LOCAL", "checked_main": "CHECKED MAIN", "release": "RELEASE"}
    for stage in STAGES:
        entry = manifest["stages"][stage]
        color = "#69DEB4" if entry["state"] == "verified" else (
            "#FFD08A" if entry["state"] == "proposed" else "#BCC9D7")
        out.append(svg_text(23, y, f"{labels[stage]}  ·  {entry['state'].upper()}",
                            size=13, color=color, weight=700))
        y += 20
        for ref in entry["evidence_ids"]:
            source = evidence[ref]
            citation = shorten_pixels(f"↗ {ref}  {source['label']}", 315, 10)
            if source["url"]:
                out.append(f'<a href="{html.escape(source["url"], quote=True)}" '
                           f'aria-label="{html.escape(source["label"], quote=True)}">')
                out.append(svg_text(23, y, citation, size=10, color="#9ED1FF"))
                out.append("</a>")
            else:
                out.append(svg_text(23, y,
                                    shorten_pixels(f"{ref}  local digest in sources.md", 315, 10),
                                    size=10, color="#B5C7D8"))
            y += 15
        y += 3
    y += 11
    out.append('<path d="M22 ' + str(y) + ' H338" stroke="#426377" stroke-width="1"/>')
    y += 25
    out.append(svg_text(22, y, "RECORD ID  /  SHA-256", size=10, color="#95AFC3", weight=700))
    y += 18
    out.append(svg_text(22, y, record_id[:32], size=10, color="#E5EDF8", family="monospace"))
    y += 16
    out.append(svg_text(22, y, record_id[32:], size=10, color="#E5EDF8", family="monospace"))
    y += 25
    out.append(svg_text(22, y, "Exact inputs: " + str(len(manifest["inputs"])) +
                        "   ·   similarity leads: " +
                        str(len(manifest.get("similarity_candidates", []))),
                        size=10, color="#AABDD0"))
    y += 19
    out.append(svg_text(22, y, "Visual index · unsigned receipt · verify sources",
                        size=10, color="#AABDD0"))
    height = y + 23
    out[0] = out[0].replace('height="1" viewBox="0 0 360 1"',
                            f'height="{height}" viewBox="0 0 360 {height}"')
    out.append("</svg>")
    return ("\n".join(out) + "\n").encode("utf-8")


def md_escape(value: str) -> str:
    safe = html.escape(value, quote=False)
    for char in ("\\", "[", "]", "|", "*", "_"):
        safe = safe.replace(char, "\\" + char)
    return safe


def render_sources(manifest: dict, record_id: str) -> bytes:
    lines = [
        "# " + md_escape(manifest["title"]),
        "",
        md_escape(manifest["summary"]),
        "",
        f"Record ID: {record_id}",
        "",
        "This card is a visual index. Its unsigned receipt checks local file consistency. "
        "It does not prove authorship, skill invocation, complete execution history, or a trusted time.",
        "",
        "## Claims and citations",
        "",
    ]
    evidence = {item["id"]: item for item in manifest["evidence"]}
    for claim in manifest["claims"]:
        lines += [f"### {CLASSES[claim['class']][0]} · {md_escape(claim['id'])}", "",
                  md_escape(claim["text"]), "", "Limit: " + md_escape(claim["limit"]), ""]
        for ref in claim["evidence_ids"]:
            item = evidence[ref]
            label = md_escape(item["label"])
            locator = (f"[{label}]({item['url']})" if item["url"] else
                       f"{label} (local SHA-256: {item['sha256']})")
            lines.append(f"- {ref}: {locator} · {item['pin']}. {md_escape(item['note'])}")
            if "observed_at" in item:
                lines.append(f"  Observed at: {md_escape(item['observed_at'])}")
        lines.append("")
    lines += ["## Evidence registry", "",
              "Every ID used by a claim or deployment stage is listed here, including "
              "evidence cited only by a stage.", ""]
    for item in manifest["evidence"]:
        label = md_escape(item["label"])
        locator = (f"[{label}]({item['url']})" if item["url"] else
                   f"{label} (local SHA-256: {item['sha256']})")
        lines.append(f"- {item['id']}: {locator} · {item['pin']}. {md_escape(item['note'])}")
        if "observed_at" in item:
            lines.append(f"  Observed at: {md_escape(item['observed_at'])}")
    lines.append("")
    lines += ["## Deployment states", "",
              "| Surface | State | Evidence IDs |", "| --- | --- | --- |"]
    for stage in STAGES:
        item = manifest["stages"][stage]
        lines.append(f"| {stage.replace('_', ' ')} | {item['state']} | " +
                     (", ".join(item["evidence_ids"]) or "none") + " |")
    lines += ["", "## Exact input bytes", "",
              "SHA-256 values refer to exact supplied bytes. A transcript is a separate input "
              "and may point to its source recording.", ""]
    for item in manifest["inputs"]:
        relation = f" · derived from {item['derived_from']}" if "derived_from" in item else ""
        lines.append(f"- {item['id']} · {item['kind']} · {md_escape(item['label'])} · "
                     f"SHA-256 {item['sha256']}{relation}")
    lines += ["", "## Similarity leads", "",
              "Optional candidate matches are search leads. Scores are not byte identity, "
              "execution evidence, or proof that a skill ran.", ""]
    for item in manifest.get("similarity_candidates", []):
        lines.append(f"- {item['id']} · input {item['input_id']} · "
                     f"{md_escape(item['algorithm'])} {md_escape(item['version'])} · "
                     f"{md_escape(item['candidate'])} · {md_escape(item['score_text'])}")
    if not manifest.get("similarity_candidates"):
        lines.append("None recorded.")
    lines.append("")
    return ("\n".join(lines)).encode("utf-8")


def file_map(manifest: dict) -> dict[str, bytes]:
    validate(manifest)
    record_id = manifest_id(manifest)
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    svg = render_svg(manifest, record_id)
    ET.fromstring(svg)
    sources = render_sources(manifest, record_id)
    receipt = {
        "schema": "provenance-card-receipt/1",
        "record_id": record_id,
        "files": {
            "manifest.json": digest(manifest_bytes),
            "card.svg": digest(svg),
            "sources.md": digest(sources),
        },
        "status": "unsigned-local-consistency-only",
    }
    receipt_bytes = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()
    return {
        "manifest.json": manifest_bytes,
        "card.svg": svg,
        "sources.md": sources,
        "receipt.json": receipt_bytes,
    }


def check_input_bindings(manifest: dict, bindings: list[str]) -> tuple[int, int]:
    inputs = {item["id"]: item["sha256"] for item in manifest["inputs"]}
    seen: set[str] = set()
    for binding in bindings:
        if "=" not in binding:
            fail("--input must use ID=FILE")
        input_id, filename = binding.split("=", 1)
        if input_id not in inputs or input_id in seen or not filename:
            fail(f"unknown, repeated, or empty input binding: {input_id}")
        seen.add(input_id)
        if digest(Path(filename).read_bytes()) != inputs[input_id]:
            fail(f"exact source bytes differ from manifest SHA-256 for {input_id}")
    return len(seen), len(inputs)


def replace_bytes(path: Path, data: bytes) -> None:
    """Replace an output entry without following symlinks or existing hardlinks."""
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build(manifest_path: Path, output: Path, force: bool, bindings: list[str]) -> None:
    manifest = load_json(manifest_path)
    files = file_map(manifest)
    checked, total = check_input_bindings(manifest, bindings)
    if output.is_symlink():
        fail("output directory must not be a symlink")
    output.mkdir(parents=True, exist_ok=True)
    if not force and any(
        (output / name).exists() or (output / name).is_symlink() for name in files
    ):
        fail("output files exist; choose a new directory or pass --force")
    for name, data in files.items():
        replace_bytes(output / name, data)
    print(f"built {output} · record {manifest_id(manifest)} · checked input bytes {checked}/{total}")


def verify(output: Path, bindings: list[str]) -> None:
    manifest = load_json(output / "manifest.json")
    expected = file_map(manifest)
    checked, total = check_input_bindings(manifest, bindings)
    for name, data in expected.items():
        actual = (output / name).read_bytes()
        if actual != data:
            fail(f"{name} differs from deterministic output")
    receipt = load_json(output / "receipt.json")
    if receipt["status"] != "unsigned-local-consistency-only":
        fail("receipt status is misleading")
    print(f"verified local consistency · record {receipt['record_id']} · "
          f"checked input bytes {checked}/{total}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    hash_command = commands.add_parser("hash", help="SHA-256 of exact source bytes")
    hash_command.add_argument("file", type=Path)
    build_command = commands.add_parser("build", help="render package from a manifest")
    build_command.add_argument("manifest", type=Path)
    build_command.add_argument("--out", type=Path, required=True)
    build_command.add_argument("--force", action="store_true")
    build_command.add_argument("--input", action="append", default=[], metavar="ID=FILE",
                               help="check actual source bytes against a declared input hash")
    verify_command = commands.add_parser("verify", help="verify a saved package offline")
    verify_command.add_argument("directory", type=Path)
    verify_command.add_argument("--input", action="append", default=[], metavar="ID=FILE",
                                help="recheck actual source bytes against a declared input hash")
    args = parser.parse_args()
    try:
        if args.command == "hash":
            print(digest(args.file.read_bytes()))
        elif args.command == "build":
            build(args.manifest, args.out, args.force, args.input)
        else:
            verify(args.directory, args.input)
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError) as error:
        print(f"provenance-card: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
