"""The product and the lab stay apart (code review 2026-10-01, A2; architecture clean-up, milestone 8): nothing in
semantic_pdf_diff imports the lab, eagerly or lazily, so a plain install is the diff tool alone; within the lab,
evaluation doesn't reach into the benches. The lab adds its commands through entry points, not imports."""
import stubs  # noqa: F401 (a clean environment)
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCT = ROOT / "src/semantic_pdf_diff"
LAB = ROOT / "lab/src/semantic_pdf_diff_lab"

def imports(path):
    """Every module a file imports, as absolute names (relative ones resolved against its package)."""
    src = next(p for p in path.parents if p.name == "src")
    package = ".".join(path.relative_to(src).with_suffix("").parts[:-1])
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")[:len(package.split(".")) - node.level + 1]
                name = ".".join(base + ([node.module] if node.module else []))
            else:
                name = node.module
            out.add(name)
            out |= {f"{name}.{a.name}" for a in node.names}
    return out

def runtime_imports(path):
    """The product modules a module imports when it runs: at load or in a function, not for type checking only."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    typing_only = {id(n) for node in ast.walk(tree) if isinstance(node, ast.If) and "TYPE_CHECKING" in ast.unparse(node.test)
                   for n in ast.walk(node)}
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and id(node) not in typing_only:
            if node.level == 1:
                out |= {node.module.split(".")[0]} if node.module else {a.name for a in node.names}
            elif node.module and node.module.startswith("semantic_pdf_diff."):
                out.add(node.module.split(".")[1])
    return out

def cycles():
    """The product's import cycles (strongly connected components of more than one module), as sets."""
    modules = {p.stem: p for p in PRODUCT.glob("*.py")}
    graph = {m: runtime_imports(p) & set(modules) - {m} for m, p in modules.items()}
    index, low, stack, found = {}, {}, [], []
    def visit(v):
        index[v] = low[v] = len(index)
        stack.append(v)
        for w in graph[v]:
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            component = set()
            while not component or v not in component:
                component.add(stack.pop())
            if len(component) > 1:
                found.append(component)
    for v in sorted(graph):
        if v not in index:
            visit(v)
    return found

# The import cycle left (code review 2026-10-08, C4: 21 modules, held by models importing the levers). Each
# architecture move that breaks a part of it shrinks this; a change that grows it fails.
CYCLE = {"compare", "context", "dispatch", "docxdocs", "extract", "fixtures", "keyvalue", "levers", "llm", "pictures",
         "pptxdocs", "provenance", "settings", "situate", "stems", "tablerules", "tables", "tablestructure", "tasks",
         "textdocs", "xlsxdocs"}

class Layers(unittest.TestCase):
    def test_the_schema_imports_nothing_of_the_product(self):
        self.assertEqual(runtime_imports(PRODUCT / "schema.py"), set())

    def test_the_import_cycle_doesnt_grow(self):
        self.assertEqual(cycles(), [CYCLE] if CYCLE else [])

class Boundaries(unittest.TestCase):
    def test_the_product_imports_nothing_from_the_lab(self):
        for path in sorted(PRODUCT.rglob("*.py")):  # subpackages too, vendor/ among them (code review 2026-10-08, E6)
            with self.subTest(module=str(path.relative_to(PRODUCT))):
                self.assertFalse({m for m in imports(path) if m.startswith("semantic_pdf_diff_lab")})

    def test_evaluation_doesnt_reach_into_the_benches(self):
        for path in sorted((LAB / "eval").rglob("*.py")):  # eval/rounds too
            with self.subTest(module=str(path.relative_to(LAB))):
                self.assertFalse({m for m in imports(path) if m.startswith("semantic_pdf_diff_lab.bench")})

    def test_the_lab_adds_its_commands_through_entry_points(self):
        from semantic_pdf_diff import cli
        self.assertLessEqual({"review", "queries"}, set(cli.lab_commands()))

if __name__ == "__main__":
    unittest.main()
