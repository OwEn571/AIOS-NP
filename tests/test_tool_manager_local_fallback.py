import unittest
from unittest.mock import patch

from aios.tool.manager import ToolManager


class ToolManagerLocalFallbackTest(unittest.TestCase):
    def test_local_name_falls_back_to_local_registry(self) -> None:
        manager = ToolManager.__new__(ToolManager)

        with patch(
            "aios.tool.manager.AutoTool.from_preloaded",
            side_effect=[RuntimeError("remote missing"), object()],
        ) as mocked_loader:
            tool = manager.load_tool_instance("hot_api")

        self.assertIsNotNone(tool)
        self.assertEqual(mocked_loader.call_args_list[0].args, ("hot_api",))
        self.assertEqual(mocked_loader.call_args_list[1].args, ("hot_api",))
        self.assertEqual(mocked_loader.call_args_list[1].kwargs, {"local": True})

    def test_namespaced_name_falls_back_to_local_short_name(self) -> None:
        manager = ToolManager.__new__(ToolManager)

        with patch(
            "aios.tool.manager.AutoTool.from_preloaded",
            side_effect=[RuntimeError("hub missing"), object()],
        ) as mocked_loader:
            tool = manager.load_tool_instance("owen/hot_api")

        self.assertIsNotNone(tool)
        self.assertEqual(mocked_loader.call_args_list[0].args, ("owen/hot_api",))
        self.assertEqual(mocked_loader.call_args_list[1].args, ("hot_api",))
        self.assertEqual(mocked_loader.call_args_list[1].kwargs, {"local": True})


if __name__ == "__main__":
    unittest.main()
