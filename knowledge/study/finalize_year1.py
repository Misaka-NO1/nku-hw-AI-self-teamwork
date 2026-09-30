"""Generate project handoff manifest, flat DB import tables, and a verified ZIP."""
import csv
import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "knowledge/study"


def main():
    report = json.loads((STUDY / "library/ingestion-report.json").read_text(encoding="utf-8"))
    verified = json.loads((STUDY / "library/verification.json").read_text(encoding="utf-8"))
    if verified["status"] != "LOCAL_PASS" or verified["data_version"] != report["data_version"]:
        raise ValueError("Verify this exact snapshot before packaging")
    with sqlite3.connect(STUDY / "library/study.sqlite3") as db:
        db.row_factory = sqlite3.Row
        materials = [dict(row) for row in db.execute("SELECT * FROM materials ORDER BY course_id,title")]
        courses = [dict(row) for row in db.execute("SELECT course_id,title,semester FROM courses ORDER BY semester,course_id")]
        counts = [dict(row) for row in db.execute("SELECT c.course_id,c.title,count(*) AS files,sum(m.page_count) AS pages,sum(m.readable_pages) AS indexed_pages FROM courses c JOIN materials m USING(course_id) WHERE m.access_scope='public' AND m.rights_status IN ('owned','authorized') GROUP BY c.course_id ORDER BY c.semester,c.course_id")]
        method_counts = dict(db.execute("SELECT extraction_method,count(*) FROM pages GROUP BY extraction_method"))
        exports = []
        for material in materials:
            mid = material["material_id"]
            file = STUDY / "exports/year1" / (mid + ".md")
            if material["rights_status"] in {"owned", "authorized"} and material["access_scope"] == "public" and file.exists():
                exports.append({"file_ref": file.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "material_id": mid,
                                "tags": {"course_id": material["course_id"], "term": json.loads(material["metadata_json"])["semester"], "access_scope": "public"},
                                "material_version": material["version"], "content_review": "not_manually_reviewed"})
        manifest = {"schema_version": "1.0.0", "data_version": report["data_version"], "target": "NK-GeniOS KB_Study",
                    "platform_import_status": "not_uploaded_or_validated", "authorization_status": "user_confirmed_authorized_public_2026-09-30",
                    "files": exports, "page_methods": method_counts, "course_counts": counts}
        (STUDY / "library/upload-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # These are a portable structured database import, not an NK-GeniOS
        # proprietary import package and not a claim of direct SQLite support.
        table_dir = STUDY / "library/tables"
        table_dir.mkdir(exist_ok=True)
        for filename, sql in [
            ("courses.csv", "SELECT * FROM courses ORDER BY course_id"),
            ("materials.csv", "SELECT * FROM materials ORDER BY course_id,title"),
            ("pages.csv", "SELECT * FROM pages ORDER BY material_id,page_number"),
            ("chunks.csv", "SELECT * FROM chunks ORDER BY material_id,page_number,char_start"),
            ("source_aliases.csv", "SELECT * FROM source_aliases ORDER BY material_id,source_ref"),
        ]:
            cursor = db.execute(sql)
            with (table_dir / filename).open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow([c[0] for c in cursor.description])
                writer.writerows(cursor)
    lines = ["# 大一期末复习资料库 · 本地入库报告", "", f"数据版本：`{report['data_version']}`。", "",
             f"源 PDF：{report['source_files']} 份；文件哈希不同的材料：{report['unique_materials']} 份；共 {report['pages']} 页。",
             f"公开候选：{len(exports)} 份；可检索页：{report['readable_pages']} 页；正文分块：{report['chunks']} 个。未入正文的页包含隐私隔离、封面、空白或短页，不等于全部识别失败。", "",
             "所有‘可检索’仅表示已提取文本，不代表公式、手写或内容经人工核验。", "",
             "| 暂定课程分类 | 文件 | 总页数 | 可检索页 |", "|---|---:|---:|---:|"]
    lines.extend(f"| {r['title']} | {r['files']} | {r['pages']} | {r['indexed_pages']} |" for r in counts)
    lines.extend(["", "## 提取方式", ""] + [f"- {key}: {value} 页" for key, value in method_counts.items()])
    lines.extend(["", "## 页码复核", "", "已检查程序设计幻灯片的可见页边界。Goodnotes 文件有页外隐藏文字，原始全量文本会把其他幻灯片误挂到当前页；本版本只收可见页面范围内的字形。", "",
                  "PDF 页序和印刷页码不同，统一引用‘PDF 第 N 页’。不把文件名的年份、‘真题’标签当成已核验官方事实。", "",
                  "## 未充分提取的页", ""])
    lines.extend(f"- {r['title']} · PDF 第 {r['page']} 页：{r['reason']}" for r in report["ocr_backlog"])
    lines.extend(["", "## 隐私隔离（不含在公开文件交接包中）", ""])
    lines.extend(f"- {r['title']}：{r['reason']} 原件留在桌面和本机忽略的 dist/study-private/，未复制到公开知识库/公开 PDF。" for r in report["privacy_held"])
    lines.extend(["", "## 发布边界", "", "依据用户授权建立公开候选文件；尚未上传 NK-GeniOS，尚未注册 D 的业务 MCP，尚未部署云端资料检索。原始桌面资料未移动或删除。", ""])
    (STUDY / "library/入库报告.md").write_text("\n".join(lines), encoding="utf-8")
    # Bundle relative repository paths so D can merge the handoff predictably.
    files = [STUDY / ".gitattributes", STUDY / "materials.year1.json", STUDY / "README-Year1.md", STUDY / "privacy-review.json", STUDY / "requirements-ingest.txt", STUDY / "build_year1.py", STUDY / "ocr_year1.py", STUDY / "ocr_windows.ps1", STUDY / "verify_year1.py", STUDY / "finalize_year1.py",
             ROOT / "backend/app/domains/study/library.py", ROOT / "backend/tests/test_study_library.py", ROOT / "docs/handoffs/A-study-year1.md", ROOT / "prompts/study-answer.md"]
    public_materials = [m for m in materials if m["rights_status"] in {"owned", "authorized"} and m["access_scope"] == "public"]
    files += [ROOT / m["pdf_ref"] for m in public_materials]
    files += [ROOT / m["file_ref"] for m in public_materials if m["file_ref"]]
    files += [STUDY / "exports/year1" / (r["material_id"] + ".md") for r in exports]
    files += sorted(p for p in (STUDY / "library").rglob("*") if p.is_file() and ".failed." not in p.name and ".building." not in p.name)
    missing = [str(p) for p in files if not p.is_file()]
    if missing:
        raise FileNotFoundError("Missing handoff assets: " + ", ".join(missing))
    zip_path = ROOT / "dist" / ("NKU-Study-Year1-" + report["data_version"] + ".zip")
    zip_path.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for file in files:
            bundle.write(file, file.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(zip_path) as bundle:
        assert bundle.testzip() is None
        assert len(bundle.namelist()) == len(files)
    zip_sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (zip_path.with_suffix(".sha256")).write_text(zip_sha + "  " + zip_path.name + "\n", encoding="utf-8")
    print(json.dumps({"data_version": report["data_version"], "export_files": len(exports), "page_methods": method_counts, "zip": str(zip_path), "zip_bytes": zip_path.stat().st_size, "zip_sha256": zip_sha}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
