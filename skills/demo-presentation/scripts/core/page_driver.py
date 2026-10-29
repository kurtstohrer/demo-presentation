"""Playwright page actions independent of recording, scenes and narration (async API).

The Python twin of page-driver.mjs: the same action vocabulary and timing, for
consumers that drive Playwright from Python.
"""

from __future__ import annotations

import asyncio
import math
import re


class PageDriver:
    def __init__(self, page, *, viewport: dict, speed: float = 1, base_url: str = "", overlay: str = "__reviewOverlay"):
        self.page = page
        self.speed = speed
        self.base_url = base_url
        self.overlay = overlay
        self.cur = (viewport["width"] / 2, viewport["height"] / 2)

    def t(self, ms: float) -> float:
        """Seconds to sleep for `ms` of authored time."""
        return ms / self.speed / 1000

    async def sleep(self, ms: float) -> None:
        await asyncio.sleep(max(0.0, self.t(ms)))

    async def show(self, method: str, args: list | None = None):
        return await self.page.evaluate(
            "([name, method, args]) => window[name]?.[method]?.(...args)", [self.overlay, method, args or []])

    def resolve_url(self, u: str) -> str:
        return u if re.match(r"^[a-z][a-z0-9+.-]*:", u, re.I) else self.base_url.rstrip("/") + u

    async def target(self, sel):
        if isinstance(sel, dict) and "x" in sel:
            return sel["x"], sel["y"], None
        loc = self.page.locator(sel).first
        await loc.wait_for(state="visible", timeout=15000)
        await loc.scroll_into_view_if_needed()
        box = await loc.bounding_box()
        return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, box

    async def move_to(self, x: float, y: float, ms: float = 650) -> None:
        dist = math.hypot(x - self.cur[0], y - self.cur[1])
        dur = round(min(ms, 250 + dist * 0.5))
        await self.show("move", [x, y, dur / self.speed])
        await self.page.mouse.move(x, y, steps=max(2, round(dur / 40)))
        await self.sleep(dur)
        self.cur = (x, y)

    async def click(self, sel, count: int = 1, button: str = "left") -> None:
        x, y, _ = await self.target(sel)
        await self.move_to(x, y)
        await self.sleep(120)
        await self.show("ripple")
        await self.page.mouse.click(x, y, click_count=count, button=button)
        await self.sleep(350)

    async def apply(self, action: dict) -> None:
        key = next((k for k in action if hasattr(self, f"a_{k}")), None)
        if not key:
            raise ValueError(f"unknown ui action: {action}")
        await getattr(self, f"a_{key}")(action[key], action)

    # ---- actions: a_<name>(value, action)
    async def a_goto(self, url, a):
        await self.page.goto(self.resolve_url(url), wait_until="domcontentloaded")
        await self.show("move", [-200, -200, 0])

    async def a_waitFor(self, sel, a):  # `timeout` (ms) on the action raises the 2-minute default
        await self.page.locator(sel).first.wait_for(state="visible", timeout=a.get("timeout") or 120000)

    async def a_waitForFunction(self, expr, a):
        await self.page.wait_for_function(expr, timeout=a.get("timeout") or 120000, polling=a.get("polling") or 250)

    async def a_click(self, sel, a):
        await self.click(sel, a.get("count") or 1, a.get("button") or "left")

    async def a_dblclick(self, sel, a):
        await self.click(sel, count=2)

    async def a_rightClick(self, sel, a):
        await self.click(sel, button="right")

    async def a_hover(self, sel, a):
        x, y, _ = await self.target(sel)
        await self.move_to(x, y)
        await self.sleep(300)

    async def a_move(self, pt, a):
        await self.move_to(pt["x"], pt["y"], pt.get("ms") or 650)

    async def a_fill(self, spec, a):
        await self.click(spec["selector"])
        if spec.get("clear") is not False:
            await self.page.keyboard.press("ControlOrMeta+a")
            await self.page.keyboard.press("Backspace")
        await self.page.keyboard.type(spec["text"], delay=self.t(spec.get("delay", 55)) * 1000)
        await self.sleep(250)

    async def a_type(self, text, a):
        await self.page.keyboard.type(text, delay=self.t(a.get("delay", 55)) * 1000)

    async def a_press(self, key, a):
        await self.page.keyboard.press(key)
        await self.sleep(300)

    async def a_keyDown(self, key, a):
        await self.page.keyboard.down(key)

    async def a_keyUp(self, key, a):
        await self.page.keyboard.up(key)

    async def a_scroll(self, spec, a):
        if spec.get("selector"):
            x, y, _ = await self.target(spec["selector"])
            await self.move_to(x, y)
        steps = 12
        for _ in range(steps):
            await self.page.mouse.wheel(0, (spec.get("y") or 0) / steps)
            await self.sleep(30)
        await self.sleep(300)

    async def a_drag(self, spec, a):
        ax, ay, _ = await self.target(spec["from"])
        if spec.get("to"):
            bx, by, _ = await self.target(spec["to"])
        else:
            bx, by = ax + (spec.get("dx") or 0), ay + (spec.get("dy") or 0)
        await self.move_to(ax, ay)
        await self.page.mouse.down()
        n = 24
        for i in range(1, n + 1):
            x, y = ax + (bx - ax) * i / n, ay + (by - ay) * i / n
            await self.page.mouse.move(x, y)
            await self.show("move", [x, y, 0])
            await self.sleep(spec.get("ms", 900) / n)
        await self.page.mouse.up()
        self.cur = (bx, by)

    async def a_spotlight(self, spec, a):
        s = {"selector": spec} if isinstance(spec, str) else spec
        _, _, box = await self.target(s["selector"])
        await self.show("spotlight", [box, s.get("text") or ""])
        await self.sleep(s.get("ms", 1200))
        if not s.get("keep"):
            await self.show("clearSpotlight")

    async def a_clearSpotlight(self, value, a):
        await self.show("clearSpotlight")

    async def a_chapter(self, spec, a):
        s = {"title": spec} if isinstance(spec, str) else spec
        await self.show("chapter", [s["title"], s.get("description") or ""])
        await self.sleep(s.get("ms", 1800))
        await self.show("clearChapter")

    async def a_eval(self, js, a):
        await self.page.evaluate(js)

    async def a_wait(self, ms, a):
        await self.sleep(float(ms))

    async def a_screenshot(self, value, a):
        pass
