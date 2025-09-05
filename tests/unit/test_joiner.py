# tests/unit/test_joiner.py
import pandas as pd
import pytest

from services.joiner import left_join, JoinerError


def test_left_join_happy_path():
    # Left table (features): 4 rows, keys a,b
    left = pd.DataFrame(
        {
            "a": [1, 2, 3, 4],
            "b": ["x", "x", "y", "z"],
            "f1": [10.0, 11.0, 12.0, 13.0],
        }
    )
    # Right table (response): one row per (a,b) except (4,"z") is missing
    right = pd.DataFrame(
        {
            "aa": [1, 2, 3],
            "bb": ["x", "x", "y"],
            "resp": [0.1, 0.2, 0.3],
        }
    )

    merged, dx = left_join(left, right, key_pairs=[("a", "aa"), ("b", "bb")])

    # shape: left-join preserves left row count
    assert len(merged) == 4
    # last row has NaN response
    assert pd.isna(merged.loc[3, "resp"])

    # diagnostics sanity
    assert dx["join_type"] == "left"
    assert dx["left_rows"] == 4
    assert dx["right_rows"] == 3
    assert dx["matched_left_rows"] == 3
    assert pytest.approx(dx["join_rate"]) == 3 / 4
    assert dx["left_only"] == 1
    # In right, unique keys = {(1,x),(2,x),(3,y)}; all appear on the left, so right_only == 0
    assert dx["right_only"] == 0
    assert isinstance(dx["dup_key_left"], int)
    assert isinstance(dx["dup_key_right"], int)
    assert dx["right_cols_added"] >= 1  # "resp"


def test_left_join_with_duplicates_and_m2m():
    # Left has duplicate key (2,'x') twice
    left = pd.DataFrame(
        {
            "a": [1, 2, 2, 4],
            "b": ["x", "x", "x", "z"],
            "f1": [10.0, 11.0, 11.1, 13.0],
        }
    )
    # Right has duplicate key (2,'x') twice as well (many-to-many)
    right = pd.DataFrame(
        {
            "aa": [2, 2, 4],
            "bb": ["x", "x", "z"],
            "resp": [0.21, 0.22, 0.4],
        }
    )

    merged, dx = left_join(left, right, key_pairs=[("a", "aa"), ("b", "bb")])

    # m2m produces row expansion for the duplicated (2,'x') pairs
    # Left has two rows with (2,'x'); Right has two rows with (2,'x') -> 2*2 = 4 merged rows for that key
    # Plus (1,'x') left-only row (no match) -> 1 row
    # Plus (4,'z') joining to one right row -> 1 row
    # Total = 4 + 1 + 1 = 6
    assert len(merged) == 6

    # dup counts should be > 0 for both sides
    assert dx["dup_key_left"] > 0
    assert dx["dup_key_right"] > 0

    # join rate counts *left rows* that found at least one match: (2,'x') rows (2 rows) + (4,'z') (1 row) = 3
    assert dx["matched_left_rows"] == 3
    assert dx["left_only"] == 1  # (1,'x')


def test_left_join_input_validation():
    left = pd.DataFrame({"a": [1]})
    right = pd.DataFrame({"aa": [1]})

    with pytest.raises(JoinerError):
        _ = left_join(left, right, key_pairs=[])

    with pytest.raises(JoinerError):
        _ = left_join(left, right, key_pairs=[("a", "missing_right_col")])

    with pytest.raises(JoinerError):
        _ = left_join(None, right, key_pairs=[("a", "aa")])  # type: ignore

    with pytest.raises(JoinerError):
        _ = left_join(left, None, key_pairs=[("a", "aa")])  # type: ignore
