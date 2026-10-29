"""Loopback review application factory. Consumers add their own document routes.

Call mount_ui after adding routes so the static catch-all stays last.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .jobs import JobRunner


def guard(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except KeyError as e:
        raise HTTPException(404, f"not found: {e}")
    except ValueError as e:
        raise HTTPException(422, str(e))


def create_app(*, title: str, runs: Path, marker: str, review, kinds, command, watch) -> FastAPI:
    runs = runs.resolve()
    app = FastAPI(title=title)
    runner = JobRunner(kinds, command)

    def run_dir(name: str) -> Path:
        d = (runs / name).resolve()
        if d.parent != runs or not d.is_dir() or not (d / marker).exists():
            raise HTTPException(404, f"no run {name}")
        return d

    @app.post("/api/runs/{name}/comments")
    def post_comment(name: str, body: dict = Body(...)):
        if not (body.get("text") or "").strip():
            raise HTTPException(422, "text is required")
        return guard(review.add_comment, run_dir(name), body["text"], t=body.get("t"), key=body.get("key"),
                     anchor=body.get("anchor"), region=body.get("region"), author=body.get("author", "reviewer"))

    @app.patch("/api/runs/{name}/comments/{cid}")
    def patch_comment(name: str, cid: str, body: dict = Body(...)):
        return guard(review.update_comment, run_dir(name), cid, status=body.get("status"), reply=body.get("reply"),
                     author=body.get("author", "reviewer"), text=body.get("text"))

    @app.delete("/api/runs/{name}/comments/{cid}")
    def del_comment(name: str, cid: str):
        review.delete_comment(run_dir(name), cid)
        return {"ok": True}

    @app.post("/api/runs/{name}/decisions")
    def post_decision(name: str, body: dict = Body(...)):
        return guard(review.add_decision, run_dir(name), body.get("scope", "run"), body.get("key"), body.get("decision", ""),
                     body.get("note", ""), author=body.get("author", "reviewer"))

    @app.post("/api/runs/{name}/status")
    def post_status(name: str, body: dict = Body(...)):
        guard(review.set_status, run_dir(name), body.get("status", ""))
        return {"ok": True}

    @app.post("/api/runs/{name}/jobs")
    def start_job(name: str, body: dict = Body(...)):
        run_dir(name)
        try:
            return runner.start(name, body.get("kind"),
                                [s for s in body.get("scenes", []) if isinstance(s, str)]).public()
        except ValueError as e:
            raise HTTPException(422, str(e))
        except RuntimeError as e:
            raise HTTPException(409, str(e))

    @app.post("/api/runs/{name}/jobs/cancel")
    def cancel_job(name: str):
        runner.cancel(name)
        return {"ok": True}

    @app.get("/api/runs/{name}/events")
    async def events(name: str, request: Request):
        d = run_dir(name)

        async def stream():
            fp = watch(d)
            previous_job = runner.jobs.get(name)
            seq = previous_job.seq if previous_job else 0
            job_state = runner.jobs[name].state if name in runner.jobs else None
            yield "retry: 2000\n\n"
            while not await request.is_disconnected():
                job = runner.jobs.get(name)
                replaced = job is not previous_job
                if replaced:
                    seq = 0
                    previous_job = job
                if job and (replaced or job.seq != seq or job.state != job_state):
                    payload = job.public(since=seq)
                    seq, job_state = job.seq, job.state
                    yield f"event: job\ndata: {json.dumps(payload)}\n\n"
                new_fp = watch(d)
                if new_fp != fp:
                    fp = new_fp
                    yield "event: changed\ndata: {}\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"cache-control": "no-cache"})

    @app.get("/files/{name}/{path:path}")
    def run_file(name: str, path: str):
        d = run_dir(name)
        f = (d / path).resolve()
        if not str(f).startswith(str(d) + os.sep) or not f.is_file():
            raise HTTPException(404)
        return FileResponse(f, headers={"cache-control": "no-cache"})

    app.state.run_dir = run_dir
    app.state.runner = runner
    return app


def mount_ui(app: FastAPI, ui: Path, node_modules: Path | None = None) -> None:
    if node_modules is not None:
        app.mount("/nm", StaticFiles(directory=node_modules), name="nm")
    app.mount("/", StaticFiles(directory=ui, html=True), name="ui")


def serve(app: FastAPI, port: int) -> None:
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
