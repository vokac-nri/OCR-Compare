from app.core.mddiff import (diff_blocks, normalize_inline, similarity,
                             split_blocks, word_diff)


class TestNormalizeInline:
    def test_emphasis_markers_stripped(self):
        assert normalize_inline("**bold** and *em* and __u__ and ~~s~~") == \
            "bold and em and u and s"

    def test_links_keep_text_drop_target(self):
        assert normalize_inline("see [the docs](http://x/y) here") == \
            "see the docs here"

    def test_images_keep_alt(self):
        assert normalize_inline("![figure 1](img/f1.png)") == "figure 1"

    def test_html_tags_dropped(self):
        assert normalize_inline('a <b>bold</b> <span style="x">word</span>') == \
            "a bold word"

    def test_code_span_ticks_dropped(self):
        assert normalize_inline("run `make all` now") == "run make all now"

    def test_snake_case_survives(self):
        assert normalize_inline("the file_name field") == "the file_name field"

    def test_escapes_unescaped(self):
        assert normalize_inline(r"100\% \(approx\.\)") == "100% (approx.)"

    def test_escaped_emphasis_marker_survives_stripping(self):
        assert normalize_inline(r"a \* b") == "a * b"
        assert normalize_inline(r"\_literal\_") == "_literal_"

    def test_whitespace_collapsed(self):
        assert normalize_inline("  a \t b  ") == "a b"


class TestSplitBlocks:
    def test_soft_wrapped_paragraph_is_one_block(self):
        blocks = split_blocks("line one\nline two\n\nnext para")
        assert [b.kind for b in blocks] == ["para", "para"]
        assert blocks[0].norm == "line one line two"

    def test_heading_levels_in_kind(self):
        blocks = split_blocks("# Title\n\n## Sub")
        assert [(b.kind, b.norm) for b in blocks] == \
            [("h1", "Title"), ("h2", "Sub")]

    def test_setext_heading_vs_hr(self):
        blocks = split_blocks("Title\n---\n\n---")
        assert [b.kind for b in blocks] == ["h2", "hr"]
        assert blocks[0].norm == "Title"

    def test_fence_is_one_block_with_verbatim_norm(self):
        blocks = split_blocks("```python\nx = 1\n\ny = 2\n```")
        assert len(blocks) == 1
        assert blocks[0].kind == "code"
        assert blocks[0].norm == "x = 1\n\ny = 2"

    def test_table_is_one_block_separator_ignored(self):
        blocks = split_blocks("| a | b |\n|---|---|\n| 1 | 2 |")
        assert len(blocks) == 1
        assert blocks[0].kind == "table"
        assert blocks[0].norm == "a | b ¦ 1 | 2"

    def test_list_items_are_separate_blocks(self):
        blocks = split_blocks("- one\n- two\n  continued")
        assert [b.kind for b in blocks] == ["list", "list"]
        assert blocks[1].norm == "two continued"

    def test_quote_grouped(self):
        blocks = split_blocks("> a\n> b")
        assert [(b.kind, b.norm) for b in blocks] == [("quote", "a b")]


class TestDiffBlocks:
    def test_markup_noise_compares_equal(self):
        left = split_blocks("# Title\n\n**Hello** world, see [x](http://a).")
        right = split_blocks("# Title\n\n__Hello__ world, see [x](http://b).")
        assert [op[0] for op in diff_blocks(left, right)] == ["equal"]

    def test_bullet_style_compares_equal(self):
        left = split_blocks("- item one\n- item two")
        right = split_blocks("* item one\n* item two")
        assert [op[0] for op in diff_blocks(left, right)] == ["equal"]

    def test_line_wrap_compares_equal(self):
        left = split_blocks("one two\nthree four")
        right = split_blocks("one two three\nfour")
        assert [op[0] for op in diff_blocks(left, right)] == ["equal"]

    def test_heading_level_change_is_a_difference(self):
        left = split_blocks("# Title")
        right = split_blocks("## Title")
        assert [op[0] for op in diff_blocks(left, right)] == ["replace"]

    def test_real_text_change_detected(self):
        left = split_blocks("same\n\nthe quick brown fox")
        right = split_blocks("same\n\nthe quick brawn fox")
        assert [op[0] for op in diff_blocks(left, right)] == ["equal", "replace"]


class TestSimilarity:
    def test_identical(self):
        assert similarity("a b c", "a b c") == 1.0

    def test_disjoint(self):
        assert similarity("alpha beta", "gamma delta") == 0.0

    def test_one_word_change_is_high(self):
        assert similarity("the quick brown fox jumps",
                          "the quick brawn fox jumps") > 0.7


class TestWordDiff:
    def test_single_word_replace(self):
        assert word_diff("the quick brown fox", "the quick brawn fox") == [
            ("equal", "the quick"),
            ("delete", "brown"),
            ("insert", "brawn"),
            ("equal", "fox"),
        ]

    def test_pure_insert(self):
        assert word_diff("a c", "a b c") == [
            ("equal", "a"), ("insert", "b"), ("equal", "c")]
