"""Bounded local FIFO with one interruptible scientific subprocess per active slot."""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .service import write

TERMINAL = {"completed", "failed", "cancelled"}


class Jobs:
    def __init__(
        self, root, workers=1, capacity=4, timeout=120, retention=900, records=16
    ):
        if not (
            1 <= workers <= capacity <= 16
            and capacity <= records <= 64
            and 0 < timeout <= 3600
            and 0 < retention <= 86400
        ):
            raise ValueError("invalid job limits")
        Path(root).mkdir(parents=True, exist_ok=True)
        self.session = tempfile.TemporaryDirectory(prefix="session-", dir=root)
        self.pool = ThreadPoolExecutor(max_workers=workers)
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.items = {}
        self.capacity, self.timeout, self.retention, self.records = (
            capacity,
            timeout,
            retention,
            records,
        )
        self.cleaner = threading.Thread(target=self.reap, daemon=True)
        self.cleaner.start()

    def reap(self):
        while not self.stop.wait(min(5, self.retention)):
            with self.lock:
                for key, item in list(self.items.items()):
                    if (
                        item["state"] in TERMINAL
                        and item["readers"] == 0
                        and time.monotonic() - item["ended"] > self.retention
                    ):
                        try:
                            shutil.rmtree(self.path(key))
                        except OSError:
                            continue
                        del self.items[key]

    def path(self, key):
        # Only server-issued keys can resolve to a path.
        if key not in self.items:
            raise KeyError(key)
        return Path(self.session.name) / key

    @contextmanager
    def hold(self, key):
        """Keep a result alive through the last byte of an active download."""
        with self.lock:
            self.items[key]["readers"] += 1
        try:
            yield
        finally:
            with self.lock:
                self.items[key]["readers"] -= 1

    def submit(self, request):
        with self.lock:
            if (
                len(self.items) >= self.records
                or sum(r["state"] not in TERMINAL for r in self.items.values())
                >= self.capacity
            ):
                raise OverflowError(
                    "job capacity reached; retry after a job finishes or expires"
                )
            key = uuid4().hex
            self.items[key] = {
                "id": key,
                "kind": request["kind"],
                "state": "queued",
                "error": None,
                "progress": 0.0,
                "cancel": False,
                "readers": 0,
            }
            try:
                out = self.path(key)
                out.mkdir()
                write(out / "request.json", request)
                self.pool.submit(self.run, key)
            except Exception:
                self.items.pop(key)
                raise
            return self.status(key)

    def status(self, key):
        with self.lock:
            r = self.items[key]
            return {k: r[k] for k in ("id", "kind", "state", "error", "progress")}

    def cancel(self, key):
        with self.lock:
            r = self.items[key]
            if r["state"] not in TERMINAL:
                r["cancel"] = True
                if r["state"] == "queued":
                    self.finish(key, "cancelled")
            return self.status(key)

    def finish(self, key, state, error=None):
        self.items[key].update(state=state, error=error, ended=time.monotonic())
        if state == "completed":
            self.items[key]["progress"] = 1.0
        logging.getLogger(__name__).info("job %s %s", key, state)

    def run(self, key):
        with self.lock:
            if key not in self.items or self.items[key]["state"] != "queued":
                return
            job = self.items[key]
            job["state"] = "running"
            out = self.path(key)
        proc = None
        try:
            env = os.environ | {
                "OMP_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
            }
            with (out / "worker.log").open("w") as log:
                proc = subprocess.Popen(
                    [sys.executable, "-m", "geoflow.web.worker", str(out)],
                    stdout=log,
                    stderr=log,
                    env=env,
                )
                deadline = time.monotonic() + self.timeout
                while proc.poll() is None:
                    if job["cancel"] or time.monotonic() >= deadline:
                        proc.kill()
                        proc.wait()
                        break
                    try:
                        complete = (out / "progress").read_bytes().split(b"\n")[:-1]
                        if complete:
                            job["progress"] = float(complete[-1])
                    except (FileNotFoundError, PermissionError, ValueError):
                        pass
                    time.sleep(0.05)
            with self.lock:
                if job["cancel"]:
                    self.finish(key, "cancelled")
                elif proc.returncode == 0:
                    self.finish(key, "completed")
                else:
                    self.finish(
                        key,
                        "failed",
                        "execution timeout"
                        if time.monotonic() >= deadline
                        else "scientific worker failed",
                    )
        except Exception:
            logging.getLogger(__name__).exception("worker %s", key)
            if proc and proc.poll() is None:
                proc.kill()
                proc.wait()
            with self.lock:
                self.finish(key, "failed", "worker could not complete")

    def close(self):
        self.stop.set()
        with self.lock:
            for key in self.items:
                self.cancel(key)
        self.pool.shutdown(wait=True, cancel_futures=True)
        self.cleaner.join()
        self.session.cleanup()
