from pathlib import Path

import pytest

from datascan.index import CandidateIndex, fingerprint


def test_batched_index_preserves_matches_across_batches_and_scopes():
    with CandidateIndex(batch_size=1) as index:
        path = Path(index.directory.name)
        index.add((0, 0, 6, 1), "A", 6, {"exact": (1., 2., 3., 4., 5., 6.)})
        index.add((1, 0, 6, 1), "B", 6, {"exact": (1., 2., 3., 4., 5., 6.)})
        index.add((2, 8, 14, 1), "A", 6, {"exact": (1., 2., 3., 4., 5., 6.)})
        with index.groups("exact") as groups:
            matches = [list(group) for group in groups]
        assert matches == [[(0, 0, 6, 1), (2, 8, 14, 1)]]
        assert index.count == 3
    assert not path.exists()


def test_temporary_index_is_removed_when_scan_fails():
    with pytest.raises(RuntimeError):
        with CandidateIndex() as index:
            path = Path(index.directory.name)
            raise RuntimeError("synthetic error")
    assert not path.exists()


def test_cancelled_query_cleans_up_without_masking_cancellation():
    cancel = False
    with CandidateIndex(cancelled=lambda: cancel) as index:
        path = Path(index.directory.name)
        index.add((0, 0, 6, 1), "", 6, {"exact": tuple(range(6))})
        cancel = True
        with pytest.raises(InterruptedError):
            with index.groups("exact") as groups:
                list(groups)
    assert not path.exists()


def test_repeated_queries_use_distinct_signatures_and_no_shared_cursor():
    with CandidateIndex() as index:
        index.add((0, 0, 6, 1), "", 6, {"exact": tuple(range(6)), "affine": tuple(range(6))})
        index.add((1, 0, 6, 1), "", 6, {"exact": tuple(range(6)), "affine": tuple(range(6))})
        for kind in ("exact", "affine"):
            with index.groups(kind) as groups:
                assert len([list(group) for group in groups]) == 1


def test_fingerprint_uses_numeric_zero_equivalence():
    assert fingerprint((-0.0, 1.2)) == fingerprint((0.0, 1.2))


def test_cancellation_inside_sql_work_reports_interrupted_not_database_error():
    with CandidateIndex() as index:
        for number in range(5000):
            index.add((number, 0, 6, 1), "", 6, {"exact": (float(number),)})
        calls = 0

        def cancelled():
            nonlocal calls
            calls += 1
            return calls > 1

        index.cancelled = cancelled
        with pytest.raises(InterruptedError):
            with index.groups("exact") as groups:
                list(groups)


def test_cancellation_during_insert_is_not_a_failure_dialog():
    cancel = False
    with CandidateIndex(cancelled=lambda: cancel) as index:
        index.add((0, 0, 6, 1), "", 6, {"exact": tuple(range(6))})
        cancel = True
        index.connection.set_progress_handler(lambda: int(cancel), 1)
        with pytest.raises(InterruptedError):
            index.add((1, 0, 6, 1), "", 6, {"exact": tuple(range(6))})
