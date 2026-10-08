"""Real CSV storage, including stale-snapshot lost update behavior."""

import csv
import pytest
from infobim.annotation.adapter.csv_repository import AnnotationCsvRepository


@pytest.fixture
def repository(tmp_path):
    repo = AnnotationCsvRepository()
    repo.create_data_source(tmp_path)
    return repo, tmp_path


def test_create_has_only_identifier_and_add_columns_is_idempotent(repository):
    repo, dataset = repository
    assert repo.columns(dataset) == ["global_id"]
    repo.add_columns(dataset, ["title", "text"])
    repo.add_columns(dataset, ["title", "text"])
    assert repo.columns(dataset) == ["global_id", "title", "text"]
    assert repo.rows(dataset) == {}


def test_upsert_replaces_in_place_appends_and_empties_omitted_fields(repository):
    repo, dataset = repository
    repo.add_columns(dataset, ["title", "text"])
    repo.upsert_rows(
        dataset,
        [
            dict(global_id="a", title="First", text="old"),
            dict(global_id="b", title="Second"),
        ],
    )
    repo.upsert_rows(
        dataset,
        [dict(global_id="a", title="Changed"), dict(global_id="c", title="Third")],
    )
    rows = repo.rows(dataset)
    assert list(rows) == ["a", "b", "c"]
    assert rows["a"] == dict(global_id="a", title="Changed", text="")
    assert rows["b"]["title"] == "Second"
    with repo.data_source_path(dataset).open(newline="") as handle:
        persisted = list(csv.DictReader(handle))
    assert [row["global_id"] for row in persisted] == ["a", "b", "c"]


@pytest.mark.parametrize(
    "row",
    [
        dict(global_id="a", unknown="bad"),
        dict(title="no identifier"),
        dict(global_id="", title="blank"),
    ],
)
def test_invalid_row_preserves_existing_csv(repository, row):
    repo, dataset = repository
    repo.add_columns(dataset, ["title"])
    before = repo.data_source_path(dataset).read_bytes()
    message = "no column" if "unknown" in row else "needs a global_id"
    with pytest.raises(ValueError, match=message):
        repo.upsert_rows(dataset, [row])
    assert repo.data_source_path(dataset).read_bytes() == before
    assert not list(dataset.rglob("*.tmp"))


def test_quotes_newlines_unicode_and_wkt_round_trip_without_temporary_files(repository):
    repo, dataset = repository
    repo.add_columns(dataset, ["title", "text", "geometry"])
    row = dict(
        global_id="a",
        title="Revisão elétrica",
        text='Comma, "quotes"\nsecond line',
        geometry="LINESTRING(1.5 2, 3 4)",
    )
    repo.upsert_rows(dataset, [row])
    assert repo.rows(dataset)["a"] == row
    assert not list(dataset.rglob("*.tmp"))


def test_newest_csv_receives_writes_and_older_csv_is_ignored(tmp_path):
    directory = tmp_path / "payload/document"
    directory.mkdir(parents=True)
    older = directory / "Annotation_Dataset_20250101000000.csv"
    newer = directory / "Annotation_Dataset_20260101000000.csv"
    older.write_text("global_id,title\nold,Old\n")
    newer.write_text("global_id,title\nnew,New\n")
    before = older.read_bytes()
    repo = AnnotationCsvRepository()
    assert repo.data_source_path(tmp_path) == newer
    assert list(repo.rows(tmp_path)) == ["new"]
    repo.upsert_rows(tmp_path, [dict(global_id="added", title="Added")])
    assert list(repo.rows(tmp_path)) == ["new", "added"]
    assert older.read_bytes() == before


def test_interleaved_read_modify_write_snapshots_can_lose_an_annotation(repository):
    # Two writers read before either replaces the file. This explicitly exercises
    # the real IO primitives, not threads/sleeps or a mock of upsert_rows.
    repo, dataset = repository
    repo.add_columns(dataset, ["title"])
    columns_a, snapshot_a = repo._read(dataset)
    columns_b, snapshot_b = repo._read(dataset)
    snapshot_a.append(dict(global_id="a", title="Writer A"))
    snapshot_b.append(dict(global_id="b", title="Writer B"))
    repo._write(dataset, columns_a, snapshot_a)
    assert list(repo.rows(dataset)) == ["a"]
    repo._write(dataset, columns_b, snapshot_b)
    assert list(repo.rows(dataset)) == ["b"]


def test_two_public_upserts_interleaved_at_read_boundary_lose_first_row(repository):
    """Pause real reads using Python tracing; repository methods stay intact."""
    import sys
    import threading

    repo, dataset = repository
    repo.add_columns(dataset, ["title"])
    read_by_a = threading.Event()
    read_by_b = threading.Event()
    written_by_a = threading.Event()
    errors = []
    read_code = AnnotationCsvRepository._read.__code__

    def writer(identifier):
        def trace(frame, event, arg):
            if frame.f_code is read_code and event == "return":
                if identifier == "a":
                    read_by_a.set()
                    if not read_by_b.wait(5):
                        raise RuntimeError("writer B did not read")
                else:
                    read_by_b.set()
                    if not written_by_a.wait(5):
                        raise RuntimeError("writer A did not write")
            return trace

        try:
            sys.settrace(trace)
            repo.upsert_rows(dataset, [dict(global_id=identifier, title=identifier)])
        except BaseException as error:
            errors.append(error)
        finally:
            sys.settrace(None)
            if identifier == "a":
                written_by_a.set()

    a = threading.Thread(target=writer, args=("a",))
    b = threading.Thread(target=writer, args=("b",))
    a.start()
    assert read_by_a.wait(5)
    b.start()
    a.join(6)
    b.join(6)
    assert not a.is_alive() and not b.is_alive()
    assert errors == []
    assert list(repo.rows(dataset)) == ["b"]


def test_atomic_update_keeps_previous_complete_csv_visible_until_replace(repository):
    """Observe real disk contents immediately before the atomic replacement."""
    import inspect
    import sys

    repo, dataset = repository
    repo.add_columns(dataset, ["title"])
    repo.upsert_rows(dataset, [dict(global_id="a", title="Previous")])
    path = repo.data_source_path(dataset)
    previous = path.read_bytes()
    source, first_line = inspect.getsourcelines(AnnotationCsvRepository._write)
    replacement_line = first_line + next(
        index for index, line in enumerate(source) if "os.replace(" in line
    )
    observed = []

    def observe(frame, event, arg):
        if (
            frame.f_code is AnnotationCsvRepository._write.__code__
            and event == "line"
            and frame.f_lineno == replacement_line
        ):
            temporary_files = list(path.parent.glob("*.tmp"))
            observed.append(
                (
                    path.read_bytes(),
                    [temporary.read_bytes() for temporary in temporary_files],
                )
            )
        return observe

    previous_trace = sys.gettrace()
    try:
        sys.settrace(observe)
        repo.upsert_rows(dataset, [dict(global_id="a", title="Updated")])
    finally:
        sys.settrace(previous_trace)
    assert len(observed) == 1
    old_contents, ready_files = observed[0]
    assert old_contents == previous
    assert len(ready_files) == 1
    assert ready_files[0].decode() == "global_id,title\r\na,Updated\r\n"
    assert path.read_bytes() == ready_files[0]
    assert repo.rows(dataset)["a"]["title"] == "Updated"
    assert not list(path.parent.glob("*.tmp"))
