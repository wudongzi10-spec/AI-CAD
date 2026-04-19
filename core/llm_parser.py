import json
import re
import time
import urllib.request

from config import API_KEY, LLM_API_BASE_URL, LLM_MODEL, LLM_PROVIDER, LLM_TIMEOUT


class LLMParser:
    """
    Turn natural-language CAD prompts into a compact JSON blueprint.
    """

    def __init__(self):
        self.max_retries = 4
        self.base_delay = 5

    def parse_instruction(self, user_input, llm_config=None, api_key=None):
        resolved_config = self._resolve_llm_config(llm_config=llm_config, api_key=api_key)
        if not resolved_config["api_key"]:
            raise ValueError("LLM API Key is not configured.")
        if not resolved_config["api_base_url"]:
            raise ValueError("LLM API endpoint is not configured.")
        if not resolved_config["model"]:
            raise ValueError("LLM model is not configured.")

        for attempt in range(self.max_retries):
            try:
                raw_response = self._call_api(user_input, resolved_config)
                clean_dict = self._extract_and_validate_json(raw_response)
                print(f"[INFO] [LLMParser] Parse attempt {attempt + 1} succeeded.")
                return clean_dict
            except Exception as exc:
                error_msg = str(exc)
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    delay = self.base_delay * (2 ** attempt)
                    print(f"[WARN] [LLMParser] Rate limited, retrying in {delay} seconds.")
                    time.sleep(delay)
                else:
                    print(f"[WARN] [LLMParser] Parse attempt {attempt + 1} failed: {error_msg}")
                    time.sleep(1)

        raise ValueError("The language model could not complete the request after multiple attempts.")

    def _resolve_llm_config(self, llm_config=None, api_key=None):
        llm_config = llm_config or {}
        return {
            "provider": (llm_config.get("provider") or LLM_PROVIDER or "moonshot").strip(),
            "api_base_url": self._normalize_api_base_url(llm_config.get("api_base_url") or LLM_API_BASE_URL or ""),
            "model": (llm_config.get("model") or LLM_MODEL or "").strip(),
            "api_key": (api_key or llm_config.get("api_key") or API_KEY or "").strip(),
        }

    def _normalize_api_base_url(self, api_base_url):
        normalized = (api_base_url or "").strip().rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized[: -len("/chat/completions")]
        return normalized

    def _call_api(self, user_input, llm_config):
        system_prompt = """
You are an expert in FreeCAD Python API.
Convert the user's natural-language 3D CAD instruction into strict JSON only.
Do not output markdown or explanation text.

Rules:
1. Use an "objects" array to define primitives.
- "id": unique identifier
- "freecad_type": one of "Part::Box", "Part::Cylinder", "Part::Sphere", "Part::Cone", "Part::Torus"
- "properties":
  - Box: Length, Width, Height
  - Cylinder: Radius, Height
  - Sphere: Radius
  - Cone: Radius1, Radius2, Height
  - Torus: Radius1, Radius2
- "rotation": {"x": 0, "y": 0, "z": 0}
- "align": {"target": "object_id", "type": "top_center" | "bottom_center" | "left" | "right" | "front" | "back" | "center", "offset": {"x": 0, "y": 0, "z": 0}}
- "position": use absolute coordinates only when there is no "align"
- target may be "origin" to mean the world origin

2. Use an "operations" array for boolean operations.
- "type": "cut" | "fuse" | "common"
- "base": base object id
- "tool": tool object id

3. Prefer align relationships for assembly-like placement.
4. For holes, slots, and cut operations, the tool object must intersect the base volume instead of only touching its surface.
5. If align is used for a cut tool, add an "offset" when needed so the tool penetrates the target by the intended depth.
6. For fuse operations, the participating solids should touch or slightly overlap; do not leave visible gaps.
7. For top_center/bottom_center alignment, positive z offset moves further away from the target and negative z offset moves into it.
8. For spheres attached to the ends of a cylinder, prefer zero z offset with top_center/bottom_center unless extra spacing is explicitly requested.
9. Do not duplicate the target half-size inside align.offset. Face-alignment types already place the object on the target face.
10. For holes, prefer centered alignment where appropriate.
11. Output valid JSON only.
        """.strip()

        data = {
            "model": llm_config["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            "temperature": 0.1,
        }

        request_url = f"{llm_config['api_base_url']}/chat/completions"
        req = urllib.request.Request(request_url, data=json.dumps(data).encode("utf-8"))
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {llm_config['api_key']}")

        response = urllib.request.urlopen(req, timeout=LLM_TIMEOUT)
        result = json.loads(response.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"]

    def _extract_and_validate_json(self, raw_str):
        match = re.search(r"\{.*\}", raw_str.replace("\n", ""), re.DOTALL)
        clean_str = match.group(0) if match else raw_str
        return json.loads(clean_str)
