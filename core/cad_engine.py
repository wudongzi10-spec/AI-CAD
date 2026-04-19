import os
import sys
import uuid

from config import FREECAD_BIN_PATH, FREECAD_PYTHON_PATH, STATIC_DIR


FreeCAD = None
Part = None
FREECAD_IMPORT_ERROR = None


def _is_freecad_python_runtime():
    executable_dir = os.path.dirname(os.path.abspath(sys.executable))
    freecad_dir = os.path.abspath(FREECAD_BIN_PATH)
    return os.path.normcase(executable_dir) == os.path.normcase(freecad_dir)


def _build_runtime_fix_hint(error_text):
    normalized = (error_text or "").lower()
    if "python311.dll" in normalized and "conflicts with this version of python" in normalized:
        return (
            "当前后端不是用 FreeCAD 自带的 Python 3.11 启动的。"
            f"请改用 `{FREECAD_PYTHON_PATH} app.py`，"
            "或执行项目根目录下的 `start_demo_backend.ps1`。"
        )
    return ""


if FREECAD_BIN_PATH and not _is_freecad_python_runtime() and FREECAD_BIN_PATH not in sys.path:
    sys.path.append(FREECAD_BIN_PATH)

if hasattr(os, "add_dll_directory") and not _is_freecad_python_runtime() and os.path.isdir(FREECAD_BIN_PATH):
    os.add_dll_directory(FREECAD_BIN_PATH)

try:
    import FreeCAD  # type: ignore
    import Part  # type: ignore
except Exception as exc:  # FreeCAD may raise non-ImportError runtime failures on Windows.
    FREECAD_IMPORT_ERROR = exc


def get_cad_engine_status():
    raw_error = "" if FREECAD_IMPORT_ERROR is None else str(FREECAD_IMPORT_ERROR)
    fix_hint = _build_runtime_fix_hint(raw_error)
    return {
        "available": FREECAD_IMPORT_ERROR is None,
        "freecad_bin_path": FREECAD_BIN_PATH,
        "freecad_python_path": FREECAD_PYTHON_PATH,
        "path_exists": os.path.isdir(FREECAD_BIN_PATH),
        "python_path_exists": os.path.isfile(FREECAD_PYTHON_PATH),
        "host_python_version": sys.version.split()[0],
        "error": raw_error,
        "fix_hint": fix_hint,
    }


class CADBuilder:
    def __init__(self, doc_name="SmartCAD"):
        status = get_cad_engine_status()
        if not status["available"]:
            details = status["fix_hint"] or status["error"] or "未知错误"
            raise RuntimeError(f"FreeCAD 引擎不可用: {details}")

        self.doc_id = f"{doc_name}_{uuid.uuid4().hex[:6]}"
        self.doc = FreeCAD.newDocument(self.doc_id)
        self.created_parts = {}
        self.final_exports = []

    def execute_blueprint(self, blueprint_dict):
        objects_data = blueprint_dict.get("objects", [])
        operations_data = blueprint_dict.get("operations", [])

        self._build_shapes(objects_data)
        self._apply_spatial_constraints(objects_data)
        self._ensure_boolean_tool_overlap(operations_data)
        self._apply_booleans(operations_data)
        return self._export_model()

    @staticmethod
    def _coerce_number(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @classmethod
    def _extract_offset_vector(cls, align):
        align = align or {}
        offset = align.get("offset") or {}
        return {
            "x": cls._coerce_number(offset.get("x", 0)),
            "y": cls._coerce_number(offset.get("y", 0)),
            "z": cls._coerce_number(offset.get("z", 0)),
        }

    @staticmethod
    def _bound_box_to_axes(bound_box):
        return {
            "x": {"min": float(bound_box.XMin), "max": float(bound_box.XMax)},
            "y": {"min": float(bound_box.YMin), "max": float(bound_box.YMax)},
            "z": {"min": float(bound_box.ZMin), "max": float(bound_box.ZMax)},
        }

    @staticmethod
    def _axis_overlap_length(base_axis, tool_axis):
        return min(base_axis["max"], tool_axis["max"]) - max(base_axis["min"], tool_axis["min"])

    @classmethod
    def _calculate_boolean_overlap_adjustment(cls, base_axes, tool_axes, op_type, epsilon=1e-4):
        separated_axes = []
        for axis in ("x", "y", "z"):
            if cls._axis_overlap_length(base_axes[axis], tool_axes[axis]) <= epsilon:
                separated_axes.append(axis)

        if len(separated_axes) != 1:
            return None

        axis = separated_axes[0]
        base_axis = base_axes[axis]
        tool_axis = tool_axes[axis]

        if tool_axis["min"] >= base_axis["max"] - epsilon:
            gap = tool_axis["min"] - base_axis["max"]
            direction = -1.0
        elif tool_axis["max"] <= base_axis["min"] + epsilon:
            gap = base_axis["min"] - tool_axis["max"]
            direction = 1.0
        else:
            return None

        tool_size = tool_axis["max"] - tool_axis["min"]
        base_size = base_axis["max"] - base_axis["min"]
        if op_type == "cut":
            penetration = min(tool_size - epsilon, base_size + epsilon)
        elif op_type == "fuse":
            penetration = min(epsilon, tool_size - epsilon)
        else:
            return None
        if penetration <= 0:
            return None

        adjustment = {"x": 0.0, "y": 0.0, "z": 0.0}
        adjustment[axis] = direction * (gap + penetration)
        return adjustment

    @classmethod
    def _calculate_cut_overlap_adjustment(cls, base_axes, tool_axes, epsilon=1e-4):
        return cls._calculate_boolean_overlap_adjustment(base_axes, tool_axes, "cut", epsilon=epsilon)

    @classmethod
    def _calculate_fuse_overlap_adjustment(cls, base_axes, tool_axes, epsilon=1e-4):
        return cls._calculate_boolean_overlap_adjustment(base_axes, tool_axes, "fuse", epsilon=epsilon)

    @staticmethod
    def _axis_span(bound_box, axis):
        if axis == "x":
            return float(bound_box.XMax - bound_box.XMin)
        if axis == "y":
            return float(bound_box.YMax - bound_box.YMin)
        return float(bound_box.ZMax - bound_box.ZMin)

    @classmethod
    def _normalize_face_alignment_offset(cls, align_type, offset, target_box):
        normalized = dict(offset)
        axis_map = {
            "top_center": ("z", 1.0),
            "bottom_center": ("z", -1.0),
            "right": ("x", 1.0),
            "left": ("x", -1.0),
            "back": ("y", 1.0),
            "front": ("y", -1.0),
        }
        axis_info = axis_map.get(align_type)
        if not axis_info:
            return normalized

        axis, direction = axis_info
        face_distance = cls._axis_span(target_box, axis) / 2.0
        offset_value = cls._coerce_number(normalized.get(axis, 0.0))
        tolerance = max(1e-4, face_distance * 0.05)

        if face_distance > 0 and offset_value * direction > 0 and abs(abs(offset_value) - face_distance) <= tolerance:
            normalized[axis] = offset_value - direction * face_distance

        return normalized

    def _build_shapes(self, objects_data):
        for obj_data in objects_data:
            obj_id = obj_data.get("id")
            freecad_type = obj_data.get("freecad_type")
            properties = obj_data.get("properties", {})
            pos = obj_data.get("position", {"x": 0, "y": 0, "z": 0})
            rot = obj_data.get("rotation", {"x": 0, "y": 0, "z": 0})

            try:
                obj = self.doc.addObject(freecad_type, obj_id)
                for prop_name, prop_value in properties.items():
                    if hasattr(obj, prop_name):
                        setattr(obj, prop_name, float(prop_value))

                obj.Placement.Rotation = FreeCAD.Rotation(
                    rot.get("z", 0),
                    rot.get("y", 0),
                    rot.get("x", 0),
                )
                obj.Placement.Base = FreeCAD.Vector(
                    pos.get("x", 0),
                    pos.get("y", 0),
                    pos.get("z", 0),
                )
                self.created_parts[obj_id] = obj
            except Exception as exc:
                print(f"[WARN] [CADEngine] Failed to create {freecad_type}: {exc}")

        self.doc.recompute()
        self.final_exports = list(self.created_parts.values())

    def _apply_spatial_constraints(self, objects_data):
        for obj_data in objects_data:
            align = obj_data.get("align")
            if not align:
                continue

            target_name = (align.get("target") or "").strip().lower()
            if target_name in {"origin", "world", "global"}:
                target_box = FreeCAD.BoundBox(0, 0, 0, 0, 0, 0)
            else:
                target_obj = self.created_parts.get(align.get("target"))
                if not target_obj:
                    continue
                target_box = target_obj.Shape.BoundBox

            curr_obj = self.created_parts.get(obj_data.get("id"))
            if not curr_obj:
                continue

            current_box = curr_obj.Shape.BoundBox
            move_vec = FreeCAD.Vector(0, 0, 0)
            align_type = align.get("type")

            move_vec.x = (target_box.XMax + target_box.XMin) / 2 - (current_box.XMax + current_box.XMin) / 2
            move_vec.y = (target_box.YMax + target_box.YMin) / 2 - (current_box.YMax + current_box.YMin) / 2

            if align_type == "top_center":
                move_vec.z = target_box.ZMax - current_box.ZMin
            elif align_type == "bottom_center":
                move_vec.z = target_box.ZMin - current_box.ZMax
            elif align_type == "right":
                move_vec.x = target_box.XMax - current_box.XMin
                move_vec.z = target_box.ZMin - current_box.ZMin
            elif align_type == "left":
                move_vec.x = target_box.XMin - current_box.XMax
                move_vec.z = target_box.ZMin - current_box.ZMin
            elif align_type == "front":
                move_vec.y = target_box.YMin - current_box.YMax
                move_vec.z = target_box.ZMin - current_box.ZMin
            elif align_type == "back":
                move_vec.y = target_box.YMax - current_box.YMin
                move_vec.z = target_box.ZMin - current_box.ZMin
            elif align_type == "center":
                move_vec.z = (target_box.ZMax + target_box.ZMin) / 2 - (current_box.ZMax + current_box.ZMin) / 2

            offset = self._extract_offset_vector(align)
            offset = self._normalize_face_alignment_offset(align_type, offset, target_box)
            move_vec += FreeCAD.Vector(offset["x"], offset["y"], offset["z"])
            curr_obj.Placement.Base += move_vec

        self.doc.recompute()

    def _ensure_boolean_tool_overlap(self, operations_data):
        for op in operations_data:
            op_type = op.get("type")
            if op_type not in {"cut", "fuse"}:
                continue

            base_id = op.get("base")
            tool_id = op.get("tool")
            base_obj = self.created_parts.get(base_id)
            tool_obj = self.created_parts.get(tool_id)
            if not (base_obj and tool_obj):
                continue

            base_axes = self._bound_box_to_axes(base_obj.Shape.BoundBox)
            tool_axes = self._bound_box_to_axes(tool_obj.Shape.BoundBox)
            adjustment = self._calculate_boolean_overlap_adjustment(base_axes, tool_axes, op_type)
            if not adjustment:
                continue

            tool_obj.Placement.Base += FreeCAD.Vector(
                adjustment["x"],
                adjustment["y"],
                adjustment["z"],
            )
            self.doc.recompute()
            print(
                f"[INFO] [CADEngine] Adjusted {op_type} tool '{tool_id}' "
                f"against '{base_id}' by {adjustment} to ensure overlap."
            )

    def _apply_booleans(self, operations_data):
        index = 0
        while index < len(operations_data):
            op = operations_data[index]
            op_type = op.get("type")

            if op_type == "fuse":
                base_id = op.get("base")
                base_obj = self.created_parts.get(base_id)
                if not base_obj:
                    index += 1
                    continue

                tools = []
                tool_ids = []
                next_index = index
                while next_index < len(operations_data):
                    next_op = operations_data[next_index]
                    if next_op.get("type") != "fuse" or next_op.get("base") != base_id:
                        break

                    tool_id = next_op.get("tool")
                    tool_obj = self.created_parts.get(tool_id)
                    if tool_obj:
                        tools.append(tool_obj)
                        tool_ids.append(tool_id)
                    next_index += 1

                if not tools:
                    index = next_index
                    continue

                result_name = f"Fuse_{base_id}_{'_'.join(tool_ids)}"
                result_obj = self.doc.addObject("Part::MultiFuse", result_name)
                result_obj.Shapes = [base_obj] + tools
                self.doc.recompute()

                if base_obj in self.final_exports:
                    self.final_exports.remove(base_obj)
                for tool_obj in tools:
                    if tool_obj in self.final_exports:
                        self.final_exports.remove(tool_obj)
                self.final_exports.append(result_obj)
                self.created_parts[base_id] = result_obj
                index = next_index
                continue

            base_obj = self.created_parts.get(op.get("base"))
            tool_obj = self.created_parts.get(op.get("tool"))
            if not (base_obj and tool_obj):
                index += 1
                continue

            result_obj = None
            if op_type == "cut":
                result_obj = self.doc.addObject("Part::Cut", f"Cut_{op.get('base')}_{op.get('tool')}")
                result_obj.Base = base_obj
                result_obj.Tool = tool_obj
            elif op_type == "common":
                result_obj = self.doc.addObject("Part::Common", f"Common_{op.get('base')}_{op.get('tool')}")
                result_obj.Base = base_obj
                result_obj.Tool = tool_obj

            if result_obj:
                self.doc.recompute()
                if base_obj in self.final_exports:
                    self.final_exports.remove(base_obj)
                if tool_obj in self.final_exports:
                    self.final_exports.remove(tool_obj)
                self.final_exports.append(result_obj)
                self.created_parts[op.get("base")] = result_obj

            index += 1

        self.doc.recompute()

    def _export_model(self):
        if not self.final_exports:
            raise ValueError("没有生成任何有效的几何体。")

        filename = f"model_{uuid.uuid4().hex[:8]}.stl"
        output_path = os.path.join(STATIC_DIR, filename)

        Part.export(self.final_exports, output_path)
        if not os.path.isfile(output_path):
            raise RuntimeError("STL export did not produce a file.")
        FreeCAD.closeDocument(self.doc_id)
        return filename
