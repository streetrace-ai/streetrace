"""Workloads package for unified agent execution.

This package provides the Workload protocol and WorkloadManager for
unified execution of agents, flows, and other work units.

The key components are:
- Workload: Protocol that all executable units must implement
- WorkloadMetadata: Immutable metadata about a workload definition
- WorkloadDefinition: Abstract base class for compiled workload definitions
- DefinitionLoader: Protocol for loading workload definitions from source files
- DslWorkloadDefinition: Compiled DSL workload definition
- DslDefinitionLoader: Loader for .sr DSL files
- DslWorkload: Runtime workload for DSL-based workflows
- YamlWorkloadDefinition: Parsed YAML workload definition
- YamlDefinitionLoader: Loader for .yaml/.yml files
- PythonWorkloadDefinition: Python module workload definition
- PythonDefinitionLoader: Loader for Python agent directories
- BasicAgentWorkload: Workload wrapper for Python and YAML agents
- WorkloadManager: Discovers, loads, and creates runnable workloads
"""

from streetrace.workloads.basic_workload import BasicAgentWorkload
from streetrace.workloads.definition import WorkloadDefinition
from streetrace.workloads.dsl_definition import DslWorkloadDefinition
from streetrace.workloads.dsl_loader import DslDefinitionLoader
from streetrace.workloads.dsl_workload import DslWorkload
from streetrace.workloads.loader import DefinitionLoader
from streetrace.workloads.manager import WorkloadManager, WorkloadNotFoundError
from streetrace.workloads.metadata import WorkloadMetadata
from streetrace.workloads.protocol import Workload
from streetrace.workloads.python_definition import PythonWorkloadDefinition
from streetrace.workloads.python_loader import PythonDefinitionLoader
from streetrace.workloads.yaml_definition import YamlWorkloadDefinition
from streetrace.workloads.yaml_loader import YamlDefinitionLoader

__all__ = [
    "BasicAgentWorkload",
    "DefinitionLoader",
    "DslDefinitionLoader",
    "DslWorkload",
    "DslWorkloadDefinition",
    "PythonDefinitionLoader",
    "PythonWorkloadDefinition",
    "Workload",
    "WorkloadDefinition",
    "WorkloadManager",
    "WorkloadMetadata",
    "WorkloadNotFoundError",
    "YamlDefinitionLoader",
    "YamlWorkloadDefinition",
]
