"""One subprocess job at a time, with bounded output for SSE cursors."""
from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from collections import deque


class Job:
    def __init__(self, name: str, kind: str, scenes: list[str], args: list[str]):
        self.name, self.kind, self.scenes = name, kind, scenes
        self.lines: deque[str] = deque(maxlen=2000)
        self._lock = threading.RLock()
        self.seq = 0  # total lines ever appended (for SSE cursors)
        self.state = "running"
        self.started, self.ended = time.time(), None
        self.code: int | None = None
        self.cmd = args
        self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                                     start_new_session=True, env={**os.environ, "PYTHONWARNINGS": "ignore", "FORCE_COLOR": "0"})
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        assert self.proc.stdout
        with self.proc.stdout:
            for line in self.proc.stdout:
                with self._lock:
                    self.lines.append(line.rstrip("\n"))
                    self.seq += 1
        code = self.proc.wait()
        with self._lock:
            self.code = code
            self.ended = time.time()
            self.state = "ok" if code == 0 else ("cancelled" if self.state == "cancelling" else "failed")

    def cancel(self):
        with self._lock:
            if self.proc.poll() is None:
                self.state = "cancelling"
                try:
                    os.killpg(self.proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def public(self, since: int | None = None) -> dict:
        with self._lock:
            return self._public(since)

    def _public(self, since: int | None = None) -> dict:
        start = max(0, self.seq - len(self.lines))
        lines = list(self.lines)
        if since is not None:
            lines = lines[max(0, since - start):]
        return {"kind": self.kind, "scenes": self.scenes, "state": self.state, "started": self.started,
                "ended": self.ended, "code": self.code, "seq": self.seq, "lines": lines if since is not None else lines[-40:]}


class JobRunner:
    def __init__(self, kinds, command):
        self.kinds, self.command = tuple(kinds), command
        self.jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, name: str, kind: str, scenes: list[str]) -> Job:
        if kind not in self.kinds:
            raise ValueError(f"kind must be one of {self.kinds}")
        # FastAPI sync handlers run in different threads. Check + launch must
        # be one critical section, including across different runs.
        with self._lock:
            busy = next((j for j in self.jobs.values() if j.state in ("running", "cancelling")), None)
            if busy:
                raise RuntimeError(f"busy: {busy.kind} on {busy.name}")
            job = Job(name, kind, scenes, self.command(name, kind, scenes))
            self.jobs[name] = job
            return job

    def cancel(self, name: str) -> None:
        with self._lock:
            if name in self.jobs:
                self.jobs[name].cancel()
