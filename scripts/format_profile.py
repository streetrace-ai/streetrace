"""Format a single profile_startup.py JSON result file as Markdown."""

import json
import sys
from pathlib import Path


def _load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _format_single_profile(profile_path: Path, out_md_path: Path) -> None:
    profile = _load_json(profile_path)
    
    lines = []
    lines.append("# ⚡ Startup Performance Profile")
    lines.append("")
    
    # Real startup time
    real_time = profile.get("real_startup_time", -1)
    lines.append("## Real Startup Time")
    lines.append(f"**{real_time:.3f}s**")
    lines.append("")
    
    # Detailed timings
    detailed = profile.get("detailed_timings", {})
    if detailed:
        lines.append("## Detailed Timing Breakdown")
        lines.append("| Phase | Time (s) | Delta (s) |")
        lines.append("|---|---|---|")
        
        # Extract phases in order
        phases = []
        for key in detailed:
            if key.endswith("_total"):
                phase_name = key.replace("_total", "")
                total_time = detailed.get(key, 0)
                delta_time = detailed.get(f"{phase_name}_delta", 0)
                phases.append((phase_name, total_time, delta_time))
        
        # Sort by total time to show execution order
        phases.sort(key=lambda x: x[1])
        
        for phase_name, total_time, delta_time in phases:
            # Format phase name nicely
            display_name = phase_name.replace("_", " ").title()
            lines.append(f"| {display_name} | {total_time:.3f} | {delta_time:.3f} |")
        lines.append("")
    
    # Issues and recommendations
    issues = profile.get("issues_and_recommendations", [])
    lines.append("## Performance Analysis")
    if issues:
        for issue in issues:
            lines.append(f"- {issue}")
    else:
        lines.append("- ✅ No startup performance issues detected!")
    lines.append("")
    
    # Note about comparison
    lines.append("*Note: This is a standalone profile. No comparison with main branch available.*")
    
    out_md = "\n".join(lines)
    with out_md_path.open("w") as f:
        f.write(out_md)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: format_profile.py profile.json out.md", file=sys.stderr)
        sys.exit(1)
    _format_single_profile(Path(sys.argv[1]), Path(sys.argv[2]))