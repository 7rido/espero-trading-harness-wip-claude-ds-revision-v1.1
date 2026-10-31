"""The one-way copy: copy what is new, never delete, never overwrite something newer."""
import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sync", ROOT / "scripts" / "sync_from_original.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class TestSync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = pathlib.Path(self.tmp.name) / "src"
        self.dst = pathlib.Path(self.tmp.name) / "dst"
        self.src.mkdir()
        self.dst.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, body="x", mtime=None):
        p = self.src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        if mtime is not None:
            import os
            os.utime(p, (mtime, mtime))
        return p

    def test_a_missing_file_is_copied(self):
        self.write("data/hlcollect/a.csv", "hello")
        self.assertEqual(sync.main(["--source", str(self.src), "--dest", str(self.dst)]), 0)
        self.assertTrue((self.dst / "data/hlcollect/a.csv").exists())

    def test_an_unchanged_file_is_not_copied_twice(self):
        self.write("data/hlcollect/a.csv", "hello")
        sync.main(["--source", str(self.src), "--dest", str(self.dst)])
        first = (self.dst / "data/hlcollect/a.csv").stat().st_mtime
        sync.main(["--source", str(self.src), "--dest", str(self.dst)])
        self.assertEqual((self.dst / "data/hlcollect/a.csv").stat().st_mtime, first)

    def test_a_newer_and_longer_file_replaces_the_old_one(self):
        self.write("data/hlcollect/a.csv", "old")
        sync.main(["--source", str(self.src), "--dest", str(self.dst)])
        import os, time
        p = self.write("data/hlcollect/a.csv", "new and longer")
        os.utime(p, (time.time() + 10, time.time() + 10))
        sync.main(["--source", str(self.src), "--dest", str(self.dst)])
        self.assertEqual((self.dst / "data/hlcollect/a.csv").read_text(), "new and longer")

    def test_a_newer_but_same_size_file_is_left_alone(self):
        self.write("data/hlcollect/a.csv", "aaaa")
        sync.main(["--source", str(self.src), "--dest", str(self.dst)])
        import os, time
        p = self.write("data/hlcollect/a.csv", "bbbb")
        os.utime(p, (time.time() + 10, time.time() + 10))
        sync.main(["--source", str(self.src), "--dest", str(self.dst)])
        self.assertEqual((self.dst / "data/hlcollect/a.csv").read_text(), "aaaa")

    def test_deleting_at_the_source_never_deletes_here(self):
        self.write("data/hlcollect/a.csv", "hello")
        sync.main(["--source", str(self.src), "--dest", str(self.dst)])
        (self.src / "data/hlcollect/a.csv").unlink()
        sync.main(["--source", str(self.src), "--dest", str(self.dst)])
        self.assertTrue((self.dst / "data/hlcollect/a.csv").exists())

    def test_dry_run_writes_nothing(self):
        self.write("data/hlcollect/a.csv", "hello")
        sync.main(["--source", str(self.src), "--dest", str(self.dst), "--dry-run"])
        self.assertFalse((self.dst / "data/hlcollect/a.csv").exists())
