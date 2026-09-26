import pytest

from app.inspect_chunks import inspect_edge_cases, inspect_email, main


def test_trace_shows_pipeline_and_real_chunks(capsys: pytest.CaptureFixture[str]) -> None:
    inspect_email("email_001", 60)
    output = capsys.readouterr().out
    for stage in ("PARSE JSON", "SELECT RECORD", "CREATE EmailData", "CLEAN BODY", "SPLIT TEXT", "ATTACH METADATA", "VERIFY"):
        assert stage in output
    assert "email_001:chunk:0000" in output
    assert "email_001:chunk:0001" in output
    assert "slice=[0:60]" in output
    assert "original unchanged" in output


def test_missing_fixture_is_explicit() -> None:
    with pytest.raises(ValueError, match="not found"):
        inspect_email("missing", 60)


def test_invalid_size_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["inspect_chunks", "--max-chars", "0"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


def test_edge_case_trace(capsys: pytest.CaptureFixture[str]) -> None:
    inspect_edge_cases()
    output = capsys.readouterr().out
    assert "all 7 edge cases" in output
    assert "body_text must be a string" in output
    assert "labels must be a list of strings" in output
    assert "0 chunks" in output
