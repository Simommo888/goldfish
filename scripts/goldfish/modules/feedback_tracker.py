"""Feedback report generation for improving the agent over time."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from .storage import save_markdown
from .utils import kb_root


def feedback_report_path(date_text: str, root: Path | None = None) -> Path:
    root = root or kb_root()
    return root / "04_Resources" / "AI-News" / "Reports" / f"AI情报反馈-{date_text}.md"


def generate_feedback_report(date_text: str, insights: List[Dict], limit: int = 10) -> str:
    if not insights:
        body = "- 今日暂无高分候选；可以手动记录想调整的偏好。"
    else:
        blocks = []
        for index, insight in enumerate(insights[:limit], start=1):
            blocks.append(
                f"""### {index}. {insight['title']}

- 来源：{insight['source']}
- 链接：{insight['url'] or '无'}
- 分类：{insight['category']}
- 建议类型：{insight['target_label']}

反馈：

- [ ] 值得沉淀
- [ ] 可做项目
- [ ] 有商业价值
- [ ] 类似内容以后多推荐
- [ ] 类似内容以后少推荐
"""
            )
        body = "\n".join(blocks)
    return f"""# AI 情报反馈 - {date_text}

> 勾选这份反馈表后，后续可以让 Agent 读取你的偏好，逐步更懂你。第一版先生成反馈入口，后续再接入自动学习。

{body}
"""


def write_feedback_report(date_text: str, insights: List[Dict], root: Path | None = None, limit: int = 10) -> Path:
    root = root or kb_root()
    return save_markdown(feedback_report_path(date_text, root), generate_feedback_report(date_text, insights, limit))


def read_feedback_reports(root: Path | None = None) -> List[Dict[str, str]]:
    root = root or kb_root()
    reports_dir = root / "04_Resources" / "AI-News" / "Reports"
    if not reports_dir.exists():
        return []
    feedback = []
    for path in sorted(reports_dir.glob("AI情报反馈-*.md")):
        content = path.read_text(encoding="utf-8", errors="replace")
        checked = re.findall(r"- \[x\] (.+)", content, flags=re.I)
        if checked:
            feedback.append({"path": str(path), "checked": "；".join(checked)})
    return feedback
