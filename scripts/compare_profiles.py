"""Diff two profile_startup.py JSON result files and emit a Markdown summary."""

import json
import sys
from pathlib import Path


def _load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _format_delta(old: float, new: float, threshold: float = 0.01) -> str:
    if old < 0 and new >= 0:
        return f"🆕 {new:.3f}s (new measurement)"
    if abs(new - old) < threshold:
        return f"{new:.3f}s (no significant change)"
    # Improve or regress
    direction = "⬇️ improved" if new < old else "⬆️ regression"
    diff = new - old
    sign = "+" if diff > 0 else "-"
    return f"{new:.3f}s ({sign}{abs(diff):.3f}s {direction})"


def _compare_profiles(main_path: Path, pr_path: Path, out_md_path: Path) -> None:
    main = _load_json(main_path)
    pr = _load_json(pr_path)

    lines = []
    lines.append("# ⚡ Startup Performance Comparison")
    lines.append("")

    # Real startup time
    main_rt = main.get("real_startup_time", -1)
    pr_rt = pr.get("real_startup_time", -1)
    lines.append("## Real Startup Time\n| Version | Time (s) |")
    lines.append("|---|---|")
    lines.append(f"| main | {main_rt:.3f} |")
    lines.append(f"| PR   | {pr_rt:.3f} |")
    lines.append(f"|      | {_format_delta(main_rt, pr_rt)} |")
    lines.append("")

    # Detailed timings
    main_det = main.get("detailed_timings", {})
    pr_det = pr.get("detailed_timings", {})
    all_keys = sorted(set(main_det.keys()) | set(pr_det.keys()))
    lines.append("## Detailed Timing Breakdown\n| Phase | main | PR | Δ |")
    lines.append("|---|---|---|---|")
    for k in all_keys:
        if not k.endswith("_delta"):
            continue
        main_v = main_det.get(k, -1)
        pr_v = pr_det.get(k, -1)
        delta = _format_delta(main_v, pr_v)
        phase = k.replace("_delta", "").replace("_", " ").title()
        lines.append(f"| {phase} | {main_v:.3f} | {pr_v:.3f} | {delta} |")
    lines.append("")

    # Issues and recs
    pr_issues = pr.get("issues_and_recommendations", [])
    lines.append("## Issues and Recommendations (for PR)")
    if pr_issues:
        lines.extend(f"- {issue}" for issue in pr_issues)
    else:
        lines.append("- ✅ No startup performance issues detected on PR!")

    out_md = "\n".join(lines)
    with out_md_path.open("w") as f:
        f.write(out_md)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: compare_profiles.py main.json pr.json out.md", file=sys.stderr)
        sys.exit(1)
    _compare_profiles(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
