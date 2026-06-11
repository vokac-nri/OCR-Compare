from app.core.scoring import _normalize, score, strip_markdown


class TestNormalize:
    def test_case_and_whitespace(self):
        assert _normalize("  Hello\n\tWORLD  ") == "hello world"

    def test_empty(self):
        assert _normalize(None) == ""


class TestStripMarkdown:
    def test_headings_emphasis_tables(self):
        md = "## Title\n\n**bold** and _it_\n\n| a | b |\n|---|---|\n| 1 | 2 |"
        flat = strip_markdown(md)
        assert "#" not in flat and "*" not in flat and "|" not in flat
        assert "Title" in flat and "bold" in flat and "1" in flat

    def test_links_images_html(self):
        assert strip_markdown("[text](http://x) ![alt](img.png) <img src='x'>").split() == \
            ["text", "alt"]


class TestScore:
    def test_identical(self):
        s = score("The quick brown fox", "the  quick BROWN fox")
        assert s == {"cer": 0.0, "wer": 0.0}

    def test_empty_reference(self):
        assert score("", "anything") == {"cer": None, "wer": None}

    def test_one_word_substitution(self):
        s = score("a b c d", "a b x d")
        assert s["wer"] == 0.25

    def test_empty_hypothesis_is_total_error(self):
        s = score("abcd", "")
        assert s["cer"] == 1.0
