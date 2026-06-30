"""
title: Markdown Normalizer
author: Fu-Jie
author_url: https://github.com/Fu-Jie/openwebui-extensions
funding_url: https://github.com/open-webui
version: 1.2.9
openwebui_id: baaa8732-9348-40b7-8359-7e009660e23c
description: A content normalizer filter that fixes common Markdown formatting issues in LLM outputs, such as broken code blocks, LaTeX formulas, and list formatting. Including LaTeX command protection.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Callable, Dict, Any
from fastapi import Request
import re
import logging
import asyncio
import json
from dataclasses import dataclass, field

# Configure logging
logger = logging.getLogger(__name__)


# i18n Translations
TRANSLATIONS = {
    "en-US": {
        "status_prefix": "✓ Markdown Normalized",
        "fix_escape": "Escape Characters",
        "fix_thought": "Thought Tags",
        "fix_details": "Details Tags",
        "fix_code": "Code Blocks",
        "fix_latex": "LaTeX Formulas",
        "fix_list": "List Format",
        "fix_close_code": "Close Code Blocks",
        "fix_fullwidth": "Full-width Symbols",
        "fix_mermaid": "Mermaid Syntax",
        "fix_heading": "Heading Format",
        "fix_table": "Table Format",
        "fix_xml": "XML Cleanup",
        "fix_emphasis": "Emphasis Spacing",
        "fix_intra_word": "Intra-word Emphasis",
        "fix_custom": "Custom Cleaner",
    },
    "zh-CN": {
        "status_prefix": "✓ Markdown 已修复",
        "fix_escape": "转义字符",
        "fix_thought": "思维标签",
        "fix_details": "Details标签",
        "fix_code": "代码块",
        "fix_latex": "LaTeX公式",
        "fix_list": "列表格式",
        "fix_close_code": "闭合代码块",
        "fix_fullwidth": "全角符号",
        "fix_mermaid": "Mermaid语法",
        "fix_heading": "标题格式",
        "fix_table": "表格格式",
        "fix_xml": "XML清理",
        "fix_emphasis": "强调空格",
        "fix_intra_word": "词内强调",
        "fix_custom": "自定义清理",
    },
    "zh-HK": {
        "status_prefix": "✓ Markdown 已修復",
        "fix_escape": "轉義字元",
        "fix_thought": "思維標籤",
        "fix_details": "Details標籤",
        "fix_code": "程式碼區塊",
        "fix_latex": "LaTeX公式",
        "fix_list": "列表格式",
        "fix_close_code": "閉合程式碼區塊",
        "fix_fullwidth": "全形符號",
        "fix_mermaid": "Mermaid語法",
        "fix_heading": "標題格式",
        "fix_table": "表格格式",
        "fix_xml": "XML清理",
        "fix_emphasis": "強調空格",
        "fix_intra_word": "詞內強調",
        "fix_custom": "自訂清理",
    },
    "zh-TW": {
        "status_prefix": "✓ Markdown 已修復",
        "fix_escape": "轉義字元",
        "fix_thought": "思維標籤",
        "fix_details": "Details標籤",
        "fix_code": "程式碼區塊",
        "fix_latex": "LaTeX公式",
        "fix_list": "列表格式",
        "fix_close_code": "閉合程式碼區塊",
        "fix_fullwidth": "全形符號",
        "fix_mermaid": "Mermaid語法",
        "fix_heading": "標題格式",
        "fix_table": "表格格式",
        "fix_xml": "XML清理",
        "fix_emphasis": "強調空格",
        "fix_intra_word": "詞內強調",
        "fix_custom": "自訂清理",
    },
    "ko-KR": {
        "status_prefix": "✓ Markdown 정규화됨",
        "fix_escape": "이스케이프 문자",
        "fix_thought": "생각 태그",
        "fix_details": "Details 태그",
        "fix_code": "코드 블록",
        "fix_latex": "LaTeX 공식",
        "fix_list": "목록 형식",
        "fix_close_code": "코드 블록 닫기",
        "fix_fullwidth": "전각 기호",
        "fix_mermaid": "Mermaid 구문",
        "fix_heading": "제목 형식",
        "fix_table": "표 형식",
        "fix_xml": "XML 정리",
        "fix_emphasis": "강조 공백",
        "fix_intra_word": "단어 내 강조",
        "fix_custom": "사용자 정의 정리",
    },
    "ja-JP": {
        "status_prefix": "✓ Markdown 正規化済み",
        "fix_escape": "エスケープ文字",
        "fix_thought": "思考タグ",
        "fix_details": "Detailsタグ",
        "fix_code": "コードブロック",
        "fix_latex": "LaTeX数式",
        "fix_list": "リスト形式",
        "fix_close_code": "コードブロックを閉じる",
        "fix_fullwidth": "全角記号",
        "fix_mermaid": "Mermaid構文",
        "fix_heading": "見出し形式",
        "fix_table": "表形式",
        "fix_xml": "XMLクリーンアップ",
        "fix_emphasis": "強調の空白",
        "fix_intra_word": "単語内強調",
        "fix_custom": "カスタムクリーナー",
    },
    "fr-FR": {
        "status_prefix": "✓ Markdown normalisé",
        "fix_escape": "Caractères d'échappement",
        "fix_thought": "Balises de pensée",
        "fix_details": "Balises Details",
        "fix_code": "Blocs de code",
        "fix_latex": "Formules LaTeX",
        "fix_list": "Format de liste",
        "fix_close_code": "Fermer les blocs de code",
        "fix_fullwidth": "Symboles pleine largeur",
        "fix_mermaid": "Syntaxe Mermaid",
        "fix_heading": "Format de titre",
        "fix_table": "Format de tableau",
        "fix_xml": "Nettoyage XML",
        "fix_emphasis": "Espacement d'emphase",
        "fix_intra_word": "Emphase intra-mot",
        "fix_custom": "Nettoyeur personnalisé",
    },
    "de-DE": {
        "status_prefix": "✓ Markdown normalisiert",
        "fix_escape": "Escape-Zeichen",
        "fix_thought": "Denk-Tags",
        "fix_details": "Details-Tags",
        "fix_code": "Code-Blöcke",
        "fix_latex": "LaTeX-Formeln",
        "fix_list": "Listenformat",
        "fix_close_code": "Code-Blöcke schließen",
        "fix_fullwidth": "Vollbreite Symbole",
        "fix_mermaid": "Mermaid-Syntax",
        "fix_heading": "Überschriftenformat",
        "fix_table": "Tabellenformat",
        "fix_xml": "XML-Bereinigung",
        "fix_emphasis": "Hervorhebungsabstände",
        "fix_intra_word": "Wortinterne Hervorhebung",
        "fix_custom": "Benutzerdefinierter Reiniger",
    },
    "es-ES": {
        "status_prefix": "✓ Markdown normalizado",
        "fix_escape": "Caracteres de escape",
        "fix_thought": "Etiquetas de pensamiento",
        "fix_details": "Etiquetas de Details",
        "fix_code": "Bloques de código",
        "fix_latex": "Fórmulas LaTeX",
        "fix_list": "Formato de lista",
        "fix_close_code": "Cerrar bloques de código",
        "fix_fullwidth": "Símbolos de ancho completo",
        "fix_mermaid": "Sintaxis Mermaid",
        "fix_heading": "Formato de encabezado",
        "fix_table": "Formato de tabla",
        "fix_xml": "Limpieza XML",
        "fix_emphasis": "Espaciado de énfasis",
        "fix_intra_word": "Énfasis intra-palabra",
        "fix_custom": "Limpiador personalizado",
    },
    "it-IT": {
        "status_prefix": "✓ Markdown normalizzato",
        "fix_escape": "Caratteri di escape",
        "fix_thought": "Tag di pensiero",
        "fix_details": "Tag Details",
        "fix_code": "Blocchi di codice",
        "fix_latex": "Formule LaTeX",
        "fix_list": "Formato elenco",
        "fix_close_code": "Chiudi blocchi di codice",
        "fix_fullwidth": "Simboli a larghezza intera",
        "fix_mermaid": "Sintassi Mermaid",
        "fix_heading": "Formato intestazione",
        "fix_table": "Formato tabella",
        "fix_xml": "Pulizia XML",
        "fix_emphasis": "Spaziatura enfasi",
        "fix_intra_word": "Enfasi intra-parola",
        "fix_custom": "Pulitore personalizzato",
    },
    "vi-VN": {
        "status_prefix": "✓ Markdown đã chuẩn hóa",
        "fix_escape": "Ký tự thoát",
        "fix_thought": "Thẻ suy nghĩ",
        "fix_details": "Thẻ Details",
        "fix_code": "Khối mã",
        "fix_latex": "Công thức LaTeX",
        "fix_list": "Định dạng danh sách",
        "fix_close_code": "Đóng khối mã",
        "fix_fullwidth": "Ký tự toàn chiều rộng",
        "fix_mermaid": "Cú pháp Mermaid",
        "fix_heading": "Định dạng tiêu đề",
        "fix_table": "Định dạng bảng",
        "fix_xml": "Dọn dẹp XML",
        "fix_emphasis": "Khoảng cách nhấn mạnh",
        "fix_intra_word": "Nhấn mạnh trong từ",
        "fix_custom": "Trình dọn dẹp tùy chỉnh",
    },
    "id-ID": {
        "status_prefix": "✓ Markdown dinormalisasi",
        "fix_escape": "Karakter escape",
        "fix_thought": "Tag pemikiran",
        "fix_details": "Tag Details",
        "fix_code": "Blok kode",
        "fix_latex": "Formula LaTeX",
        "fix_list": "Format daftar",
        "fix_close_code": "Tutup blok kode",
        "fix_fullwidth": "Simbol lebar penuh",
        "fix_mermaid": "Sintaks Mermaid",
        "fix_heading": "Format heading",
        "fix_table": "Format tabel",
        "fix_xml": "Pembersihan XML",
        "fix_emphasis": "Spasi penekanan",
        "fix_intra_word": "Penekanan intra-kata",
        "fix_custom": "Pembersih kustom",
    },
}




@dataclass
class NormalizerConfig:
    """Configuration class for enabling/disabling specific normalization rules"""

    enable_escape_fix: bool = False  # Fix excessive escape characters (Default False for safety)
    enable_escape_fix_in_code_blocks: bool = (
        False  # Apply escape fix inside code blocks (default: False for safety)
    )
    enable_thought_tag_fix: bool = True  # Normalize thought tags
    enable_details_tag_fix: bool = True  # Normalize <details> tags (like thought tags)
    enable_code_block_fix: bool = True  # Fix code block formatting
    enable_latex_fix: bool = True  # Fix LaTeX formula formatting
    enable_list_fix: bool = (
        False  # Fix list item newlines (default off as it can be aggressive)
    )
    enable_unclosed_block_fix: bool = True  # Auto-close unclosed code blocks
    enable_fullwidth_symbol_fix: bool = False  # Fix full-width symbols in code blocks
    enable_mermaid_fix: bool = True  # Fix common Mermaid syntax errors
    enable_heading_fix: bool = (
        True  # Fix missing space in headings (#Header -> # Header)
    )
    enable_table_fix: bool = True  # Fix missing closing pipe in tables
    enable_xml_tag_cleanup: bool = True  # Cleanup leftover XML tags
    enable_emphasis_spacing_fix: bool = False  # Fix spaces inside **emphasis**
    enable_intra_word_emphasis_fix: bool = (
        False  # Move opening emphasis marker to word start (e.g. series**,** -> **series,**)
    )

    # Custom cleaner functions (for advanced extension)
    custom_cleaners: List[Callable[[str], str]] = field(default_factory=list)


class ContentNormalizer:
    """LLM Output Content Normalizer - Production Grade Implementation"""

    # --- 1. Pre-compiled Regex Patterns (Performance Optimization) ---
    _PATTERNS = {
        # Code block prefix: if ``` is not at start of line (ignoring whitespace)
        "code_block_prefix": re.compile(r"(\S[ \t]*)(```)"),
        # Code block suffix: ```lang followed by non-whitespace (no newline)
        "code_block_suffix": re.compile(r"(```[\w\+\-\.]*)[ \t]+([^\n\r])"),
        # Code block indent: whitespace at start of line + ```
        "code_block_indent": re.compile(r"^[ \t]+(```)", re.MULTILINE),
        # Thought tag: </thought> followed by optional whitespace/newlines
        "thought_end": re.compile(
            r"</(thought|think|thinking)>[ \t]*\n*", re.IGNORECASE
        ),
        "thought_start": re.compile(r"<(thought|think|thinking)>", re.IGNORECASE),
        # Details tag: </details> followed by optional whitespace/newlines
        "details_end": re.compile(r"</details>[ \t]*\n*", re.IGNORECASE),
        # Self-closing details tag: <details ... /> followed by optional whitespace (but NOT already having newline)
        "details_self_closing": re.compile(
            r"(<details[^>]*/\s*>)(?!\n)", re.IGNORECASE
        ),
        # LaTeX block: \[ ... \]
        "latex_bracket_block": re.compile(r"\\\[(.+?)\\\]", re.DOTALL),
        # LaTeX inline: \( ... \)
        "latex_paren_inline": re.compile(r"\\\((.+?)\\\)"),
        # List item: non-newline + digit + dot + space
        "list_item": re.compile(r"([^\n])(\d+\. )"),
        # XML artifacts (e.g. Claude's)
        "xml_artifacts": re.compile(
            r"</?(?:antArtifact|antThinking|artifact)[^>]*>", re.IGNORECASE
        ),
        # Mermaid: Match various node shapes and quote unquoted labels
        # Fix "reverse optimization": Must precisely match shape delimiters to avoid breaking structure
        # Priority: Longer delimiters match first
        "mermaid_node": re.compile(
            r'("[^"\\]*(?:\\.[^"\\]*)*")|'  # Match quoted strings first (Group 1)
            r"(\w+)(?:"
            r"(\(\(\()(?![\"])(.*?)(?<![\"])(\)\)\))|"  # (((...))) Double Circle
            r"(\(\()(?![\"])(.*?)(?<![\"])(\)\))|"  # ((...)) Circle
            r"(\(\[)(?![\"])(.*?)(?<![\"])(\]\))|"  # ([...]) Stadium
            r"(\[\()(?![\"])(.*?)(?<![\"])(\)\])|"  # [(...)] Cylinder
            r"(\[\[)(?![\"])(.*?)(?<![\"])(\]\])|"  # [[...]] Subroutine
            r"(\{\{)(?![\"])(.*?)(?<![\"])(\}\})|"  # {{...}} Hexagon
            r"(\[/)(?![\"])(.*?)(?<![\"])(/\])|"  # [/.../] Parallelogram
            r"(\[\\)(?![\"])(.*?)(?<![\"])(\\\])|"  # [\...\] Parallelogram Alt
            r"(\[/)(?![\"])(.*?)(?<![\"])(\\\])|"  # [/...\] Trapezoid
            r"(\[\\)(?![\"])(.*?)(?<![\"])(\/\])|"  # [\.../] Trapezoid Alt
            r"(\()(?![\"])([^)]*?)(?<![\"])(\))|"  # (...) Round - Modified to be safer
            r"(\[)(?![\"])(.*?)(?<![\"])(\])|"  # [...] Square
            r"(\{)(?![\"])(.*?)(?<![\"])(\})|"  # {...} Rhombus
            r"(>)(?![\"])(.*?)(?<![\"])(\])"  # >...] Asymmetric
            r")"
            r"(\s*\[\d+\])?",  # Capture optional citation [1]
            re.DOTALL,
        ),
        # Heading: #Heading -> # Heading
        "heading_space": re.compile(r"^(#+)([^ \n#])", re.MULTILINE),
        # Table: | col1 | col2 -> | col1 | col2 |
        "table_pipe": re.compile(r"^(\|.*[^|\n])$", re.MULTILINE),
        # Emphasis spacing: ** text ** -> **text**, __ text __ -> __text__
        # Matches emphasis blocks within a single line. We use a recursive approach
        # in _fix_emphasis_spacing to handle nesting and spaces correctly.
        # NOTE: We use [^\n] instead of . to prevent cross-line matching.
        # Supports: * (italic), ** (bold), *** (bold+italic), _ (italic), __ (bold), ___ (bold+italic)
        "emphasis_spacing": re.compile(
            r"(?<!\*|_)(\*{1,3}|_{1,3})(?P<inner>(?:(?!\1)[^\n])*?)(\1)(?!\*|_)"
        ),
        # Intra-word emphasis: series**,** -> **series,**
        # Matches an alphanumeric word directly followed by an opening emphasis marker
        # (~~, **, __, ***, ___) that wraps ONLY punctuation (no whitespace/word chars),
        # then the same closing marker. The opening marker is moved before the word so
        # the punctuation (e.g. an added comma) renders together with the word.
        # NOTE: Alternation lists longer markers first so *** / ___ win over ** / __.
        # NOTE: `word` is `[^\W_]+(?:_[^\W_]+)*` so snake_case identifiers like
        # `my_var` stay intact instead of being split into `my_` + `var`. The
        # trailing `(?:_[^\W_]+)*` only allows underscores that sit *between*
        # word-char runs, so a run of trailing underscores (e.g. `word___`)
        # is left for the marker alternation to consume as `___` rather than
        # being swallowed by `word`. This keeps triple-underscore markers
        # (`word___,___`) working while still protecting `my_var__bold__`
        # (which never matches because `content` excludes word chars).
        "intra_word_emphasis": re.compile(
            r"(?P<word>[^\W_]+(?:_[^\W_]+)*)"
            r"(?P<marker>\*\*\*|___|\*\*|__|~~)"
            r"(?P<content>[^\s\w]+?)"
            r"(?P=marker)"
        ),
    }

    def __init__(self, config: Optional[NormalizerConfig] = None):
        self.config = config or NormalizerConfig()
        self.applied_fixes = []

    def normalize(self, content: str) -> str:
        """Main entry point: apply all normalization rules in order"""
        self.applied_fixes = []
        if not content:
            return content

        original_content = content  # Keep a copy for logging

        try:
            # 1. Escape character fix (Must be first)
            if self.config.enable_escape_fix:
                original = content
                content = self._fix_escape_characters(content)
                if content != original:
                    self.applied_fixes.append("Fix Escape Chars")

            # 2. Thought tag normalization
            if self.config.enable_thought_tag_fix:
                original = content
                content = self._fix_thought_tags(content)
                if content != original:
                    self.applied_fixes.append("Normalize Thought Tags")

            # 3. Details tag normalization (must be before heading fix)
            if self.config.enable_details_tag_fix:
                original = content
                content = self._fix_details_tags(content)
                if content != original:
                    self.applied_fixes.append("Normalize Details Tags")

            # 4. Code block formatting fix
            if self.config.enable_code_block_fix:
                original = content
                content = self._fix_code_blocks(content)
                if content != original:
                    self.applied_fixes.append("Fix Code Blocks")

            # 4. LaTeX formula normalization
            if self.config.enable_latex_fix:
                original = content
                content = self._fix_latex_formulas(content)
                if content != original:
                    self.applied_fixes.append("Normalize LaTeX")

            # 5. List formatting fix
            if self.config.enable_list_fix:
                original = content
                content = self._fix_list_formatting(content)
                if content != original:
                    self.applied_fixes.append("Fix List Format")

            # 6. Unclosed code block fix
            if self.config.enable_unclosed_block_fix:
                original = content
                content = self._fix_unclosed_code_blocks(content)
                if content != original:
                    self.applied_fixes.append("Close Code Blocks")

            # 7. Full-width symbol fix (in code blocks only)
            if self.config.enable_fullwidth_symbol_fix:
                original = content
                content = self._fix_fullwidth_symbols_in_code(content)
                if content != original:
                    self.applied_fixes.append("Fix Full-width Symbols")

            # 8. Mermaid syntax fix
            if self.config.enable_mermaid_fix:
                original = content
                content = self._fix_mermaid_syntax(content)
                if content != original:
                    self.applied_fixes.append("Fix Mermaid Syntax")

            # 9. Heading fix
            if self.config.enable_heading_fix:
                original = content
                content = self._fix_headings(content)
                if content != original:
                    self.applied_fixes.append("Fix Headings")

            # 10. Table fix
            if self.config.enable_table_fix:
                original = content
                content = self._fix_tables(content)
                if content != original:
                    self.applied_fixes.append("Fix Tables")

            # 11. XML tag cleanup
            if self.config.enable_xml_tag_cleanup:
                original = content
                content = self._cleanup_xml_tags(content)
                if content != original:
                    self.applied_fixes.append("Cleanup XML Tags")

            # 12. Emphasis spacing fix
            if self.config.enable_emphasis_spacing_fix:
                original = content
                content = self._fix_emphasis_spacing(content)
                if content != original:
                    self.applied_fixes.append("Fix Emphasis Spacing")

            # 13. Intra-word emphasis fix (run after emphasis spacing so any
            # inner spaces are already collapsed, e.g. `** , **` -> `**, **` first)
            if self.config.enable_intra_word_emphasis_fix:
                original = content
                content = self._fix_intra_word_emphasis(content)
                if content != original:
                    self.applied_fixes.append("Fix Intra-word Emphasis")

            # 9. Custom cleaners
            for cleaner in self.config.custom_cleaners:
                original = content
                content = cleaner(content)
                if content != original:
                    self.applied_fixes.append("Custom Cleaner")

            if self.applied_fixes:
                logger.info(f"Markdown Normalizer Applied Fixes: {self.applied_fixes}")
                logger.debug(
                    f"--- Original Content ---\n{original_content}\n------------------------"
                )
                logger.debug(
                    f"--- Normalized Content ---\n{content}\n--------------------------"
                )

            return content

        except Exception as e:
            # Production safeguard: return original content on error
            logger.error(f"Content normalization failed: {e}", exc_info=True)
            return original_content

    def _fix_escape_characters(self, content: str) -> str:
        """Fix excessive escape characters while protecting LaTeX, code blocks, and inline code."""

        def clean_text(text: str) -> str:
            # First handle literal escaped newlines
            text = text.replace("\\r\\n", "\n")
            text = text.replace("\\n", "\n")
            
            # Then handle double backslashes that are not followed by n or r
            # (which would have been part of an escaped newline handled above)
            # Use regex to replace \\ with \ only if not followed by n or r
            # But wait, \n is already \n (actual newline) here.
            # So we can safely replace all remaining \\ with \
            text = text.replace("\\\\", "\\")
            return text

        # 1. Protect block code
        parts = content.split("```")
        for i in range(0, len(parts)):
            is_code_block = (i % 2 != 0)
            if is_code_block and not self.config.enable_escape_fix_in_code_blocks:
                continue
                
            if not is_code_block:
                # 2. Protect inline code
                inline_parts = parts[i].split("`")
                for k in range(0, len(inline_parts), 2):  # Even indices are non-inline-code text
                    # 3. Protect LaTeX formulas within text (safe for $$ and $)
                    # Use regex to split and keep delimiters
                    sub_parts = re.split(
                        r"(\$\$.*?\$\$|\$.*?\$)", inline_parts[k], flags=re.DOTALL
                    )
                    for j in range(0, len(sub_parts), 2):  # Even indices are non-math text
                        sub_parts[j] = clean_text(sub_parts[j])
                    inline_parts[k] = "".join(sub_parts)
                parts[i] = "`".join(inline_parts)
            else:
                # Inside code block and enable_escape_fix_in_code_blocks is True
                parts[i] = clean_text(parts[i])

        return "```".join(parts)

    def _fix_thought_tags(self, content: str) -> str:
        """Normalize thought tags: unify naming and fix spacing"""
        # 1. Standardize start tag: <think>, <thinking> -> <thought>
        content = self._PATTERNS["thought_start"].sub("<thought>", content)
        # 2. Standardize end tag and ensure newlines: </think> -> </thought>\n\n
        return self._PATTERNS["thought_end"].sub("</thought>\n\n", content)

    def _fix_details_tags(self, content: str) -> str:
        """Normalize <details> tags: ensure proper spacing after closing tags

        Handles two cases:
        1. </details> followed by content -> ensure double newline
        2. <details .../> (self-closing) followed by content -> ensure newline

        Note: Only applies outside of code blocks to avoid breaking code examples.
        """
        parts = content.split("```")
        for i in range(0, len(parts), 2):  # Even indices are markdown text
            # 1. Ensure double newline after </details>
            parts[i] = self._PATTERNS["details_end"].sub("</details>\n\n", parts[i])
            # 2. Ensure newline after self-closing <details ... />
            parts[i] = self._PATTERNS["details_self_closing"].sub(r"\1\n", parts[i])

        return "```".join(parts)

    def _fix_code_blocks(self, content: str) -> str:
        """Fix code block formatting (prefixes, suffixes, indentation)"""
        # Ensure newline before ```
        content = self._PATTERNS["code_block_prefix"].sub(r"\n\1", content)
        # Ensure newline after ```lang
        content = self._PATTERNS["code_block_suffix"].sub(r"\1\n\2", content)
        return content

    def _fix_latex_formulas(self, content: str) -> str:
        r"""Normalize LaTeX formulas: \[ -> $$ (block), \( -> $ (inline)"""
        content = self._PATTERNS["latex_bracket_block"].sub(r"$$\1$$", content)
        content = self._PATTERNS["latex_paren_inline"].sub(r"$\1$", content)
        return content

    def _fix_list_formatting(self, content: str) -> str:
        """Fix missing newlines in lists (e.g., 'text1. item' -> 'text\\n1. item')"""
        return self._PATTERNS["list_item"].sub(r"\1\n\2", content)

    def _fix_unclosed_code_blocks(self, content: str) -> str:
        """Auto-close unclosed code blocks"""
        if content.count("```") % 2 != 0:
            content += "\n```"
        return content

    def _fix_fullwidth_symbols_in_code(self, content: str) -> str:
        """Convert full-width symbols to half-width inside code blocks"""
        FULLWIDTH_MAP = {
            "，": ",",
            "。": ".",
            "（": "(",
            "）": ")",
            "【": "[",
            "】": "]",
            "；": ";",
            "：": ":",
            "？": "?",
            "！": "!",
            "＂": '"',  # U+FF02 FULLWIDTH QUOTATION MARK
            "＇": "'",  # U+FF07 FULLWIDTH APOSTROPHE
            "“": '"',
            "”": '"',
            "‘": "'",
            "’": "'",
        }

        parts = content.split("```")
        # Code block content is at odd indices: 1, 3, 5...
        for i in range(1, len(parts), 2):
            for full, half in FULLWIDTH_MAP.items():
                parts[i] = parts[i].replace(full, half)

        return "```".join(parts)

    def _fix_mermaid_syntax(self, content: str) -> str:
        """Fix common Mermaid syntax errors while preserving node shapes"""

        def replacer(match):
            # Group 1 is Quoted String (if matched)
            if match.group(1):
                return match.group(1)

            # Group 2 is ID
            id_str = match.group(2)

            # Find matching shape group
            groups = match.groups()
            citation = groups[-1] or ""  # Last group is citation

            # Iterate over shape groups (excluding the last citation group)
            for i in range(2, len(groups) - 1, 3):
                if groups[i] is not None:
                    open_char = groups[i]
                    content = groups[i + 1]
                    close_char = groups[i + 2]

                    # Append citation to content if present
                    if citation:
                        content += citation

                    # Escape quotes in content
                    content = content.replace('"', '\\"')

                    return f'{id_str}{open_char}"{content}"{close_char}'

            return match.group(0)

        parts = content.split("```")
        for i in range(1, len(parts), 2):
            # Check if it's a mermaid block
            lang_line = parts[i].split("\n", 1)[0].strip().lower()
            if "mermaid" in lang_line:
                # Protect edge labels (text between link start and arrow) from being modified
                # by temporarily replacing them with placeholders.
                edge_labels = []

                def protect_edge_label(m):
                    start = m.group(1)  # Link start: --, -., or ==
                    label = m.group(2)  # Text content
                    arrow = m.group(3)  # Arrow/end pattern
                    edge_labels.append((start, label, arrow))
                    return f"___EDGE_LABEL_{len(edge_labels)-1}___"

                edge_label_pattern = (
                    r"(--|-\.|\=\=)\s+(.+?)\s+(--+[>ox]?|--+\|>|\.-[>ox]?|=+[>ox]?)"
                )
                protected = re.sub(edge_label_pattern, protect_edge_label, parts[i])

                # Apply the comprehensive regex fix to protected content
                fixed = self._PATTERNS["mermaid_node"].sub(replacer, protected)

                # Restore edge labels
                for idx, (start, label, arrow) in enumerate(edge_labels):
                    fixed = fixed.replace(
                        f"___EDGE_LABEL_{idx}___", f"{start} {label} {arrow}"
                    )

                parts[i] = fixed

                # Auto-close subgraphs
                subgraph_count = len(
                    re.findall(r"\bsubgraph\b", parts[i], re.IGNORECASE)
                )
                end_count = len(re.findall(r"\bend\b", parts[i], re.IGNORECASE))

                if subgraph_count > end_count:
                    missing_ends = subgraph_count - end_count
                    parts[i] = parts[i].rstrip() + ("\n    end" * missing_ends) + "\n"

        return "```".join(parts)

    def _fix_headings(self, content: str) -> str:
        """Fix missing space in headings: #Heading -> # Heading"""
        parts = content.split("```")
        for i in range(0, len(parts), 2):  # Even indices are markdown text
            parts[i] = self._PATTERNS["heading_space"].sub(r"\1 \2", parts[i])
        return "```".join(parts)

    def _fix_tables(self, content: str) -> str:
        """Fix tables missing closing pipe"""
        parts = content.split("```")
        for i in range(0, len(parts), 2):
            parts[i] = self._PATTERNS["table_pipe"].sub(r"\1|", parts[i])
        return "```".join(parts)

    def _cleanup_xml_tags(self, content: str) -> str:
        """Remove leftover XML tags"""
        return self._PATTERNS["xml_artifacts"].sub("", content)

    def _fix_emphasis_spacing(self, content: str) -> str:
        """Fix spaces inside **emphasis** or _emphasis_
        Example: ** text ** -> **text**, **text ** -> **text**, ** text** -> **text**
        """

        def replacer(match):
            symbol = match.group(1)
            inner = match.group("inner")

            # Recursive step: Fix emphasis spacing INSIDE the current block first
            inner = self._PATTERNS["emphasis_spacing"].sub(replacer, inner)

            stripped_inner = inner.strip()
            if stripped_inner == inner:
                return f"{symbol}{inner}{symbol}"

            if not stripped_inner:
                return match.group(0)

            # Heuristic checks
            if inner.startswith(" ") and inner.endswith(" "):
                if symbol == "*":
                    if not any(c.isalpha() for c in inner):
                        return match.group(0)

            if symbol == "*" and inner.lstrip().startswith(("*", "_")):
                return match.group(0)

            if symbol == "*" and inner.startswith("   "):
                return match.group(0)

            if symbol in stripped_inner:
                return match.group(0)

            return f"{symbol}{stripped_inner}{symbol}"

        parts = content.split("```")
        for i in range(0, len(parts), 2):
            while True:
                new_part = self._PATTERNS["emphasis_spacing"].sub(replacer, parts[i])
                if new_part == parts[i]:
                    break
                parts[i] = new_part
        return "```".join(parts)

    def _fix_intra_word_emphasis(self, content: str) -> str:
        """Move opening emphasis marker to the start of an intra-word group.

        When LLMs mark up punctuation-only additions inside a word boundary,
        e.g. `series**,**` (added comma) or `word~~,~~` (added strikethrough),
        many Markdown parsers refuse to render the inline emphasis because the
        opening delimiter is intra-word. Moving the opening marker to the start
        of the word produces a renderable `**series,**` / `~~word,~~`.

        Only transforms cases where the wrapped content is *pure punctuation*
        (no whitespace, no word characters) so legitimate `**bold**` /
        `__bold__` / `~~strike~~` markup is left untouched. Code blocks and
        inline code are skipped via the standard `split("```")` partitioning.
        """

        def replacer(match):
            word = match.group("word")
            marker = match.group("marker")
            inner = match.group("content")
            # Skip if content somehow slipped through with whitespace or word
            # chars (defensive; the regex already restricts this).
            if any(c.isspace() or c.isalnum() for c in inner):
                return match.group(0)
            return f"{marker}{word}{inner}{marker}"

        parts = content.split("```")
        for i in range(0, len(parts), 2):  # Even indices are markdown text
            # Protect inline code (backtick spans) from modification.
            inline_parts = parts[i].split("`")
            for k in range(0, len(inline_parts), 2):  # Even indices = non-code
                # Single-pass is sufficient: the pattern cannot nest because
                # `content` is restricted to pure punctuation, so a match cannot
                # contain another word+marker+content+marker sequence.
                inline_parts[k] = self._PATTERNS["intra_word_emphasis"].sub(
                    replacer, inline_parts[k]
                )
            parts[i] = "`".join(inline_parts)
        return "```".join(parts)


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=50,
            description="Priority level (lower = earlier).",
        )
        enable_escape_fix: bool = Field(
            default=False,
            description="Fix excessive escape characters (\\n, \\t, etc.). Default: False for safety.",
        )
        enable_escape_fix_in_code_blocks: bool = Field(
            default=False,
            description="Apply escape fix inside code blocks (Warning: May break valid code).",
        )
        enable_thought_tag_fix: bool = Field(
            default=True,
            description="Normalize thought tags (<think> -> <thought>).",
        )
        enable_details_tag_fix: bool = Field(
            default=True,
            description="Normalize <details> tags (add blank line after closing tag).",
        )
        enable_code_block_fix: bool = Field(
            default=True,
            description="Fix code block formatting (indentation, newlines).",
        )
        enable_latex_fix: bool = Field(
            default=True,
            description="Normalize LaTeX formulas (\\[ -> $$, \\( -> $).",
        )
        enable_list_fix: bool = Field(
            default=False,
            description="Fix list item newlines (Experimental).",
        )
        enable_unclosed_block_fix: bool = Field(
            default=True,
            description="Auto-close unclosed code blocks.",
        )
        enable_fullwidth_symbol_fix: bool = Field(
            default=False,
            description="Fix full-width symbols in code blocks.",
        )
        enable_mermaid_fix: bool = Field(
            default=True,
            description="Fix common Mermaid syntax errors (e.g. unquoted labels).",
        )
        enable_heading_fix: bool = Field(
            default=True,
            description="Fix missing space in headings (#Header -> # Header).",
        )
        enable_table_fix: bool = Field(
            default=True,
            description="Fix missing closing pipe in tables.",
        )
        enable_xml_tag_cleanup: bool = Field(
            default=True,
            description="Cleanup leftover XML tags.",
        )
        enable_emphasis_spacing_fix: bool = Field(
            default=False,
            description="Fix spaces inside **emphasis** (e.g. ** text ** -> **text**).",
        )
        enable_intra_word_emphasis_fix: bool = Field(
            default=False,
            description=(
                "Move opening emphasis marker to the start of an intra-word "
                "group (e.g. series**,** -> **series,**) so added punctuation "
                "renders. Useful for grammar/spelling diff outputs."
            ),
        )
        show_status: bool = Field(
            default=True,
            description="Show status notification when fixes are applied.",
        )
        show_debug_log: bool = Field(
            default=False,
            description="Print debug logs to browser console (F12).",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.fallback_map = {
            "zh": "zh-CN",
            "en": "en-US",
            "ko": "ko-KR",
            "ja": "ja-JP",
            "fr": "fr-FR",
            "de": "de-DE",
            "es": "es-ES",
            "it": "it-IT",
            "vi": "vi-VN",
            "id": "id-ID",
            "es-AR": "es-ES",
            "es-MX": "es-ES",
            "fr-CA": "fr-FR",
            "en-CA": "en-US",
            "en-GB": "en-US",
            "en-AU": "en-US",
            "de-AT": "de-DE",
        }

    def _resolve_language(self, lang: str) -> str:
        """Resolve the best matching language code from the TRANSLATIONS dict."""
        target_lang = lang

        # 1. Direct match
        if target_lang in TRANSLATIONS:
            return target_lang

        # 2. Variant fallback (explicit mapping)
        if target_lang in self.fallback_map:
            target_lang = self.fallback_map[target_lang]
            if target_lang in TRANSLATIONS:
                return target_lang

        # 3. Base language fallback (e.g. fr-BE -> fr-FR)
        if "-" in lang:
            base_lang = lang.split("-")[0]
            for supported_lang in TRANSLATIONS:
                if supported_lang.startswith(base_lang + "-"):
                    return supported_lang

        # 4. Final Fallback to en-US
        return "en-US"

    def _get_translation(self, lang: str, key: str, **kwargs) -> str:
        """Get translated string for the given language and key."""
        target_lang = self._resolve_language(lang)

        # Retrieve dictionary
        lang_dict = TRANSLATIONS.get(target_lang, TRANSLATIONS["en-US"])

        # Get string
        text = lang_dict.get(key, TRANSLATIONS["en-US"].get(key, key))

        # Format if arguments provided
        if kwargs:
            try:
                text = text.format(**kwargs)
            except Exception as e:
                logger.warning(f"Translation formatting failed for {key}: {e}")

        return text

    async def _get_user_context(
        self,
        __user__: Optional[dict],
        __event_call__: Optional[Callable] = None,
        __request__: Optional[Request] = None,
    ) -> dict:
        """
        Robust extraction of user context with multi-level fallback for language detection.
        Priority: localStorage (via JS) > HTTP headers > User profile > en-US
        """
        user_data = __user__ if isinstance(__user__, dict) else {}
        user_id = user_data.get("id", "unknown_user")
        user_name = user_data.get("name", "User")
        user_language = user_data.get("language", "en-US")

        # 1. Fallback: HTTP Accept-Language header
        if __request__ and hasattr(__request__, "headers"):
            accept_lang = __request__.headers.get("accept-language", "")
            if accept_lang:
                user_language = accept_lang.split(",")[0].split(";")[0]

        # 2. Priority: Frontend localStorage via JS (requires timeout protection)
        if __event_call__:
            try:
                js_code = """
                    try {
                        return (
                            document.documentElement.lang ||
                            localStorage.getItem('locale') || 
                            navigator.language || 
                            'en-US'
                        );
                    } catch (e) {
                        return 'en-US';
                    }
                """
                # MUST use wait_for with timeout to prevent backend deadlock
                frontend_lang = await asyncio.wait_for(
                    __event_call__({"type": "execute", "data": {"code": js_code}}),
                    timeout=2.0,
                )
                if frontend_lang and isinstance(frontend_lang, str):
                    user_language = frontend_lang
            except Exception:
                pass  # Fallback to existing language

        return {
            "user_id": user_id,
            "user_name": user_name,
            "user_language": user_language,
        }

    def _get_chat_context(
        self, body: dict, __metadata__: Optional[dict] = None
    ) -> Dict[str, str]:
        """Unified extraction of chat context information"""
        chat_id = ""
        message_id = ""

        if isinstance(body, dict):
            chat_id = body.get("chat_id", "")
            message_id = body.get("id", "")

            if not chat_id or not message_id:
                body_metadata = body.get("metadata", {})
                if isinstance(body_metadata, dict):
                    if not chat_id:
                        chat_id = body_metadata.get("chat_id", "")
                    if not message_id:
                        message_id = body_metadata.get("message_id", "")

        if __metadata__ and isinstance(__metadata__, dict):
            if not chat_id:
                chat_id = __metadata__.get("chat_id", "")
            if not message_id:
                message_id = __metadata__.get("message_id", "")

        return {
            "chat_id": str(chat_id).strip(),
            "message_id": str(message_id).strip(),
        }

    def _contains_html(self, content: str) -> bool:
        """Check if content contains HTML tags"""
        pattern = r"<\s*/?\s*(?:html|head|body|div|p|hr|ul|ol|li|table|thead|tbody|tfoot|tr|td|th|img|a|code|pre|blockquote|h[1-6]|script|style|form|input|button|label|select|option|iframe|link|meta|title)\b"
        return bool(re.search(pattern, content, re.IGNORECASE))

    async def _emit_status(
        self, __event_emitter__, applied_fixes: List[str], lang: str
    ):
        """Emit status notification with i18n support"""
        if not self.valves.show_status or not applied_fixes:
            return

        # Map internal fix IDs to i18n keys
        fix_key_map = {
            "Fix Escape Chars": "fix_escape",
            "Normalize Thought Tags": "fix_thought",
            "Normalize Details Tags": "fix_details",
            "Fix Code Blocks": "fix_code",
            "Normalize LaTeX": "fix_latex",
            "Fix List Format": "fix_list",
            "Close Code Blocks": "fix_close_code",
            "Fix Full-width Symbols": "fix_fullwidth",
            "Fix Mermaid Syntax": "fix_mermaid",
            "Fix Headings": "fix_heading",
            "Fix Tables": "fix_table",
            "Cleanup XML Tags": "fix_xml",
            "Fix Emphasis Spacing": "fix_emphasis",
            "Fix Intra-word Emphasis": "fix_intra_word",
            "Custom Cleaner": "fix_custom",
        }

        prefix = self._get_translation(lang, "status_prefix")
        translated_fixes = [
            self._get_translation(lang, fix_key_map.get(fix, fix))
            for fix in applied_fixes
        ]

        description = f"{prefix}: {', '.join(translated_fixes)}"

        try:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": description,
                        "done": True,
                    },
                }
            )
        except Exception as e:
            logger.error(f"Error emitting status: {e}")

    async def _emit_debug_log(
        self,
        __event_call__,
        applied_fixes: List[str],
        original: str,
        normalized: str,
        chat_id: str = "",
    ):
        """Emit debug log to browser console via JS execution"""
        if not self.valves.show_debug_log or not __event_call__:
            return

        try:
            js_code = f"""
                (async function() {{
                    console.group("🛠️ Markdown Normalizer Debug");
                    console.log("Chat ID:", {json.dumps(chat_id)});
                    console.log("Applied Fixes:", {json.dumps(applied_fixes, ensure_ascii=False)});
                    console.log("Original Content:", {json.dumps(original, ensure_ascii=False)});
                    console.log("Normalized Content:", {json.dumps(normalized, ensure_ascii=False)});
                    console.groupEnd();
                }})();
            """
            await __event_call__(
                {
                    "type": "execute",
                    "data": {"code": js_code},
                }
            )
        except Exception as e:
            # We don't want to fail the whole normalization if debug logging fails
            pass

    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
        __event_call__=None,
        __metadata__: Optional[dict] = None,
        __request__: Optional[Request] = None,
    ) -> dict:
        """Process response body"""
        if "messages" in body and body["messages"]:
            last = body["messages"][-1]
            content = last.get("content", "") or ""

            if last.get("role") == "assistant" and isinstance(content, str):
                if self._contains_html(content):
                    return body

                if (
                    '""&quot;' in content
                    or "tool_call_id" in content
                    or '<details type="tool_calls"' in content
                ):
                    return body

                config = NormalizerConfig(
                    enable_escape_fix=self.valves.enable_escape_fix,
                    enable_escape_fix_in_code_blocks=self.valves.enable_escape_fix_in_code_blocks,
                    enable_thought_tag_fix=self.valves.enable_thought_tag_fix,
                    enable_details_tag_fix=self.valves.enable_details_tag_fix,
                    enable_code_block_fix=self.valves.enable_code_block_fix,
                    enable_latex_fix=self.valves.enable_latex_fix,
                    enable_list_fix=self.valves.enable_list_fix,
                    enable_unclosed_block_fix=self.valves.enable_unclosed_block_fix,
                    enable_fullwidth_symbol_fix=self.valves.enable_fullwidth_symbol_fix,
                    enable_mermaid_fix=self.valves.enable_mermaid_fix,
                    enable_heading_fix=self.valves.enable_heading_fix,
                    enable_table_fix=self.valves.enable_table_fix,
                    enable_xml_tag_cleanup=self.valves.enable_xml_tag_cleanup,
                    enable_emphasis_spacing_fix=self.valves.enable_emphasis_spacing_fix,
                    enable_intra_word_emphasis_fix=self.valves.enable_intra_word_emphasis_fix,
                )

                normalizer = ContentNormalizer(config)
                new_content = normalizer.normalize(content)

                if new_content != content:
                    last["content"] = new_content

                    if __event_emitter__:
                        user_ctx = await self._get_user_context(
                            __user__, __event_call__, __request__
                        )
                        await self._emit_status(
                            __event_emitter__,
                            normalizer.applied_fixes,
                            user_ctx["user_language"],
                        )
                        chat_ctx = self._get_chat_context(body, __metadata__)
                        await self._emit_debug_log(
                            __event_call__,
                            normalizer.applied_fixes,
                            content,
                            new_content,
                            chat_id=chat_ctx["chat_id"],
                        )

        return body
