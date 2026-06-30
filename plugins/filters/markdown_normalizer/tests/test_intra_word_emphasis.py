"""
Tests for intra-word emphasis fix (issue #97).

Covers the case where LLMs mark up punctuation-only additions inside a word
boundary, e.g. `series**,**` (added comma rendered in bold) which most Markdown
parsers refuse to render because the opening delimiter is intra-word. The fix
moves the opening marker to the start of the word so the wrapped punctuation
renders together with the word.
"""

import pytest


class TestIntraWordEmphasisFix:
    """Test that intra-word emphasis markers are moved to the word start."""

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            # Bold (**) wrapping a single added punctuation char
            ("series**,**", "**series,**"),
            ("series**.**", "**series.**"),
            ("series**!**", "**series!**"),
            ("series**;**", "**series;**"),
            ("series**:**", "**series:**"),
            # Strikethrough (~~) — the issue's primary use case
            ("series~~,~~", "~~series,~~"),
            ("word~~.~~", "~~word.~~"),
            # Underscore bold (__) wrapping punctuation
            ("word__!__", "__word!__"),
            ("word__,__", "__word,__"),
            # Triple markers (*** / ___) wrapping punctuation
            ("word***,***", "***word,***"),
            ("word___,___", "___word,___"),
            # Multiple punctuation chars wrapped
            ("series**?!**", "**series?!**"),
            ("series**...**", "**series...**"),
            # Numeric "word" prefix is also handled
            ("100**,**", "**100,**"),
            # Multiple occurrences in one line
            (
                "series**,** and word2**.**",
                "**series,** and **word2.**",
            ),
            # Inside a sentence
            (
                "The text series**,** is now fixed.",
                "The text **series,** is now fixed.",
            ),
            # CJK word prefix
            ("中文**,**", "**中文,**"),
            # snake_case variable name with punctuation addition — the
            # underscore inside the identifier must NOT split the word, so
            # `my_var` stays intact and the marker moves to its start.
            ("my_var__,__", "__my_var,__"),
            ("my_var**,**", "**my_var,**"),
            ("my_var~~,~~", "~~my_var,~~"),
            ("snake_case_var**.**", "**snake_case_var.**"),
        ],
    )
    def test_intra_word_emphasis_fixed(
        self, intra_word_only_normalizer, input_str, expected
    ):
        """Intra-word emphasis wrapping pure punctuation should be moved."""
        assert intra_word_only_normalizer.normalize(input_str) == expected

    @pytest.mark.parametrize(
        "input_str",
        [
            # Already-correct emphasis at line start (no leading word)
            "**bold**",
            "~~strike~~",
            "__bold__",
            "***bold italic***",
            "___bold italic___",
            # Legitimate emphasis preceded by a word but wrapping text
            "word**bold**",
            "word~~strike~~",
            "word__bold__",
            # Math-like intra-word emphasis wrapping digits/letters (legitimate)
            "a**2**",
            "x**2**b",
            # Emphasis wrapping content with whitespace (already renderable)
            "series** , **",
            "series**a b**",
            # Underscore inside identifiers (snake_case) — must not match
            "my_var__bold__",
            "word_with_underscore",
            "a_b_c_d",
            # Horizontal rules
            "---",
            "***",
            "___",
        ],
    )
    def test_safe_cases_unchanged(self, intra_word_only_normalizer, input_str):
        """Legitimate emphasis and identifiers must not be modified."""
        assert intra_word_only_normalizer.normalize(input_str) == input_str


class TestIntraWordEmphasisCodeProtection:
    """Test that code blocks and inline code are never modified."""

    def test_intra_word_emphasis_in_code_block_unchanged(
        self, intra_word_only_normalizer
    ):
        """Code blocks should be completely skipped."""
        input_str = "```python\nseries**,** should stay\n```"
        assert intra_word_only_normalizer.normalize(input_str) == input_str

    def test_intra_word_emphasis_in_inline_code_unchanged(
        self, intra_word_only_normalizer
    ):
        """Inline code spans should be completely skipped."""
        input_str = "Use `series**,**` as a variable name."
        assert intra_word_only_normalizer.normalize(input_str) == input_str

    def test_mixed_text_and_code_block(
        self, intra_word_only_normalizer
    ):
        """Only markdown text outside code blocks should be fixed."""
        input_str = (
            "Outside series**,** text\n"
            "```python\nseries**,** unchanged\n```\n"
            "More word**.** outside."
        )
        expected = (
            "Outside **series,** text\n"
            "```python\nseries**,** unchanged\n```\n"
            "More **word.** outside."
        )
        assert intra_word_only_normalizer.normalize(input_str) == expected

    def test_mixed_text_and_inline_code(
        self, intra_word_only_normalizer
    ):
        """Only text outside inline code should be fixed."""
        input_str = "Fix series**,** but skip `series**,**` here."
        expected = "Fix **series,** but skip `series**,**` here."
        assert intra_word_only_normalizer.normalize(input_str) == expected


class TestIntraWordEmphasisCombinedWithSpacing:
    """Test interaction with the emphasis spacing fix when both are enabled."""

    def test_spacing_then_intra_word(self, normalizer):
        """`series** , **` -> spacing fixes inner spaces -> intra-word moves marker.

        With both fixes enabled the result should be `**series,**`.
        """
        input_str = "series** , **"
        expected = "**series,**"
        assert normalizer.normalize(input_str) == expected

    def test_already_correct_unchanged_with_both(self, normalizer):
        """Already-correct `**series,**` should remain unchanged."""
        input_str = "**series,**"
        assert normalizer.normalize(input_str) == input_str


class TestIntraWordEmphasisDisabled:
    """Test that the fix is a no-op when disabled."""

    def test_disabled_does_not_modify(self, emphasis_only_normalizer):
        """When only emphasis_spacing is enabled (intra-word off), the
        punctuation-only intra-word pattern must NOT be moved.
        """
        input_str = "series**,**"
        # emphasis_spacing only strips inner spaces, content `,` is untouched,
        # so the intra-word structure remains.
        assert emphasis_only_normalizer.normalize(input_str) == input_str
