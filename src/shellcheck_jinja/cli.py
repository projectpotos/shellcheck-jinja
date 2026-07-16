"""Render Jinja2 shell templates with fixture data and lint them with shellcheck."""

from __future__ import annotations

import argparse
import subprocess
import sys
import sysconfig
import tempfile
from functools import cache
from pathlib import Path
from typing import Any

import jinja2
import yaml
from ansible.plugins.loader import filter_loader

MAPPING_FILE = "mapping.yml"


def _shellcheck() -> Path:
    """Return the shellcheck binary of the pinned shellcheck-py dependency."""
    return Path(sysconfig.get_path("scripts")) / "shellcheck"


@cache
def _ansible_filters() -> dict[str, Any]:
    """Collect ansible's Jinja filters under both short and fully-qualified names."""
    filters: dict[str, Any] = {}
    for plugin in filter_loader.all():
        func = plugin.j2_function
        filters[plugin.ansible_name] = func
        filters[plugin.ansible_name.rpartition(".")[2]] = func
    return filters


def _environment(template_dir: Path) -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=False,
        keep_trailing_newline=True,
        autoescape=False,
    )
    env.filters.update(_ansible_filters())
    return env


def _load_mapping(mapping_path: Path) -> dict[str, list[str]]:
    """Read the template to fixtures mapping, normalizing values to lists."""
    raw = yaml.safe_load(mapping_path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{mapping_path}: must be a YAML mapping of template to fixture files")
    mapping: dict[str, list[str]] = {}
    for template, fixtures in raw.items():
        if isinstance(fixtures, str):
            fixtures = [fixtures]
        if not isinstance(fixtures, list) or not all(isinstance(f, str) for f in fixtures):
            raise ValueError(f"{mapping_path}: {template}: must map to a fixture file or a list of them")
        mapping[str(template)] = fixtures
    return mapping


def _output_name(fixture_name: str) -> str:
    """
    Helper to render nice output.
    """
    base = "--".join(Path(fixture_name).parts).removesuffix(".yml")
    if base.endswith(".sh"):
        return base
    stem, _, variant = base.rpartition(".")
    return f"{stem.removesuffix('.sh')}.{variant}.sh"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shellcheck-jinja", description=__doc__)
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=Path("tests/shellcheck-fixtures"),
        help="directory containing the mapping and fixture files (default: %(default)s)",
    )
    parser.add_argument(
        "--path-base",
        type=Path,
        default=Path("."),
        help="base directory the mapped template paths are relative to (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    mapping_path = args.fixtures_dir / MAPPING_FILE
    if not mapping_path.is_file():
        print(f"shellcheck-jinja: no {mapping_path}, nothing to do")
        return 0
    try:
        mapping = _load_mapping(mapping_path)
    except ValueError as exc:
        print(f"shellcheck-jinja: error: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []
    rendered: list[str] = []
    referenced = {args.fixtures_dir / fixture for fixtures in mapping.values() for fixture in fixtures}

    errors.extend(
        f"{orphan}: fixture not referenced in {mapping_path}"
        for orphan in sorted(args.fixtures_dir.rglob("*.yml"))
        if orphan != mapping_path and orphan not in referenced
    )

    # The tempdir lives inside the working tree so shellcheck picks up a
    # repository .shellcheckrc when checking the rendered scripts.
    with tempfile.TemporaryDirectory(prefix=".shellcheck-jinja-", dir=".") as tmp:
        tmpdir = Path(tmp)
        for template, fixtures in sorted(mapping.items()):
            template_path = args.path_base / template
            if not template_path.is_file():
                errors.append(f"{mapping_path}: {template}: no such template under {args.path_base}")
                continue
            env = _environment(template_path.parent)
            for fixture_name in fixtures:
                fixture = args.fixtures_dir / fixture_name
                if not fixture.is_file():
                    errors.append(f"{mapping_path}: {template}: fixture {fixture} not found")
                    continue
                context = yaml.safe_load(fixture.read_text()) or {}
                if not isinstance(context, dict):
                    errors.append(f"{fixture}: fixture must be a YAML mapping")
                    continue
                out = tmpdir / _output_name(fixture_name)
                try:
                    out.write_text(env.get_template(template_path.name).render(**context))
                except jinja2.TemplateError as exc:
                    errors.append(f"{template_path} with {fixture}: {type(exc).__name__}: {exc}")
                    continue
                print(f"shellcheck-jinja: rendered {template_path} with {fixture}")
                rendered.append(out.name)

        if errors:
            for error in errors:
                print(f"shellcheck-jinja: error: {error}", file=sys.stderr)
            return 1
        if not rendered:
            print("shellcheck-jinja: nothing mapped, nothing to do")
            return 0

        return subprocess.run([_shellcheck(), "--", *rendered], cwd=tmpdir, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
