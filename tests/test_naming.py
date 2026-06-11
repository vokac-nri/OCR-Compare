from datetime import datetime
from pathlib import Path

from app.core.naming import (file_folder_name, output_file_name, run_dir_name,
                             sanitize_stem, unique_run_dir)


class TestRunDirName:
    def test_spec_example_format(self):
        assert run_dir_name(datetime(2026, 6, 10, 14, 13)) == "10JUN20261413"

    def test_zero_padding(self):
        assert run_dir_name(datetime(2026, 1, 2, 3, 4)) == "02JAN20260304"

    def test_locale_independent_months(self):
        # Built from an explicit table, never strftime("%b")
        assert run_dir_name(datetime(2026, 12, 31, 23, 59)) == "31DEC20262359"

    def test_collision_suffix(self, tmp_path):
        now = datetime(2026, 6, 10, 14, 13)
        (tmp_path / "10JUN20261413").mkdir()
        assert unique_run_dir(tmp_path, now).name == "10JUN20261413_2"


class TestSanitize:
    def test_clean_passthrough(self):
        assert sanitize_stem("mycooldoc1") == "mycooldoc1"

    def test_bad_chars_collapse(self):
        assert sanitize_stem("my cool döc (final)") == "my_cool_d_c_final"

    def test_empty_fallback(self):
        assert sanitize_stem("???") == "file"

    def test_truncation(self):
        assert len(sanitize_stem("x" * 200)) == 80


class TestFolderAndFileNames:
    def test_spec_example(self):
        assert file_folder_name(Path("mycooldoc1.pdf"), set()) == "mycooldoc1_pdf"
        assert file_folder_name(Path("mycoolpic.png"), set()) == "mycoolpic_png"

    def test_collision_case_insensitive(self):
        # Original case is preserved; collisions are detected case-insensitively
        # (NTFS is case-insensitive).
        taken = {"report_pdf"}
        assert file_folder_name(Path("Report.PDF"), taken) == "Report_pdf_2"

    def test_output_file_name_spec_example(self):
        assert output_file_name("paddleocr", "mycooldoc1_pdf", "md") == \
            "paddleocr_mycooldoc1_pdf.md"

    def test_hyphenated_engine_id(self):
        assert output_file_name("paddleocr-vl", "doc_pdf", "md") == \
            "paddleocr_vl_doc_pdf.md"
