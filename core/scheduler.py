from __future__ import annotations

import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


NotificationCallback = Callable[[str, str], None]  # (title, body)


@dataclass
class TimerTask:
    """一次性倒计时任务。"""
    id: str
    message: str
    created_at: float
    fire_at: float
    fired: bool = False


@dataclass
class CronTask:
    """循环定时任务。"""
    id: str
    interval_seconds: int
    command: str
    created_at: float
    next_run: float
    last_result: str = ""
    last_run_at: float = 0.0
    run_count: int = 0


@dataclass
class CronResult:
    """单次 cron 执行结果。"""
    id: str
    command: str
    output: str
    exit_code: int
    run_at: float


class Scheduler:
    """后台定时任务调度器。"""

    def __init__(self, notify: NotificationCallback | None = None) -> None:
        self._notify = notify or (lambda title, body: None)
        self._timers: dict[str, TimerTask] = {}
        self._crons: dict[str, CronTask] = {}
        self._cron_results: dict[str, list[CronResult]] = {}  # cron_id -> 最近 N 条结果
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """启动后台调度线程。"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止后台调度线程。"""
        self._running = False

    # --- 倒计时 ---

    def set_timer(self, seconds: int, message: str) -> str:
        """创建倒计时任务，返回任务 ID。"""
        task_id = uuid.uuid4().hex[:8]
        now = time.time()
        task = TimerTask(
            id=task_id,
            message=message,
            created_at=now,
            fire_at=now + seconds,
        )
        with self._lock:
            self._timers[task_id] = task
        return task_id

    def list_timers(self) -> list[dict[str, Any]]:
        """列出所有倒计时任务。"""
        now = time.time()
        with self._lock:
            return [
                {
                    "id": t.id,
                    "message": t.message,
                    "remaining_seconds": max(0, int(t.fire_at - now)),
                    "fired": t.fired,
                }
                for t in self._timers.values()
            ]

    def cancel_timer(self, task_id: str) -> bool:
        """取消倒计时任务。"""
        with self._lock:
            return self._timers.pop(task_id, None) is not None

    # --- Cron ---

    def add_cron(self, interval_seconds: int, command: str) -> str:
        """创建定时执行任务，返回任务 ID。"""
        task_id = uuid.uuid4().hex[:8]
        now = time.time()
        task = CronTask(
            id=task_id,
            interval_seconds=interval_seconds,
            command=command,
            created_at=now,
            next_run=now + interval_seconds,
        )
        with self._lock:
            self._crons[task_id] = task
            self._cron_results[task_id] = []
        return task_id

    def list_crons(self) -> list[dict[str, Any]]:
        """列出所有 cron 任务和最近执行结果。"""
        now = time.time()
        with self._lock:
            result = []
            for t in self._crons.values():
                results = self._cron_results.get(t.id, [])
                last_output = results[-1].output if results else ""
                result.append({
                    "id": t.id,
                    "command": t.command,
                    "interval_seconds": t.interval_seconds,
                    "next_run_in": max(0, int(t.next_run - now)),
                    "run_count": t.run_count,
                    "last_result": last_output,
                })
            return result

    def remove_cron(self, task_id: str) -> bool:
        """取消 cron 任务。"""
        with self._lock:
            self._cron_results.pop(task_id, None)
            return self._crons.pop(task_id, None) is not None

    # --- 后台循环 ---

    def _run_loop(self) -> None:
        """后台调度主循环，每秒检查一次。"""
        while self._running:
            now = time.time()
            self._check_timers(now)
            self._check_crons(now)
            time.sleep(1)

    def _check_timers(self, now: float) -> None:
        """检查到期的倒计时任务。"""
        with self._lock:
            fired = []
            for task in self._timers.values():
                if not task.fired and now >= task.fire_at:
                    task.fired = True
                    fired.append(task)
        for task in fired:
            self._notify("Timer", task.message)

    def _check_crons(self, now: float) -> None:
        """检查到期的 cron 任务。"""
        to_run: list[CronTask] = []
        with self._lock:
            for task in self._crons.values():
                if now >= task.next_run:
                    task.next_run = now + task.interval_seconds
                    task.run_count += 1
                    to_run.append(task)

        for task in to_run:
            self._execute_cron(task)

    def _execute_cron(self, task: CronTask) -> None:
        """执行 cron 命令并记录结果。"""
        try:
            result = subprocess.run(
                task.command, shell=True, capture_output=True, text=True, timeout=60,
            )
            output = (result.stdout + result.stderr).strip() or "[no output]"
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            output = "[timeout: command exceeded 60s]"
            exit_code = -1
        except Exception as exc:
            output = f"[error: {exc}]"
            exit_code = -1

        cron_result = CronResult(
            id=task.id,
            command=task.command,
            output=output,
            exit_code=exit_code,
            run_at=time.time(),
        )
        with self._lock:
            results = self._cron_results.get(task.id, [])
            results.append(cron_result)
            # 只保留最近 20 条结果
            if len(results) > 20:
                self._cron_results[task.id] = results[-20:]
            task.last_result = output
            task.last_run_at = time.time()

        self._notify("Cron", f"[{task.command}]\n{output}")
