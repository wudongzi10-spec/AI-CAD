import os
import time
import json
from collections import defaultdict, deque
from urllib import error as urllib_error
from urllib import request as urllib_request

from flask import Flask, jsonify, has_request_context, request, send_from_directory
from flask_cors import CORS

from config import (
    ADMIN_ACCESS_CODE,
    API_KEY,
    APP_CORS_ORIGINS,
    APP_HOST,
    APP_PORT,
    BASE_DIR,
    DEMO_ACCESS_CODE,
    DEMO_ALLOW_DELETE,
    DEMO_ALLOW_DOWNLOAD,
    DEMO_ALLOW_GENERATE,
    DEMO_HISTORY_LIMIT,
    DEMO_MAX_INSTRUCTION_LENGTH,
    DEMO_MODE,
    DEMO_NAME,
    DEMO_RATE_LIMIT_MAX_REQUESTS,
    DEMO_RATE_LIMIT_WINDOW_SECONDS,
    DEMO_SHOW_HISTORY,
    FREECAD_BIN_PATH,
    LLM_API_BASE_URL,
    LLM_MODEL,
    LLM_PROVIDER,
    MAX_HISTORY_LIMIT,
    STATIC_DIR,
)
from core.cad_engine import CADBuilder, get_cad_engine_status
from core.llm_parser import LLMParser
from core.prompt_templates import get_prompt_templates, get_template_by_id
from database.db_manager import DatabaseManager


LEGACY_LLM_API_KEY_SETTING = "moonshot_api_key"
LLM_PROVIDER_SETTING = "llm_provider"
LLM_API_BASE_URL_SETTING = "llm_api_base_url"
LLM_MODEL_SETTING = "llm_model"
LLM_API_KEY_SETTING = "llm_api_key"

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": APP_CORS_ORIGINS or "*"}})

db = DatabaseManager()
llm = LLMParser()
generate_rate_buckets = defaultdict(deque)
LLM_PROVIDER_PRESETS = [
    {"provider": "moonshot", "api_base_url": "https://api.moonshot.cn/v1"},
    {"provider": "deepseek", "api_base_url": "https://api.deepseek.com/v1"},
    {"provider": "openrouter", "api_base_url": "https://openrouter.ai/api/v1"},
    {"provider": "qwen", "api_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    {"provider": "siliconflow", "api_base_url": "https://api.siliconflow.cn/v1"},
    {"provider": "openai", "api_base_url": "https://api.openai.com/v1"},
]


def _count_static_models():
    if not os.path.isdir(STATIC_DIR):
        return 0
    return len([name for name in os.listdir(STATIC_DIR) if name.lower().endswith(".stl")])


def _parse_limit(raw_limit, default=50):
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = default
    return max(1, min(limit, MAX_HISTORY_LIMIT))


def _normalize_source_record_id(value):
    if value in (None, "", 0, "0"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("source_record_id must be an integer.") from exc


def _remove_file_with_retry(file_path, retries=5, delay=0.2):
    if not os.path.exists(file_path):
        return True

    last_error = None
    for _ in range(retries):
        try:
            os.remove(file_path)
            return True
        except PermissionError as exc:
            last_error = exc
            time.sleep(delay)

    if last_error:
        raise last_error
    return False


def _json_error(message, status_code=400, **extra):
    payload = {"status": "error", "message": message}
    if extra:
        payload.update(extra)
    return jsonify(payload), status_code


def _get_client_identifier():
    if not has_request_context():
        return "local"

    forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for

    real_ip = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    return (request.remote_addr or "unknown").strip()


def _is_local_request():
    if not has_request_context():
        return True

    client_id = _get_client_identifier()
    return client_id in {"127.0.0.1", "::1", "localhost"}


def _has_admin_access():
    if _is_local_request():
        return True

    if not ADMIN_ACCESS_CODE:
        return False

    supplied_code = (
        request.headers.get("X-Admin-Access-Code")
        or request.args.get("admin_access_code", "")
        or request.cookies.get("admin_access_code", "")
    )
    return supplied_code == ADMIN_ACCESS_CODE


def _check_demo_access():
    if not DEMO_ACCESS_CODE:
        return True

    supplied_code = (
        request.headers.get("X-Demo-Access-Code")
        or request.args.get("demo_access_code", "")
        or request.cookies.get("demo_access_code", "")
    )
    return supplied_code == DEMO_ACCESS_CODE


def _enforce_generate_rate_limit():
    client_id = _get_client_identifier()
    now = time.time()
    bucket = generate_rate_buckets[client_id]
    window_start = now - DEMO_RATE_LIMIT_WINDOW_SECONDS

    while bucket and bucket[0] < window_start:
        bucket.popleft()

    if len(bucket) >= DEMO_RATE_LIMIT_MAX_REQUESTS:
        retry_after = max(1, int(DEMO_RATE_LIMIT_WINDOW_SECONDS - (now - bucket[0])))
        response = jsonify(
            {
                "status": "error",
                "message": f"Public demo rate limit exceeded. Try again in {retry_after} seconds.",
                "retry_after_seconds": retry_after,
            }
        )
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        return response

    bucket.append(now)
    return None


def _mask_secret(secret):
    if not secret:
        return ""
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}{'*' * (len(secret) - 8)}{secret[-4:]}"


def _normalize_api_base_url(api_base_url):
    normalized = (api_base_url or "").strip().rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized[: -len("/chat/completions")]
    return normalized


def _choose_detected_model(provider, models):
    model_ids = [str(item.get("id", "")).strip() for item in models if str(item.get("id", "")).strip()]
    if not model_ids:
        return ""

    preferred_models = {
        "moonshot": ["moonshot-v1-8k", "moonshot-v1-32k", "kimi-k2-0905-preview"],
        "deepseek": ["deepseek-chat", "deepseek-reasoner"],
        "openai": ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4o"],
        "qwen": ["qwen-plus", "qwen-turbo", "qwen-max"],
    }

    for candidate in preferred_models.get(provider, []):
        if candidate in model_ids:
            return candidate

    return model_ids[0]


def _fetch_provider_models(api_key, api_base_url):
    models_url = f"{_normalize_api_base_url(api_base_url)}/models"
    req = urllib_request.Request(models_url)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    response = urllib_request.urlopen(req, timeout=20)
    payload = json.loads(response.read().decode("utf-8"))
    models = payload.get("data") if isinstance(payload, dict) else None
    return models if isinstance(models, list) else []


def _detect_llm_provider(api_key):
    last_error = None
    for preset in LLM_PROVIDER_PRESETS:
        try:
            models = _fetch_provider_models(api_key, preset["api_base_url"])
            detected_model = _choose_detected_model(preset["provider"], models)
            if detected_model:
                return {
                    "provider": preset["provider"],
                    "api_base_url": preset["api_base_url"],
                    "model": detected_model,
                    "api_key": api_key,
                }
        except urllib_error.HTTPError as exc:
            last_error = exc
            if exc.code in {401, 403, 404}:
                continue
        except Exception as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise ValueError(f"Unable to auto-detect the LLM provider from this API key: {last_error}")
    raise ValueError("Unable to auto-detect the LLM provider from this API key.")


def _get_runtime_llm_config():
    db_provider = (db.get_setting(LLM_PROVIDER_SETTING, "") or "").strip()
    db_api_base_url = (db.get_setting(LLM_API_BASE_URL_SETTING, "") or "").strip()
    db_model = (db.get_setting(LLM_MODEL_SETTING, "") or "").strip()
    db_api_key = (db.get_setting(LLM_API_KEY_SETTING, "") or "").strip()
    if not db_api_key:
        db_api_key = (db.get_setting(LEGACY_LLM_API_KEY_SETTING, "") or "").strip()

    source = "database" if db_api_key else "environment"
    runtime_api_key = db_api_key or (API_KEY or "").strip()
    has_runtime_api_key = bool(runtime_api_key)

    return {
        "provider": (db_provider or (LLM_PROVIDER or "moonshot").strip() or "moonshot") if has_runtime_api_key else "",
        "api_base_url": _normalize_api_base_url(db_api_base_url or (LLM_API_BASE_URL or "").strip()) if has_runtime_api_key else "",
        "model": (db_model or (LLM_MODEL or "").strip()) if has_runtime_api_key else "",
        "api_key": runtime_api_key,
        "source": source if runtime_api_key else "missing",
    }


def _get_llm_status_payload():
    runtime_llm = _get_runtime_llm_config()
    return {
        "ok": bool(runtime_llm["api_key"] and runtime_llm["api_base_url"] and runtime_llm["model"]),
        "source": runtime_llm["source"],
        "configured": bool(runtime_llm["api_key"]),
        "provider": runtime_llm["provider"],
        "api_base_url": runtime_llm["api_base_url"],
        "model": runtime_llm["model"],
        "masked_api_key": _mask_secret(runtime_llm["api_key"]),
        "can_manage": _is_local_request() or bool(ADMIN_ACCESS_CODE),
        "requires_admin_code": (not _is_local_request()) and bool(ADMIN_ACCESS_CODE),
        "compatibility": "openai_compatible_chat_completions",
    }


def _public_runtime_config():
    return {
        "demo_mode": DEMO_MODE,
        "demo_name": DEMO_NAME,
        "requires_access_code": bool(DEMO_ACCESS_CODE),
        "show_history": DEMO_SHOW_HISTORY,
        "allow_generate": DEMO_ALLOW_GENERATE,
        "allow_delete": DEMO_ALLOW_DELETE,
        "allow_download": DEMO_ALLOW_DOWNLOAD,
        "max_instruction_length": DEMO_MAX_INSTRUCTION_LENGTH,
        "rate_limit_window_seconds": DEMO_RATE_LIMIT_WINDOW_SECONDS,
        "rate_limit_max_requests": DEMO_RATE_LIMIT_MAX_REQUESTS,
        "history_limit": DEMO_HISTORY_LIMIT,
    }


@app.before_request
def protect_demo_routes():
    if not DEMO_MODE:
        return None

    protected_paths = {
        "/api/generate",
        "/api/history",
        "/api/download",
        "/api/settings/llm",
    }
    if request.path in protected_paths or request.path.startswith("/api/history/"):
        if not _check_demo_access():
            return _json_error("Demo access code is required.", 401)

    return None


@app.route("/", methods=["GET"])
@app.route("/index.html", methods=["GET"])
def serve_index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api/public-config", methods=["GET"])
def get_public_config():
    return jsonify({"status": "success", "data": _public_runtime_config()})


@app.route("/api/health", methods=["GET"])
def get_health():
    cad_status = get_cad_engine_status()
    stats = db.get_history_stats()

    return jsonify(
        {
            "status": "success",
            "services": {
                "database": {"ok": db.healthcheck()},
                "llm": _get_llm_status_payload(),
                "cad_engine": cad_status,
                "static_dir": {"ok": os.path.isdir(STATIC_DIR), "model_file_count": _count_static_models()},
            },
            "summary": {
                "history_records": stats["total_count"],
                "model_file_count": _count_static_models(),
                "freecad_path_exists": os.path.isdir(FREECAD_BIN_PATH),
            },
            "runtime": _public_runtime_config(),
        }
    )


@app.route("/api/settings/llm", methods=["GET"])
def get_llm_settings():
    return jsonify({"status": "success", "data": _get_llm_status_payload()})


@app.route("/api/settings/llm", methods=["POST"])
def update_llm_settings():
    if not _has_admin_access():
        return _json_error("Admin access is required to update the LLM configuration.", 403)

    data = request.get_json(silent=True) or {}
    api_key = (data.get("api_key") or "").strip()
    clear = bool(data.get("clear"))

    if clear:
        db.delete_setting(LLM_API_KEY_SETTING)
        db.delete_setting(LLM_PROVIDER_SETTING)
        db.delete_setting(LLM_API_BASE_URL_SETTING)
        db.delete_setting(LLM_MODEL_SETTING)
        db.delete_setting(LEGACY_LLM_API_KEY_SETTING)
        return jsonify({"status": "success", "message": "Stored LLM configuration cleared.", "data": _get_llm_status_payload()})

    if not api_key:
        return _json_error("api_key is required unless clear=true.", 400)

    detected_llm = _detect_llm_provider(api_key)
    db.set_setting(LLM_PROVIDER_SETTING, detected_llm["provider"])
    db.set_setting(LLM_API_BASE_URL_SETTING, detected_llm["api_base_url"])
    db.set_setting(LLM_MODEL_SETTING, detected_llm["model"])
    db.set_setting(LLM_API_KEY_SETTING, detected_llm["api_key"])
    db.delete_setting(LEGACY_LLM_API_KEY_SETTING)

    return jsonify(
        {
            "status": "success",
            "message": "LLM configuration auto-detected and saved.",
            "data": _get_llm_status_payload(),
        }
    )


@app.route("/api/stats", methods=["GET"])
def get_stats():
    stats = db.get_history_stats()
    stats["model_file_count"] = _count_static_models()
    return jsonify({"status": "success", "data": stats})


@app.route("/api/templates", methods=["GET"])
def get_templates():
    category = request.args.get("category", "")
    keyword = request.args.get("keyword", "")
    templates = get_prompt_templates(category=category, keyword=keyword)
    return jsonify({"status": "success", "data": templates, "count": len(templates)})


@app.route("/api/generate", methods=["POST"])
def generate_model():
    if DEMO_MODE and not DEMO_ALLOW_GENERATE:
        return _json_error("Public demo generation is currently disabled.", 403)

    rate_limited_response = _enforce_generate_rate_limit() if DEMO_MODE else None
    if rate_limited_response is not None:
        return rate_limited_response

    data = request.get_json(silent=True) or {}
    template_id = (data.get("template_id") or "").strip()
    source_record_id = _normalize_source_record_id(data.get("source_record_id"))

    selected_template = get_template_by_id(template_id) if template_id else None
    if template_id and not selected_template:
        return _json_error("Template does not exist.", 400)

    instruction = (data.get("instruction") or "").strip()
    if not instruction and selected_template:
        instruction = selected_template["instruction"]

    if not instruction:
        return _json_error("Instruction cannot be empty.", 400)

    if DEMO_MODE and len(instruction) > DEMO_MAX_INSTRUCTION_LENGTH:
        return _json_error(
            f"Instruction is too long for the public demo. Limit: {DEMO_MAX_INSTRUCTION_LENGTH} characters.",
            400,
        )

    runtime_llm = _get_runtime_llm_config()
    if not runtime_llm["api_key"]:
        return _json_error("LLM API Key is not configured.", 503)
    if not runtime_llm["api_base_url"]:
        return _json_error("LLM API endpoint is not configured.", 503)
    if not runtime_llm["model"]:
        return _json_error("LLM model is not configured.", 503)

    try:
        print(f"\n[INFO] [MainService] Received instruction: {instruction}")
        blueprint_dict = llm.parse_instruction(instruction, llm_config=runtime_llm)

        builder = CADBuilder()
        filename = builder.execute_blueprint(blueprint_dict)

        record_id = db.insert_history(
            instruction=instruction,
            parsed_json=blueprint_dict,
            file_path=f"/static/{filename}",
            status="success",
            template_id=template_id,
            source_record_id=source_record_id,
        )

        return jsonify(
            {
                "status": "success",
                "message": "Model generated successfully.",
                "record_id": record_id,
                "parsed_params": blueprint_dict,
                "model_url": f"/static/{filename}",
                "template_id": template_id,
                "source_record_id": source_record_id,
            }
        )
    except Exception as exc:
        db.insert_history(
            instruction=instruction,
            status=f"error: {str(exc)}",
            template_id=template_id,
            source_record_id=source_record_id,
        )
        print(f"[ERROR] [MainService] Generation failed: {exc}")
        return _json_error(str(exc), 500)


@app.route("/api/history", methods=["GET"])
def get_history():
    if DEMO_MODE and not DEMO_SHOW_HISTORY:
        return _json_error("Public demo history is disabled.", 403)

    keyword = (request.args.get("keyword") or "").strip()
    status_filter = (request.args.get("status") or "all").strip().lower()
    if status_filter not in {"all", "success", "error"}:
        status_filter = "all"

    limit = _parse_limit(request.args.get("limit"), default=50)
    if DEMO_MODE:
        limit = min(limit, DEMO_HISTORY_LIMIT)

    history = db.get_all_history(keyword=keyword, status_filter=status_filter, limit=limit)

    return jsonify(
        {
            "status": "success",
            "data": history,
            "filters": {"keyword": keyword, "status": status_filter, "limit": limit},
            "count": len(history),
        }
    )


@app.route("/api/history/<int:record_id>", methods=["GET"])
def get_history_detail(record_id):
    if DEMO_MODE and not DEMO_SHOW_HISTORY:
        return _json_error("Public demo history is disabled.", 403)

    history_item = db.get_history_by_id(record_id)
    if not history_item:
        return _json_error("History record does not exist.", 404)
    return jsonify({"status": "success", "data": history_item})


@app.route("/api/history/<int:record_id>", methods=["DELETE"])
def delete_history(record_id):
    if DEMO_MODE and not DEMO_ALLOW_DELETE:
        return _json_error("Deleting history is disabled in public demo mode.", 403)

    history_item = db.get_history_by_id(record_id)
    if not history_item:
        return _json_error("History record does not exist.", 404)

    try:
        file_path_url = history_item.get("file_path")
        if file_path_url:
            filename = file_path_url.split("/")[-1]
            physical_path = os.path.join(STATIC_DIR, filename)
            if os.path.exists(physical_path):
                _remove_file_with_retry(physical_path)
                print(f"[INFO] [Cleanup] Removed model file: {filename}")

        db.delete_history(record_id)
        return jsonify({"status": "success", "message": "History record removed."})
    except Exception as exc:
        print(f"[ERROR] [Cleanup] Delete failed: {exc}")
        return _json_error(str(exc), 500)


@app.route("/api/download", methods=["GET"])
def download_model():
    if DEMO_MODE and not DEMO_ALLOW_DOWNLOAD:
        return _json_error("Model download is disabled in public demo mode.", 403)

    file_path = request.args.get("path")
    if not file_path:
        return _json_error("Missing file path.", 400)

    filename = os.path.basename(file_path)
    try:
        return send_from_directory(STATIC_DIR, filename, as_attachment=True)
    except Exception:
        return _json_error("File does not exist.", 404)


if __name__ == "__main__":
    print("==================================================")
    print("[INFO] AI-CAD backend service is starting")
    print("[INFO] Features: templates, stats, history, LLM parser, CAD engine, public demo mode")
    print("==================================================")
    app.run(host=APP_HOST, port=APP_PORT, debug=False)
