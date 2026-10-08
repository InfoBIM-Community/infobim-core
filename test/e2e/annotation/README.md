# Annotation command tests

Install both repositories and brasidatacenter in the same virtual environment,
including pytest, pydantic, rdflib, ezdxf, sismic, pyshacl and
`PySide6-Essentials`. Missing Qt raises a clear collection error; no test skips.
Linux also needs libegl1, libgl1, libxkbcommon0, libfontconfig1 and libdbus-1-3.

```sh
QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD/src:$PWD" python -m pytest -q test/e2e/annotation test/unit/annotation
```

Setup uses installed CLI subprocesses (`init`, `project --create`). The annotation
subprocess runs the actual CLI entry point with `--json`; QTimers simulate only
the human's point selection and form input. Every project lives under tmp_path.
See [REPORT.md](REPORT.md) for coverage, deliberate mutation checks and active defect assertions.
