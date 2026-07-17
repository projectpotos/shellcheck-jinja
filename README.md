# shellcheck-jinja


`shellcheck-jinja` is a simple tool to shellcheck scripts based on their jinja2 template.
To render the actual script, you have to provide fixtures with the expected jinja variables.

## Usage

```console
$ uv run shellcheck-jinja [--fixtures-dir tests/shellcheck-fixtures] [--path-base .] [--update]
```

- `--fixtures-dir`: directory containing the mapping and fixture files
  (default `tests/shellcheck-fixtures`).
- `--path-base`: base directory the mapped template paths are relative to
  (default `.`).
- `--update`: regenerate the snapshot files

## File mapping

The fixtures directory must contain a file named `mapping.yml` that maps
each template to one or more fixture files. Template paths are relative to
the path base, fixture paths are relative to the fixtures directory:

```yaml
---
src/templates/my-script.sh.j2:
  - my-script.sh.yml
  - my-script.sh.with-other-options.yml
src/templates/my-other-script.sh.j2: my-other-script.sh.yml
```

Each fixture is a YAML mapping that supplies the full Jinja context for one template.

If a template contains if statements, it's worth adding multiple fixtures, so all possible cases are convered.

## Rendering

The rendering tries to match the behavior from ansible as close as possible.

Currently the jinja environment provides the all the builtin ansible filters. Filter plugins from other collections are not yet supported. Also, some variables like `ansible_facts` wont be populated automatically. If you need such variables, make sure to include them in your fixtures.

## Snapshots

The rendered scripts are stored as snapshot files in a `snapshots/` directory
inside the fixtures directory and are committed to the repository. This makes
the actually rendered scripts visible in reviews: any change to a template or
fixture shows up as a diff of the resulting shell script.

By default the tool renders every template and fails if a snapshot is missing,
out of date, or no longer produced by any mapping entry. Run with `--update`
to (re)generate the snapshots and remove stale ones, then commit the result.
Shellcheck runs against the snapshot files, so a repository `.shellcheckrc`
applies to them as usual.


## CI and pre-commit

potos repositories run this tool through the `shellcheck-jinja` input of the
[lint workflow](https://potos.dev/actions/workflows/lint/), and locally
as a pre-commit hook:

```yaml
- repo: local
  hooks:
    - id: shellcheck-jinja
      name: shellcheck-jinja
      entry: uv run shellcheck-jinja --update
      language: system
      files: (\.sh\.j2$|^tests/shellcheck-fixtures/)
      pass_filenames: false
```

Both expect the repository to provide this tool in its locked uv project as
a git dependency pinned to a tag:

```toml
[dependency-groups]
lint = ["shellcheck-jinja"]

[tool.uv.sources]
shellcheck-jinja = { git = "https://github.com/projectpotos/shellcheck-jinja", tag = "v0.1.0" }
```
