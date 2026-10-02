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

class Boundaries(unittest.TestCase):
    def test_the_product_imports_nothing_from_the_lab(self):
        for path in sorted(PRODUCT.glob("*.py")):
            with self.subTest(module=path.name):
                self.assertFalse({m for m in imports(path) if m.startswith("semantic_pdf_diff_lab")})

    def test_evaluation_doesnt_reach_into_the_benches(self):
        for path in sorted((LAB / "eval").glob("*.py")):
            with self.subTest(module=path.name):
                self.assertFalse({m for m in imports(path) if m.startswith("semantic_pdf_diff_lab.bench")})

    def test_the_lab_adds_its_commands_through_entry_points(self):
        from semantic_pdf_diff import cli
        self.assertLessEqual({"review", "queries"}, set(cli.lab_commands()))

if __name__ == "__main__":
    unittest.main()
