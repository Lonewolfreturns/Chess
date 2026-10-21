"""A tiny coroutine animation runner.

Animation scripts are Python generators. They can yield:
  * a number          -> wait that many seconds
  * a Tween           -> wait until the tween finishes
  * a list of Tweens  -> run them in parallel and wait for all
  * None              -> wait one frame
"""
from __future__ import annotations

import math
from typing import Callable


def linear(t):
    return t


def ease_in_out(t):
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_in(t):
    return t * t * t


def ease_out_back(t, s=1.70158):
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def ease_out_elastic(t):
    if t in (0, 1):
        return t
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi / 3)) + 1


class Tween:
    def __init__(self, duration: float, update: Callable[[float], None], ease=ease_in_out,
                 on_done: Callable[[], None] | None = None):
        self.duration = max(0.0001, duration)
        self.update = update
        self.ease = ease
        self.on_done = on_done
        self.elapsed = 0.0
        self.done = False

    def step(self, dt: float):
        if self.done:
            return
        self.elapsed += dt
        t = min(1.0, self.elapsed / self.duration)
        self.update(self.ease(t))
        if t >= 1.0:
            self.done = True
            if self.on_done:
                self.on_done()

    def finish(self):
        if not self.done:
            self.update(self.ease(1.0))
            self.done = True
            if self.on_done:
                self.on_done()


class Task:
    def __init__(self, gen, on_done=None):
        self.gen = gen
        self.on_done = on_done
        self.wait = 0.0
        self.tweens: list[Tween] = []
        self.done = False


class Animator:
    def __init__(self):
        self.tasks: list[Task] = []
        self.speed = 1.0

    @property
    def busy(self) -> bool:
        return bool(self.tasks)

    def run(self, gen, on_done=None) -> Task:
        task = Task(gen, on_done)
        self.tasks.append(task)
        self._advance(task, 0.0)
        return task

    def step(self, dt: float):
        dt *= self.speed
        for task in list(self.tasks):
            if task.done:
                continue
            if task.tweens:
                for tw in task.tweens:
                    tw.step(dt)
                task.tweens = [tw for tw in task.tweens if not tw.done]
                if task.tweens:
                    continue
            if task.wait > 0:
                task.wait -= dt
                if task.wait > 0:
                    continue
            self._advance(task, dt)

    def _advance(self, task: Task, dt: float):
        while True:
            try:
                y = next(task.gen)
            except StopIteration:
                self._finish(task)
                return
            except Exception:
                self._finish(task)
                raise
            if y is None:
                return
            if isinstance(y, (int, float)):
                if y > 0:
                    task.wait = float(y)
                    return
                continue
            tweens = y if isinstance(y, (list, tuple)) else [y]
            tweens = [tw for tw in tweens if isinstance(tw, Tween) and not tw.done]
            if tweens:
                task.tweens = tweens
                for tw in tweens:
                    tw.step(0.0)
                return

    def _finish(self, task: Task):
        task.done = True
        if task in self.tasks:
            self.tasks.remove(task)
        if task.on_done:
            task.on_done()

    def cancel_all(self):
        """Stop every running script (callers resync the scene afterwards)."""
        tasks, self.tasks = self.tasks, []
        for task in tasks:
            for tw in task.tweens:
                tw.done = True
            try:
                task.gen.close()
            except Exception:
                pass
            task.done = True
