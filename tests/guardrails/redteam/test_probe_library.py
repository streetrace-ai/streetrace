"""Tests for probe library YAML loading, validation, and filtering."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from streetrace.guardrails.redteam.probe_library import (
    ProbeCategory,
    ProbeDefinition,
    ProbeLibrary,
)
from streetrace.guardrails.types import GuardrailAction


class TestProbeDefinition:
    """Verify ProbeDefinition Pydantic model validation."""

    def test_valid_probe(self) -> None:
        probe = ProbeDefinition(
            name="test-probe",
            description="A test probe",
            category=ProbeCategory.INJECTION,
            attack_strings=["attack1", "attack2"],
            expected_action=GuardrailAction.BLOCK,
        )
        assert probe.name == "test-probe"
        assert probe.category == ProbeCategory.INJECTION
        assert len(probe.attack_strings) == 2
        assert probe.expected_action == GuardrailAction.BLOCK

    def test_missing_name_raises(self) -> None:
        with pytest.raises(ValueError, match="name"):
            ProbeDefinition(
                name="",
                description="A test probe",
                category=ProbeCategory.INJECTION,
                attack_strings=["attack1"],
                expected_action=GuardrailAction.BLOCK,
            )

    def test_empty_attack_strings_raises(self) -> None:
        with pytest.raises(ValueError, match="attack_strings"):
            ProbeDefinition(
                name="test-probe",
                description="A test probe",
                category=ProbeCategory.INJECTION,
                attack_strings=[],
                expected_action=GuardrailAction.BLOCK,
            )

    def test_all_categories(self) -> None:
        members = {m.value for m in ProbeCategory}
        assert members == {"injection", "drift", "tool_abuse"}

    def test_all_expected_actions(self) -> None:
        for action in [
            GuardrailAction.BLOCK,
            GuardrailAction.WARN,
            GuardrailAction.ALLOW,
        ]:
            probe = ProbeDefinition(
                name="test",
                description="desc",
                category=ProbeCategory.INJECTION,
                attack_strings=["x"],
                expected_action=action,
            )
            assert probe.expected_action == action


class TestProbeLibrary:
    """Verify probe discovery, loading, and filtering."""

    @pytest.fixture
    def probe_dir(self, tmp_path: Path) -> Path:
        """Create a temporary directory with probe YAML files."""
        injection_probe = {
            "name": "sql-injection",
            "description": "SQL injection probe",
            "category": "injection",
            "attack_strings": ["'; DROP TABLE users;--"],
            "expected_action": "block",
        }
        drift_probe = {
            "name": "gradual-escalation",
            "description": "Gradual escalation probe",
            "category": "drift",
            "attack_strings": ["step1", "step2", "step3"],
            "expected_action": "warn",
        }
        tool_probe = {
            "name": "tool-poisoning",
            "description": "Tool poisoning probe",
            "category": "tool_abuse",
            "attack_strings": ["malicious tool desc"],
            "expected_action": "block",
        }
        (tmp_path / "injection.yaml").write_text(yaml.dump(injection_probe))
        (tmp_path / "drift.yaml").write_text(yaml.dump(drift_probe))
        (tmp_path / "tool.yaml").write_text(yaml.dump(tool_probe))
        return tmp_path

    def test_load_directory(self, probe_dir: Path) -> None:
        library = ProbeLibrary()
        library.load_directory(probe_dir)
        probes = library.get_probes()
        assert len(probes) == 3

    def test_get_probes_by_category(self, probe_dir: Path) -> None:
        library = ProbeLibrary()
        library.load_directory(probe_dir)
        injection_probes = library.get_probes(
            category=ProbeCategory.INJECTION,
        )
        assert len(injection_probes) == 1
        assert injection_probes[0].name == "sql-injection"

    def test_get_probes_empty_category(self, probe_dir: Path) -> None:
        library = ProbeLibrary()
        library.load_directory(probe_dir)
        drift_probes = library.get_probes(category=ProbeCategory.DRIFT)
        assert len(drift_probes) == 1

    def test_load_directory_ignores_non_yaml(self, tmp_path: Path) -> None:
        (tmp_path / "readme.txt").write_text("not a probe")
        (tmp_path / "valid.yaml").write_text(
            yaml.dump({
                "name": "valid",
                "description": "valid probe",
                "category": "injection",
                "attack_strings": ["x"],
                "expected_action": "block",
            }),
        )
        library = ProbeLibrary()
        library.load_directory(tmp_path)
        assert len(library.get_probes()) == 1

    def test_load_directory_empty(self, tmp_path: Path) -> None:
        library = ProbeLibrary()
        library.load_directory(tmp_path)
        assert len(library.get_probes()) == 0

    def test_load_directory_nonexistent_raises(self) -> None:
        library = ProbeLibrary()
        with pytest.raises(FileNotFoundError):
            library.load_directory(Path("/nonexistent/path"))

    def test_validate_probe_valid(self) -> None:
        library = ProbeLibrary()
        probe = ProbeDefinition(
            name="test",
            description="desc",
            category=ProbeCategory.INJECTION,
            attack_strings=["x"],
            expected_action=GuardrailAction.BLOCK,
        )
        # Should not raise
        library.validate_probe(probe)

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        (tmp_path / "bad.yaml").write_text(
            yaml.dump({
                "name": "",
                "description": "desc",
                "category": "injection",
                "attack_strings": ["x"],
                "expected_action": "block",
            }),
        )
        library = ProbeLibrary()
        with pytest.raises(ValueError, match="name"):
            library.load_directory(tmp_path)

    def test_load_yml_extension(self, tmp_path: Path) -> None:
        (tmp_path / "probe.yml").write_text(
            yaml.dump({
                "name": "yml-probe",
                "description": "probe with yml ext",
                "category": "drift",
                "attack_strings": ["y"],
                "expected_action": "warn",
            }),
        )
        library = ProbeLibrary()
        library.load_directory(tmp_path)
        assert len(library.get_probes()) == 1

    def test_multiple_load_directories(
        self, probe_dir: Path, tmp_path: Path,
    ) -> None:
        extra_dir = tmp_path / "extra"
        extra_dir.mkdir()
        (extra_dir / "extra.yaml").write_text(
            yaml.dump({
                "name": "extra-probe",
                "description": "extra",
                "category": "injection",
                "attack_strings": ["z"],
                "expected_action": "block",
            }),
        )
        library = ProbeLibrary()
        library.load_directory(probe_dir)
        library.load_directory(extra_dir)
        assert len(library.get_probes()) == 4
