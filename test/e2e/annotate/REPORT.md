# InfoBIM annotation test report

Final command:

```sh
QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD/src:$PWD" python -m pytest -q test/e2e/annotation test/unit/annotation
```

Result: **32 passed, 3 failed**, 60.68 s, on `daybreak-release` (`20ef455d`).
The three active failures prove DWG returns PostconditionError instead of a clear
MIME LookupError, and the annotation viewer is hidden after capture/before details
(two tests). Production was not repaired and no skip/xfail was added.

Coverage includes real command/project/DXF/Qt/CSV/RDF/ETL integration, all type
resolution forms and ambiguity, append and same-ID resave, cancellation/location
refusal, CSV atomic replacement and special characters, deterministic concurrent
upsert loss, and the real in-process FSM plus form/window lifecycle contracts.
Qt is mandatory at collection; see [README.md](README.md).

The complete report contains all twelve suspected issues, additional differences,
and the exact test for each of **34 detected and restored mutations**:
[Shared detailed report](../../../../ontobdc/test/e2e/annotation/REPORT.md).
The reproducible mutation runner and JSON evidence are in the ontobdc test tree.

Separately, the six existing project-update cases still fail (three missing-facade
errors and three ID-routing errors). They were neither changed nor counted in
annotation results. The user's pre-existing pyproject.toml edit was preserved.

New files exist only under test/. No commit or push was performed.
