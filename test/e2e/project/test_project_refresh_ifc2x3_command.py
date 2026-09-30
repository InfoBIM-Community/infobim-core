import shutil
from typing import ClassVar, Set
from pathlib import Path

import ifcopenshell

from test.e2e.project_workspace import ProjectE2eWorkspace
from test.e2e.cli_process_runner import CliInvocationResult, _BaseCliProcessRunner


class _LongTimeoutInfobimCliProcessRunner(_BaseCliProcessRunner):
    _TIMEOUT_SECONDS: int = 900
    _EXECUTABLE_NAME: str = "infobim"


class TestInfobimProjectRefreshIfc2x3Command:
    """
    An IFC2X3 model can be refreshed into a project and reported healthy.

    IFC2X3 defines fewer derived unit types than IFC4 and derives FARAD with
    an electric-current exponent of 1, so the unit check must only require
    what the model's own schema can express.
    """

    FIXTURE: ClassVar[Path] = (
        Path(__file__).resolve().parents[1] / "fixtures" / "ifc" / "BasicHouse.ifc"
    )

    def test_refresh_accepts_embedded_ifc2x3_model(self, tmp_path: Path) -> None:
        fixture_bytes: bytes = self.FIXTURE.read_bytes()
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        model_path: Path = workspace.project / self.FIXTURE.name
        shutil.copyfile(self.FIXTURE, model_path)
        original_model: ifcopenshell.file = ifcopenshell.open(str(model_path))
        assert original_model.schema_identifier == "IFC2X3"
        original_project_id: str = original_model.by_type("IfcProject")[0].GlobalId
        product: ifcopenshell.entity_instance
        original_product_ids: Set[str] = {
            product.GlobalId for product in original_model.by_type("IfcProduct")
        }

        runner: _LongTimeoutInfobimCliProcessRunner = (
            _LongTimeoutInfobimCliProcessRunner(tmp_path)
        )
        result: CliInvocationResult = runner.run(
            "project", "--global-id", workspace.selector("id"), "--refresh"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "InfoBIM Project Refreshed"
        assert result.json["content"]["current_state"] == "__project_ready_to_render__"
        assert model_path.name in workspace.manifest_files()
        refreshed_model: ifcopenshell.file = ifcopenshell.open(str(model_path))
        assert refreshed_model.schema_identifier == "IFC2X3"
        assert refreshed_model.by_type("IfcProject")[0].GlobalId == original_project_id
        assert {
            product.GlobalId for product in refreshed_model.by_type("IfcProduct")
        } == original_product_ids

        health: CliInvocationResult = runner.run(
            "project", "--global-id", workspace.selector("id"), "--health"
        )
        assert health.exit_code == 0, health.stdout + health.stderr
        assert health.json["severity"] == "SUCCESS", health.stdout
        assert health.json["content"]["healthy"] is True
        assert self.FIXTURE.read_bytes() == fixture_bytes
