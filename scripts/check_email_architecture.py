"""Fail on direct mail transport outside the central adapter. Standard library only."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {"apps/notifications/email_delivery.py"}
MAIL_NAMES = {"send_mail", "send_mass_mail", "mail_admins", "mail_managers",
              "EmailMessage", "EmailMultiAlternatives", "get_connection", "SMTP", "SMTP_SSL"}
MODULES = ("django.core.mail", "smtplib", "aiosmtplib")

def violations(source, filename):
    if filename in ALLOWED:
        return []
    tree = ast.parse(source, filename=filename)
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if any(module == m or module.startswith(m + ".") for m in MODULES):
                # Permit exception imports, not transport constructors or wildcard imports.
                if any(alias.name in MAIL_NAMES or alias.name == "*" or
                       module.startswith("django.core.mail.backends") for alias in node.names):
                    findings.append((node.lineno, "direct mail transport import"))
        elif isinstance(node, ast.Import):
            if any(any(alias.name == m or alias.name.startswith(m + ".") for m in MODULES)
                   for alias in node.names):
                findings.append((node.lineno, "direct mail module import"))
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"send_messages", "sendmail", "send_message"}:
                findings.append((node.lineno, "direct mail transport call"))
    return findings

def scan(root=ROOT):
    findings = []
    for directory in ("apps", "config", "scripts"):
        for path in sorted((root / directory).rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            if any(part in {"tests", "migrations", "__pycache__"} for part in path.parts) or path.name.startswith("test_") or path.name == "tests.py":
                continue
            for line, message in violations(path.read_text(encoding="utf-8-sig"), rel):
                findings.append(f"{rel}:{line}: {message}")
    return findings

if __name__ == "__main__":
    findings = scan()
    for finding in findings:
        print(finding)
    if findings:
        raise SystemExit(1)
    print("Email architecture check passed")
