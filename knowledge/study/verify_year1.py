"""Run local verification and save actual outcomes for C/D handoff."""
import hashlib
import importlib.util
import io
import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "knowledge/study"


def main():
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "backend/tests"), pattern="test_study_library.py")
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    print(log.getvalue(), flush=True)
    if not result.wasSuccessful():
        raise SystemExit(1)
    spec = importlib.util.spec_from_file_location("year1_library", ROOT / "backend/app/domains/study/library.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    library = module.StudyLibrary()
    query_cases = [("y1-s1-programming", "数组"), ("y1-s2-programming", "构造函数"),
                   ("y1-s1-calculus", "极限"), ("y1-s2-calculus", "积分"),
                   ("y1-s1-linear-algebra", "矩阵"), ("y1-s2-physics", "电场"),
                   ("y1-s2-probability", "条件概率"), ("y1-s1-ideology", "理想"),
                   ("y1-s2-marxism", "实践")]
    queries = []
    for course_id, topic in query_cases:
        items = library.search_materials({"course_id": course_id, "topic": topic, "limit": 5})
        assert items and any(i["evidence"] for i in items), (course_id, topic, "No actual body evidence")
        queries.append({"course_id": course_id, "topic": topic, "matched_materials": len(items),
                        "samples": [{"title": i["title"], "material_id": i["material_id"], "pages": [e["page_label"] for e in i["evidence"]]} for i in items[:2]]})
    with closing(sqlite3.connect(STUDY / "library/study.sqlite3")) as db:
        public_count = db.execute("SELECT count(*) FROM materials WHERE access_scope='public'").fetchone()[0]
        all_count = db.execute("SELECT count(*) FROM materials").fetchone()[0]
        pages = db.execute("SELECT count(*) FROM pages WHERE quality_status NOT IN ('privacy_hold','needs_ocr_or_visual_review')").fetchone()[0]
        methods = dict(db.execute("SELECT extraction_method,count(*) FROM pages GROUP BY extraction_method"))
        for mid, pdf, sha in db.execute("SELECT material_id,pdf_ref,sha256 FROM materials WHERE access_scope='public'"):
            assert hashlib.sha256((ROOT / pdf).read_bytes()).hexdigest() == sha
        assert db.execute("SELECT count(*) FROM chunks c JOIN materials m USING(material_id) WHERE m.access_scope!='public'").fetchone()[0] == 0
    verification = {"status": "LOCAL_PASS", "platform_status": "NOT_INTEGRATED",
                    "data_version": library.data_version(), "unittest": {"run": result.testsRun, "failed": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)},
                    "public_materials": public_count, "catalog_materials": all_count, "indexed_pages": pages, "page_methods": methods,
                    "queries": queries, "checks": ["StudyCatalog JSON Schema 1.0.0", "SQLite integrity and foreign keys", "all public PDF SHA-256", "all chunk offsets match stored page text", "read-only SQL", "private/pending isolation", "path allowlist", "Goodnotes off-page citation regression", "held material body absent"],
                    "not_verified": ["all formulas/code/OCR by a human", "complete privacy review of every page", "NK-GeniOS import/tool call", "D's live backend deployment", "C's official course mapping", "full backend test suite"]}
    (STUDY / "library/verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (STUDY / "library/test-results.txt").write_text(log.getvalue(), encoding="utf-8")
    print(json.dumps(verification, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
