from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


SUPPORTED_LANGUAGES = {
    ".c": "C",
    ".cpp": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
}


@dataclass(slots=True, frozen=True)
class ParseErrorRecord:
    code: str
    message: str
    line: int | None = None
    column: int | None = None


@dataclass(slots=True, frozen=True)
class ParsedSymbol:
    symbol_type: str
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    signature: str | None = None
    docstring: str | None = None
    parent_qualified_name: str | None = None
    calls: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ParsedFile:
    language: str | None
    module_name: str | None
    package_name: str | None
    imports: tuple[str, ...]
    symbols: tuple[ParsedSymbol, ...]
    errors: tuple[ParseErrorRecord, ...]
    fallback_used: bool = False


class Parser(Protocol):
    language: str

    def parse(self, path: Path, text: str) -> ParsedFile: ...


class PythonParser:
    language = "Python"

    def parse(self, path: Path, text: str) -> ParsedFile:
        module_name = _module_name(path)
        errors: list[ParseErrorRecord] = []
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            return _fallback_parsed_file(path, text, self.language, exc)

        imports: list[str] = []
        symbols: list[ParsedSymbol] = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
                imports.extend(names)
                symbols.append(
                    ParsedSymbol(
                        symbol_type="import",
                        name=", ".join(names),
                        qualified_name=", ".join(names),
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        signature=_line_slice(text, node.lineno, getattr(node, "end_lineno", node.lineno)),
                        metadata={"imports": names},
                    )
                )
            elif isinstance(node, ast.ImportFrom):
                names = [alias.name for alias in node.names]
                module = node.module or ""
                imports.append(module)
                symbols.append(
                    ParsedSymbol(
                        symbol_type="import",
                        name=module,
                        qualified_name=f"{module}:{', '.join(names)}".strip(":"),
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        signature=_line_slice(text, node.lineno, getattr(node, "end_lineno", node.lineno)),
                        metadata={"imports": names, "module": module},
                    )
                )
            elif isinstance(node, ast.ClassDef):
                symbols.extend(_python_class_symbols(text, node, parent=None))
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                symbols.extend(_python_function_symbols(text, node, parent=None))
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                symbols.extend(_python_constant_symbols(text, node, parent=None))

        return ParsedFile(
            language=self.language,
            module_name=module_name,
            package_name=_package_name(path),
            imports=tuple(dict.fromkeys(imports)),
            symbols=tuple(symbols),
            errors=tuple(errors),
        )


class RegexParser:
    def __init__(self, language: str, profile: dict[str, object]) -> None:
        self.language = language
        self._profile = profile

    def parse(self, path: Path, text: str) -> ParsedFile:
        try:
            return self._parse(path, text)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return _fallback_parsed_file(path, text, self.language, exc)

    def _parse(self, path: Path, text: str) -> ParsedFile:
        lines = text.splitlines()
        imports: list[str] = []
        symbols: list[ParsedSymbol] = []
        errors: list[ParseErrorRecord] = []
        i = 0
        while i < len(lines):
            raw_line = lines[i]
            stripped = raw_line.strip()
            if not stripped:
                i += 1
                continue
            import_match = _match_any(stripped, self._profile["imports"])
            if import_match:
                imports.append(import_match.group(1) if import_match.groups() else stripped)
                i += 1
                continue
            symbol_match = _match_any(stripped, self._profile["symbols"])
            if symbol_match is None:
                i += 1
                continue
            symbol_type = symbol_match.group("kind")
            name = symbol_match.group("name")
            start_line = i + 1
            end_line = _brace_end_line(lines, i)
            qualified_name = _qualified_name(path, name, symbol_type)
            signature = _line_slice(text, start_line, end_line)
            docstring = _leading_comment_block(lines, i)
            calls = tuple(sorted(_extract_calls(signature)))
            symbols.append(
                ParsedSymbol(
                    symbol_type=symbol_type,
                    name=name,
                    qualified_name=qualified_name,
                    start_line=start_line,
                    end_line=end_line,
                    signature=signature,
                    docstring=docstring,
                    calls=calls,
                    metadata={"language": self.language},
                )
            )
            i = max(i + 1, end_line)
        return ParsedFile(
            language=self.language,
            module_name=_module_name(path),
            package_name=_package_name(path),
            imports=tuple(dict.fromkeys(imports)),
            symbols=tuple(symbols),
            errors=tuple(errors),
        )


class ParserRegistry:
    def __init__(self) -> None:
        self._python = PythonParser()
        self._parsers: dict[str, Parser] = {
            "Python": self._python,
            "JavaScript": RegexParser(
                "JavaScript",
                {
                    "imports": (
                        re.compile(r"^(?:import\s+.+?from\s+['\"]([^'\"]+)['\"])"),
                        re.compile(r"^(?:import\s+['\"]([^'\"]+)['\"])"),
                        re.compile(r"^(?:const\s+.+?=\s+require\(['\"]([^'\"]+)['\"]\))"),
                    ),
                    "symbols": (
                        re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+(?P<name>[A-Za-z_][$\w]*)"),
                        re.compile(r"^(?:export\s+)?class\s+(?P<name>[A-Za-z_][$\w]*)"),
                        re.compile(r"^(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_][$\w]*)\s*="),
                    ),
                },
            ),
            "TypeScript": RegexParser(
                "TypeScript",
                {
                    "imports": (
                        re.compile(r"^(?:import\s+.+?from\s+['\"]([^'\"]+)['\"])"),
                        re.compile(r"^(?:import\s+['\"]([^'\"]+)['\"])"),
                    ),
                    "symbols": (
                        re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+(?P<name>[A-Za-z_][$\w]*)"),
                        re.compile(r"^(?:export\s+)?class\s+(?P<name>[A-Za-z_][$\w]*)"),
                        re.compile(r"^(?:export\s+)?interface\s+(?P<name>[A-Za-z_][$\w]*)"),
                        re.compile(r"^(?:export\s+)?type\s+(?P<name>[A-Za-z_][$\w]*)\s*="),
                        re.compile(r"^(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_][$\w]*)\s*="),
                    ),
                },
            ),
            "Java": RegexParser(
                "Java",
                {
                    "imports": (re.compile(r"^import\s+([^;]+);"),),
                    "symbols": (
                        re.compile(r"^(?:public|protected|private|static|final|\s)+class\s+(?P<name>[A-Za-z_][$\w]*)"),
                        re.compile(r"^(?:public|protected|private|static|final|\s)+interface\s+(?P<name>[A-Za-z_][$\w]*)"),
                        re.compile(r"^(?:public|protected|private|static|final|\s)+(?:[A-Za-z_][$\w<>\[\], ?]+)\s+(?P<name>[A-Za-z_][$\w]*)\s*\("),
                    ),
                },
            ),
            "C#": RegexParser(
                "C#",
                {
                    "imports": (re.compile(r"^using\s+([^;]+);"),),
                    "symbols": (
                        re.compile(r"^(?:public|private|internal|protected|static|sealed|abstract|\s)+class\s+(?P<name>[A-Za-z_][$\w]*)"),
                        re.compile(r"^(?:public|private|internal|protected|static|sealed|abstract|\s)+interface\s+(?P<name>[A-Za-z_][$\w]*)"),
                        re.compile(r"^(?:public|private|internal|protected|static|sealed|abstract|\s)+(?:[A-Za-z_][$\w<>\[\], ?]+)\s+(?P<name>[A-Za-z_][$\w]*)\s*\("),
                    ),
                },
            ),
            "C++": RegexParser(
                "C++",
                {
                    "imports": (re.compile(r"^#include\s+(.+)$"),),
                    "symbols": (
                        re.compile(r"^(?:class|struct)\s+(?P<name>[A-Za-z_][$\w]*)"),
                        re.compile(r"^(?:inline\s+)?(?:[A-Za-z_][$\w:<>\[\], ?]+)\s+(?P<name>[A-Za-z_][$\w]*)\s*\("),
                    ),
                },
            ),
            "Go": RegexParser(
                "Go",
                {
                    "imports": (re.compile(r"^import\s+(?:\(|['\"])?([^'\")]+)"),),
                    "symbols": (
                        re.compile(r"^type\s+(?P<name>[A-Za-z_][$\w]*)\s+(?:struct|interface)"),
                        re.compile(r"^func\s+(?:\([^)]+\)\s*)?(?P<name>[A-Za-z_][$\w]*)\s*\("),
                        re.compile(r"^const\s+(?P<name>[A-Za-z_][$\w]*)\s*="),
                    ),
                },
            ),
        }

    def parse(self, path: Path, text: str) -> ParsedFile:
        language = SUPPORTED_LANGUAGES.get(path.suffix.casefold())
        if language is None:
            return _fallback_parsed_file(path, text, None, ValueError("unsupported language"))
        parser = self._parsers.get(language)
        if parser is None:
            return _fallback_parsed_file(path, text, language, ValueError("unsupported parser"))
        return parser.parse(path, text)


def _python_class_symbols(
    text: str, node: ast.ClassDef, *, parent: ParsedSymbol | None
) -> list[ParsedSymbol]:
    qualified_name = node.name if parent is None else f"{parent.qualified_name}.{node.name}"
    symbols = [
        ParsedSymbol(
            symbol_type="class",
            name=node.name,
            qualified_name=qualified_name,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno),
            signature=_python_signature(node),
            docstring=ast.get_docstring(node, clean=False),
            parent_qualified_name=parent.qualified_name if parent else None,
            calls=_python_calls(node),
            metadata={
                "bases": [_safe_unparse(base) for base in node.bases],
                "keywords": [keyword.arg for keyword in node.keywords if keyword.arg],
            },
        )
    ]
    for child in node.body:
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            symbols.extend(_python_function_symbols(text, child, parent=symbols[0]))
        elif isinstance(child, ast.Assign | ast.AnnAssign):
            symbols.extend(_python_constant_symbols(text, child, parent=symbols[0]))
    return symbols


def _python_function_symbols(
    text: str, node: ast.FunctionDef | ast.AsyncFunctionDef, *, parent: ParsedSymbol | None
) -> list[ParsedSymbol]:
    kind = "method" if parent and parent.symbol_type == "class" else "function"
    if node.name == "__init__":
        kind = "constructor"
    if isinstance(node, ast.AsyncFunctionDef):
        kind = f"async_{kind}"
    qualified_name = node.name if parent is None else f"{parent.qualified_name}.{node.name}"
    return [
        ParsedSymbol(
            symbol_type=kind,
            name=node.name,
            qualified_name=qualified_name,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno),
            signature=_python_signature(node),
            docstring=ast.get_docstring(node, clean=False),
            parent_qualified_name=parent.qualified_name if parent else None,
            calls=_python_calls(node),
            metadata={
                "returns": _safe_unparse(node.returns) if node.returns else None,
                "decorators": [_safe_unparse(item) for item in node.decorator_list],
            },
        )
    ]


def _python_constant_symbols(
    text: str, node: ast.Assign | ast.AnnAssign, *, parent: ParsedSymbol | None
) -> list[ParsedSymbol]:
    start_line = node.lineno
    end_line = getattr(node, "end_lineno", node.lineno)
    targets: list[str] = []
    if isinstance(node, ast.Assign):
        for target in node.targets:
            targets.extend(_assignment_names(target))
    else:
        targets.extend(_assignment_names(node.target))
    if not targets:
        return []
    symbols: list[ParsedSymbol] = []
    for target in targets:
        kind = "constant" if target.isupper() else "type_definition" if "type" in target.lower() else "assignment"
        qualified_name = target if parent is None else f"{parent.qualified_name}.{target}"
        symbols.append(
            ParsedSymbol(
                symbol_type=kind,
                name=target,
                qualified_name=qualified_name,
                start_line=start_line,
                end_line=end_line,
                signature=_line_slice(text, start_line, end_line),
                parent_qualified_name=parent.qualified_name if parent else None,
                metadata={"annotation": _safe_unparse(node.annotation) if isinstance(node, ast.AnnAssign) and node.annotation else None},
            )
        )
    return symbols


def _python_signature(node: ast.AST) -> str | None:
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - ast.unparse may fail on invalid nodes
        return None


def _python_calls(node: ast.AST) -> tuple[str, ...]:
    calls: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = _call_name(child.func)
            if name:
                calls.add(name)
    return tuple(sorted(calls))


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _call_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return None


def _assignment_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Tuple):
        names: list[str] = []
        for item in node.elts:
            names.extend(_assignment_names(item))
        return names
    return []


def _safe_unparse(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - defensive
        return None


def _match_any(value: str, patterns: Iterable[re.Pattern[str]]) -> re.Match[str] | None:
    for pattern in patterns:
        match = pattern.match(value)
        if match is not None:
            return match
    return None


def _brace_end_line(lines: list[str], start_index: int) -> int:
    depth = 0
    seen_open = False
    for index in range(start_index, len(lines)):
        line = lines[index]
        depth += line.count("{") - line.count("}")
        if "{" in line:
            seen_open = True
        if seen_open and depth <= 0:
            return index + 1
        if not seen_open and line.rstrip().endswith(";"):
            return index + 1
    return len(lines) or 1


def _leading_comment_block(lines: list[str], index: int) -> str | None:
    comment_lines: list[str] = []
    cursor = index - 1
    while cursor >= 0:
        stripped = lines[cursor].strip()
        if not stripped:
            if comment_lines:
                break
            cursor -= 1
            continue
        if stripped.startswith(("//", "#", "/*", "*", "*/")):
            comment_lines.append(stripped)
            cursor -= 1
            continue
        break
    if not comment_lines:
        return None
    return "\n".join(reversed(comment_lines))


def _qualified_name(path: Path, name: str, symbol_type: str) -> str:
    module = _module_name(path) or path.stem
    if symbol_type in {"class", "interface", "struct"}:
        return f"{module}.{name}"
    return f"{module}.{name}"


def _module_name(path: Path) -> str | None:
    stem = path.with_suffix("").as_posix().replace("/", ".")
    return stem or None


def _package_name(path: Path) -> str | None:
    parents = list(path.parent.parts)
    return ".".join(parents) if parents else None


def _line_slice(text: str, start_line: int, end_line: int) -> str:
    lines = text.splitlines()
    start = max(start_line - 1, 0)
    end = min(end_line, len(lines))
    return "\n".join(lines[start:end])


def _fallback_parsed_file(
    path: Path, text: str, language: str | None, exc: Exception
) -> ParsedFile:
    lines = text.splitlines()
    chunk_size = 120
    symbols: list[ParsedSymbol] = []
    for start in range(1, len(lines) + 1, chunk_size):
        end = min(start + chunk_size - 1, len(lines))
        symbols.append(
            ParsedSymbol(
                symbol_type="text_chunk",
                name=f"{path.stem}:{start}-{end}",
                qualified_name=f"{_module_name(path) or path.stem}:{start}-{end}",
                start_line=start,
                end_line=end,
                signature=_line_slice(text, start, end),
                metadata={"fallback": True},
            )
        )
    if not symbols:
        symbols.append(
            ParsedSymbol(
                symbol_type="text_chunk",
                name=path.stem,
                qualified_name=_module_name(path) or path.stem,
                start_line=1,
                end_line=1,
                signature="",
                metadata={"fallback": True},
            )
        )
    return ParsedFile(
        language=language,
        module_name=_module_name(path),
        package_name=_package_name(path),
        imports=(),
        symbols=tuple(symbols),
        errors=(
            ParseErrorRecord(
                code="parse_fallback",
                message=str(exc),
            ),
        ),
        fallback_used=True,
    )

