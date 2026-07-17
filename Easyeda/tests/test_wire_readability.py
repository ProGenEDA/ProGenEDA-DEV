from Easyeda.geometry import (
    WireSpanIndex,
    _candidate_paths,
    _path_is_compact,
    segments_collinear_overlap,
)


def test_collinear_overlap_requires_positive_shared_length() -> None:
    assert segments_collinear_overlap((0, 0), (0, 20), (0, 10), (0, 30))
    assert segments_collinear_overlap((0, 5), (20, 5), (10, 5), (30, 5))
    assert not segments_collinear_overlap((0, 0), (0, 20), (0, 20), (0, 30))
    assert not segments_collinear_overlap((0, 0), (0, 20), (5, 0), (5, 20))
    assert not segments_collinear_overlap((0, 0), (20, 0), (10, -10), (10, 10))


def test_wire_span_index_reserves_only_same_axis_spans() -> None:
    index = WireSpanIndex()
    index.add("NET_A", (10, 0), (10, 30))
    index.add("NET_A", (0, 40), (30, 40))

    assert index.overlaps((((10, 20), (10, 50)),), "NET_B")
    assert index.overlaps((((20, 40), (50, 40)),), "NET_B")
    assert not index.overlaps((((10, 30), (10, 50)),), "NET_B")
    assert not index.overlaps((((0, 20), (30, 20)),), "NET_B")
    assert not index.overlaps((((10, 20), (10, 50)),), "NET_A")


def test_wire_span_index_rollback_removes_failed_route() -> None:
    index = WireSpanIndex()
    checkpoint = index.checkpoint()
    index.add("FAILED", (10, 0), (10, 30))
    index.rollback(checkpoint)

    assert not index.overlaps((((10, 10), (10, 40)),), "NEXT")


def test_dense_lane_search_stays_local_to_branch() -> None:
    paths = _candidate_paths(
        (100.0, 100.0),
        (300.0, 300.0),
        (100.0, 100.0, 300.0, 300.0),
        23,
    )
    coordinates = [point for path in paths for point in path]

    assert min(point[0] for point in coordinates) >= -8.0
    assert max(point[0] for point in coordinates) <= 408.0
    assert min(point[1] for point in coordinates) >= -8.0
    assert max(point[1] for point in coordinates) <= 408.0


def test_compact_path_budget_rejects_perimeter_loops() -> None:
    assert _path_is_compact(((0.0, 0.0), (0.0, 30.0), (100.0, 30.0), (100.0, 0.0)))
    assert not _path_is_compact(
        ((0.0, 0.0), (0.0, 1000.0), (100.0, 1000.0), (100.0, 0.0))
    )
