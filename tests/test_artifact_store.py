import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime_support.artifacts import AIOSStorageArtifactStore, LocalArtifactStore
from runtime_support.env import load_project_env


class LocalArtifactStoreTest(unittest.TestCase):
    def test_write_and_read_text_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = LocalArtifactStore(root=Path(temp_dir))

            text_path = store.write_text("intermediate/example.txt", "hello")
            json_path = store.write_json("output/example.json", {"ok": True})

            self.assertTrue(store.exists(text_path))
            self.assertEqual(store.read_text(text_path), "hello")
            self.assertEqual(store.read_json(json_path), {"ok": True})

    def test_glob_uses_store_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = LocalArtifactStore(root=Path(temp_dir))
            store.write_text("intermediate/a.txt", "a")
            store.write_text("intermediate/b.txt", "b")

            matches = store.glob("intermediate/*.txt")
            self.assertEqual([path.name for path in matches], ["a.txt", "b.txt"])

    def test_glob_in_resolves_explicit_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = LocalArtifactStore(root=Path(temp_dir))
            store.write_text("custom/nested/a.json", "{}")

            matches = store.glob_in(Path(temp_dir) / "custom" / "nested", "*.json")
            self.assertEqual([path.name for path in matches], ["a.json"])

    def test_load_project_env_parses_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env.local"
            env_path.write_text("UNIT_TEST_ENV=hello\n", encoding="utf-8")

            original = os.environ.copy()
            try:
                os.environ.pop("UNIT_TEST_ENV", None)
                loaded = load_project_env(env_path)
                self.assertEqual(loaded, env_path)
                self.assertEqual(os.environ.get("UNIT_TEST_ENV"), "hello")
            finally:
                os.environ.clear()
                os.environ.update(original)

    def test_aios_storage_store_writes_via_kernel_and_reads_locally(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = AIOSStorageArtifactStore(
                root=root,
                agent_name="artifact-test",
                base_url="http://127.0.0.1:8001",
                local_fallback=False,
            )

            def fake_mount():
                return {"response": {"finished": True, "response_message": f"mounted:{root}"}}

            def fake_create_dir(path):
                Path(path).mkdir(parents=True, exist_ok=True)
                return {"response": {"finished": True, "response_message": f"dir:{path}"}}

            def fake_write_file(path, content):
                path = Path(path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                return {"response": {"finished": True, "response_message": f"write:{path}"}}

            def fake_read_file(path):
                path = Path(path)
                return {
                    "file_path": str(path),
                    "content": path.read_text(encoding="utf-8"),
                }

            def fake_list_dir(path, recursive=False):
                path = Path(path)
                entries = []
                iterable = path.rglob("*") if recursive else path.glob("*")
                for item in iterable:
                    entries.append(
                        {
                            "name": item.name,
                            "path": str(item),
                            "is_dir": item.is_dir(),
                            "size": 0 if item.is_dir() else item.stat().st_size,
                        }
                    )
                return {"entries": entries}

            def fake_delete_file(path):
                path = Path(path)
                path.unlink(missing_ok=True)
                return {"response": {"finished": True, "response_message": {"deleted": True}}}

            with patch("runtime_support.artifacts.AIOSStorageArtifactStore._kernel_mount", side_effect=fake_mount), patch(
                "runtime_support.artifacts.AIOSStorageArtifactStore._kernel_create_dir",
                side_effect=fake_create_dir,
            ), patch(
                "runtime_support.artifacts.AIOSStorageArtifactStore._kernel_write_file",
                side_effect=fake_write_file,
            ), patch(
                "runtime_support.artifacts.AIOSStorageArtifactStore._kernel_read_file",
                side_effect=fake_read_file,
            ), patch(
                "runtime_support.artifacts.AIOSStorageArtifactStore._kernel_list_dir",
                side_effect=fake_list_dir,
            ), patch(
                "runtime_support.artifacts.AIOSStorageArtifactStore._kernel_delete_file",
                side_effect=fake_delete_file,
            ):
                text_path = store.write_text("intermediate/example.txt", "kernel")
                json_path = store.write_json("output/example.json", {"ok": True})
                matches = store.glob("intermediate/*.txt")
                self.assertTrue(store.exists(text_path))
                self.assertEqual(store.read_text(text_path), "kernel")
                self.assertEqual(store.read_json(json_path), {"ok": True})
                deleted = store.delete_file("intermediate/example.txt")

            self.assertEqual(store.describe()["backend"], "aios")
            self.assertEqual([path.name for path in matches], ["example.txt"])
            self.assertTrue(deleted)


if __name__ == "__main__":
    unittest.main()
