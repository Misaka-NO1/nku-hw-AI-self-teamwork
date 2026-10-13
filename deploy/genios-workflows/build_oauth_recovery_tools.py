"""Build only public tool schemas, never export plugin authentication settings."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HEADERS = [
    {"name": "platform-user-id", "in": "header", "required": True,
     "description": "固定隐藏引用 SYS_USERID；模型不可填写，不能使用聊天中的身份。",
     "schema": {"type": "string"}},
    {"name": "platform-attestation", "in": "header", "required": True,
     "description": "只能引用本轮 attest_my_platform_identity.data.platform_attestation；不接收用户提供的证明。",
     "schema": {"type": "string"}},
]
ENVELOPE = {"type": "object", "required": ["ok", "data", "meta"],
            "properties": {"ok": {"type": "boolean"}, "data": {"type": "object"},
                           "meta": {"type": "object"}}}
QUERY = {"type": "object", "required": ["query_json"], "additionalProperties": False,
         "properties": {"query_json": {"type": "string", "description": "业务 JSON 只编码一次，不含账号、课表、workspace 或令牌。"}}}


def operation(name, description, body=None):
    result = {"operationId": name, "summary": name, "description": description}
    if body is not None:
        result["requestBody"] = {"required": True, "content": {"application/json": {"schema": body}}}
    return result


def build():
    paths = {}
    # Reuse authored business request schemas and descriptions without credentials.
    task = json.loads((ROOT / "personal-task-tools.openapi.json").read_text(encoding="utf-8"))
    degree = json.loads((ROOT / "degree-progress-tools.openapi.json").read_text(encoding="utf-8"))
    paths.update(copy.deepcopy(task["paths"]))
    paths.update(copy.deepcopy(degree["paths"]))
    paths["/oauth/records"] = {"get": operation("read_my_demo_records",
        "无业务输入。读取本人当前 OAuth 授权且固定 GeniOS 身份匹配的实际已保存课表。先本轮 attest，再传短期证明。"
        "依据本次 data.schedule/timetable 及 dataset_kind 回答课程、周次、地点、revision、保存时间；历史 demo 名字不是演示数据判据。"
        "失败不可声称空课表，不回退夹具或其他账号，不只说将读取就结束。不写入，需 demo:read。")}
    paths["/oauth/time/free-slots"] = {"post": operation("find_my_demo_free_slots",
        "需 demo:read，本轮身份核验后查询本人课表及已保存活动综合空档。query_json 仅含 window:{start,end}、min_minutes、"
        "buffers:{before_minutes,after_minutes}。时间含秒及+08:00。不得传账号、workspace、课表或令牌。返回完整 data.slots，"
        "保留 coverage/warnings，不截成一小时，不把失败当无空档，不保存。", QUERY)}
    paths["/oauth/time/check"] = {"post": operation("check_my_demo_time",
        "需 demo:read，本轮身份核验后检查本人课表及已保存安排。query_json 为一次编码的合法事件/DDL 计算请求；"
        "活动 event.start/end 不能遗漏，deadline 使用截止和耗时等实际业务字段。"
        "必须保留 conflicts 与 candidate_slots、coverage/warnings，不编造输入缺项、时间或结果，不保存。", QUERY)}
    paths["/oauth/tasks/summary"] = {"get": operation("read_my_demo_task_summary",
        "需 tasks:read，无业务输入，只在本人明确查询待办时读取本人当前真实摘要，不因新对话自动调用。"
        "先本轮身份核验，失败不答零条或假空列表，不新建后台推送、不写入。")}
    paths["/oauth/devices/bind"] = {"post": operation("bind_my_browser",
        "需 devices:bind，固定身份和本轮证明与真实 OAuth 账号匹配。仅旧 OAuth 兼容绑定，不用于 existing_space 正常绑定。"
        "本人明确确认绑定自己的设备码后 confirm_binding=true；设备码只定位浏览器，不证明身份。成功后仍须原浏览器领取。"
        "已有固定平台空间正常绑定使用 onboard_my_browser(intent=bind)，不误用本工具、重建或迁移。",
        {"type": "object", "additionalProperties": False, "required": ["device_code", "confirm_binding"],
         "properties": {"device_code": {"type": "string", "pattern": "^DEV-[A-Z2-7]{26}$"},
                        "confirm_binding": {"type": "boolean", "description": "仅本人明确确认后为 true"}}})}
    paths["/api/v1/auth/genios/associate"] = {"post": operation("associate_my_original_space",
        "仅真实 lookup 返回 legacy_authorization_required 且本人明确同意时，用本轮签名、固定 SYS_USERID 与本人有效 OAuth "
        "关联原空间并绑定当前浏览器。existing_space 必须使用 onboard_my_browser(intent=bind)，不走迁移。"
        "不创建、复制、合并或删除旧数据；设备码不是身份。",
        {"type": "object", "additionalProperties": False, "required": ["device_code", "intent", "confirmed"],
         "properties": {"device_code": {"type": "string", "pattern": "^DEV-[A-Z2-7]{26}$"},
                        "intent": {"type": "string", "enum": ["bind"]},
                        "confirmed": {"type": "boolean", "description": "仅本人明确确认原空间关联后为 true"}}})}
    for methods in paths.values():
        for op in methods.values():
            # School importer uses summary as the actual callable tool name.
            op["summary"] = op["operationId"]
            op["parameters"] = copy.deepcopy(HEADERS)
            op["responses"] = {"200": {"description": "非空成功信封投影，data 完整返回；非 2xx 仍失败。401/invalid_token 须本人重授权，不重绑或创建空间。",
                "content": {"application/json": {"schema": copy.deepcopy(ENVELOPE)}}}}
    result = {"openapi": "3.0.3", "info": {"title": "本人空间 OAuth 连接恢复工具", "version": "1.0.0"},
              "servers": task["servers"], "paths": paths,
              "components": {"schemas": {"QueryInput": QUERY}}}
    names = [op["operationId"] for methods in paths.values() for op in methods.values()]
    assert len(names) == len(set(names)) == 12
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    assert "client_secret" not in serialized and "Authorization" not in serialized
    (ROOT / "oauth-recovery-tools.openapi.json").write_text(serialized, encoding="utf-8")
    print(json.dumps({"tool_count": len(names), "tools": names, "credentials": False}, ensure_ascii=False))


if __name__ == "__main__":
    build()
