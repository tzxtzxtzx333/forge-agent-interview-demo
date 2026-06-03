"""
context/repo_map.py

Repo-map：把整个 repo 的结构压缩成一段摘要字符串，注入 system prompt。

核心思路（简化版 Aider repo-map）：
1. 用 tree-sitter 扫描源码文件，提取函数/类定义
2. 用正则 fallback 处理 tree-sitter 不支持或未安装的语言
3. 按"重要性"排序：顶层定义 > 方法，文件越小越可能是核心文件
4. 按 token 预算截取，生成摘要字符串

## 多语言支持

tree-sitter 每种语言需要单独安装语言包：

    pip install tree-sitter-python       # Python（必装）
    pip install tree-sitter-javascript   # JavaScript
    pip install tree-sitter-typescript   # TypeScript
    pip install tree-sitter-go           # Go
    pip install tree-sitter-rust         # Rust
    pip install tree-sitter-java         # Java

未安装的语言自动降级为正则解析，不报错。
新增语言只需在 _LANG_REGISTRY 里加一行。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# 语言注册表
# 格式：文件扩展名 → (pip 包名, 模块属性名)
# 运行时按需 import，失败时静默跳过，降级为正则
# ---------------------------------------------------------------------------

_LANG_REGISTRY: dict[str, tuple[str, str]] = {
    ".py":  ("tree_sitter_python",     "language"),
    ".js":  ("tree_sitter_javascript", "language"),
    ".ts":  ("tree_sitter_typescript", "language_typescript"),
    ".tsx": ("tree_sitter_typescript", "language_tsx"),
    ".go":  ("tree_sitter_go",         "language"),
    ".rs":  ("tree_sitter_rust",       "language"),
    ".java":("tree_sitter_java",       "language"),
    ".cpp": ("tree_sitter_cpp",        "language"),
    ".c":   ("tree_sitter_c",          "language"),
    ".rb":  ("tree_sitter_ruby",       "language"),
}

_LANGUAGE_NAMES: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".rb": "ruby",
}

# AST 节点类型 → symbol kind 映射（各语言通用名）
_FUNC_NODES: frozenset[str] = frozenset({
    "function_definition",       # Python, Go, C, C++
    "async_function_definition", # Python async def
    "function_declaration",      # JS, TS, Java
    "method_declaration",        # Java
    "method_definition",         # JS class method
    "function_item",             # Rust fn
    "arrow_function",            # JS arrow（跳过，通常是匿名的）
})
_CLASS_NODES: frozenset[str] = frozenset({
    "class_definition",   # Python
    "class_declaration",  # JS, TS, Java
    "struct_item",        # Rust struct
    "impl_item",          # Rust impl
    "interface_declaration",  # TS/Java
    "type_definition",    # Go type
    "struct_specifier",   # C/C++
})

_METHOD_LIKE_PARENTS: frozenset[str] = frozenset({
    "class_body",
    "class_definition",
    "class_declaration",
    "impl_item",
    "impl_block",
    "declaration_list",
    "field_declaration_list",
})

# 跳过的目录
_SKIP_DIRS: frozenset[str] = frozenset({
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    ".mypy_cache", ".pytest_cache", "dist", "build",
})

_SUPPORTED_EXTS: frozenset[str] = frozenset(_LANG_REGISTRY)

# 已加载的 tree-sitter Language 对象缓存（避免重复 import）
_lang_cache: dict[str, object] = {}   # ext → Language or None


def _get_language(ext: str):
    """
    按文件扩展名获取 tree-sitter Language 对象。
    未安装时返回 None，调用方降级为正则。
    """
    if ext in _lang_cache:
        return _lang_cache[ext]

    entry = _LANG_REGISTRY.get(ext)
    if entry is None:
        _lang_cache[ext] = None
        return None

    module_name, attr_name = entry
    try:
        import importlib
        from tree_sitter import Language
        mod = importlib.import_module(module_name)
        lang_fn = getattr(mod, attr_name)
        lang = Language(lang_fn())
        _lang_cache[ext] = lang
        return lang
    except Exception:
        _lang_cache[ext] = None
        return None


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class Symbol:
    """一个提取出来的符号（函数或类定义）。"""
    name: str
    kind: str           # "function" | "class" | "method"
    line: int
    file: Path
    language: str
    indent: int = 0

    @property
    def is_toplevel(self) -> bool:
        return self.indent == 0


@dataclass
class FileInfo:
    """一个文件的元信息和符号列表。"""
    path: Path
    size: int
    symbols: list[Symbol] = field(default_factory=list)

    @property
    def rel_path(self) -> str:
        return str(self.path)

    def importance_score(self) -> float:
        top_level = sum(1 for s in self.symbols if s.is_toplevel)
        size_penalty = self.size / 10_000
        return top_level - size_penalty


# ---------------------------------------------------------------------------
# RepoMap
# ---------------------------------------------------------------------------

class RepoMap:
    """
    扫描 repo，生成摘要字符串。

    用法：
        rm = RepoMap(repo_path="/path/to/repo")
        summary = rm.build(budget=8000)
    """

    def __init__(self, repo_path: str | Path) -> None:
        self._root = Path(repo_path).resolve()

    def build(self, budget: int = 8000) -> str:
        files = self._scan()
        if not files:
            return "(empty repository)"

        files.sort(key=lambda f: f.importance_score(), reverse=True)

        lines: list[str] = []
        char_count = 0
        max_chars = budget * 4

        for fi in files:
            block = self._format_file(fi)
            if char_count + len(block) > max_chars:
                remaining = len(files) - files.index(fi)
                lines.append(f"... ({remaining} more files not shown)")
                break
            lines.append(block)
            char_count += len(block)

        return "\n".join(lines)

    def _scan(self) -> list[FileInfo]:
        results: list[FileInfo] = []
        for path in sorted(self._root.rglob("*")):
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            if not path.is_file():
                continue
            size = path.stat().st_size
            if size > 500_000:
                continue

            fi = FileInfo(path=path.relative_to(self._root), size=size)
            ext = path.suffix.lower()

            if ext in _SUPPORTED_EXTS:
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    fi.symbols = _extract_symbols(content, fi.path, ext)
                except OSError:
                    pass

            results.append(fi)
        return results

    def _format_file(self, fi: FileInfo) -> str:
        sym_count = len(fi.symbols)
        header = f"{fi.rel_path}"
        if sym_count:
            header += f" ({sym_count} symbol{'s' if sym_count != 1 else ''})"

        if not fi.symbols:
            return header + "\n"

        sym_lines = [header + ":"]
        for sym in fi.symbols:
            prefix = "    " if not sym.is_toplevel else "  "
            sym_lines.append(f"{prefix}{sym.kind} {sym.name} (line {sym.line})")
        return "\n".join(sym_lines) + "\n"


# ---------------------------------------------------------------------------
# 符号提取（对外暴露，供测试使用）
# ---------------------------------------------------------------------------

def _extract_symbols(content: str, filepath: Path, ext: str) -> list[Symbol]:
    """
    按扩展名选择解析方式：tree-sitter（如已安装）或正则 fallback。
    """
    lang = _get_language(ext)
    if lang is not None:
        return _extract_with_treesitter(content, filepath, lang, ext)
    return _extract_symbols_regex(content, filepath, ext)


def _extract_with_treesitter(content: str, filepath: Path, lang, ext: str) -> list[Symbol]:
    """用 tree-sitter 提取符号，失败时降级为正则。"""
    try:
        from tree_sitter import Parser
        parser = Parser(lang)
        tree = parser.parse(content.encode("utf-8", errors="replace"))
        return _walk_tree(tree.root_node, filepath, ext)
    except Exception:
        return _extract_symbols_regex(content, filepath, ext)


def _walk_tree(node, filepath: Path, ext: str) -> list[Symbol]:
    """递归遍历 tree-sitter AST，提取函数和类定义。"""
    results: list[Symbol] = []
    ntype = node.type
    language = _language_name(ext)

    if ntype in _FUNC_NODES and ntype != "arrow_function":
        name_node = node.child_by_field_name("name")
        if name_node:
            indent = node.start_point[1]
            kind = "method" if _is_method_node(node) else "function"
            results.append(Symbol(
                name=name_node.text.decode("utf-8", errors="replace"),
                kind=kind,
                line=node.start_point[0] + 1,
                file=filepath,
                language=language,
                indent=indent,
            ))
    elif ntype in _CLASS_NODES:
        name_node = node.child_by_field_name("name")
        if ntype == "struct_specifier" and name_node is None:
            name_node = node.child_by_field_name("body")
        if name_node:
            indent = node.start_point[1]
            results.append(Symbol(
                name=_clean_symbol_name(name_node.text.decode("utf-8", errors="replace")),
                kind="class" if ntype != "interface_declaration" else "interface",
                line=node.start_point[0] + 1,
                file=filepath,
                language=language,
                indent=indent,
            ))

    for child in node.children:
        results.extend(_walk_tree(child, filepath, ext))

    return results


# 保留原函数名供测试 import
def _extract_python_symbols(content: str, filepath: Path) -> list[Symbol]:
    """兼容旧接口，测试文件用此名调用。"""
    return _extract_symbols(content, filepath, ".py")


def _extract_symbols_regex(content: str, filepath: Path, ext: str | None = None) -> list[Symbol]:
    """正则 fallback，支持多语言。"""
    symbols: list[Symbol] = []
    language = _language_name(ext or filepath.suffix.lower())
    for lineno, line in enumerate(content.splitlines(), start=1):
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        match = _match_symbol_regex(stripped, language)
        if match is None:
            continue
        kind, name = match
        if kind == "function" and indent > 0 and language in {"python", "ruby", "rust", "cpp"}:
            kind = "method"
        if kind == "function" and language == "cpp" and "::" in stripped:
            kind = "method"
        if kind == "method" and indent == 0 and language in {"java", "cpp", "ruby", "javascript", "typescript"}:
            if not (language == "cpp" and "::" in stripped):
                kind = "function"
        symbols.append(Symbol(
            name=name,
            kind=kind,
            line=lineno,
            file=filepath,
            language=language,
            indent=indent,
        ))
    return symbols


def _language_name(ext: str) -> str:
    return _LANGUAGE_NAMES.get(ext.lower(), ext.lstrip(".").lower() or "text")


def _clean_symbol_name(name: str) -> str:
    return name.strip().strip("{}").strip()


def _is_method_node(node) -> bool:
    parent = getattr(node, "parent", None)
    while parent is not None:
        if parent.type in _METHOD_LIKE_PARENTS:
            return True
        if parent.type in {"module", "program", "source_file"}:
            return False
        parent = parent.parent
    return node.start_point[1] > 0


def _match_symbol_regex(line: str, language: str) -> tuple[str, str] | None:
    patterns = _REGEX_PATTERNS.get(language, _REGEX_PATTERNS["default"])
    for pattern, kind in patterns:
        match = pattern.match(line)
        if match:
            name = match.groupdict().get("method") or match.group("name")
            return kind, name
    return None


_REGEX_PATTERNS: dict[str, list[tuple[re.Pattern[str], str]]] = {
    "python": [
        (re.compile(r"^(?:async\s+def|def)\s+(?P<name>[A-Za-z_]\w*)\s*\("), "function"),
        (re.compile(r"^class\s+(?P<name>[A-Za-z_]\w*)\b"), "class"),
    ],
    "javascript": [
        (re.compile(r"^function\s+(?P<name>[A-Za-z_]\w*)\s*\("), "function"),
        (re.compile(r"^class\s+(?P<name>[A-Za-z_]\w*)\b"), "class"),
        (re.compile(r"^(?:async\s+)?(?P<name>[A-Za-z_]\w*)\s*\([^;]*\)\s*\{"), "method"),
    ],
    "typescript": [
        (re.compile(r"^function\s+(?P<name>[A-Za-z_]\w*)\s*\("), "function"),
        (re.compile(r"^class\s+(?P<name>[A-Za-z_]\w*)\b"), "class"),
        (re.compile(r"^interface\s+(?P<name>[A-Za-z_]\w*)\b"), "interface"),
        (re.compile(r"^(?:public|private|protected|static|async|\s)*\s*(?P<name>[A-Za-z_]\w*)\s*\([^;]*\)\s*(?::|\{)"), "method"),
    ],
    "tsx": [
        (re.compile(r"^function\s+(?P<name>[A-Za-z_]\w*)\s*\("), "function"),
        (re.compile(r"^class\s+(?P<name>[A-Za-z_]\w*)\b"), "class"),
        (re.compile(r"^interface\s+(?P<name>[A-Za-z_]\w*)\b"), "interface"),
    ],
    "go": [
        (re.compile(r"^func\s+\([^)]+\)\s*(?P<name>[A-Za-z_]\w*)\s*\("), "method"),
        (re.compile(r"^func\s+(?P<name>[A-Za-z_]\w*)\s*\("), "function"),
        (re.compile(r"^type\s+(?P<name>[A-Za-z_]\w*)\s+(?:struct|interface)\b"), "class"),
    ],
    "rust": [
        (re.compile(r"^(?:pub\s+)?fn\s+(?P<name>[A-Za-z_]\w*)\s*\("), "function"),
        (re.compile(r"^(?:pub\s+)?struct\s+(?P<name>[A-Za-z_]\w*)\b"), "class"),
        (re.compile(r"^impl\s+(?P<name>[A-Za-z_]\w*)\b"), "class"),
    ],
    "java": [
        (re.compile(r"^(?:public\s+)?(?:class|interface)\s+(?P<name>[A-Za-z_]\w*)\b"), "class"),
        (re.compile(r"^(?:public|private|protected|static|final|abstract|\s)+[\w<>\[\]]+\s+(?P<name>[A-Za-z_]\w*)\s*\("), "method"),
    ],
    "c": [
        (re.compile(r"^(?:static\s+)?(?:[\w\*]+\s+)+(?P<name>[A-Za-z_]\w*)\s*\([^;]*\)\s*\{?"), "function"),
    ],
    "cpp": [
        (re.compile(r"^class\s+(?P<name>[A-Za-z_]\w*)\b"), "class"),
        (re.compile(r"^(?:[\w:<>~]+\s+)+(?P<name>[A-Za-z_]\w*)::(?P<method>[A-Za-z_~]\w*)\s*\("), "method"),
        (re.compile(r"^(?:[\w:<>~]+\s+)+(?P<name>[A-Za-z_~]\w*)\s*\("), "function"),
    ],
    "ruby": [
        (re.compile(r"^class\s+(?P<name>[A-Za-z_]\w*)\b"), "class"),
        (re.compile(r"^def\s+(?P<name>[A-Za-z_]\w*[!?=]?)\b"), "method"),
    ],
    "default": [
        (re.compile(r"^(?:async\s+def|def|function|func|fn)\s+(?P<name>[A-Za-z_]\w*)\b"), "function"),
        (re.compile(r"^class\s+(?P<name>[A-Za-z_]\w*)\b"), "class"),
    ],
}
