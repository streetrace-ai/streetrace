"""Tests for SequenceAnomalyDetector: suspicious sequence detection."""

from __future__ import annotations

from streetrace.guardrails.cognitive.sequence_anomaly import (
    SequenceAnomalyDetector,
    SequencePattern,
)


class TestSuspiciousSequenceDetection:
    """Verify detection of suspicious tool-use sequences."""

    def test_exfiltration_pattern_detected(self) -> None:
        """Detect read_file -> encode -> send_email pattern."""
        patterns = [
            SequencePattern(
                name="data_exfiltration",
                sequence=["read_file", "encode_base64", "send_email"],
            ),
        ]
        detector = SequenceAnomalyDetector(patterns=patterns)

        detector.record_tool_call("read_file")
        detector.record_tool_call("encode_base64")
        result = detector.record_tool_call("send_email")

        assert result.detected is True
        assert result.pattern_name == "data_exfiltration"
        assert result.sequence == [
            "read_file", "encode_base64", "send_email",
        ]

    def test_partial_match_not_detected(self) -> None:
        """Partial sequence does not trigger detection."""
        patterns = [
            SequencePattern(
                name="data_exfiltration",
                sequence=["read_file", "encode_base64", "send_email"],
            ),
        ]
        detector = SequenceAnomalyDetector(patterns=patterns)

        detector.record_tool_call("read_file")
        result = detector.record_tool_call("encode_base64")

        assert result.detected is False

    def test_wildcard_pattern_matching(self) -> None:
        """Wildcard '*' matches any tool name in sequence."""
        patterns = [
            SequencePattern(
                name="privilege_escalation",
                sequence=["list_users", "modify_permissions", "*"],
            ),
        ]
        detector = SequenceAnomalyDetector(patterns=patterns)

        detector.record_tool_call("list_users")
        detector.record_tool_call("modify_permissions")
        result = detector.record_tool_call("any_tool")

        assert result.detected is True
        assert result.pattern_name == "privilege_escalation"

    def test_glob_pattern_matching(self) -> None:
        """Glob prefix 'encode_*' matches encode_base64."""
        patterns = [
            SequencePattern(
                name="data_exfiltration",
                sequence=["read_file", "encode_*", "send_*"],
            ),
        ]
        detector = SequenceAnomalyDetector(patterns=patterns)

        detector.record_tool_call("read_file")
        detector.record_tool_call("encode_base64")
        result = detector.record_tool_call("send_email")

        assert result.detected is True


class TestBenignSequences:
    """Verify benign sequences do not trigger detection."""

    def test_benign_sequence_passes(self) -> None:
        """Normal tool-use sequence does not trigger."""
        patterns = [
            SequencePattern(
                name="data_exfiltration",
                sequence=["read_file", "encode_base64", "send_email"],
            ),
        ]
        detector = SequenceAnomalyDetector(patterns=patterns)

        detector.record_tool_call("read_file")
        detector.record_tool_call("write_file")
        result = detector.record_tool_call("list_files")

        assert result.detected is False

    def test_empty_patterns_never_detects(self) -> None:
        """No patterns configured means nothing detected."""
        detector = SequenceAnomalyDetector(patterns=[])

        result = detector.record_tool_call("anything")
        assert result.detected is False

    def test_order_matters(self) -> None:
        """Reversed sequence does not match."""
        patterns = [
            SequencePattern(
                name="data_exfiltration",
                sequence=["read_file", "encode_base64", "send_email"],
            ),
        ]
        detector = SequenceAnomalyDetector(patterns=patterns)

        detector.record_tool_call("send_email")
        detector.record_tool_call("encode_base64")
        result = detector.record_tool_call("read_file")

        assert result.detected is False


class TestReset:
    """Verify sequence reset behavior."""

    def test_reset_clears_history(self) -> None:
        """Reset clears tool call history."""
        patterns = [
            SequencePattern(
                name="data_exfiltration",
                sequence=["read_file", "encode_base64", "send_email"],
            ),
        ]
        detector = SequenceAnomalyDetector(patterns=patterns)

        detector.record_tool_call("read_file")
        detector.record_tool_call("encode_base64")
        detector.reset()
        result = detector.record_tool_call("send_email")

        assert result.detected is False
