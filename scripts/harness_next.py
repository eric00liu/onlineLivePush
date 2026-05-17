#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BACKLOG = ROOT / ".harness" / "BACKLOG.md"
STATE = ROOT / ".harness" / "STATE.md"


def main() -> int:
    backlog = BACKLOG.read_text(encoding="utf-8").splitlines()
    candidates = collect_candidates(backlog)
    selected = select_candidate(candidates)
    if selected is None:
        print("No open or in-progress backlog tasks found.")
        return 0

    print(f"Priority: {selected['priority']}")
    print(f"Status: {selected['status_label']}")
    print(f"Task: {selected['task_id']}")
    details = selected["details"]
    if details:
        print()
        print("\n".join(details))
    print()
    print("Resume prompt:")
    print("继续执行 .harness/RUNBOOK.md。先执行 Decomposition Gate，必要时把当前进行中或下一个 P0/P1 任务拆成更小任务；然后完成一个具体任务切片。完成后更新 STATE、BACKLOG、DECISIONS，并运行 dev_check。")
    return 0


def collect_candidates(lines: list[str]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    current_priority = ""
    for index, line in enumerate(lines):
        if line.startswith("## "):
            current_priority = line.removeprefix("## ").strip()
            continue
        stripped = line.strip()
        status_label = task_status(stripped)
        if status_label is None:
            continue
        task_id = stripped.split("`", 2)[1]
        candidates.append(
            {
                "priority": current_priority,
                "status_label": status_label,
                "task_id": task_id,
                "details": collect_details(lines, index + 1),
            }
        )
    return candidates


def task_status(stripped: str) -> str | None:
    if stripped.startswith("- [~] `"):
        return "in progress"
    if stripped.startswith("- [ ] `"):
        return "open"
    return None


def select_candidate(candidates: list[dict[str, object]]) -> dict[str, object] | None:
    priority_rank = {"P0": 0, "P1": 1}
    relevant = [
        task for task in candidates if priority_rank.get(str(task["priority"]), 99) <= 1
    ]
    pool = relevant or candidates
    for status_label in ("in progress", "open"):
        for task in pool:
            if task["status_label"] == status_label:
                return task
    return None


def collect_details(lines: list[str], start: int) -> list[str]:
    details: list[str] = []
    for line in lines[start:]:
        if line.startswith("## ") or line.strip().startswith("- ["):
            break
        if line.strip():
            details.append(line)
    return details


if __name__ == "__main__":
    raise SystemExit(main())
