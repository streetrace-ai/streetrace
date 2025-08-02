"""Standalone startup performance profiler for StreetRace.

This script provides detailed analysis of application startup performance,
identifying bottlenecks and providing actionable recommendations.

Usage:
    python scripts/profile_startup.py
    python scripts/profile_startup.py --json  # Output as JSON
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


class StartupProfiler:
    """Detailed startup profiling with bottleneck identification."""

    def __init__(self):
        """Initialize the profiler."""
        self.profile_data: list[tuple[str, float]] = []
        self.start_time = time.perf_counter()

    def checkpoint(self, name: str):
        """Record a timing checkpoint."""
        current_time = time.perf_counter()
        elapsed = current_time - self.start_time
        self.profile_data.append((name, elapsed))

    def get_report(self) -> dict[str, float]:
        """Get a performance report showing time deltas."""
        report = {}
        prev_time = 0.0

        for name, total_time in self.profile_data:
            delta = total_time - prev_time
            report[f"{name}_total"] = total_time
            report[f"{name}_delta"] = delta
            prev_time = total_time

        return report

    def analyze_bottlenecks(self, report: dict[str, float]) -> list[str]:
        """Analyze the report and identify performance bottlenecks."""
        issues = []
        recommendations = []

        # Check commands import time
        commands_time = report.get("commands_import_delta", 0)
        if commands_time > 0.5:  # 500ms threshold
            issues.append(
                f"🚨 CRITICAL: Commands import took {commands_time:.3f}s (>0.5s)",
            )
            recommendations.append(
                "Commands are importing Google ADK at module level. "
                "Apply TYPE_CHECKING optimization.",
            )
        elif commands_time > 0.1:  # 100ms threshold
            issues.append(
                f"⚠️  WARNING: Commands import took {commands_time:.3f}s (>0.1s)",
            )
            recommendations.append(
                "Commands import is slower than expected. "
                "Check for heavy imports in streetrace/commands/definitions/",
            )

        # Check total startup time
        total_time = report.get("app_created_total", 0)
        if total_time > 2.0:  # 2 second threshold
            issues.append(
                f"🚨 CRITICAL: Total startup took {total_time:.3f}s (>2.0s)",
            )
            recommendations.append(
                "Startup time is unacceptably slow. Focus on the largest time deltas.",
            )
        elif total_time > 1.0:  # 1 second threshold
            issues.append(
                f"⚠️  WARNING: Total startup took {total_time:.3f}s (>1.0s)",
            )
            recommendations.append(
                "Startup time is slower than target. Consider lazy loading deps.",
            )

        # Check app import time specifically
        app_import_time = report.get("app_import_delta", 0)
        if app_import_time > 0.5:
            issues.append(
                f"🚨 CRITICAL: App import took {app_import_time:.3f}s (>0.5s)",
            )
            recommendations.append(
                "App import is very slow. Check for expensive imports.",
            )

        # Check basic imports
        basic_imports_time = report.get("basic_imports_delta", 0)
        if basic_imports_time > 0.05:  # 50ms threshold
            issues.append(
                f"⚠️  WARNING: Basic imports took {basic_imports_time:.3f}s (>0.05s)",
            )
            recommendations.append(
                "Basic imports are slower than expected. "
                "Check args.py and log.py for heavy dependencies.",
            )

        return issues + recommendations


def profile_detailed_startup() -> dict:
    """Run detailed startup profiling."""
    profiler = StartupProfiler()

    # Clear module cache for clean measurement
    profiler.checkpoint("start")

    import sys

    modules_to_clear = [name for name in sys.modules if name.startswith("streetrace.")]
    for module_name in modules_to_clear:
        if module_name in sys.modules:
            del sys.modules[module_name]

    profiler.checkpoint("cache_cleared")

    # Phase 1: Basic imports
    from streetrace.args import Args

    profiler.checkpoint("basic_imports")

    # Phase 2: App import (triggers most of the import chain)
    from streetrace.app import create_app

    profiler.checkpoint("app_import")

    # Phase 3: Heavy command imports
    profiler.checkpoint("commands_import")

    # Phase 4: Agent manager (previously expensive)
    profiler.checkpoint("agent_manager_import")

    # Phase 5: App creation
    from pathlib import Path

    args = Args(
        path=Path.cwd(),
        model="default",
        list_sessions=False,
        prompt=None,
        arbitrary_prompt=None,
        version=False,
    )
    profiler.checkpoint("args_created")

    _ = create_app(args)
    profiler.checkpoint("app_created")

    return profiler.get_report()


def measure_real_startup() -> float:
    """Measure real startup time using subprocess."""
    start_time = time.perf_counter()

    # Try multiple ways to run streetrace
    commands_to_try = [
        [sys.executable, "-m", "streetrace", "--version"],
        ["poetry", "run", "streetrace", "--version"],
        ["streetrace", "--version"],
    ]

    result = None
    for cmd in commands_to_try:
        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                check=False,
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
                timeout=30,
            )
            if result.returncode == 0:
                break
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    end_time = time.perf_counter()

    if not result or result.returncode != 0:
        error_msg = result.stderr if result else "No command succeeded"
        print(f"⚠️  Warning: streetrace command failed: {error_msg}")
        return -1

    return end_time - start_time


def main():
    """Run Streetrace startup profiling."""
    parser = argparse.ArgumentParser(
        description="Profile StreetRace startup performance",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--save", type=str, help="Save results to file")
    args = parser.parse_args()

    print("🔍 Profiling StreetRace startup performance...\n")

    # Measure real startup time
    print("📊 Measuring real startup time...")
    real_startup_time = measure_real_startup()

    # Run detailed profiling
    print("🔬 Running detailed import profiling...")
    detailed_report = profile_detailed_startup()

    # Analyze bottlenecks
    profiler = StartupProfiler()
    issues = profiler.analyze_bottlenecks(detailed_report)

    # Prepare results
    results = {
        "real_startup_time": real_startup_time,
        "detailed_timings": detailed_report,
        "issues_and_recommendations": issues,
        "timestamp": time.time(),
    }

    if args.json:
        json_output = json.dumps(results, indent=2)
        if args.save:
            Path(args.save).write_text(json_output)
        else:
            print(json_output)
        return

    # Human-readable output
    print("\n" + "=" * 60)
    print("🚀 STARTUP PERFORMANCE REPORT")
    print("=" * 60 + "\n")

    if real_startup_time > 0:
        print(f"⏱️  **Real startup time**: {real_startup_time:.3f}s")
    else:
        print("⏱️  **Real startup time**: Could not measure (command failed)")

    print("\n📋 **Detailed timing breakdown**:")
    for name, total_time in detailed_report.items():
        if name.endswith("_delta"):
            phase_name = name.replace("_delta", "").replace("_", " ").title()
            delta_time = total_time
            print(f"   • {phase_name:<25}: {delta_time:>8.3f}s")

    print()
    if issues:
        print("🚨 **Issues and Recommendations**:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    else:
        print("✅ **No performance issues detected!**")
        print("   Startup performance is within acceptable thresholds.")

    print("\n💡 **General optimization tips**:")
    print("   • Use TYPE_CHECKING for type-only imports from heavy libraries")
    print("   • Move expensive imports inside functions where they're used")
    print("   • Consider lazy loading for optional functionality")
    print("   • Profile imports with: python -X importtime -m streetrace --version")

    # Save results if requested
    if args.save:
        save_path = Path(args.save)
        with save_path.open("w") as f:
            json.dump(results, f, indent=2)
        print(f"📁 Results saved to: {save_path}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
