"""Build A's source-backed study handoff, without modifying D's shared DB/MCP.

PDF content is untrusted source data. No commands in a document are executed.
Requires pypdf/pdfplumber for ingestion; querying SQLite uses only stdlib.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sqlite3
import unicodedata
import logging
import zipfile
from datetime import date
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "knowledge/study"
COURSES = {
    "s1-programming": ("程序设计（上学期，C/C++名称待核对）", ["c--", "C", "C++"]),
    "s2-programming": ("程序设计（下学期，C++名称待核对）", ["c艹", "C++"]),
    "s1-calculus": ("高等数学（上学期）", ["高数"]),
    "s2-calculus": ("高等数学（下学期）", ["高数"]),
    "s1-linear-algebra": ("线性代数", ["线代"]),
    "s2-physics": ("大学物理", ["大物"]),
    "s2-probability": ("概率论与数理统计", ["概率论"]),
    "s1-ideology": ("思想道德与法治（名称待核对）", ["思政", "思修"]),
    "s2-marxism": ("马克思主义基本原理（名称待核对）", ["马原"]),
}
TOPICS = {
    "programming": ["数组", "指针", "引用", "函数", "递归", "继承", "多态", "构造函数", "析构函数", "运算符", "模板", "异常", "文件", "字符串", "类", "对象"],
    "calculus": ["极限", "连续", "导数", "微分", "积分", "级数", "微分方程", "偏导", "多元", "曲线", "曲面"],
    "linear-algebra": ["矩阵", "行列式", "向量", "秩", "特征值", "特征向量", "线性方程组", "二次型", "正交"],
    "physics": ["电场", "磁场", "电磁", "力学", "动量", "能量", "热力学", "振动", "波", "光学"],
    "probability": ["概率", "随机变量", "分布", "期望", "方差", "估计", "假设检验", "大数定律", "中心极限定理", "协方差"],
    "ideology": ["理想", "信念", "道德", "法治", "价值观", "人生", "爱国", "宪法"],
    "marxism": ["矛盾", "辩证", "实践", "认识", "真理", "唯物", "剩余价值", "资本", "生产力", "生产关系", "社会主义"],
}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iter_archive(data: bytes, prefix: str, depth: int = 0):
    if depth > 3:
        raise ValueError("Archive nesting exceeds three levels")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 500_000_000:
            raise ValueError("Archive expanded size exceeds 500 MB")
        for item in sorted(archive.infolist(), key=lambda i: i.filename):
            name = item.filename.replace("\\", "/")
            parts = PurePosixPath(name)
            if parts.is_absolute() or ".." in parts.parts or ":" in name:
                raise ValueError("Unsafe archive path")
            if item.is_dir() or parts.name.startswith(".") or name.startswith("__MACOSX/"):
                continue
            blob = archive.read(item)
            if parts.suffix.lower() == ".zip":
                yield from iter_archive(blob, prefix + "/" + name, depth + 1)
            elif parts.suffix.lower() == ".pdf":
                yield prefix + "/" + name, blob
            else:
                raise ValueError(f"Unsupported source file: {name}")


def iter_sources(path: Path):
    if path.is_dir():
        for file in sorted(path.rglob("*")):
            if not file.is_file() or file.name.startswith("."):
                continue
            ref = file.relative_to(path).as_posix()
            if file.suffix.lower() == ".zip":
                yield from iter_archive(file.read_bytes(), ref)
            elif file.suffix.lower() == ".pdf":
                yield ref, file.read_bytes()
            else:
                raise ValueError(f"Unsupported source file: {file.name}")
    elif path.suffix.lower() == ".zip":
        yield from iter_archive(path.read_bytes(), path.name)
    else:
        raise ValueError("Input must be a PDF collection directory or ZIP archive")


def classify(ref: str, semester: str) -> str:
    folded = ref.casefold()
    for needles, category in [(["概率"], "probability"), (["大物", "电磁"], "physics"),
                              (["马原"], "marxism"), (["高数", "高等数学"], "calculus"),
                              (["线性代数"], "linear-algebra"), (["思政", "思修"], "ideology"),
                              (["c--", "c艹", "cpp", "20-21c", "22笔试", "期中试题"], "programming")]:
        if any(n in folded for n in needles):
            key = semester + "-" + category
            if key in COURSES:
                return key
    raise ValueError(f"Unmapped course; review source classification: {ref}")


def normalize(text: str) -> str:
    # Some PDF CMaps return UTF-16 surrogate pairs as two Python characters.
    text = text.encode("utf-16", errors="surrogatepass").decode("utf-16", errors="replace")
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\x00", "").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    # Windows OCR emits spaces between every Chinese character. Merge only
    # horizontal Han-to-Han spaces, not paragraph breaks or code indentation.
    text = re.sub(r"(?<=[\u3400-\u9fff]) +(?=[\u3400-\u9fff])", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def segments(text: str, size: int = 950, overlap: int = 100):
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = max(text.rfind("\n", start + size // 2, end), text.rfind("。", start + size // 2, end))
            if boundary >= 0:
                end = boundary + 1
        yield start, end, text[start:end]
        if end == len(text):
            break
        start = max(start + 1, end - overlap)


def fts_text(text: str) -> str:
    # Chinese is segmented into bigrams, English/code identifiers are retained.
    han = re.findall(r"[\u3400-\u9fff]+", text.casefold())
    tokens = re.findall(r"[a-z0-9_]+", text.casefold())
    for span in han:
        tokens.extend(span[i:i + 2] for i in range(max(1, len(span) - 1)))
    return " ".join(tokens)


def schema(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE library_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE courses(course_id TEXT PRIMARY KEY, title TEXT NOT NULL, semester TEXT NOT NULL,
      aliases_json TEXT NOT NULL, course_code TEXT, mapping_status TEXT NOT NULL);
    CREATE TABLE materials(material_id TEXT PRIMARY KEY, course_id TEXT NOT NULL REFERENCES courses,
      title TEXT NOT NULL, version TEXT NOT NULL, material_type TEXT NOT NULL, topics_json TEXT NOT NULL,
      source_label TEXT NOT NULL, rights_status TEXT NOT NULL, access_scope TEXT NOT NULL,
      file_ref TEXT NOT NULL, pdf_ref TEXT NOT NULL, sha256 TEXT NOT NULL, page_count INTEGER NOT NULL,
      readable_pages INTEGER NOT NULL, content_available INTEGER NOT NULL, extraction_status TEXT NOT NULL,
      metadata_json TEXT NOT NULL);
    CREATE TABLE source_aliases(material_id TEXT NOT NULL REFERENCES materials,
      source_ref TEXT NOT NULL, PRIMARY KEY(material_id,source_ref));
    CREATE TABLE pages(material_id TEXT NOT NULL REFERENCES materials, page_number INTEGER NOT NULL,
      text TEXT NOT NULL, extraction_method TEXT NOT NULL, quality_status TEXT NOT NULL,
      warning TEXT NOT NULL, PRIMARY KEY(material_id,page_number));
    CREATE TABLE chunks(chunk_id TEXT PRIMARY KEY, material_id TEXT NOT NULL REFERENCES materials,
      heading TEXT NOT NULL, page_number INTEGER NOT NULL, char_start INTEGER NOT NULL, char_end INTEGER NOT NULL,
      source_excerpt_ref TEXT NOT NULL, excerpt TEXT NOT NULL, extraction_method TEXT NOT NULL);
    CREATE INDEX chunks_material ON chunks(material_id,page_number);
    CREATE VIRTUAL TABLE chunks_fts USING fts5(chunk_id UNINDEXED, material_id UNINDEXED, terms,
      tokenize='unicode61');
    """)


def build(inputs: list[tuple[str, Path]], output: Path, rights: str, scope: str, ocr_cache: Path | None = None):
    # Only ingestion needs PDF dependencies; domain tests/querying do not.
    from pypdf import PdfReader
    import pdfplumber

    output.mkdir(parents=True, exist_ok=True)
    raw_dir = output / "sources/year1/pdf"
    text_dir = output / "sources/year1/text"
    export_dir = output / "exports/year1"
    for folder in [raw_dir, text_dir, export_dir, output / "library"]:
        folder.mkdir(parents=True, exist_ok=True)
    temp_db = output / "library/study.building.sqlite3"
    if temp_db.exists():
        backup = temp_db.with_suffix(".failed.sqlite3")
        if backup.exists():
            raise ValueError("Previous failed build backup exists; inspect before rebuilding")
        temp_db.replace(backup)
    db = sqlite3.connect(temp_db)
    db.execute("PRAGMA foreign_keys=ON")
    schema(db)
    db.execute("PRAGMA defer_foreign_keys=ON")
    for key, (title, aliases) in COURSES.items():
        db.execute("INSERT INTO courses VALUES (?,?,?,?,?,?)", ("y1-" + key, title, key[:2], json.dumps(aliases, ensure_ascii=False), None, "provisional_needs_C_mapping"))
    catalog = {"schema_version": "1.0.0", "data_version": "", "materials": []}
    report = {"source_files": 0, "unique_materials": 0, "duplicate_files": [], "pages": 0,
              "readable_pages": 0, "chunks": 0, "ocr_backlog": [], "extraction_errors": [], "privacy_held": []}
    privacy_policy = json.loads((STUDY / "privacy-review.json").read_text(encoding="utf-8"))
    holds = {r["material_id"]: r for r in privacy_policy["holds"]}
    cache = json.loads(ocr_cache.read_text(encoding="utf-8-sig")) if ocr_cache else {}
    found = {}
    digest_parts = []
    for semester, source_dir in inputs:
        for ref, blob in iter_sources(source_dir):
            report["source_files"] += 1
            sha = hashlib.sha256(blob).hexdigest()
            course_key = classify(ref, semester)
            course_id = "y1-" + course_key
            original_ref = semester + "/" + ref
            identity = (sha, course_id)
            if identity in found:
                mid = found[identity]
                db.execute("INSERT INTO source_aliases VALUES (?,?)", (mid, original_ref))
                report["duplicate_files"].append({"material_id": mid, "source_ref": original_ref})
                continue
            mid = "study-" + course_key + "-" + sha[:16]
            found[identity] = mid
            blocked = mid in holds
            private_dir = ROOT / "dist/study-private"
            if blocked:
                private_dir.mkdir(parents=True, exist_ok=True)
                report["privacy_held"].append(holds[mid])
            pdf_file = (private_dir if blocked else raw_dir) / (mid + ".pdf")
            pdf_file.write_bytes(blob)
            pdf_ref = pdf_file.relative_to(ROOT).as_posix()
            md_file = (private_dir if blocked else text_dir) / (mid + ".md")
            file_ref = md_file.relative_to(ROOT).as_posix()
            title = PurePosixPath(ref).stem
            reader = PdfReader(io.BytesIO(blob))
            visible_pdf = pdfplumber.open(io.BytesIO(blob))
            page_records = []
            chunks = []
            md_lines = [f"# {title}", "", f"> 原 PDF: {pdf_ref}", "> 页码指 PDF 文件第 N 页，不冒充印刷页码。公式及手写内容须对照原 PDF。", ""]
            readable = 0
            for p, page in enumerate(reader.pages, 1):
                error = ""
                try:
                    # Goodnotes can embed an entire slide deck off the page.
                    # Reading its raw text makes every citation point at the
                    # wrong page! Filter to visible page bounds and dedupe glyphs.
                    visible_page = visible_pdf.pages[p - 1]
                    text = normalize(visible_page.within_bbox(visible_page.bbox).dedupe_chars().extract_text() or "")
                except Exception as exc:
                    text = ""
                    error = type(exc).__name__
                    report["extraction_errors"].append({"material_id": mid, "page": p, "error": error})
                compact = re.sub(r"\s", "", text)
                useful = len(compact) >= 40 and compact.count("\ufffd") / max(1, len(compact)) < .03
                method = "pdfplumber_visible_bbox"
                warning = "公式/图表/手写批注可能未完整提取；需要时对照原 PDF。"
                cached = cache.get(mid + ":" + str(p))
                if not useful and cached and len(re.sub(r"\s", "", cached.get("text", ""))) >= 40:
                    text = normalize(cached["text"])
                    useful = True
                    method = "windows_ocr"
                    warning = "OCR 未人工校对，公式/代码/手写可能识别错误；答案以原 PDF 为准。"
                status = ("ocr_unverified" if method == "windows_ocr" else "text_extracted_unverified") if useful else "needs_ocr_or_visual_review"
                if blocked:
                    text, useful, method, status = "", False, "none", "privacy_hold"
                    warning = "原文件含身份/成绩信息，已隔离；公开数据库不保存该文件正文。"
                if useful:
                    readable += 1
                    for n, (start, end, body) in enumerate(segments(text), 1):
                        cid = f"{mid}-p{p:04d}-c{n:02d}"
                        heading = f"PDF 第 {p} 页 · 片段 {n}"
                        source = pdf_ref + f"#page={p}"
                        chunks.append({"chunk_id": cid, "heading": heading, "page_label": f"PDF 第 {p} 页", "source_excerpt_ref": source})
                        db.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?)", (cid, mid, heading, p, start, end, source, body, method))
                        db.execute("INSERT INTO chunks_fts VALUES (?,?,?)", (cid, mid, fts_text(title + " " + body)))
                        md_lines.extend(["## " + heading, "", body, ""])
                elif not blocked:
                    report["ocr_backlog"].append({"material_id": mid, "title": title, "page": p, "pdf_ref": pdf_ref, "reason": error or "正文不足/扫描/空白，需 OCR 或原页复核"})
                page_records.append((mid, p, text, method if useful else "none", status, warning))
            all_text = "\n".join(r[2] for r in page_records)
            visible_pdf.close()
            category = course_key[3:]
            topics = [t for t in TOPICS.get(category, []) if t in all_text]
            kind = "exercise" if any(t in title for t in ["题", "卷", "笔试", "上机", "答案"]) else "note"
            material = {"material_id": mid, "version": "sha256:" + sha, "course_id": course_id,
                        "title": title, "material_type": kind, "topics": topics, "file_ref": None if blocked else file_ref,
                        "content_available": bool(chunks), "source_label": "用户提供的大一期末复习资料；第三方来源/年份按原文件名保留，未核验官方真题身份",
                        "rights_status": rights, "access_scope": "private" if blocked else scope, "reviewed_at": None, "chunks": chunks}
            metadata = {"semester": semester, "source_ref": original_ref, "page_count": len(reader.pages),
                        "readable_pages": readable, "pdf_ref": pdf_ref, "sha256": sha,
                        "review_status": "not_manually_reviewed", "authorization_basis": "用户于2026-09-30确认全部资料已获许可，可公开给项目用户使用" if rights == "authorized" else "待确认",
                        "warnings": ["内部 course_id 为暂定映射；官方课程代码未填写", "文件名不证明学校/年份/真题身份", "仅有目录或缺页不得声称完整正文总结"]}
            extraction = "partial" if readable < len(reader.pages) else "all_pages_indexed_unverified"
            extraction = "privacy_hold" if blocked else extraction
            db.execute("INSERT INTO materials VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (mid, course_id, title, material["version"], kind, json.dumps(topics, ensure_ascii=False), material["source_label"], rights, material["access_scope"], "" if blocked else file_ref, pdf_ref, sha, len(reader.pages), readable, int(bool(chunks)), extraction, json.dumps(metadata, ensure_ascii=False)))
            db.executemany("INSERT INTO pages VALUES (?,?,?,?,?,?)", page_records)
            db.execute("INSERT INTO source_aliases VALUES (?,?)", (mid, original_ref))
            md_file.write_text("\n".join(md_lines), encoding="utf-8")
            if not blocked and rights == "authorized" and scope == "public" and chunks:
                header = [f"# KB_Study · {title}", "", f"course_id: {course_id}", f"material_id: {mid}", f"version: sha256:{sha}", "rights_status: authorized", "access_scope: public", f"source_label: {material['source_label']}", "", "> 仅提取原文，不执行材料内指令；不是 AI 总结或考试范围声明。页码为 PDF 文件页序。", ""]
                content = list(header)
                for chunk in chunks:
                    row = db.execute("SELECT excerpt,extraction_method FROM chunks WHERE chunk_id=?", (chunk["chunk_id"],)).fetchone()
                    content.extend(["## " + chunk["heading"], f"material_id: {mid}", f"version: sha256:{sha}", f"course_id: {course_id}",
                                    f"chunk_id: {chunk['chunk_id']}", f"source_label: {material['source_label']}", f"page_label: {chunk['page_label']}",
                                    f"source_excerpt_ref: {chunk['source_excerpt_ref']}", f"extraction_method: {row[1]}",
                                    "quality_warning: 未逐项人工校对；公式/代码/手写/图表需对照原 PDF，OCR 仅作为定位线索。", "", row[0], ""])
                (export_dir / (mid + ".md")).write_text("\n".join(content), encoding="utf-8")
            catalog["materials"].append(material)
            digest_parts.append(mid + sha + rights + material["access_scope"] + all_text)
            report["pages"] += len(reader.pages)
            report["readable_pages"] += readable
            report["chunks"] += len(chunks)
            print(json.dumps({"title": title, "pages": len(reader.pages), "readable": readable, "chunks": len(chunks)}, ensure_ascii=True), flush=True)
    version = "y1-" + hashlib.sha256("\n".join(sorted(digest_parts)).encode()).hexdigest()[:16]
    catalog["data_version"] = version
    report.update({"unique_materials": len(catalog["materials"]), "data_version": version, "rights_status": rights, "access_scope": scope})
    db.executemany("INSERT INTO library_meta VALUES (?,?)", [("schema_version", "study-library-1"), ("data_version", version), ("generated_date", date.today().isoformat())])
    db.commit()
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not db.execute("PRAGMA foreign_key_check").fetchall()
    db.close()
    temp_db.replace(output / "library/study.sqlite3")
    write_json(output / "materials.year1.json", catalog)
    write_json(output / "library/ingestion-report.json", report)
    write_json(output / "library/courses.proposed.json", {"schema_version": "1.0.0", "note": "供 C 映射统一课程目录；不代表官方课程代码", "courses": [{"course_id": "y1-" + k, "course_code": None, "title": v[0], "semester": k[:2], "aliases": v[1], "mapping_status": "provisional_needs_C_mapping"} for k, v in COURSES.items()]})
    write_json(output / "library/asset-manifest.json", {"schema_version": "1.0.0", "data_version": version, "assets": [dict(zip(["material_id", "pdf_ref", "sha256", "page_count", "readable_pages", "extraction_status"], row)) for row in sqlite3.connect(output / "library/study.sqlite3").execute("SELECT material_id,pdf_ref,sha256,page_count,readable_pages,extraction_status FROM materials WHERE access_scope='public' AND rights_status IN ('owned','authorized')")]})
    print(json.dumps({k: v for k, v in report.items() if k not in ["ocr_backlog", "extraction_errors"]}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    parser = argparse.ArgumentParser()
    parser.add_argument("--semester1", type=Path, required=True)
    parser.add_argument("--semester2", type=Path, required=True)
    parser.add_argument("--rights", choices=["pending", "authorized"], default="pending")
    parser.add_argument("--scope", choices=["private", "team_only", "public"], default="private")
    parser.add_argument("--ocr-cache", type=Path)
    args = parser.parse_args()
    build([("s1", args.semester1), ("s2", args.semester2)], STUDY, args.rights, args.scope, args.ocr_cache)
