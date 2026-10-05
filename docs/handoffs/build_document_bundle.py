"""Package project documents for handoff, without credentials or build artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote
import zipfile


STAMP = "2026-10-01"
HANDOFF = f"docs/handoffs/接手GPT必读-项目完整交接-{STAMP}.md"
INDEX = f"docs/handoffs/项目文档总索引-{STAMP}.md"
PATTERNS = [
    re.compile(r"\b(?:AKID[A-Za-z0-9]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+([A-Za-z0-9_./+=-]{32,})", re.I),
    re.compile(r"\beyJ[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?:MCP_SERVICE_TOKEN|MCP_PROBE_TOKEN|SecretKey|secret_key)\s*[\"'`]*\s*[:=]\s*[\"']?([A-Za-z0-9_+/=.-]{24,})", re.I),
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_secrets(name: str, data: bytes) -> None:
    body = data.decode("utf-8-sig")
    for pattern in PATTERNS:
        for match in pattern.finditer(body):
            candidate = match.group(1) if match.lastindex else match.group(0)
            if any(word in candidate.lower() for word in ("replace", "example", "placeholder", "change-me", "your-token")):
                continue
            # Never disclose the matching value, even on failure.
            raise ValueError(f"Potential credential detected; review before bundling: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-dir", required=True, type=Path)
    parser.add_argument("--contest-dir", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode("utf-8").split("\0")
    names = {name for name in tracked if name.endswith(".md")}
    names.update((HANDOFF, INDEX))
    supporting = {name for name in tracked if name.endswith(".json") and name.startswith(("contracts/", "fixtures/", "knowledge/"))}
    originals = sorted(args.original_dir.glob("*.md"), key=lambda p: p.name)
    for name in ("南开大学2026年“华为杯”AI应用创新大赛报名启动通知.md", "南开大学2026年“华为杯”AI应用创新大赛 · 比赛方案.md", "首页.md"):
        originals.append(args.contest_dir / name)
    for path in originals:
        if not path.is_file():
            raise FileNotFoundError(path)

    index = [
        f"# 项目文档总索引（{STAMP}）", "",
        "本索引列出交接包中全部文档与接口/夹具/知识配套数据。最先阅读同目录的“接手GPT必读-项目完整交接”。", "",
        "原始资料按本机项目文档目录归档，额外方案仅是参考原文，不代表用户已批准执行；仓库当前四份任务书为给 A/B/C/D 的最新分发版本。", "",
        "ZIP 内部路径保留仓库层级；此索引中的仓库链接在仓库中可点击，原始文件请从 ZIP 的 01-原始项目文档目录读取。", "",
        "包不含密钥、账号、会话、.env、数据库、云上传环境 ZIP、可部署候选包或图片资产。截图仍由证据文档记录原本路径，未随文档包转发。", "",
        "## 给四名同学分发的任务书", "",
    ]
    taskbooks = sorted(name for name in names if name.startswith("docs/agent-prompts/"))
    for name in taskbooks:
        index.append(f"- [{Path(name).name}]({quote('../agent-prompts/' + Path(name).name)})")
    index += ["", f"## 原始项目资料（{len(originals)} 份）", ""]
    index += [f"- `01-原始项目文档/{path.name}`" for path in originals]
    index += ["", f"## 仓库 Markdown 文档（{len(names)} 份，含本索引与完整交接）", ""]
    for name in sorted(names):
        index.append(f"- [{name}]({quote('../../' + name)})")
    index += ["", f"## 配套 JSON（{len(supporting)} 份）", ""]
    for name in sorted(supporting):
        index.append(f"- [{name}]({quote('../../' + name)})")
    index += ["", "## 完整性核查", "", "ZIP 根目录 MANIFEST.json 列每个条目字节数和 SHA256；可独立解压后按清单验证。压缩包 SHA256 另存同名 .sha256 文件。", ""]
    (root / INDEX).write_text("\n".join(index), encoding="utf-8")

    payloads: dict[str, bytes] = {}
    payloads["00-交接入口/先读-完整交接.md"] = (root / HANDOFF).read_bytes()
    payloads["00-交接入口/项目文档总索引.md"] = (root / INDEX).read_bytes()
    for path in originals:
        payloads["01-原始项目文档/" + path.name] = path.read_bytes()
    for name in sorted(names | supporting):
        payloads["02-仓库文档/" + name] = (root / name).read_bytes()
    for name, data in payloads.items():
        check_secrets(name, data)

    manifest = {
        "handoff_date": STAMP,
        "timezone": "Asia/Shanghai",
        "repository": "https://github.com/Misaka-NO1/nku-hw-AI-self-teamwork",
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=root, text=True).strip(),
        "repository_head_at_packaging": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "cloud_005_source_commit": "853d17dd3557d8872f0f78e5f13a12acadc514f1",
        "not_a_deployment_or_platform_import_package": True,
        "counts": {"original_markdown": len(originals), "repository_markdown": len(names), "supporting_json": len(supporting), "entrypoint_copies": 2},
        "files": [{"path": name, "bytes": len(data), "sha256": digest(data)} for name, data in sorted(payloads.items())],
    }
    out = root / "docs/handoffs/dist"
    out.mkdir(parents=True, exist_ok=True)
    archive = out / f"南开校园助手-全部项目文档与GPT交接-{STAMP}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, data in sorted(payloads.items()):
            zipped.writestr(name, data)
        zipped.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        assert len(zipped.namelist()) == len(set(zipped.namelist()))
        actual = json.loads(zipped.read("MANIFEST.json"))
        assert set(zipped.namelist()) == {item["path"] for item in actual["files"]} | {"MANIFEST.json"}
        for item in actual["files"]:
            blob = zipped.read(item["path"])
            assert len(blob) == item["bytes"] and digest(blob) == item["sha256"]
    fingerprint = digest(archive.read_bytes())
    archive.with_suffix(".zip.sha256").write_text(f"{fingerprint}  {archive.name}\n", encoding="utf-8")
    print(json.dumps({"archive": str(archive), "sha256": fingerprint, "counts": manifest["counts"], "zip_entries": len(payloads) + 1, "integrity_verified": True, "credential_pattern_check": "no_matches_not_a_security_guarantee"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
