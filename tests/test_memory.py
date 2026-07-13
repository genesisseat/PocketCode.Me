import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


class TestMemory(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.tmp.name)
        import memory as memory_mod
        self._orig_pocket_dir = memory_mod.POCKET_DIR
        self._orig_memory_file = memory_mod.MEMORY_FILE
        memory_mod.POCKET_DIR = self.tmp_dir
        memory_mod.MEMORY_FILE = self.tmp_dir / "memory.json"

    def tearDown(self):
        import memory as memory_mod
        memory_mod.POCKET_DIR = self._orig_pocket_dir
        memory_mod.MEMORY_FILE = self._orig_memory_file
        self.tmp.cleanup()

    def _mod(self):
        import memory as memory_mod
        return memory_mod

    def test_remember_detail_and_preference(self):
        mod = self._mod()
        mod.remember_detail("prefers concise answers")
        mod.remember_preference("tone", "concise")
        data = mod.load_memory()
        self.assertIn("prefers concise answers", data["details"])
        self.assertEqual(data["preferences"]["tone"], "concise")

    def test_build_memory_context_contains_summary(self):
        mod = self._mod()
        mod.remember_detail("likes Python")
        mod.remember_preference("language", "Python")
        context = mod.build_memory_context()
        self.assertIn("likes Python", context)
        self.assertIn("language: Python", context)

    def test_forget_memory_entry(self):
        mod = self._mod()
        mod.remember_preference("tone", "formal")
        removed = mod.forget_memory_entry("tone")
        self.assertTrue(removed)
        data = mod.load_memory()
        self.assertNotIn("tone", data["preferences"])
