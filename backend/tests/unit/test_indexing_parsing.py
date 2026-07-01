from __future__ import annotations

from pathlib import Path

import pytest

from app.parsing.index import ParserRegistry


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "indexing"


@pytest.mark.parametrize(
    ("relative_path", "expected_language"),
    [
        ("python/sample.py", "Python"),
        ("javascript/sample.js", "JavaScript"),
        ("typescript/sample.ts", "TypeScript"),
        ("java/Sample.java", "Java"),
        ("csharp/Sample.cs", "C#"),
        ("cpp/sample.cpp", "C++"),
        ("go/sample.go", "Go"),
    ],
)
def test_supported_language_parsers_extract_symbols(
    relative_path: str, expected_language: str
) -> None:
    parser = ParserRegistry()
    path = FIXTURES / relative_path
    parsed = parser.parse(path, path.read_text(encoding="utf-8"))
    assert parsed.language == expected_language
    assert parsed.symbols
    assert parsed.module_name
    assert any(symbol.start_line <= symbol.end_line for symbol in parsed.symbols)


def test_unsupported_language_uses_text_fallback() -> None:
    parser = ParserRegistry()
    path = FIXTURES / "unsupported" / "README.txt"
    parsed = parser.parse(path, path.read_text(encoding="utf-8"))
    assert parsed.fallback_used is True
    assert parsed.symbols
    assert parsed.symbols[0].symbol_type == "text_chunk"
    assert parsed.errors


def test_syntax_error_uses_text_fallback() -> None:
    parser = ParserRegistry()
    path = FIXTURES / "syntax-error" / "broken.py"
    parsed = parser.parse(path, path.read_text(encoding="utf-8"))
    assert parsed.fallback_used is True
    assert parsed.symbols
    assert parsed.errors

