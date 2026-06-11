import pytest

from app.core.pages import parse_pages_spec, target_indices


class TestParsePagesSpec:
    def test_singles_and_ranges(self):
        assert parse_pages_spec("2-5,8") == [2, 3, 4, 5, 8]

    def test_single_page(self):
        assert parse_pages_spec("7") == [7]

    def test_dedup_and_sort(self):
        assert parse_pages_spec("8,2-4,3") == [2, 3, 4, 8]

    def test_whitespace_tolerated(self):
        assert parse_pages_spec(" 1 , 3 - 4 ".replace(" ", "")) == [1, 3, 4]
        assert parse_pages_spec("1, 3-4") == [1, 3, 4]

    @pytest.mark.parametrize("bad", ["", "  ", "abc", "1-", "-3", "0", "5-2", "1,,x", "1.5"])
    def test_invalid_specs_raise(self, bad):
        with pytest.raises(ValueError):
            parse_pages_spec(bad)


class TestTargetIndices:
    def test_explicit_pages_win(self):
        assert target_indices([2, 3, 99], max_pages=1, engine_cap=1, total=10) == [1, 2]

    def test_max_pages(self):
        assert target_indices(None, max_pages=3, engine_cap=None, total=10) == [0, 1, 2]

    def test_zero_means_all(self):
        assert target_indices(None, max_pages=0, engine_cap=None, total=4) == [0, 1, 2, 3]

    def test_engine_cap_applies(self):
        assert target_indices(None, max_pages=8, engine_cap=3, total=10) == [0, 1, 2]

    def test_user_limit_below_engine_cap(self):
        assert target_indices(None, max_pages=2, engine_cap=3, total=10) == [0, 1]

    def test_total_clamps(self):
        assert target_indices(None, max_pages=8, engine_cap=None, total=2) == [0, 1]

    def test_explicit_out_of_range_dropped_entirely(self):
        assert target_indices([99], max_pages=8, engine_cap=None, total=2) == []
