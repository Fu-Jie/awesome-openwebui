"""
Shared fixtures for Markdown Normalizer tests.
"""

import pytest
import sys
import os

# Add the parent directory to sys.path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from markdown_normalizer import ContentNormalizer, NormalizerConfig


@pytest.fixture
def normalizer():
    """Default normalizer with all fixes enabled."""
    config = NormalizerConfig(
        enable_escape_fix=True,
        enable_thought_tag_fix=True,
        enable_details_tag_fix=True,
        enable_code_block_fix=True,
        enable_latex_fix=True,
        enable_list_fix=False,  # Experimental, keep off by default
        enable_unclosed_block_fix=True,
        enable_fullwidth_symbol_fix=False,
        enable_mermaid_fix=True,
        enable_heading_fix=True,
        enable_table_fix=True,
        enable_xml_tag_cleanup=True,
        enable_emphasis_spacing_fix=True,
        enable_intra_word_emphasis_fix=True,
    )
    return ContentNormalizer(config)


@pytest.fixture
def emphasis_only_normalizer():
    """Normalizer with only emphasis spacing fix enabled."""
    config = NormalizerConfig(
        enable_escape_fix=False,
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
        enable_emphasis_spacing_fix=True,
        enable_intra_word_emphasis_fix=False,
    )
    return ContentNormalizer(config)


@pytest.fixture
def intra_word_only_normalizer():
    """Normalizer with only intra-word emphasis fix enabled."""
    config = NormalizerConfig(
        enable_escape_fix=False,
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
        enable_intra_word_emphasis_fix=True,
    )
    return ContentNormalizer(config)


@pytest.fixture
def mermaid_only_normalizer():
    """Normalizer with only Mermaid fix enabled."""
    config = NormalizerConfig(
        enable_escape_fix=False,
        enable_thought_tag_fix=False,
        enable_details_tag_fix=False,
        enable_code_block_fix=False,
        enable_latex_fix=False,
        enable_list_fix=False,
        enable_unclosed_block_fix=False,
        enable_fullwidth_symbol_fix=False,
        enable_mermaid_fix=True,
        enable_heading_fix=False,
        enable_table_fix=False,
        enable_xml_tag_cleanup=False,
        enable_emphasis_spacing_fix=False,
    )
    return ContentNormalizer(config)
