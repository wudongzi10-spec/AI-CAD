import unittest

from app import _detect_unsupported_instruction
from core.cad_engine import CADBuilder


class _Box:
    def __init__(self, xmin, ymin, zmin, xmax, ymax, zmax):
        self.XMin = xmin
        self.YMin = ymin
        self.ZMin = zmin
        self.XMax = xmax
        self.YMax = ymax
        self.ZMax = zmax


def _shift_bounds(bounds, adjustment):
    shifted = {}
    for axis in ("x", "y", "z"):
        shifted[axis] = {
            "min": bounds[axis]["min"] + adjustment.get(axis, 0.0),
            "max": bounds[axis]["max"] + adjustment.get(axis, 0.0),
        }
    return shifted


class CADBuilderBooleanAdjustmentTests(unittest.TestCase):
    def test_unsupported_instruction_detector_rejects_freeform_object(self):
        message = _detect_unsupported_instruction("帮我建一个长得很像皮卡丘的十二面体。")

        self.assertIn("暂不支持", message)

    def test_validate_blueprint_rejects_unsupported_primitive(self):
        blueprint = {
            "objects": [
                {
                    "id": "dodecahedron",
                    "freecad_type": "Part::RegularPolygon",
                    "properties": {"Number of sides": 12, "Radius": 1},
                }
            ],
            "operations": [],
        }

        with self.assertRaisesRegex(ValueError, "Unsupported CAD primitive"):
            CADBuilder._validate_blueprint(blueprint)

    def test_validate_blueprint_rejects_missing_required_property(self):
        blueprint = {
            "objects": [
                {
                    "id": "box",
                    "freecad_type": "Part::Box",
                    "properties": {"Length": 10, "Width": 10},
                }
            ],
            "operations": [],
        }

        with self.assertRaisesRegex(ValueError, "Missing required properties"):
            CADBuilder._validate_blueprint(blueprint)

    def test_validate_blueprint_rejects_unsupported_boolean_operation(self):
        blueprint = {
            "objects": [
                {
                    "id": "box",
                    "freecad_type": "Part::Box",
                    "properties": {"Length": 10, "Width": 10, "Height": 10},
                }
            ],
            "operations": [{"type": "subtract", "base": "box", "tool": "box"}],
        }

        with self.assertRaisesRegex(ValueError, "Unsupported boolean operation"):
            CADBuilder._validate_blueprint(blueprint)

    def test_top_center_offset_matching_target_half_height_is_normalized(self):
        target_box = _Box(0.0, 0.0, 0.0, 100.0, 100.0, 100.0)

        normalized = CADBuilder._normalize_face_alignment_offset(
            "top_center",
            {"x": 0.0, "y": 0.0, "z": 50.0},
            target_box,
        )

        self.assertEqual(normalized["z"], 0.0)

    def test_top_center_offset_matching_target_full_height_is_normalized(self):
        target_box = _Box(0.0, 0.0, 0.0, 50.0, 50.0, 50.0)

        normalized = CADBuilder._normalize_face_alignment_offset(
            "top_center",
            {"x": 0.0, "y": 0.0, "z": 50.0},
            target_box,
        )

        self.assertEqual(normalized["z"], 0.0)

    def test_bottom_center_offset_matching_target_half_height_is_normalized(self):
        target_box = _Box(-10.0, -10.0, -40.0, 10.0, 10.0, 40.0)

        normalized = CADBuilder._normalize_face_alignment_offset(
            "bottom_center",
            {"x": 0.0, "y": 0.0, "z": -40.0},
            target_box,
        )

        self.assertEqual(normalized["z"], 0.0)

    def test_left_offset_matching_current_width_is_normalized(self):
        target_box = _Box(-50.0, -50.0, -2.5, 50.0, 50.0, 2.5)
        current_box = _Box(0.0, 0.0, 0.0, 20.0, 20.0, 20.0)

        normalized = CADBuilder._normalize_face_alignment_offset(
            "left",
            {"x": -20.0, "y": 0.0, "z": 0.0},
            target_box,
            current_box,
        )

        self.assertEqual(normalized["x"], 0.0)

    def test_right_offset_matching_target_width_is_normalized(self):
        target_box = _Box(-50.0, -50.0, -2.5, 50.0, 50.0, 2.5)
        current_box = _Box(-15.0, -15.0, -15.0, 15.0, 15.0, 15.0)

        normalized = CADBuilder._normalize_face_alignment_offset(
            "right",
            {"x": 100.0, "y": 0.0, "z": 0.0},
            target_box,
            current_box,
        )

        self.assertEqual(normalized["x"], 0.0)

    def test_non_matching_offset_is_preserved(self):
        target_box = _Box(0.0, 0.0, 0.0, 100.0, 100.0, 100.0)

        normalized = CADBuilder._normalize_face_alignment_offset(
            "top_center",
            {"x": 0.0, "y": 0.0, "z": 15.0},
            target_box,
        )

        self.assertEqual(normalized["z"], 15.0)

    def test_cut_tool_touching_top_face_is_shifted_into_base(self):
        base_axes = {
            "x": {"min": 0.0, "max": 60.0},
            "y": {"min": 0.0, "max": 60.0},
            "z": {"min": 0.0, "max": 60.0},
        }
        tool_axes = {
            "x": {"min": 15.0, "max": 45.0},
            "y": {"min": 15.0, "max": 45.0},
            "z": {"min": 60.0, "max": 160.0},
        }

        adjustment = CADBuilder._calculate_cut_overlap_adjustment(base_axes, tool_axes)

        self.assertIsNotNone(adjustment)
        self.assertEqual(adjustment["x"], 0.0)
        self.assertEqual(adjustment["y"], 0.0)
        self.assertLess(adjustment["z"], -59.9)

        shifted_tool = _shift_bounds(tool_axes, adjustment)
        self.assertGreater(CADBuilder._axis_overlap_length(base_axes["z"], shifted_tool["z"]), 59.9)

    def test_cut_tool_with_single_axis_gap_is_shifted_sideways(self):
        base_axes = {
            "x": {"min": 0.0, "max": 40.0},
            "y": {"min": 0.0, "max": 40.0},
            "z": {"min": 0.0, "max": 20.0},
        }
        tool_axes = {
            "x": {"min": 40.0, "max": 60.0},
            "y": {"min": 10.0, "max": 30.0},
            "z": {"min": 0.0, "max": 20.0},
        }

        adjustment = CADBuilder._calculate_cut_overlap_adjustment(base_axes, tool_axes)

        self.assertIsNotNone(adjustment)
        self.assertLess(adjustment["x"], -19.9)
        self.assertEqual(adjustment["y"], 0.0)
        self.assertEqual(adjustment["z"], 0.0)

    def test_cut_tool_separated_on_multiple_axes_is_left_unchanged(self):
        base_axes = {
            "x": {"min": 0.0, "max": 40.0},
            "y": {"min": 0.0, "max": 40.0},
            "z": {"min": 0.0, "max": 20.0},
        }
        tool_axes = {
            "x": {"min": 40.0, "max": 60.0},
            "y": {"min": 40.0, "max": 60.0},
            "z": {"min": 20.0, "max": 40.0},
        }

        adjustment = CADBuilder._calculate_cut_overlap_adjustment(base_axes, tool_axes)

        self.assertIsNone(adjustment)

    def test_fuse_tool_with_gap_is_shifted_to_slightly_overlap(self):
        base_axes = {
            "x": {"min": -10.0, "max": 10.0},
            "y": {"min": -10.0, "max": 10.0},
            "z": {"min": 0.0, "max": 80.0},
        }
        tool_axes = {
            "x": {"min": -25.0, "max": 25.0},
            "y": {"min": -25.0, "max": 25.0},
            "z": {"min": 120.0, "max": 170.0},
        }

        adjustment = CADBuilder._calculate_fuse_overlap_adjustment(base_axes, tool_axes)

        self.assertIsNotNone(adjustment)
        self.assertEqual(adjustment["x"], 0.0)
        self.assertEqual(adjustment["y"], 0.0)
        self.assertLess(adjustment["z"], -40.0)

        shifted_tool = _shift_bounds(tool_axes, adjustment)
        self.assertGreater(CADBuilder._axis_overlap_length(base_axes["z"], shifted_tool["z"]), 0.0)
        self.assertLess(CADBuilder._axis_overlap_length(base_axes["z"], shifted_tool["z"]), 0.01)

    def test_fuse_anchor_uses_tools_align_target(self):
        align_targets = {
            "cylinder": "base_cube",
            "cone": "cylinder",
        }
        op = {"type": "fuse", "base": "base_cube", "tool": "cone"}

        anchor_id = CADBuilder._resolve_boolean_anchor_id(op, align_targets)

        self.assertEqual(anchor_id, "cylinder")


if __name__ == "__main__":
    unittest.main()
