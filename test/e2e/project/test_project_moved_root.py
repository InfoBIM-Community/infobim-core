import shutil
from pathlib import Path
from typing import Any, Dict, List


from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimProjectMovedRoot:
    """
    A project keeps working after its storage root is moved, or opened in a
    different file system from the one it was created in (e.g. created in a
    browser's virtual one and opened on disk): the root is found by its
    ``.__ontobdc__`` marker and the recorded locations are reconciled with
    where things are now.
    """

    @staticmethod
    def _infobim(cwd: Path, *arguments: str) -> Dict[str, Any]:
        result: CliInvocationResult = InfobimCliProcessRunner(cwd).run(*arguments)
        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["severity"] is None, result.stdout
        return result.json

    def _create_then_move(self, tmp_path: Path) -> Path:
        created_at: Path = tmp_path / "created-at"
        created_at.mkdir()
        self._infobim(created_at, "init")
        created: Dict[str, Any] = self._infobim(created_at, "project", "--create", "Meu Projeto")
        assert Path(created["content"]["path"]).name == "meu-projeto"
        moved_to: Path = (tmp_path / "moved-to").resolve()
        shutil.move(str(created_at), str(moved_to))
        return moved_to

    def test_inspect_inside_the_moved_project_works(self, tmp_path: Path) -> None:
        root: Path = self._create_then_move(tmp_path)

        inspected: Dict[str, Any] = self._infobim(root / "meu-projeto", "project", "--inspect")

        assert inspected["title"] == "InfoBIM Project"
        assert isinstance(inspected["content"]["tree"], dict)

    def test_list_at_the_moved_root_shows_the_project_where_it_is_now(
        self, tmp_path: Path
    ) -> None:
        root: Path = self._create_then_move(tmp_path)

        listed: Dict[str, Any] = self._infobim(root, "project", "--list")

        projects: List[Dict[str, Any]] = listed["content"]["projects"]
        assert [Path(project["location"]).resolve() for project in projects] == [
            root / "meu-projeto"
        ]

    def test_another_project_can_be_created_in_the_moved_root(self, tmp_path: Path) -> None:
        root: Path = self._create_then_move(tmp_path)

        created: Dict[str, Any] = self._infobim(root, "project", "--create", "Outro")

        assert Path(created["content"]["path"]).resolve() == root / "outro"
        listed: Dict[str, Any] = self._infobim(root, "project", "--list")
        assert sorted(
            Path(project["location"]).resolve().name for project in listed["content"]["projects"]
        ) == ["meu-projeto", "outro"]
