from __future__ import annotations

from .. import main as main_module


class FakeLock:
    def __init__(self, try_results, lock_info=(True, 1234, "host", "BatesPosture")):
        self._try_results = list(try_results)
        self._lock_info = lock_info
        self.remove_stale_calls = 0
        self.stale_lock_time = None

    def setStaleLockTime(self, value: int) -> None:
        self.stale_lock_time = value

    def tryLock(self) -> bool:
        return self._try_results.pop(0)

    def getLockInfo(self):
        return self._lock_info

    def removeStaleLockFile(self) -> bool:
        self.remove_stale_calls += 1
        return True


def test_acquire_single_instance_lock_returns_lock_when_available(monkeypatch):
    fake_lock = FakeLock([True])
    monkeypatch.setattr(main_module, "QLockFile", lambda path: fake_lock)

    lock = main_module._acquire_single_instance_lock("/tmp/batesposture.lock")

    assert lock is fake_lock
    assert fake_lock.stale_lock_time == 0


def test_acquire_single_instance_lock_removes_stale_non_app_lock(monkeypatch):
    fake_lock = FakeLock([False, True])
    monkeypatch.setattr(main_module, "QLockFile", lambda path: fake_lock)
    monkeypatch.setattr(main_module, "_process_looks_like_batesposture", lambda pid: False)

    lock = main_module._acquire_single_instance_lock("/tmp/batesposture.lock")

    assert lock is fake_lock
    assert fake_lock.remove_stale_calls == 1


def test_acquire_single_instance_lock_preserves_active_app_lock(monkeypatch):
    fake_lock = FakeLock([False])
    monkeypatch.setattr(main_module, "QLockFile", lambda path: fake_lock)
    monkeypatch.setattr(main_module, "_process_looks_like_batesposture", lambda pid: True)

    lock = main_module._acquire_single_instance_lock("/tmp/batesposture.lock")

    assert lock is None
    assert fake_lock.remove_stale_calls == 0
