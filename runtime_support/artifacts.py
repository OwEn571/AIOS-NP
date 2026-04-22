from __future__ import annotations

import json
import os
import threading
from fnmatch import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from project_paths import DATA_ROOT


class ArtifactStore(Protocol):
    def resolve_path(self, path: str | Path) -> Path:
        ...

    def ensure_dir(self, path: str | Path) -> Path:
        ...

    def exists(self, path: str | Path) -> bool:
        ...

    def write_text(self, path: str | Path, content: str) -> str:
        ...

    def write_json(self, path: str | Path, payload: Any) -> str:
        ...

    def read_text(self, path: str | Path) -> str:
        ...

    def read_json(self, path: str | Path) -> Any:
        ...

    def glob(self, pattern: str) -> list[Path]:
        ...

    def glob_in(self, directory: str | Path, pattern: str) -> list[Path]:
        ...

    def delete_file(self, path: str | Path) -> bool:
        ...

    def delete_dir(self, path: str | Path, recursive: bool = False) -> bool:
        ...

    def describe(self) -> dict[str, Any]:
        ...


@dataclass
class LocalArtifactStore:
    root: Path = DATA_ROOT

    def resolve_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return self.root.joinpath(*candidate.parts)

    def ensure_parent(self, path: str | Path) -> Path:
        resolved = self.resolve_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def ensure_dir(self, path: str | Path) -> Path:
        resolved = self.resolve_path(path)
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def exists(self, path: str | Path) -> bool:
        return self.resolve_path(path).exists()

    def write_text(self, path: str | Path, content: str) -> str:
        resolved = self.ensure_parent(path)
        resolved.write_text(content, encoding="utf-8")
        return str(resolved)

    def write_json(self, path: str | Path, payload: Any) -> str:
        resolved = self.ensure_parent(path)
        resolved.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(resolved)

    def read_text(self, path: str | Path) -> str:
        return self.resolve_path(path).read_text(encoding="utf-8")

    def read_json(self, path: str | Path) -> Any:
        return json.loads(self.read_text(path))

    def glob(self, pattern: str) -> list[Path]:
        return sorted(self.root.glob(pattern))

    def glob_in(self, directory: str | Path, pattern: str) -> list[Path]:
        resolved_dir = self.resolve_path(directory)
        return sorted(resolved_dir.glob(pattern))

    def delete_file(self, path: str | Path) -> bool:
        resolved = self.resolve_path(path)
        if not resolved.exists():
            return False
        resolved.unlink(missing_ok=True)
        return True

    def delete_dir(self, path: str | Path, recursive: bool = False) -> bool:
        resolved = self.resolve_path(path)
        if not resolved.exists():
            return False
        if recursive:
            import shutil

            shutil.rmtree(resolved)
        else:
            resolved.rmdir()
        return True

    def describe(self) -> dict[str, Any]:
        return {
            "backend": "local",
            "root": str(self.root),
        }


@dataclass
class AIOSStorageArtifactStore:
    root: Path = DATA_ROOT
    agent_name: str = "news_artifact_store"
    base_url: str = "http://127.0.0.1:8001"
    local_fallback: bool = True
    auto_mount: bool = True
    _local_store: LocalArtifactStore = field(init=False)
    _mounted: bool = field(default=False, init=False)
    _mount_lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _kernel_write_count: int = field(default=0, init=False)
    _fallback_write_count: int = field(default=0, init=False)
    _kernel_read_count: int = field(default=0, init=False)
    _fallback_read_count: int = field(default=0, init=False)
    _last_error: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._local_store = LocalArtifactStore(root=self.root)

    def resolve_path(self, path: str | Path) -> Path:
        return self._local_store.resolve_path(path)

    def ensure_dir(self, path: str | Path) -> Path:
        resolved = self.resolve_path(path)
        try:
            self._mount_if_needed()
            self._kernel_create_dir(resolved)
            self._last_error = None
        except Exception as exc:
            self._last_error = str(exc)
            self._fallback_write_count += 1
            if not self.local_fallback:
                raise
            self._local_store.ensure_dir(resolved)
        return resolved

    def exists(self, path: str | Path) -> bool:
        return self._local_store.exists(path)

    def write_text(self, path: str | Path, content: str) -> str:
        resolved = self.resolve_path(path)
        try:
            self._mount_if_needed()
            self._kernel_create_dir(resolved.parent)
            self._kernel_write_file(resolved, content)
            self._kernel_write_count += 1
            self._last_error = None
        except Exception as exc:
            self._last_error = str(exc)
            self._fallback_write_count += 1
            if not self.local_fallback:
                raise
            self._local_store.write_text(resolved, content)
        return str(resolved)

    def write_json(self, path: str | Path, payload: Any) -> str:
        return self.write_text(
            path,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )

    def read_text(self, path: str | Path) -> str:
        resolved = self.resolve_path(path)
        try:
            self._mount_if_needed()
            payload = self._kernel_read_file(resolved)
            self._kernel_read_count += 1
            self._last_error = None
            return str(payload.get("content") or "")
        except Exception as exc:
            self._last_error = str(exc)
            self._fallback_read_count += 1
            if not self.local_fallback:
                raise
            return self._local_store.read_text(path)

    def read_json(self, path: str | Path) -> Any:
        return json.loads(self.read_text(path))

    def glob(self, pattern: str) -> list[Path]:
        try:
            return self._kernel_glob(self.root, pattern)
        except Exception as exc:
            self._last_error = str(exc)
            if not self.local_fallback:
                raise
            return self._local_store.glob(pattern)

    def glob_in(self, directory: str | Path, pattern: str) -> list[Path]:
        resolved_dir = self.resolve_path(directory)
        try:
            return self._kernel_glob_in(resolved_dir, pattern)
        except Exception as exc:
            self._last_error = str(exc)
            if not self.local_fallback:
                raise
            return self._local_store.glob_in(directory, pattern)

    def delete_file(self, path: str | Path) -> bool:
        resolved = self.resolve_path(path)
        try:
            self._mount_if_needed()
            self._kernel_delete_file(resolved)
            self._last_error = None
            return True
        except Exception as exc:
            self._last_error = str(exc)
            if not self.local_fallback:
                raise
            return self._local_store.delete_file(resolved)

    def delete_dir(self, path: str | Path, recursive: bool = False) -> bool:
        resolved = self.resolve_path(path)
        try:
            self._mount_if_needed()
            self._kernel_delete_dir(resolved, recursive=recursive)
            self._last_error = None
            return True
        except Exception as exc:
            self._last_error = str(exc)
            if not self.local_fallback:
                raise
            return self._local_store.delete_dir(resolved, recursive=recursive)

    def describe(self) -> dict[str, Any]:
        return {
            "backend": "aios",
            "root": str(self.root),
            "agent_name": self.agent_name,
            "base_url": self.base_url,
            "auto_mount": self.auto_mount,
            "mounted": self._mounted,
            "local_fallback": self.local_fallback,
            "kernel_write_count": self._kernel_write_count,
            "fallback_write_count": self._fallback_write_count,
            "kernel_read_count": self._kernel_read_count,
            "fallback_read_count": self._fallback_read_count,
            "last_error": self._last_error,
        }

    def _mount_if_needed(self) -> None:
        if not self.auto_mount or self._mounted:
            return
        with self._mount_lock:
            if self._mounted:
                return
            self._kernel_mount()
            self._mounted = True

    def _kernel_mount(self) -> None:
        from cerebrum.storage.apis import mount as storage_mount

        response = storage_mount(
            self.agent_name,
            str(self.root),
            base_url=self.base_url,
        )
        self._assert_storage_success(response, "mount")

    def _kernel_create_dir(self, path: Path) -> None:
        from cerebrum.storage.apis import create_dir

        response = create_dir(
            self.agent_name,
            str(path),
            base_url=self.base_url,
        )
        self._assert_storage_success(response, "create_dir")

    def _kernel_write_file(self, path: Path, content: str) -> None:
        from cerebrum.storage.apis import write_file

        response = write_file(
            self.agent_name,
            str(path),
            content,
            base_url=self.base_url,
        )
        self._assert_storage_success(response, "write")

    def _kernel_read_file(self, path: Path) -> dict[str, Any]:
        from cerebrum.storage.apis import read_file

        response = read_file(
            self.agent_name,
            str(path),
            base_url=self.base_url,
        )
        return self._extract_storage_payload(response, "read_file")

    def _kernel_list_dir(self, path: Path, recursive: bool = False) -> dict[str, Any]:
        from cerebrum.storage.apis import list_dir

        response = list_dir(
            self.agent_name,
            str(path),
            recursive=recursive,
            base_url=self.base_url,
        )
        return self._extract_storage_payload(response, "list_dir")

    def _kernel_delete_file(self, path: Path) -> None:
        from cerebrum.storage.apis import delete_file

        response = delete_file(
            self.agent_name,
            str(path),
            base_url=self.base_url,
        )
        self._extract_storage_payload(response, "delete_file")

    def _kernel_delete_dir(self, path: Path, recursive: bool = False) -> None:
        from cerebrum.storage.apis import delete_dir

        response = delete_dir(
            self.agent_name,
            str(path),
            recursive=recursive,
            base_url=self.base_url,
        )
        self._extract_storage_payload(response, "delete_dir")

    def _kernel_glob(self, root: Path, pattern: str) -> list[Path]:
        pattern_path = Path(pattern)
        parent = pattern_path.parent
        name_pattern = pattern_path.name or "*"
        search_dir = root if str(parent) in {"", "."} else self.resolve_path(parent)
        return self._kernel_glob_in(search_dir, name_pattern)

    def _kernel_glob_in(self, directory: Path, pattern: str) -> list[Path]:
        recursive = "**" in pattern
        normalized_pattern = pattern.replace("**/", "")
        payload = self._kernel_list_dir(directory, recursive=recursive)
        entries = payload.get("entries") or []
        matched: list[Path] = []
        for entry in entries:
            if entry.get("is_dir"):
                continue
            entry_path = Path(str(entry.get("path")))
            try:
                relative_name = entry_path.relative_to(directory).as_posix()
            except ValueError:
                relative_name = entry_path.name
            if fnmatch(relative_name, normalized_pattern) or fnmatch(entry_path.name, normalized_pattern):
                matched.append(entry_path)
        return sorted(matched)

    def _assert_storage_success(self, raw_response: Any, operation: str) -> None:
        payload = raw_response.get("response") if isinstance(raw_response, dict) else raw_response
        if not isinstance(payload, dict):
            raise RuntimeError(f"AIOS storage {operation} returned invalid payload: {raw_response!r}")
        if payload.get("error"):
            raise RuntimeError(f"AIOS storage {operation} failed: {payload['error']}")
        if payload.get("finished") is False:
            raise RuntimeError(f"AIOS storage {operation} did not finish successfully")

    def _extract_storage_payload(self, raw_response: Any, operation: str) -> dict[str, Any]:
        self._assert_storage_success(raw_response, operation)
        response_wrapper = raw_response.get("response") if isinstance(raw_response, dict) else raw_response
        message = response_wrapper.get("response_message")
        if isinstance(message, dict):
            if message.get("error"):
                raise RuntimeError(f"AIOS storage {operation} failed: {message['error']}")
            return message
        if isinstance(message, str):
            try:
                parsed = json.loads(message)
            except json.JSONDecodeError:
                return {"message": message}
            if isinstance(parsed, dict):
                if parsed.get("error"):
                    raise RuntimeError(f"AIOS storage {operation} failed: {parsed['error']}")
                return parsed
            return {"message": message}
        return {"message": message}


_DEFAULT_STORE: ArtifactStore | None = None
_DEFAULT_STORE_SIGNATURE: tuple[Any, ...] | None = None


def _artifact_store_signature() -> tuple[Any, ...]:
    return (
        os.getenv("AIOS_ARTIFACT_STORE_BACKEND", "local").strip().lower(),
        os.getenv("AIOS_NP_DATA_DIR", str(DATA_ROOT)),
        os.getenv("AIOS_ARTIFACT_AGENT_NAME", "news_artifact_store"),
        os.getenv("CEREBRUM_KERNEL_URL", "http://127.0.0.1:8001"),
        os.getenv("AIOS_ARTIFACT_STORE_FALLBACK_LOCAL", "true").strip().lower(),
        os.getenv("AIOS_ARTIFACT_AUTO_MOUNT", "true").strip().lower(),
    )


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def build_artifact_store() -> ArtifactStore:
    backend = os.getenv("AIOS_ARTIFACT_STORE_BACKEND", "local").strip().lower()
    root = Path(os.getenv("AIOS_NP_DATA_DIR", str(DATA_ROOT)))
    if backend == "aios":
        return AIOSStorageArtifactStore(
            root=root,
            agent_name=os.getenv("AIOS_ARTIFACT_AGENT_NAME", "news_artifact_store").strip(),
            base_url=os.getenv("CEREBRUM_KERNEL_URL", "http://127.0.0.1:8001").strip(),
            local_fallback=_bool_env("AIOS_ARTIFACT_STORE_FALLBACK_LOCAL", True),
            auto_mount=_bool_env("AIOS_ARTIFACT_AUTO_MOUNT", True),
        )
    return LocalArtifactStore(root=root)


def reset_artifact_store() -> None:
    global _DEFAULT_STORE, _DEFAULT_STORE_SIGNATURE
    _DEFAULT_STORE = None
    _DEFAULT_STORE_SIGNATURE = None


def get_artifact_store() -> ArtifactStore:
    global _DEFAULT_STORE, _DEFAULT_STORE_SIGNATURE
    signature = _artifact_store_signature()
    if _DEFAULT_STORE is None or _DEFAULT_STORE_SIGNATURE != signature:
        _DEFAULT_STORE = build_artifact_store()
        _DEFAULT_STORE_SIGNATURE = signature
    return _DEFAULT_STORE


def describe_artifact_store(store: ArtifactStore | None = None) -> dict[str, Any]:
    target = store or get_artifact_store()
    if hasattr(target, "describe"):
        return target.describe()
    return {"backend": type(target).__name__}
