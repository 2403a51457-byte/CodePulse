"""Static Python source analyzer. Repository files are parsed, never executed."""
from __future__ import annotations
import ast
import re
from pathlib import Path

EXCLUDED = {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", "instance", "site-packages"}
MAX_FILE_BYTES = 1_000_000
MAX_PYTHON_FILES = 5000
SECRET_NAME = re.compile(r"(password|passwd|secret|api[_-]?key|access[_-]?token)", re.I)
PLACEHOLDERS = {"", "your_key", "your_api_key", "changeme", "change_me", "none", "null", "xxx", "placeholder", "<your-token>"}


def _finding(rel, line, severity, category, message):
    return {"file": rel, "line": int(line or 1), "severity": severity, "category": category, "message": message}


def _complexity(function):
    branches = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.And, ast.Or, ast.ExceptHandler, ast.comprehension, ast.Match)
    return 1 + sum(isinstance(node, branches) for node in ast.walk(function))


def _unused_import_findings(tree, rel):
    imported = []
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((a.asname or a.name.split(".")[0], node.lineno) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.extend((a.asname or a.name, node.lineno) for a in node.names if a.name != "*")
    for name, line in imported:
        if name not in used and name != "__future__":
            findings.append(_finding(rel, line, "Low", "Unused import", f"Imported name '{name}' appears unused (heuristic check)."))
    return findings


def _security_findings(tree, rel):
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
            if name in {"eval", "exec"}:
                findings.append(_finding(rel, node.lineno, "High", "Dynamic code execution", f"'{name}()' executes dynamically constructed code; avoid it for untrusted input."))
            if name in {"loads", "load"} and isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "pickle":
                findings.append(_finding(rel, node.lineno, "High", "Unsafe deserialization", "Unpickling untrusted data can execute arbitrary code."))
            if name == "load" and isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "yaml":
                findings.append(_finding(rel, node.lineno, "Medium", "Unsafe YAML loading", "Use yaml.safe_load for untrusted YAML input."))
            if name in {"run", "Popen", "call", "check_output"} and isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "subprocess":
                if any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords):
                    findings.append(_finding(rel, node.lineno, "High", "Shell injection risk", "subprocess is called with shell=True; prefer argument lists with shell=False."))
            if name in {"md5", "sha1"} and isinstance(func, ast.Attribute):
                findings.append(_finding(rel, node.lineno, "Medium", "Weak hash algorithm", f"{name.upper()} is unsuitable for security-sensitive hashing; use SHA-256 or stronger."))
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str) and len(value.value) >= 8:
                for target in targets:
                    names = [n.id for n in ast.walk(target) if isinstance(n, ast.Name)]
                    if any(SECRET_NAME.search(n) for n in names) and value.value.lower() not in PLACEHOLDERS:
                        findings.append(_finding(rel, node.lineno, "High", "Possible hardcoded secret", "A credential-like variable is assigned a string literal; load secrets from environment variables."))
                        break
            if isinstance(value, ast.Constant) and value.value is True:
                for target in targets:
                    names = [n.id.lower() for n in ast.walk(target) if isinstance(n, ast.Name)]
                    if any("debug" in n for n in names):
                        findings.append(_finding(rel, node.lineno, "Medium", "Debug mode enabled", "Debug mode appears enabled; disable it in production."))
    return findings


def analyze_python_file(path, root):
    rel = path.relative_to(root).as_posix()
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return [_finding(rel, 1, "Low", "File skipped", f"File exceeds the {MAX_FILE_BYTES // 1000} KB analysis limit.")]
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=rel)
    except SyntaxError as exc:
        return [_finding(rel, exc.lineno, "High", "Syntax error", exc.msg)]
    except OSError as exc:
        return [_finding(rel, 1, "Low", "Read error", f"Could not read file: {exc}" )]
    findings = _unused_import_findings(tree, rel) + _security_findings(tree, rel)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = getattr(node, "end_lineno", node.lineno) - node.lineno + 1
            if length > 50:
                findings.append(_finding(rel, node.lineno, "Medium", "Long function", f"Function '{node.name}' spans {length} lines; consider splitting it."))
            complexity = _complexity(node)
            if complexity > 10:
                findings.append(_finding(rel, node.lineno, "Medium", "High complexity", f"Function '{node.name}' has estimated complexity {complexity}."))
        elif isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append(_finding(rel, node.lineno, "Medium", "Bare exception", "Bare except can hide unexpected errors; catch specific exceptions."))
    for line_no, line in enumerate(source.splitlines(), 1):
        if len(line) > 120:
            findings.append(_finding(rel, line_no, "Low", "Long line", f"Line contains {len(line)} characters."))
        if re.search(r"\b(TODO|FIXME|XXX)\b", line):
            findings.append(_finding(rel, line_no, "Low", "TODO/FIXME", "Unfinished-work marker found; review and resolve it."))
    return findings


def analyze_repository(repo_path):
    root = Path(repo_path).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError("Repository folder does not exist or is not a directory.")
    py_files = []
    for path in root.rglob("*.py"):
        try:
            relative = path.relative_to(root)
            if any(part in EXCLUDED for part in relative.parts) or path.is_symlink():
                continue
            py_files.append(path)
            if len(py_files) >= MAX_PYTHON_FILES:
                break
        except (OSError, ValueError):
            continue
    findings = []
    for path in py_files:
        findings.extend(analyze_python_file(path, root))
    defected = sorted({item["file"] for item in findings})
    return {"files_scanned": len(py_files), "defected_files": len(defected), "scanned_file_names": [p.relative_to(root).as_posix() for p in py_files], "findings": findings}
