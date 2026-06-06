"""Surface 日志记录器 — 记录真实对话中的 Surface 数据用于后处理分析。

嵌入 main.py 的 _consume_surface 中，每轮记录：
- 11 维人格参数
- 决策 action
- 价值抵抗结果
- 良心压力
- 安全层级别

输出: CSV，用于后处理分析。

隐私处理：
- session_id 默认做 SHA256 单向哈希（可通过 anonymize=False 关闭）
- 自动清理超过 max_age_days 天的旧日志文件
"""

from __future__ import annotations

import csv
import hashlib
import time
from pathlib import Path
from typing import Any


class SurfaceLogger:
    """记录真实对话中的 Surface 数据。"""

    def __init__(
        self,
        output_dir: str = "output/surface_logs",
        anonymize: bool = True,
        max_age_days: int = 7,
    ) -> None:
        self._dir = Path(output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._anonymize = anonymize
        self._max_age_days = max_age_days
        self._filepath = self._dir / f"surface_log_{int(time.time())}.csv"
        self._header_written = False
        self._fieldnames = [
            "timestamp", "session_id", "turn",
            # 12 维人格 (v1.7: 11→12)
            "expression_drive", "perception_acuity", "boundary_permeability",
            "inner_coherence", "relational_gravity",
            "warmth_bias", "directness", "curiosity",
            "patience", "intimacy_pull",
            "relational_autonomy", "exploration_openness",  # v1.7: autonomy_guard 拆分
            # Surface 关键信号
            "action", "phi_smoothed", "body_criticality", "cascade_active",
            "guard_allowed", "guard_risk_score",
            # 价值抵抗
            "resistance", "tension_type", "conflict_values", "aligned_values",
            # 良心
            "pressure", "alignment_score",
            # 安全层
            "safety_level",
        ]
        # 启动时清理旧日志
        self._cleanup_old_logs()

    def _anonymize_session(self, session_id: str) -> str:
        """单向哈希 session_id，不存储原始值。"""
        return hashlib.sha256(session_id.encode()).hexdigest()[:12]

    def _cleanup_old_logs(self) -> None:
        """删除超过 max_age_days 的日志文件。"""
        cutoff = time.time() - self._max_age_days * 86400
        for f in self._dir.glob("surface_log_*.csv"):
            if f.stat().st_mtime < cutoff:
                f.unlink()

    def log(
        self,
        session_id: str,
        turn: int,
        personality: dict[str, dict[str, float]],
        action: str,
        resistance: float = 0.0,
        tension_type: str = "",
        conflict_values: list[str] | None = None,
        aligned_values: list[str] | None = None,
        pressure: float = 0.0,
        alignment_score: float = 0.5,
        safety_level: str = "normal",
        phi_smoothed: float = 0.0,
        body_criticality: float = 0.0,
        cascade_active: bool = False,
        guard_allowed: bool = True,
        guard_risk_score: float = 0.0,
    ) -> None:
        """记录一轮 Surface 数据。"""
        sid = self._anonymize_session(session_id) if self._anonymize else session_id[:8]

        row = {
            "timestamp": time.time(),
            "session_id": sid,
            "turn": turn,
            "expression_drive": personality.get("deep", {}).get("expression_drive", 0.5),
            "perception_acuity": personality.get("deep", {}).get("perception_acuity", 0.5),
            "boundary_permeability": personality.get("deep", {}).get("boundary_permeability", 0.5),
            "inner_coherence": personality.get("deep", {}).get("inner_coherence", 0.5),
            "relational_gravity": personality.get("deep", {}).get("relational_gravity", 0.5),
            "warmth_bias": personality.get("surface", {}).get("warmth_bias", 0.5),
            "directness": personality.get("surface", {}).get("directness", 0.5),
            "curiosity": personality.get("surface", {}).get("curiosity", 0.5),
            "patience": personality.get("surface", {}).get("patience", 0.5),
            "intimacy_pull": personality.get("surface", {}).get("intimacy_pull", 0.5),
            # v1.7: autonomy_guard 拆分为 2 维
            "relational_autonomy": personality.get("surface", {}).get("relational_autonomy", 0.5),
            "exploration_openness": personality.get("surface", {}).get("exploration_openness", 0.5),
            "action": action,
            "phi_smoothed": phi_smoothed,
            "body_criticality": body_criticality,
            "cascade_active": cascade_active,
            "guard_allowed": guard_allowed,
            "guard_risk_score": guard_risk_score,
            "resistance": resistance,
            "tension_type": tension_type,
            "conflict_values": ";".join(conflict_values or []),
            "aligned_values": ";".join(aligned_values or []),
            "pressure": pressure,
            "alignment_score": alignment_score,
            "safety_level": safety_level,
        }

        with open(self._filepath, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self._fieldnames)
            if not self._header_written:
                writer.writeheader()
                self._header_written = True
            writer.writerow(row)
