"""Unit tests for normalized comparison functions.

Test the normalization logic used by the `~` operator for comparing
LLM outputs that may contain formatting noise.
"""



class TestNormalizeForComparison:
    """Test the normalize_for_comparison() function."""

    def test_lowercase_conversion(self):
        """Convert text to lowercase."""
        from streetrace.dsl.runtime.utils import normalize_for_comparison

        assert normalize_for_comparison("HELLO") == "hello"
        assert normalize_for_comparison("Hello World") == "hello world"

    def test_strip_whitespace(self):
        """Strip leading and trailing whitespace."""
        from streetrace.dsl.runtime.utils import normalize_for_comparison

        assert normalize_for_comparison("  hello  ") == "hello"
        assert normalize_for_comparison("\thello\n") == "hello"
        assert normalize_for_comparison("\n\nhello\n\n") == "hello"

    def test_remove_punctuation(self):
        """Remove punctuation marks."""
        from streetrace.dsl.runtime.utils import normalize_for_comparison

        assert normalize_for_comparison("Hello!") == "hello"
        assert normalize_for_comparison("Hello?") == "hello"
        assert normalize_for_comparison("Hello.") == "hello"
        assert normalize_for_comparison("Hello,") == "hello"
        assert normalize_for_comparison("Hello;") == "hello"
        assert normalize_for_comparison("Hello:") == "hello"

    def test_remove_markdown_bold(self):
        """Remove markdown bold modifiers."""
        from streetrace.dsl.runtime.utils import normalize_for_comparison

        assert normalize_for_comparison("**bold**") == "bold"
        assert normalize_for_comparison("**Hello World**") == "hello world"

    def test_remove_markdown_italic(self):
        """Remove markdown italic modifiers."""
        from streetrace.dsl.runtime.utils import normalize_for_comparison

        assert normalize_for_comparison("*italic*") == "italic"
        assert normalize_for_comparison("_italic_") == "italic"

    def test_remove_markdown_code(self):
        """Remove markdown inline code modifiers."""
        from streetrace.dsl.runtime.utils import normalize_for_comparison

        assert normalize_for_comparison("`code`") == "code"
        assert normalize_for_comparison("```code```") == "code"

    def test_remove_markdown_headers(self):
        """Remove markdown header markers."""
        from streetrace.dsl.runtime.utils import normalize_for_comparison

        assert normalize_for_comparison("# Header") == "header"
        assert normalize_for_comparison("## Header") == "header"
        assert normalize_for_comparison("### Header") == "header"

    def test_collapse_multiple_whitespace(self):
        """Collapse multiple whitespace to single space."""
        from streetrace.dsl.runtime.utils import normalize_for_comparison

        assert normalize_for_comparison("hello    world") == "hello world"
        assert normalize_for_comparison("hello\n\nworld") == "hello world"
        assert normalize_for_comparison("hello\t\tworld") == "hello world"

    def test_combined_normalization(self):
        """Test combined normalization rules from spec."""
        from streetrace.dsl.runtime.utils import normalize_for_comparison

        # Spec example: "**Drifting.**\n" -> "drifting"
        assert normalize_for_comparison("**Drifting.**\n") == "drifting"

        # More complex cases
        assert normalize_for_comparison("  **Hello!**  ") == "hello"
        assert normalize_for_comparison("_DRIFTING_...") == "drifting"
        assert normalize_for_comparison("`YES`!") == "yes"

    def test_empty_string(self):
        """Handle empty string input."""
        from streetrace.dsl.runtime.utils import normalize_for_comparison

        assert normalize_for_comparison("") == ""

    def test_only_whitespace(self):
        """Handle whitespace-only string."""
        from streetrace.dsl.runtime.utils import normalize_for_comparison

        assert normalize_for_comparison("   ") == ""
        assert normalize_for_comparison("\n\t\r") == ""

    def test_only_punctuation(self):
        """Handle punctuation-only string."""
        from streetrace.dsl.runtime.utils import normalize_for_comparison

        assert normalize_for_comparison("...") == ""
        assert normalize_for_comparison("!?!") == ""


class TestNormalizedEquals:
    """Test the normalized_equals() function."""

    def test_exact_match(self):
        """Test exact string match."""
        from streetrace.dsl.runtime.utils import normalized_equals

        assert normalized_equals("DRIFTING", "DRIFTING") is True

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        from streetrace.dsl.runtime.utils import normalized_equals

        assert normalized_equals("drifting", "DRIFTING") is True
        assert normalized_equals("Drifting", "DRIFTING") is True

    def test_markdown_formatting(self):
        """Test matching through markdown formatting."""
        from streetrace.dsl.runtime.utils import normalized_equals

        assert normalized_equals("**Drifting.**\n", "DRIFTING") is True
        assert normalized_equals("_Drifting_", "DRIFTING") is True
        assert normalized_equals("`DRIFTING`", "drifting") is True

    def test_whitespace_handling(self):
        """Test matching with whitespace variations."""
        from streetrace.dsl.runtime.utils import normalized_equals

        assert normalized_equals("  Drifting!  ", "DRIFTING") is True
        assert normalized_equals("\nDRIFTING\n", "drifting") is True

    def test_non_matching_strings(self):
        """Test non-matching strings return False."""
        from streetrace.dsl.runtime.utils import normalized_equals

        assert normalized_equals("I am drifting", "DRIFTING") is False
        assert normalized_equals("DRIFTING AWAY", "DRIFTING") is False
        assert normalized_equals("NOT_DRIFTING", "DRIFTING") is False

    def test_spec_table_examples(self):
        """Test all examples from the spec table."""
        from streetrace.dsl.runtime.utils import normalized_equals

        # | Left | Right | Result |
        # | "DRIFTING" | "DRIFTING" | true |
        assert normalized_equals("DRIFTING", "DRIFTING") is True

        # | "drifting" | "DRIFTING" | true |
        assert normalized_equals("drifting", "DRIFTING") is True

        # | "**Drifting.**\n" | "DRIFTING" | true |
        assert normalized_equals("**Drifting.**\n", "DRIFTING") is True

        # | "  Drifting!  " | "DRIFTING" | true |
        assert normalized_equals("  Drifting!  ", "DRIFTING") is True

        # | "I am drifting" | "DRIFTING" | false |
        assert normalized_equals("I am drifting", "DRIFTING") is False

    def test_non_string_inputs_left(self):
        """Test with non-string left input."""
        from streetrace.dsl.runtime.utils import normalized_equals

        assert normalized_equals(42, "42") is True
        bool_val = True
        assert normalized_equals(bool_val, "true") is True
        assert normalized_equals(None, "none") is True

    def test_non_string_inputs_right(self):
        """Test with non-string right input."""
        from streetrace.dsl.runtime.utils import normalized_equals

        bool_val = True
        assert normalized_equals("42", 42) is True
        assert normalized_equals("true", bool_val) is True
        assert normalized_equals("none", None) is True

    def test_both_non_string(self):
        """Test with both inputs non-string."""
        from streetrace.dsl.runtime.utils import normalized_equals

        bool_val = True
        assert normalized_equals(42, 42) is True
        assert normalized_equals(bool_val, bool_val) is True

    def test_empty_strings(self):
        """Test with empty strings."""
        from streetrace.dsl.runtime.utils import normalized_equals

        assert normalized_equals("", "") is True
        assert normalized_equals("  ", "") is True
        assert normalized_equals("", "  ") is True

    def test_yes_no_variations(self):
        """Test common LLM response patterns."""
        from streetrace.dsl.runtime.utils import normalized_equals

        # YES variations
        assert normalized_equals("**Yes**", "YES") is True
        assert normalized_equals("Yes!", "YES") is True
        assert normalized_equals("  yes  ", "YES") is True
        assert normalized_equals("YES.", "yes") is True

        # NO variations
        assert normalized_equals("**No**", "NO") is True
        assert normalized_equals("No!", "NO") is True
        assert normalized_equals("  no  ", "NO") is True
