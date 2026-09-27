#!/usr/bin/env python3
"""Report brittle Django test contracts without failing CI.

The goal is to surface assertions that are likely to drift during legitimate UI
refactors: exact rendered HTML, page-wide occurrence counts, and long copy
strings. The script deliberately exits zero so it can guide cleanup while the
existing test suite remains authoritative.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "apps"
ASSERT_METHODS = {"assertContains", "assertNotContains", "assertRedirects"}
LONG_COPY_THRESHOLD = 70


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    kind: str
    message: str


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        # f-strings are dynamic, but retaining static fragments is useful for
        # identifying exact markup contracts.
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("{...}")
        return "".join(parts)
    return None


def audit_file(path: Path) -> list[Finding]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [Finding(path, 1, "parse", f"Could not inspect test file: {exc}")]

    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        method = node.func.attr
        if method not in ASSERT_METHODS:
            continue

        line = getattr(node, "lineno", 1)
        value = _literal_string(node.args[1]) if len(node.args) > 1 else None

        if method in {"assertContains", "assertNotContains"}:
            if any(keyword.arg == "count" for keyword in node.keywords):
                findings.append(
                    Finding(
                        path,
                        line,
                        "page-wide-count",
                        "Occurrence-count assertion can become brittle when another component reuses the same class or text. Scope the assertion to the component under test.",
                    )
                )

            if value:
                stripped = value.strip()
                if "<" in stripped and ">" in stripped:
                    findings.append(
                        Finding(
                            path,
                            line,
                            "exact-html",
                            "Exact rendered-HTML assertion is sensitive to harmless markup/accessibility changes. Prefer a stable semantic hook, route, role, or targeted component assertion.",
                        )
                    )
                elif len(stripped) >= LONG_COPY_THRESHOLD:
                    findings.append(
                        Finding(
                            path,
                            line,
                            "long-copy",
                            "Long presentation-copy assertion may drift during copy/design revisions. Keep it only when the wording itself is a product contract.",
                        )
                    )

        if method == "assertRedirects" and value and "settings" in value.lower():
            findings.append(
                Finding(
                    path,
                    line,
                    "route-contract",
                    "Settings redirect contract: verify this assertion uses the canonical shared account-settings architecture rather than a retired role-specific page.",
                )
            )

    return findings


def iter_test_files() -> list[Path]:
    files = set(APPS.glob("**/tests.py"))
    files.update(APPS.glob("**/test_*.py"))
    return sorted(path for path in files if path.is_file())


def main() -> int:
    findings: list[Finding] = []
    for path in iter_test_files():
        findings.extend(audit_file(path))

    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.kind] = counts.get(finding.kind, 0) + 1
        relative = finding.path.relative_to(ROOT)
        message = finding.message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::warning file={relative},line={finding.line},title=Test contract audit ({finding.kind})::{message}")

    print("\nTest contract audit summary")
    print("---------------------------")
    print(f"Files inspected: {len(iter_test_files())}")
    print(f"Potentially brittle assertions: {len(findings)}")
    for kind in sorted(counts):
        print(f"  {kind}: {counts[kind]}")
    print("\nThis audit is advisory; the Django test suite remains the blocking source of truth.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
