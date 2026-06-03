from __future__ import annotations

from pathlib import Path

import pytest

from context.repo_map import RepoMap, _extract_symbols, _get_language


def _assert_symbol(
    symbols,
    *,
    name: str,
    kind: str,
    language: str,
    line: int | None = None,
    file_name: str | None = None,
):
    symbol = next((s for s in symbols if s.name == name and s.kind == kind), None)
    assert symbol is not None, f"missing {kind} {name}: {symbols}"
    assert symbol.language == language
    if line is not None:
        assert symbol.line == line
    if file_name is not None:
        assert symbol.file == Path(file_name)


@pytest.mark.parametrize(
    ("file_name", "code", "expected"),
    [
        (
            "sample.py",
            "def top_level():\n    pass\n\nclass App:\n    def run(self):\n        pass\n",
            [("top_level", "function", "python", 1), ("App", "class", "python", 4), ("run", "method", "python", 5)],
        ),
        (
            "sample.js",
            "function topLevel() {\n  return 1;\n}\n\nclass Widget {\n  render() {\n    return 2;\n  }\n}\n",
            [("topLevel", "function", "javascript", 1), ("Widget", "class", "javascript", 5), ("render", "method", "javascript", 6)],
        ),
        (
            "sample.ts",
            "function topLevel(): number {\n  return 1;\n}\n\ninterface User {\n  id: string;\n}\n\nclass Service {\n  run(task: string): void {}\n}\n",
            [("topLevel", "function", "typescript", 1), ("User", "interface", "typescript", 5), ("Service", "class", "typescript", 9), ("run", "method", "typescript", 10)],
        ),
        (
            "sample.go",
            "package main\n\ntype Service struct{}\n\nfunc TopLevel() {}\n\nfunc (s Service) Run() {}\n",
            [("Service", "class", "go", 3), ("TopLevel", "function", "go", 5), ("Run", "method", "go", 7)],
        ),
        (
            "sample.rs",
            "pub struct Service;\n\nfn top_level() {}\n\nimpl Service {\n    fn run(&self) {}\n}\n",
            [("Service", "class", "rust", 1), ("top_level", "function", "rust", 3), ("run", "method", "rust", 6)],
        ),
        (
            "Sample.java",
            "public class Sample {\n    public void run() {}\n}\n",
            [("Sample", "class", "java", 1), ("run", "method", "java", 2)],
        ),
        (
            "sample.c",
            "int top_level(int value) {\n    return value;\n}\n",
            [("top_level", "function", "c", 1)],
        ),
        (
            "sample.cpp",
            "class Widget {\npublic:\n    void render();\n};\n\nvoid Widget::render() {}\nint top_level() { return 1; }\n",
            [("Widget", "class", "cpp", 1), ("render", "method", "cpp", 3), ("top_level", "function", "cpp", 7)],
        ),
        (
            "sample.rb",
            "class App\n  def run\n  end\nend\n",
            [("App", "class", "ruby", 1), ("run", "method", "ruby", 2)],
        ),
    ],
)
def test_extract_symbols_multilanguage(file_name, code, expected):
    ext = Path(file_name).suffix.lower()
    symbols = _extract_symbols(code, Path(file_name), ext)
    assert symbols
    for name, kind, language, line in expected:
        _assert_symbol(symbols, name=name, kind=kind, language=language, line=line, file_name=file_name)


@pytest.mark.parametrize(
    ("file_name", "code"),
    [
        ("sample.py", "def alpha():\n    pass\n"),
        ("sample.js", "function beta() {}\n"),
        ("sample.ts", "interface User {}\n"),
        ("sample.go", "func Gamma() {}\n"),
        ("sample.rs", "fn delta() {}\n"),
        ("Sample.java", "public class Sample {}\n"),
        ("sample.c", "int echo(void) { return 0; }\n"),
        ("sample.cpp", "class Widget {};\n"),
        ("sample.rb", "class App\nend\n"),
    ],
)
def test_repo_map_build_contains_symbols(tmp_path, file_name, code):
    path = tmp_path / file_name
    path.write_text(code, encoding="utf-8")
    repo_map = RepoMap(tmp_path).build(budget=10_000)
    assert file_name in repo_map


@pytest.mark.parametrize(
    ("ext", "code", "expected_names"),
    [
        (".js", "function beta() {}\n", {"beta"}),
        (".ts", "interface User {}\n", {"User"}),
        (".go", "type Service struct{}\nfunc Run() {}\n", {"Service", "Run"}),
        (".rs", "pub struct Service;\nfn run() {}\n", {"Service", "run"}),
        (".java", "public class Sample {}\n", {"Sample"}),
        (".c", "int echo(void) { return 0; }\n", {"echo"}),
        (".cpp", "class Widget {};\n", {"Widget"}),
        (".rb", "class App\nend\n", {"App"}),
    ],
)
def test_fallback_path_still_extracts_symbols(monkeypatch, ext, code, expected_names):
    monkeypatch.setattr("context.repo_map._get_language", lambda _: None)
    file_name = f"sample{ext}"
    symbols = _extract_symbols(code, Path(file_name), ext)
    names = {s.name for s in symbols}
    assert expected_names.issubset(names)


@pytest.mark.parametrize("ext", [".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".rb"])
def test_treesitter_specific_check_is_optional(ext):
    language = _get_language(ext)
    if language is None:
        pytest.skip(f"tree-sitter language package not available for {ext}")
    assert language is not None
