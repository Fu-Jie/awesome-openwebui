"""Regression test for issue #97: intra-word emphasis rendering.

Issue: When LLMs mark up punctuation-only additions inside a word boundary,
e.g. `series**,**` (added comma rendered in bold) or `word~~,~~` (added
strikethrough), the Open WebUI Markdown parser refuses to render the inline
emphasis because the opening delimiter is intra-word.

The fix moves the opening emphasis marker to the start of the word so the
wrapped punctuation renders together with the word:
    `series**,**`  ->  `**series,**`
    `word~~,~~`    ->  `~~word,~~`
"""

from plugins.filters.markdown_normalizer.markdown_normalizer import (
    ContentNormalizer,
    NormalizerConfig,
)


def _norm(**kwargs):
    """Build a normalizer with all fixes off, then enable the requested ones."""
    config_kwargs = dict(
        enable_escape_fix=False,
        enable_escape_fix_in_code_blocks=False,
        enable_thought_tag_fix=False,
        enable_details_tag_fix=False,
        enable_code_block_fix=False,
        enable_latex_fix=False,
        enable_list_fix=False,
        enable_unclosed_block_fix=False,
        enable_fullwidth_symbol_fix=False,
        enable_mermaid_fix=False,
        enable_heading_fix=False,
        enable_table_fix=False,
        enable_xml_tag_cleanup=False,
        enable_emphasis_spacing_fix=False,
        enable_intra_word_emphasis_fix=False,
    )
    config_kwargs.update(kwargs)
    return ContentNormalizer(NormalizerConfig(**config_kwargs))


def test_intra_word_bold_punctuation_moved():
    """`series**,**` should become `**series,**`."""
    norm = _norm(enable_intra_word_emphasis_fix=True)
    assert norm.normalize("series**,**") == "**series,**"


def test_intra_word_strikethrough_punctuation_moved():
    """`word~~,~~` should become `~~word,~~`."""
    norm = _norm(enable_intra_word_emphasis_fix=True)
    assert norm.normalize("word~~,~~") == "~~word,~~"


def test_intra_word_underscore_bold_punctuation_moved():
    """`word__,__` should become `__word,__`."""
    norm = _norm(enable_intra_word_emphasis_fix=True)
    assert norm.normalize("word__,__") == "__word,__"


def test_legitimate_emphasis_preserved():
    """Already-correct emphasis and emphasis wrapping text must not change."""
    norm = _norm(enable_intra_word_emphasis_fix=True)
    for unchanged in (
        "**bold**",
        "word**bold**",     # content has letters -> legitimate
        "a**2**",           # content is digit -> math-like, leave alone
        "my_var__bold__",   # snake_case identifier, no match
    ):
        assert norm.normalize(unchanged) == unchanged, repr(unchanged)


def test_code_block_and_inline_code_protected():
    """Intra-word emphasis inside code blocks and inline code is preserved."""
    norm = _norm(enable_intra_word_emphasis_fix=True)
    code_block = "```python\nseries**,** unchanged\n```"
    assert norm.normalize(code_block) == code_block
    inline_code = "Use `series**,**` here."
    assert norm.normalize(inline_code) == inline_code


def test_intra_word_disabled_by_default():
    """When disabled (the default), the intra-word pattern is left as-is."""
    # Use the default config: enable_intra_word_emphasis_fix defaults to False.
    norm = ContentNormalizer(NormalizerConfig())
    assert norm.normalize("series**,**") == "series**,**"


if __name__ == "__main__":
    for fn in (
        test_intra_word_bold_punctuation_moved,
        test_intra_word_strikethrough_punctuation_moved,
        test_intra_word_underscore_bold_punctuation_moved,
        test_legitimate_emphasis_preserved,
        test_code_block_and_inline_code_protected,
        test_intra_word_disabled_by_default,
    ):
        try:
            fn()
            print(f"✅ {fn.__name__} passed.")
        except AssertionError as e:
            print(f"❌ {fn.__name__} FAILED: {e}")
            raise
