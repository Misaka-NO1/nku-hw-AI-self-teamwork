"""Stdlib tests can also be collected by the project's pytest suite."""
import importlib.util
import io
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
library_spec = importlib.util.spec_from_file_location("study_library", ROOT / "backend/app/domains/study/library.py")
library_module = importlib.util.module_from_spec(library_spec)
library_spec.loader.exec_module(library_module)
StudyLibrary = library_module.StudyLibrary

spec = importlib.util.spec_from_file_location("study_builder", ROOT / "knowledge/study/build_year1.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.sqlite3"
        self.db = sqlite3.connect(self.path)
        builder.schema(self.db)
        self.db.execute("INSERT INTO library_meta VALUES ('data_version','test-v1')")
        self.db.execute("INSERT INTO courses VALUES ('course-a','课程甲','s1','[]',NULL,'provisional')")
        self.db.execute("INSERT INTO courses VALUES ('course-b','课程乙','s1','[]',NULL,'provisional')")
        for mid, course, rights, scope, body in [
            ("allowed", "course-a", "authorized", "public", "构造函数初始化对象。继承支持代码复用。"),
            ("private", "course-a", "authorized", "private", "构造函数私人资料"),
            ("pending", "course-a", "pending", "public", "构造函数待授权"),
            ("team", "course-a", "authorized", "team_only", "构造函数团队资料"),
            ("other-course", "course-b", "authorized", "public", "构造函数其他课程"),
        ]:
            self.db.execute("INSERT INTO materials VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (mid, course, mid, "1", "note", "[]", "自创测试", rights, scope, "knowledge/study/sources/test.md", "knowledge/study/sources/year1/pdf/test.pdf", "a" * 64, 1, 1, 1, "text", "{}"))
            self.db.execute("INSERT INTO pages VALUES (?,?,?,?,?,?)", (mid, 1, body, "pdf_text", "unverified", "对照原 PDF"))
            self.db.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?)", (mid + "-c1", mid, "PDF 第 1 页", 1, 0, len(body), "knowledge/study/sources/year1/pdf/test.pdf#page=1", body, "pdf_text"))
            self.db.execute("INSERT INTO chunks_fts VALUES (?,?,?)", (mid + "-c1", mid, builder.fts_text(body)))
        self.db.commit()
        self.db.close()
        self.library = StudyLibrary(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def query(self, topic=None, course_id="course-a", limit=5):
        return self.library.search_materials({"course_id": course_id, "topic": topic, "limit": limit})

    def test_chinese_body_query_and_page_citation(self):
        items = self.query("构造函数")
        self.assertEqual([i["material_id"] for i in items], ["allowed"])
        self.assertEqual(items[0]["evidence"][0]["page_label"], "PDF 第 1 页")
        self.assertIn("#page=1", items[0]["evidence"][0]["source_excerpt_ref"])

    def test_null_topic_and_rights_isolation(self):
        self.assertEqual([i["material_id"] for i in self.query()], ["allowed"])
        for mid in ["pending", "team", "private", "missing"]:
            with self.assertRaises(KeyError):
                self.library.get_material(mid)
            with self.assertRaises(KeyError):
                self.library.resolve_download(mid)

    def test_wrong_course_and_missing_topic(self):
        self.assertEqual(self.query("量子纠缠"), [])
        self.assertEqual(self.query("构造函数", "missing-course"), [])
        self.assertEqual([i["material_id"] for i in self.query("构造函数", "course-b")], ["other-course"])

    def test_injection_is_plain_query_not_sql_or_fts(self):
        self.assertEqual(self.query('" OR 1=1; DROP TABLE materials; --'), [])
        self.assertEqual(self.query(None, "course-a' OR 1=1 --"), [])
        self.assertEqual(len(self.query()), 1)

    def test_input_bounds_and_no_arbitrary_fields(self):
        for limit in [0, 21, True, "5"]:
            with self.assertRaises(ValueError):
                self.query(limit=limit)
        with self.assertRaises(ValueError):
            self.query("a" * 501)
        with self.assertRaises(ValueError):
            self.library.search_materials({"course_id": "course-a", "topic": None, "limit": 5, "path": "/etc/passwd"})

    def test_read_only_connection_and_page_bounds(self):
        with self.library._connect() as db:
            with self.assertRaises(sqlite3.OperationalError):
                db.execute("DELETE FROM materials")
        with self.assertRaises(ValueError):
            self.library.read_pages("allowed", 1, 10)
        self.assertEqual(self.library.read_pages("allowed", 1, 1)[0]["text"], "构造函数初始化对象。继承支持代码复用。")

    def test_download_allowlist(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE materials SET pdf_ref='../secret.pdf' WHERE material_id='allowed'")
            db.commit()
        with self.assertRaises(KeyError):
            self.library.resolve_download("allowed")

    def test_extraction_warnings_and_private_ids(self):
        self.assertEqual(self.library.extraction_warnings(["allowed"])[0]["code"], "STUDY_TEXT_UNREVIEWED")
        with self.assertRaises(KeyError):
            self.library.extraction_warnings(["private"])
        with self.assertRaises(ValueError):
            self.library.extraction_warnings(["allowed"] * 21)

    def test_normalize_compatibility_and_surrogates(self):
        self.assertEqual(builder.normalize("⼤学\ud835\udc00"), "大学A")
        self.assertNotIn("\ud835", builder.normalize("孤立\ud835"))

    def test_chunk_offsets_recover_source(self):
        source = "函数继承。\n" * 450
        pieces = list(builder.segments(source))
        self.assertGreater(len(pieces), 1)
        for start, end, body in pieces:
            self.assertEqual(body, source[start:end])
            self.assertLessEqual(len(body), 950)
        self.assertEqual(pieces[-1][1], len(source))

    def test_archive_paths_are_rejected(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("../../evil.pdf", b"not a pdf")
        with self.assertRaises(ValueError):
            list(builder.iter_archive(data.getvalue(), "test"))


class RealSnapshotTests(unittest.TestCase):
    @unittest.skipUnless((ROOT / "knowledge/study/library/study.sqlite3").exists(), "Real materials not present")
    def test_real_snapshot_and_core_catalog_contract(self):
        import hashlib
        from jsonschema import Draft202012Validator
        study = ROOT / "knowledge/study"
        catalog = json.loads((study / "materials.year1.json").read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "contracts/core.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator({"$ref": "#/$defs/StudyCatalog", "$defs": schema["$defs"]}).validate(catalog)
        with closing(sqlite3.connect(study / "library/study.sqlite3")) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(db.execute("SELECT count(*) FROM materials").fetchone()[0], len(catalog["materials"]))
            for pdf, sha in db.execute("SELECT pdf_ref,sha256 FROM materials WHERE access_scope='public'"):
                self.assertEqual(hashlib.sha256((ROOT / pdf).read_bytes()).hexdigest(), sha)
            self.assertEqual(db.execute("SELECT count(*) FROM chunks c JOIN materials m USING(material_id) WHERE m.access_scope='private'").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM pages p JOIN materials m USING(material_id) WHERE m.access_scope='private' AND length(p.text)>0").fetchone()[0], 0)
            for excerpt, text, start, end in db.execute("SELECT c.excerpt,p.text,c.char_start,c.char_end FROM chunks c JOIN pages p ON p.material_id=c.material_id AND p.page_number=c.page_number"):
                self.assertEqual(excerpt, text[start:end])
        library = StudyLibrary()
        self.assertEqual(library.data_version(), catalog["data_version"])
        self.assertTrue(library.search_materials({"course_id": "y1-s2-programming", "topic": "构造函数", "limit": 5}))
        self.assertEqual(library.search_materials({"course_id": "y1-s2-probability", "topic": "构造函数", "limit": 5}), [])
        # Regression: Goodnotes' hidden off-page slides must not be cited as p1.
        cover = library.read_pages("study-s1-programming-b8a8c17240ffa3e4", 1, 1)[0]["text"]
        self.assertIn("高级语言程序设计", cover)
        self.assertNotIn("程序填空", cover)
        with self.assertRaises(KeyError):
            library.get_material("study-s1-programming-7267a3cd0b2e11aa")


if __name__ == "__main__":
    unittest.main()
