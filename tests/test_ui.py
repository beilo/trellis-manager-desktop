from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.api import TrellisAPI  # noqa: E402
from app.config import ManagerConfig, save_config  # noqa: E402


class FakeDialogWindow:
    def __init__(self, result: list[str] | None) -> None:
        self.result = result

    def create_file_dialog(self, *_args: object, **_kwargs: object) -> list[str] | None:
        return self.result


class TrellisManagerUiTest(unittest.TestCase):
    def test_get_config_serializes_paths_for_frontend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            repo = Path(tmp) / "Trellis"
            project = Path(tmp) / "crm-web-b2c"
            save_config(
                ManagerConfig(
                    trellis_repo=repo,
                    projects=[project],
                    last_selected_project=project,
                    recent_projects=[project],
                ),
                config_path,
            )

            api = TrellisAPI(config_file=config_path)

            self.assertEqual(
                api.get_config(),
                {
                    "trellis_repo": str(repo),
                    "projects": [str(project)],
                    "last_selected_project": str(project),
                    "recent_projects": [str(project)],
                },
            )

    def test_project_apis_persist_list_and_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            repo = Path(tmp) / "Trellis"
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            save_config(ManagerConfig(trellis_repo=repo, projects=[first]), config_path)

            api = TrellisAPI(config_file=config_path)

            api.save_projects([str(first), str(second), str(first)], str(second))
            self.assertEqual(api.get_projects(), [str(first), str(second)])
            self.assertEqual(api.get_config()["last_selected_project"], str(second))

            api.remove_project(str(second))
            self.assertEqual(api.get_projects(), [str(first)])
            self.assertEqual(api.get_config()["last_selected_project"], str(first))

    def test_select_directory_handles_missing_and_present_window(self) -> None:
        api = TrellisAPI()

        self.assertIsNone(api.select_directory())

        api.set_window(FakeDialogWindow(["/tmp/project"]))  # type: ignore[arg-type]
        self.assertEqual(api.select_directory(), "/tmp/project")

        api.set_window(FakeDialogWindow(None))  # type: ignore[arg-type]
        self.assertIsNone(api.select_directory())


if __name__ == "__main__":
    unittest.main()
