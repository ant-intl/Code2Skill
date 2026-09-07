"""Repository discovery and dependency-free source-unit parsing."""

from __future__ import annotations

import ast
import hashlib
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .config import ScanConfig
from .schemas import SourceUnit
from .security import is_probably_binary, is_within, secret_marker


LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
}

GENERIC_FUNCTION_PATTERNS = [
    re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"),
    re.compile(r"\bfunc\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\([^)]*\)[^{]*\{"),
    re.compile(r"\bfn\s+([A-Za-z_]\w*)\s*\([^)]*\)[^{]*\{"),
    re.compile(
        r"(?m)^[ \t]*(?:public|private|protected|static|final|async|export|inline|virtual|const|\s)+"
        r"[A-Za-z_$][\w$:<>,\[\]?*&. ]*\s+([A-Za-z_$][\w$]*)\s*\([^;{}]*\)\s*(?:throws\s+[^\{]+)?\{"
    ),
]

PYTHON_BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try)
if hasattr(ast, "Match"):
    PYTHON_BRANCH_NODES = PYTHON_BRANCH_NODES + (getattr(ast, "Match"),)


def discover_repositories(input_path: str) -> List[Path]:
    root = Path(input_path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Input must be a directory: {root}")
    if (root / ".git").exists():
        return [root]
    children = [
        item
        for item in sorted(root.iterdir())
        if item.is_dir() and not item.name.startswith(".") and (item / ".git").exists()
    ]
    return children or [root]


def scan_repository(
    repo: Path, config: ScanConfig
) -> Tuple[List[SourceUnit], List[Dict[str, str]]]:
    root = repo.resolve()
    units: List[SourceUnit] = []
    skipped: List[Dict[str, str]] = []
    for path in _source_files(root, config):
        relative = str(path.relative_to(root))
        if not config.include_tests and _is_test_path(relative):
            skipped.append({"path": relative, "reason": "test_file"})
            continue
        if not is_within(root, path):
            skipped.append({"path": relative, "reason": "path_escape"})
            continue
        if path.stat().st_size > config.max_file_bytes:
            skipped.append({"path": relative, "reason": "file_too_large"})
            continue
        payload = path.read_bytes()
        if is_probably_binary(payload):
            skipped.append({"path": relative, "reason": "binary_file"})
            continue
        text = payload.decode("utf-8", errors="replace")
        marker = secret_marker(text)
        if marker:
            skipped.append({"path": relative, "reason": f"secret_marker:{marker}"})
            continue
        parsed = _parse_file(root, path, text, config)
        if not parsed:
            skipped.append({"path": relative, "reason": "no_reusable_sized_unit"})
        units.extend(parsed)
    return units, skipped


def _source_files(root: Path, config: ScanConfig) -> Iterable[Path]:
    allowed = set(config.allowed_extensions)
    skip_dirs = set(config.skip_dirs)
    for current, dirs, files in os.walk(root):
        dirs[:] = [
            name for name in dirs if name not in skip_dirs and not name.startswith(".")
        ]
        for name in sorted(files):
            path = Path(current) / name
            if not name.startswith(".") and path.suffix.lower() in allowed:
                yield path


def _parse_file(
    root: Path, path: Path, text: str, config: ScanConfig
) -> List[SourceUnit]:
    if path.suffix.lower() == ".py":
        units = _parse_python(root, path, text, config)
    else:
        units = _parse_brace_language(root, path, text, config)
    if units:
        return units
    stripped = text.strip()
    if len(stripped.splitlines()) < config.min_unit_lines:
        return []
    unit_type = "command_entrypoint" if _looks_like_entrypoint(path, text) else "file"
    return _fit_or_chunk(
        _make_unit(
            root,
            path,
            text,
            path.stem,
            unit_type,
            1,
            max(1, len(text.splitlines())),
            "file scope",
            {"fallback": True},
        ),
        config,
    )


def _parse_python(
    root: Path, path: Path, text: str, config: ScanConfig
) -> List[SourceUnit]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    lines = text.splitlines()
    parent: Dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node

    units: List[SourceUnit] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = int(getattr(node, "lineno", 1))
        end = int(getattr(node, "end_lineno", start))
        if end - start + 1 < config.min_unit_lines:
            continue
        class_name = ""
        current = parent.get(node)
        while current is not None:
            if isinstance(current, ast.ClassDef):
                class_name = current.name
                break
            current = parent.get(current)
        symbol = f"{class_name}.{node.name}" if class_name else node.name
        unit_type = "method" if class_name else "function"
        code = "\n".join(lines[start - 1 : end])
        interface = _python_interface(node)
        metadata = {
            "class_name": class_name,
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "parameters": len(node.args.args) + len(node.args.kwonlyargs),
            "branches": sum(
                isinstance(item, PYTHON_BRANCH_NODES) for item in ast.walk(node)
            ),
            "raises": sum(isinstance(item, ast.Raise) for item in ast.walk(node)),
            "calls": sum(isinstance(item, ast.Call) for item in ast.walk(node)),
        }
        units.extend(
            _fit_or_chunk(
                _make_unit(
                    root, path, code, symbol, unit_type, start, end, interface, metadata
                ),
                config,
            )
        )
    return units


def _python_interface(node: ast.AST) -> str:
    assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    args: List[str] = [arg.arg for arg in node.args.posonlyargs + node.args.args]
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    args.extend(arg.arg for arg in node.args.kwonlyargs)
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    return f"{prefix}{node.name}({', '.join(args)})"


def _parse_brace_language(
    root: Path, path: Path, text: str, config: ScanConfig
) -> List[SourceUnit]:
    matches: List[Tuple[int, int, str]] = []
    for pattern in GENERIC_FUNCTION_PATTERNS:
        for match in pattern.finditer(text):
            open_index = text.find("{", match.start(), match.end())
            if open_index >= 0:
                matches.append((match.start(), open_index, match.group(1)))
    matches.sort()

    seen = set()
    units: List[SourceUnit] = []
    for start_index, open_index, name in matches:
        if (start_index, name) in seen:
            continue
        seen.add((start_index, name))
        end_index = _matching_brace(text, open_index)
        if end_index is None:
            continue
        start_line = text.count("\n", 0, start_index) + 1
        end_line = text.count("\n", 0, end_index) + 1
        if end_line - start_line + 1 < config.min_unit_lines:
            continue
        code = text[start_index : end_index + 1].strip()
        interface = code.split("{", 1)[0].strip().replace("\n", " ")
        metadata = {
            "branches": len(
                re.findall(r"\b(if|for|while|switch|match|try|catch)\b", code)
            ),
            "calls": len(re.findall(r"\b[A-Za-z_$][\w$]*\s*\(", code)),
        }
        units.extend(
            _fit_or_chunk(
                _make_unit(
                    root,
                    path,
                    code,
                    name,
                    "function",
                    start_line,
                    end_line,
                    interface,
                    metadata,
                ),
                config,
            )
        )
    return units


def _matching_brace(text: str, start: int) -> Optional[int]:
    depth = 0
    quote = ""
    escaped = False
    line_comment = False
    block_comment = False
    index = start
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            index += 1
            continue
        if char == "/" and nxt == "/":
            line_comment = True
            index += 2
            continue
        if char == "/" and nxt == "*":
            block_comment = True
            index += 2
            continue
        if char in {'"', "'", "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _fit_or_chunk(unit: SourceUnit, config: ScanConfig) -> List[SourceUnit]:
    if len(unit.code.encode("utf-8")) <= config.max_unit_bytes:
        return [unit]
    lines = unit.code.splitlines()
    chunks: List[SourceUnit] = []
    current: List[str] = []
    current_bytes = 0
    ranges: List[Tuple[int, int, str]] = []
    start = 0
    for index, line in enumerate(lines):
        line_bytes = len((line + "\n").encode("utf-8"))
        if current and current_bytes + line_bytes > config.max_unit_bytes:
            ranges.append((start, index, "\n".join(current)))
            start = index
            current = []
            current_bytes = 0
        current.append(line)
        current_bytes += line_bytes
    if current:
        ranges.append((start, len(lines), "\n".join(current)))
    for index, (start_offset, end_offset, code) in enumerate(ranges, start=1):
        metadata = dict(unit.parser_metadata)
        metadata.update(
            {
                "chunked_from": unit.unit_type,
                "parent_symbol": unit.symbol,
                "chunk_index": index,
                "chunk_count": len(ranges),
            }
        )
        chunks.append(
            _make_unit_from_values(
                repo_name=unit.repo_name,
                repo_path=unit.repo_path,
                relative_path=unit.relative_path,
                language=unit.language,
                symbol=f"{unit.symbol}::chunk_{index}_of_{len(ranges)}",
                unit_type=f"{unit.unit_type}_chunk",
                line_start=unit.line_start + start_offset,
                line_end=unit.line_start + end_offset - 1,
                interface=f"{unit.interface} [chunk {index}/{len(ranges)}]",
                code=code,
                parser_metadata=metadata,
            )
        )
    return chunks


def _make_unit(
    root: Path,
    path: Path,
    code: str,
    symbol: str,
    unit_type: str,
    line_start: int,
    line_end: int,
    interface: str,
    metadata: Dict[str, object],
) -> SourceUnit:
    return _make_unit_from_values(
        repo_name=root.name,
        repo_path=str(root),
        relative_path=str(path.relative_to(root)),
        language=LANGUAGES.get(path.suffix.lower(), path.suffix.lstrip(".") or "text"),
        symbol=symbol,
        unit_type=unit_type,
        line_start=line_start,
        line_end=line_end,
        interface=interface,
        code=code,
        parser_metadata=dict(metadata),
    )


def _make_unit_from_values(**payload: object) -> SourceUnit:
    seed = "|".join(
        str(payload[key])
        for key in (
            "repo_name",
            "relative_path",
            "symbol",
            "line_start",
            "line_end",
            "code",
        )
    )
    payload["data_id"] = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:20]
    return SourceUnit(**payload)  # type: ignore[arg-type]


def _looks_like_entrypoint(path: Path, text: str) -> bool:
    name = path.name.lower()
    return (
        name in {"main.py", "main.go", "main.rs", "cli.py", "index.js", "index.ts"}
        or '__name__ == "__main__"' in text
        or "public static void main" in text
    )


def _is_test_path(relative: str) -> bool:
    normalized = "/" + relative.replace("\\", "/").lower()
    name = normalized.rsplit("/", 1)[-1]
    return (
        "/tests/" in normalized
        or "/test/" in normalized
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith((".spec.ts", ".spec.js", ".test.ts", ".test.js"))
    )
