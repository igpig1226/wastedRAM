"""Bounded checks for two explicitly supported pure-Python coding requests."""

import ast
import json
import re
import shutil
import subprocess
import sys


TESTS = {
    "parse_port": """assert parse_port(443) == 443
assert parse_port('443') == 443
assert parse_port(1) == 1
assert parse_port(65535) == 65535
for invalid in (0, 65536, 'abc', True, False, 443.0, '443.0', None):
    try:
        parse_port(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(repr(invalid))
""",
    "max_score": """assert max_score([]) is None
assert max_score([1, 7, 3]) == 7
assert max_score([-5, -2, -9]) == -2
""",
}


def target(task):
    if not isinstance(task, str):
        return None
    if "JavaScript fetch(" in task and "response.ok" in task:
        return "js_fetch"
    if "pytest fixture" in task and "SQLite" in task:
        return "sqlite_fixture"
    if "path.exists()" in task and "path.write_text" in task:
        return "exclusive_file"
    if "def reserve(conn, sku, request_id, quantity)" in task:
        return "sqlite_reserve"
    for name in TESTS:
        if re.search(r"\b" + name + r"\s*\(", task):
            return name
    return None


def check(task, answer):
    """Run only a restricted pure function in a time-limited isolated interpreter."""
    name = target(task)
    if name is None:
        return None
    if name == "js_fetch":
        return check_javascript(answer)
    if name == "sqlite_fixture":
        return check_fixture(answer)
    if name == "exclusive_file":
        return check_exclusive_file(answer)
    if name == "sqlite_reserve":
        return check_reserve(answer)
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", answer, re.I | re.S)
    for block in blocks or [answer]:
        try:
            tree = ast.parse(block)
        except SyntaxError:
            continue
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
        if not functions:
            continue
        function = functions[0]
        forbidden = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.ClassDef,
                     ast.AsyncFunctionDef, ast.With, ast.AsyncWith, ast.Try, ast.Lambda)
        allowed_calls = {"int", "str", "isinstance", "type", "len", "range", "max", "min", "ValueError"}
        allowed_methods = {"isdigit", "isdecimal", "strip", "lstrip"}
        nodes = list(ast.walk(function))
        if len(nodes) > 250 or any(isinstance(node, forbidden) or
            isinstance(node, ast.Name) and node.id.startswith("__") or
            isinstance(node, ast.Attribute) and (node.attr.startswith("__") or node.attr not in allowed_methods) or
            isinstance(node, ast.Call) and not (
                isinstance(node.func, ast.Name) and node.func.id in allowed_calls or
                isinstance(node.func, ast.Attribute) and node.func.attr in allowed_methods
            ) for node in nodes):
            continue
        source = ast.get_source_segment(block, function)
        harness = ("import builtins\n"
                   "safe = {key: getattr(builtins, key) for key in "
                   "('int', 'str', 'bool', 'float', 'isinstance', 'type', 'len', 'range', "
                   "'max', 'min', 'ValueError', 'AssertionError', 'repr')}\n"
                   "scope = {'__builtins__': safe}\n"
                   "exec(compile(source, '<answer>', 'exec'), scope)\n"
                   "exec(tests, scope)\n")
        process = subprocess.run(
            [sys.executable, "-I", "-S", "-c", "source = " + repr(source) +
             "\ntests = " + repr(TESTS[name]) + "\n" + harness],
            capture_output=True, timeout=2, check=False, env={},
        )
        if process.returncode == 0:
            return True
    return False


_JS_TEST = r"""
const vm = require('node:vm');
const {source, name} = JSON.parse(process.argv[1]);
let timer;
const context = {
  AbortController, Error, TypeError, Number,
  setTimeout(callback, ms) { if (ms !== 5000) throw Error('timeout must be 5 seconds'); timer = callback; return 1; },
  clearTimeout() {},
  fetch: async () => ({ok: true, json: async () => ({good: true})}),
};
vm.runInNewContext(source, context, {timeout: 500});
(async () => {
  if (!(await context[name]()).good) throw Error('JSON not returned');
  context.fetch = async () => ({ok: false, status: 500, json: async () => ({bad: true})});
  let rejected = false;
  try { await context[name](); } catch (error) { rejected = /500/.test(String(error.message)); }
  if (!rejected) throw Error('HTTP 500 accepted');
  context.fetch = (_, options) => {
    if (!options.signal) throw Error('missing abort signal');
    return new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(Error('aborted'))));
  };
  const pending = context[name]();
  await Promise.resolve();
  timer();
  try { await pending; throw Error('timeout not propagated'); }
  catch (error) { if (error.message === 'timeout not propagated') throw error; }
})().catch(() => process.exitCode = 1);
"""


def check_javascript(answer):
    node = shutil.which("node")
    sandbox = shutil.which("sandbox-exec") if sys.platform == "darwin" else None
    blocks = re.findall(r"```(?:javascript|js)\s*\n(.*?)```", answer, re.I | re.S)
    if not node or not sandbox or not blocks:
        return False
    for source in blocks:
        match = re.search(r"async\s+function\s+(\w+)\s*\(", source)
        if not match or len(source) > 12000:
            continue
        process = subprocess.run(
            [sandbox, "-p", "(version 1)(allow default)(deny network*)",
             node, "--permission", "--max-old-space-size=64", "-e", _JS_TEST,
             json.dumps({"source": source, "name": match.group(1)})],
            capture_output=True, timeout=2, check=False, env={},
        )
        if process.returncode == 0:
            return True
    return False


def check_fixture(answer):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", answer, re.I | re.S)
    for block in blocks:
        try:
            tree = ast.parse(block)
        except SyntaxError:
            continue
        for function in (node for node in tree.body if isinstance(node, ast.FunctionDef)
                         and any(isinstance(child, ast.Yield) for child in ast.walk(node))):
            nodes = list(ast.walk(function))
            if len(nodes) > 200 or any(
                # Only allow sqlite3, tempfile, pathlib imports
                isinstance(node, ast.Import) and not all(
                    alias.name in {"sqlite3", "tempfile", "pathlib", "os", "os.path"}
                    for alias in node.names
                ) or
                isinstance(node, ast.ImportFrom) and (
                    node.module not in {"sqlite3", "tempfile", "pathlib", "os", "os.path"}
                    or node.level != 0
                ) or
                isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef, ast.Global, ast.Nonlocal)) or
                # Block sandbox-escape builtins
                isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and
                    node.func.id in {"eval", "exec", "compile", "__import__", "getattr",
                                     "setattr", "delattr", "globals", "locals", "vars", "dir"}
                for node in nodes
            ):
                continue
            function.decorator_list = []
            source = ast.get_source_segment(block, function)
            if not source:
                continue
            source = source[source.index("def "):]
            harness = ("import sqlite3, tempfile, pathlib, os, builtins\n"
                       "_real_import = builtins.__import__\n"
                       "def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):\n"
                       "    if name not in ('sqlite3', 'tempfile', 'pathlib', 'os', 'os.path'):\n"
                       "        raise ImportError('blocked: ' + repr(name))\n"
                       "    return _real_import(name, globals, locals, fromlist, level)\n"
                       "scope = {'sqlite3': sqlite3, 'tempfile': tempfile,\n"
                       "         'pathlib': pathlib, 'Path': pathlib.Path, 'os': os,\n"
                       "         '__name__': '__main__',\n"
                       "         '__builtins__': {'__import__': _safe_import,\n"
                       "             'True': True, 'False': False, 'None': None,\n"
                       "             'Exception': Exception, 'StopIteration': StopIteration,\n"
                       "             'RuntimeError': RuntimeError,\n"
                       "             'print': print, 'len': len, 'str': str, 'int': int,\n"
                       "             'list': list, 'dict': dict, 'tuple': tuple, 'bool': bool,\n"
                       "             'next': next, 'iter': iter, 'range': range,\n"
                       "             'isinstance': isinstance, 'hasattr': hasattr}}\n"
                       "exec(compile(source, '<fixture>', 'exec'), scope)\n"
                       "with tempfile.TemporaryDirectory() as _tmp_dir:\n"
                       "    _tmp_path = pathlib.Path(_tmp_dir)\n"
                       "    if uses_tmp_path:\n"
                       "        generator = scope[name](tmp_path=_tmp_path)\n"
                       "    else:\n"
                       "        generator = scope[name]()\n"
                       "    connection = next(generator)\n"
                       "    connection.execute('SELECT 1')\n"
                       "    generator.close()\n"
                       "    try:\n"
                       "        connection.execute('SELECT 1')\n"
                       "    except sqlite3.ProgrammingError:\n"
                       "        pass\n"
                       "    else:\n"
                       "        raise AssertionError('connection left open after generator.close()')\n")
            # Detect whether the fixture function takes a tmp_path parameter
            _uses_tmp_path = any(
                isinstance(arg, ast.arg) and arg.arg == "tmp_path"
                for arg in function.args.args
            )
            process = subprocess.run(
                [sys.executable, "-I", "-S", "-c",
                 "source = " + repr(source) + "\nname = " + repr(function.name) +
                 "\nuses_tmp_path = " + repr(_uses_tmp_path) + "\n" + harness],
                capture_output=True, timeout=5, check=False, env={},
            )
            if process.returncode == 0:
                return True
    return False


_RESERVE_TESTS = """
import sqlite3, tempfile, os, concurrent.futures
with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'inventory.db')
    conn = sqlite3.connect(path, timeout=3)
    conn.executescript('CREATE TABLE inventory(sku TEXT PRIMARY KEY, available INTEGER NOT NULL);'
                       'CREATE TABLE reservations(request_id TEXT PRIMARY KEY, sku TEXT, quantity INTEGER);'
                       "INSERT INTO inventory VALUES('A', 2);")
    conn.commit()
    assert reserve(conn, 'A', 'req-1', 1) == 'req-1'
    assert reserve(conn, 'A', 'req-1', 1) == 'req-1'
    assert conn.execute("SELECT available FROM inventory WHERE sku='A'").fetchone()[0] == 1
    conn.close()
    def worker(request_id):
        connection = sqlite3.connect(path, timeout=3)
        try:
            return reserve(connection, 'A', request_id, 1)
        finally:
            connection.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, ('req-2', 'req-3')))
    assert sum(value is not None for value in results) == 1
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT available FROM inventory WHERE sku='A'").fetchone()[0] == 0
    assert conn.execute('SELECT COUNT(*) FROM reservations').fetchone()[0] == 2
    conn.execute('BEGIN')
    conn.execute("INSERT INTO inventory VALUES('B', 1)")
    try:
        reserve(conn, 'A', 'req-4', 1)
    except Exception:
        pass
    assert conn.in_transaction, 'caller transaction was committed or rolled back'
    assert conn.execute("SELECT available FROM inventory WHERE sku='B'").fetchone()[0] == 1
    conn.rollback()
    conn.close()
"""


def check_reserve(answer):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", answer, re.I | re.S)
    for block in blocks:
        try:
            tree = ast.parse(block)
        except SyntaxError:
            continue
        for function in (node for node in tree.body if isinstance(node, ast.FunctionDef)
                         and node.name == "reserve"):
            nodes = list(ast.walk(function))
            if len(nodes) > 300 or any(
                isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal,
                                  ast.ClassDef, ast.AsyncFunctionDef, ast.With, ast.AsyncWith,
                                  ast.Lambda)) or
                isinstance(node, ast.Subscript) and (not isinstance(node.value, ast.Name) or
                    node.value.id not in {"row", "existing", "prior", "result"} or
                    not isinstance(node.slice, ast.Constant) or
                    node.slice.value not in (0, 1)) or
                isinstance(node, ast.Name) and (node.id.startswith("__") or node.id not in
                    {"conn", "sku", "request_id", "quantity", "int", "str", "bool", "isinstance",
                     "ValueError", "RuntimeError", "TypeError", "Exception", "row", "existing", "prior", "cur", "cursor", "result"}) or
                isinstance(node, ast.Attribute) and (not (
                    isinstance(node.value, ast.Name) and
                    node.value.id in {"conn", "row", "existing", "prior", "cur", "cursor", "result"} or
                    node.attr == "fetchone" and isinstance(node.value, ast.Call) and
                    isinstance(node.value.func, ast.Attribute) and
                    isinstance(node.value.func.value, ast.Name) and
                    node.value.func.value.id == "conn" and node.value.func.attr == "execute") or
                    node.attr not in {"execute", "fetchone", "rowcount", "in_transaction", "commit", "rollback"}) or
                isinstance(node, ast.Call) and not (
                    isinstance(node.func, ast.Name) and node.func.id in
                    {"isinstance", "ValueError", "RuntimeError", "TypeError"} or
                    isinstance(node.func, ast.Attribute) and node.func.attr in
                    {"execute", "fetchone", "commit", "rollback"}) or
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and
                    node.func.attr == "execute" and (not node.args or
                    not isinstance(node.args[0], ast.Constant) or
                    not isinstance(node.args[0].value, str) or
                    ";" in node.args[0].value or
                    not re.match(r"^\s*(?:BEGIN(?: IMMEDIATE)?|COMMIT|ROLLBACK|"
                                 r"SELECT\b.*\bFROM\s+(?:inventory|reservations)\b|"
                                 r"UPDATE\s+inventory\b|INSERT\s+INTO\s+reservations\b)",
                                 node.args[0].value, re.I | re.S))
                for node in nodes
            ):
                continue
            source = ast.get_source_segment(block, function)
            harness = ("safe = {key: getattr(__import__('builtins'), key) for key in "
                       "('int', 'str', 'bool', 'isinstance', 'ValueError', 'RuntimeError', 'TypeError', 'Exception')}\n"
                       "scope = {'__builtins__': safe}\n"
                       "exec(compile(source, '<reserve>', 'exec'), scope)\n"
                       "reserve = scope['reserve']\n" + _RESERVE_TESTS)
            process = subprocess.run(
                [sys.executable, "-I", "-S", "-c", "source = " + repr(source) + "\n" + harness],
                capture_output=True, timeout=5, check=False, env={},
            )
            if process.returncode == 0:
                return True
    return False


def check_exclusive_file(answer):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", answer, re.I | re.S)
    for block in blocks:
        try:
            tree = ast.parse(block)
        except SyntaxError:
            continue
        if len(list(ast.walk(tree))) > 160 or any(
            # Only stdlib os/pathlib imports; block subprocess, socket, ctypes, etc.
            isinstance(node, ast.Import) and not all(
                alias.name in {"os", "pathlib"} for alias in node.names
            ) or
            isinstance(node, ast.ImportFrom) and (
                node.module not in {"os", "pathlib", "os.path"} or node.level != 0
            ) or
            # Keep it simple: no classes, async, global/nonlocal
            isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef, ast.Global, ast.Nonlocal)) or
            # Block dunder/jailbreak attribute access and Path methods that bypass exclusive-open
            isinstance(node, ast.Attribute) and (
                node.attr.startswith("_") or
                node.attr in {"write_text", "write_bytes", "mkdir", "rmdir",
                              "unlink", "rename", "replace", "chmod", "touch"}
            ) or
            # Block sandbox-escape builtins by name
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and
                node.func.id in {"eval", "exec", "compile", "__import__", "getattr",
                                 "setattr", "delattr", "globals", "locals", "vars", "dir"}
            for node in ast.walk(tree)
        ):
            continue
        # Strip os imports: the harness injects a sandboxed os with only open/fdopen/O_*.
        # Keep pathlib imports so Path type annotations and Path(path) construction work.
        source = "\n".join(line for line in block.splitlines()
                          if line.strip() != "import os"
                          and not line.strip().startswith("from os import"))
        harness = ("import tempfile, pathlib, os, types, builtins\n"
                   "with tempfile.TemporaryDirectory() as directory:\n"
                   "    os.chdir(directory)\n"
                   "    path = pathlib.Path(directory) / 'item.txt'\n"
                   "    def exclusive_open(candidate, mode='r', *a, **kw):\n"
                   "        assert mode in ('x', 'xt', 'xb'), repr(mode)\n"
                   "        return open(candidate, mode)\n"
                   "    def exclusive_os_open(candidate, flags, mode=0o777):\n"
                   "        assert flags & os.O_EXCL and flags & os.O_CREAT\n"
                   "        return os.open(candidate, flags, 0o600)\n"
                   "    safe_os = types.SimpleNamespace(open=exclusive_os_open, fdopen=os.fdopen,\n"
                   "        O_WRONLY=os.O_WRONLY, O_CREAT=os.O_CREAT, O_EXCL=os.O_EXCL)\n"
                   "    _real_import = builtins.__import__\n"
                   "    def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):\n"
                   "        if name not in ('os', 'pathlib', 'os.path'):\n"
                   "            raise ImportError('blocked import: ' + repr(name))\n"
                   "        return _real_import(name, globals, locals, fromlist, level)\n"
                   "    safe = {'open': exclusive_open, 'FileExistsError': FileExistsError,\n"
                   "            '__import__': _safe_import,\n"
                   "            'True': True, 'False': False, 'None': None,\n"
                   "            'bool': bool, 'str': str, 'int': int, 'print': print,\n"
                   "            'Exception': Exception, 'OSError': OSError, 'IOError': OSError}\n"
                   "    scope = {'__builtins__': safe, 'path': path, 'os': safe_os,\n"
                   "             'pathlib': pathlib, 'Path': pathlib.Path,\n"
                   "             '__name__': '__main__'}\n"
                   "    for _ in range(2):\n"
                   "        exec(compile(source, '<file>', 'exec'), scope)\n"
                   "        if 'write_once' in scope: scope['write_once'](path)\n"
                   "        assert path.read_text() == 'hello'\n")
        process = subprocess.run(
            [sys.executable, "-I", "-S", "-c", "source = " + repr(source) + "\n" + harness],
            capture_output=True, timeout=2, check=False, env={},
        )
        if process.returncode == 0:
            return True
    return False
