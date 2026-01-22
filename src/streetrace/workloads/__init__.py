"""Workloads package for unified agent execution.

This package provides the Workload protocol and WorkloadManager for
unified execution of agents, flows, and other work units.

The key components are:
- Workload: Protocol that all executable units must implement
- BasicAgentWorkload: Workload wrapper for Python and YAML agents
- WorkloadManager: Discovers, loads, and creates runnable workloads
"""

from streetrace.workloads.basic_workload import BasicAgentWorkload
from streetrace.workloads.manager import WorkloadManager
from streetrace.workloads.protocol import Workload

__all__ = [
    "BasicAgentWorkload",
    "Workload",
    "WorkloadManager",
]
