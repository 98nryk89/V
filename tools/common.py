"""検証スクリプト共通: 結果の収集と表示。"""
from __future__ import annotations

from dataclasses import dataclass, field

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


@dataclass
class Report:
    title: str
    items: list[tuple[str, str]] = field(default_factory=list)

    def ok(self, msg: str) -> None:
        self.items.append((PASS, msg))

    def warn(self, msg: str) -> None:
        self.items.append((WARN, msg))

    def fail(self, msg: str) -> None:
        self.items.append((FAIL, msg))

    def count(self, level: str) -> int:
        return sum(1 for lv, _ in self.items if lv == level)

    @property
    def passed(self) -> bool:
        return self.count(FAIL) == 0

    def render(self) -> str:
        lines = [f"== {self.title} =="]
        lines += [f"[{lv}] {msg}" for lv, msg in self.items]
        verdict = "合格" if self.passed else "不合格"
        lines.append(
            f"-- {verdict}  (FAIL {self.count(FAIL)} / WARN {self.count(WARN)} / PASS {self.count(PASS)})"
        )
        return "\n".join(lines)
