"""Tests for the shellcheck-jinja CLI."""

from pathlib import Path

import pytest

from shellcheck_jinja.cli import _load_mapping, main

DATA_DIR = Path(__file__).parent / "data"
CLEAN_TEMPLATE = (DATA_DIR / "greet.sh.j2").read_text()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write(root: Path, path: str, content: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


def test_load_mapping_normalizes_values(tmp_path):
    mapping_file = tmp_path / "mapping.yml"
    mapping_file.write_text("a.sh.j2: a.sh.yml\nb.sh.j2: [b.sh.yml, b.sh.extra.yml]\n")
    assert _load_mapping(mapping_file) == {"a.sh.j2": ["a.sh.yml"], "b.sh.j2": ["b.sh.yml", "b.sh.extra.yml"]}


def test_load_mapping_rejects_bad_shapes(tmp_path):
    mapping_file = tmp_path / "mapping.yml"
    mapping_file.write_text("- a.sh.j2\n")
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        _load_mapping(mapping_file)


def test_passing_example(monkeypatch, capsys):
    monkeypatch.chdir(DATA_DIR / "passing")
    assert main([]) == 0
    assert capsys.readouterr().out.count("rendered templates/greet.sh.j2") == 2


def test_failing_example(monkeypatch):
    monkeypatch.chdir(DATA_DIR / "failing")
    assert main([]) != 0


def test_incomplete_fixture_fails(repo, capsys):
    write(repo, "templates/greet.sh.j2", CLEAN_TEMPLATE)
    write(repo, "tests/shellcheck-fixtures/greet.sh.yml", "{}\n")
    write(repo, "tests/shellcheck-fixtures/mapping.yml", "templates/greet.sh.j2: greet.sh.yml\n")
    assert main([]) == 1
    assert "UndefinedError" in capsys.readouterr().err


def test_missing_template_and_fixture_fail(repo, capsys):
    write(repo, "tests/shellcheck-fixtures/mapping.yml", "templates/gone.sh.j2: gone.sh.yml\n")
    assert main([]) == 1
    assert "no such template" in capsys.readouterr().err


def test_unreferenced_fixture_fails(repo, capsys):
    write(repo, "templates/greet.sh.j2", CLEAN_TEMPLATE)
    write(repo, "tests/shellcheck-fixtures/greet.sh.yml", "greeting: hello\n")
    write(repo, "tests/shellcheck-fixtures/stray.sh.yml", "greeting: hello\n")
    write(repo, "tests/shellcheck-fixtures/mapping.yml", "templates/greet.sh.j2: greet.sh.yml\n")
    assert main([]) == 1
    assert "not referenced" in capsys.readouterr().err


def test_invalid_mapping_value_fails(repo, capsys):
    write(repo, "tests/shellcheck-fixtures/mapping.yml", "templates/greet.sh.j2: {nested: wrong}\n")
    assert main([]) == 1
    assert "must map to a fixture file" in capsys.readouterr().err


def test_missing_fixture_fails(repo, capsys):
    write(repo, "templates/greet.sh.j2", CLEAN_TEMPLATE)
    write(repo, "tests/shellcheck-fixtures/mapping.yml", "templates/greet.sh.j2: gone.sh.yml\n")
    assert main([]) == 1
    assert "not found" in capsys.readouterr().err


def test_non_mapping_fixture_fails(repo, capsys):
    write(repo, "templates/greet.sh.j2", CLEAN_TEMPLATE)
    write(repo, "tests/shellcheck-fixtures/greet.sh.yml", "- not a mapping\n")
    write(repo, "tests/shellcheck-fixtures/mapping.yml", "templates/greet.sh.j2: greet.sh.yml\n")
    assert main([]) == 1
    assert "must be a YAML mapping" in capsys.readouterr().err


def test_missing_mapping_is_a_noop(repo, capsys):
    assert main([]) == 0
    assert "nothing to do" in capsys.readouterr().out


def test_empty_mapping_is_a_noop(repo, capsys):
    write(repo, "tests/shellcheck-fixtures/mapping.yml", "{}\n")
    assert main([]) == 0
    assert "nothing to do" in capsys.readouterr().out


def test_path_base_and_fixtures_dir_args(repo, capsys):
    write(repo, "src/templates/greet.sh.j2", CLEAN_TEMPLATE)
    write(repo, "checks/greet.sh.yml", "greeting: hello\n")
    write(repo, "checks/mapping.yml", "greet.sh.j2: greet.sh.yml\n")
    assert main(["--path-base", "src/templates", "--fixtures-dir", "checks"]) == 0
    assert "rendered src/templates/greet.sh.j2" in capsys.readouterr().out
