"""Real contexts and on-disk fixtures without CLI subprocesses."""

import ezdxf
from ontobdc.cli.adapter.context import IsolatedCliContextAdapter


def context(root):
    directory = root / ".__ontobdc__"
    directory.mkdir(exist_ok=True)
    (directory / "config.yaml").write_text("context: {}\n")
    return IsolatedCliContextAdapter([], root_dir=str(root))


def workspace(root):
    from ontobdc.container.plugin.check.is_container_metadata_ready.hotfix import (
        main as metadata,
    )
    from ontobdc.container.plugin.check.is_container_storage_index_ready.hotfix import (
        main as index,
    )
    from ontobdc.container.plugin.check.is_container_datapackage_updated.hotfix import (
        main as datapackage,
    )
    from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
        main as manifest,
    )

    execution = context(root)
    directory = root / "hospital-norte"
    directory.mkdir()
    for prepare in [metadata, index, datapackage, manifest]:
        assert prepare(container_path=str(directory), root_path=str(root)) == 0
    drawing = directory / "planta.dxf"
    document = ezdxf.new()
    document.modelspace().add_line((0, 0), (10, 10))
    document.saveas(drawing)
    return directory, drawing, execution
