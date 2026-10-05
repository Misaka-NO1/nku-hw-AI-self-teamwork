"""Read-only A module repository for D's existing search_study_materials adapter.

No MCP registration, shared DB migration, arbitrary SQL or private access here.
Public result shape matches the existing study service's summaries and evidence.
"""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATABASE = REPOSITORY_ROOT / "knowledge/study/library/study.sqlite3"
PUBLIC_FILTER = "m.access_scope='public' AND m.rights_status IN ('owned','authorized')"


def _terms(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9_]+", text.casefold())
    for span in re.findall(r"[\u3400-\u9fff]+", text):
        tokens.extend(span[i:i + 2] for i in range(max(1, len(span) - 1)))
    return list(dict.fromkeys(tokens))[:80]


class StudyLibrary:
    """Path is injected by the server, never accepted from an Agent argument."""

    def __init__(self, database_path: Path = DEFAULT_DATABASE):
        self.path = Path(database_path).resolve()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        try:
            yield connection
        finally:
            connection.close()

    def data_version(self) -> str:
        with self._connect() as db:
            return db.execute("SELECT value FROM library_meta WHERE key='data_version'").fetchone()[0]

    def list_courses(self) -> list[dict]:
        with self._connect() as db:
            return [dict(row) for row in db.execute(f"""SELECT c.course_id,c.title,c.semester,
                c.course_code,c.mapping_status,count(*) AS material_count
                FROM courses c JOIN materials m USING(course_id) WHERE {PUBLIC_FILTER}
                GROUP BY c.course_id ORDER BY c.semester,c.course_id""")]

    @staticmethod
    def _summary(row, evidence):
        return {key: row[key] for key in ["material_id", "course_id", "title", "version", "material_type", "rights_status", "access_scope", "source_label"]} | {
            "topics": json.loads(row["topics_json"]), "content_available": bool(row["content_available"]),
            "evidence": evidence,
            "material_url": f"/tools/study?course_id={quote(row['course_id'], safe='')}&material_id={quote(row['material_id'], safe='')}",
            "download_url": f"/api/v1/study/materials/{quote(row['material_id'], safe='')}/download",
            "file_format": "pdf",
            "file_name": row["title"] + ".pdf",
        }

    def list_materials(self) -> list[dict]:
        """Complete licensed public file catalog, without snippets or top-N limits."""
        with self._connect() as db:
            rows = db.execute(f"SELECT m.* FROM materials m WHERE {PUBLIC_FILTER} ORDER BY course_id,title,material_id").fetchall()
            return [self._summary(row, []) for row in rows]

    @staticmethod
    def _evidence(row):
        return {"chunk_id": row["chunk_id"], "heading": row["heading"],
                "page_label": f"PDF 第 {row['page_number']} 页", "source_excerpt_ref": row["source_excerpt_ref"],
                "excerpt": row["excerpt"]}

    def search_materials(self, query: dict, principal=None) -> list[dict]:
        """Same StudyQuery fields as A's existing public function. Public only.

        D constructs principal and enforces deployment/auth gates before calling.
        This does not authorize team/private materials from a supplied principal.
        Chinese bigram AND retrieval; no LLM/embedding dependency.
        """
        if set(query) != {"course_id", "topic", "limit"}:
            raise ValueError("StudyQuery requires exactly course_id, topic, limit")
        course_id, topic, limit = query["course_id"], query["topic"], query["limit"]
        if not isinstance(course_id, str) or not 1 <= len(course_id) <= 128:
            raise ValueError("Invalid course_id")
        if topic is not None and (not isinstance(topic, str) or len(topic) > 500):
            raise ValueError("topic must be null or a string of at most 500 characters")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("limit must be an integer from 1 to 20")
        _ = principal
        with self._connect() as db:
            rows = db.execute(f"SELECT m.* FROM materials m WHERE m.course_id=? AND {PUBLIC_FILTER} ORDER BY title,material_id", (course_id,)).fetchall()
            results = []
            term = (topic or "").strip().casefold()
            tokens = _terms(term)
            hits = {}
            if term and tokens:
                expression = " AND ".join('"' + token.replace('"', '""') + '"' for token in tokens)
                for hit in db.execute(f"""SELECT c.*,bm25(chunks_fts) AS rank
                    FROM chunks_fts JOIN chunks c ON c.chunk_id=chunks_fts.chunk_id
                    JOIN materials m ON m.material_id=c.material_id
                    WHERE chunks_fts MATCH ? AND m.course_id=? AND {PUBLIC_FILTER}
                    ORDER BY rank,c.chunk_id LIMIT 200""", (expression, course_id)):
                    hits.setdefault(hit["material_id"], []).append(hit)
            for row in rows:
                matches = hits.get(row["material_id"], [])
                metadata_match = bool(term and term in (row["title"] + " " + " ".join(json.loads(row["topics_json"]))).casefold())
                if term and not matches and not metadata_match:
                    continue
                if not term:
                    matches = db.execute("SELECT * FROM chunks WHERE material_id=? ORDER BY page_number,char_start LIMIT 3", (row["material_id"],)).fetchall()
                # Narrow snippets per material keep tool output bounded.
                evidence = [self._evidence(hit) for hit in matches[:3]]
                rank = min((hit["rank"] for hit in matches if "rank" in hit.keys()), default=0)
                results.append((rank - (1 if metadata_match else 0), self._summary(row, evidence)))
            results.sort(key=lambda pair: (pair[0], pair[1]["material_id"]))
            return [item for _, item in results[:limit]]

    def get_material(self, material_id: str, principal=None) -> dict:
        _ = principal
        with self._connect() as db:
            row = db.execute(f"SELECT m.* FROM materials m WHERE material_id=? AND {PUBLIC_FILTER}", (material_id,)).fetchone()
            if row is None:
                raise KeyError("Material not found")
            evidence = [self._evidence(c) for c in db.execute("SELECT * FROM chunks WHERE material_id=? ORDER BY page_number,char_start LIMIT 3", (material_id,))]
            return self._summary(row, evidence)

    def read_pages(self, material_id: str, page_start: int, page_end: int) -> list[dict]:
        """Internal bounded PDF preview/excerpt reader; D owns REST exposure."""
        if type(page_start) is not int or type(page_end) is not int or page_start < 1 or not page_start <= page_end <= page_start + 3:
            raise ValueError("Read 1-4 PDF pages per request")
        self.get_material(material_id)
        with self._connect() as db:
            rows = db.execute("SELECT page_number,text,extraction_method,quality_status,warning FROM pages WHERE material_id=? AND page_number BETWEEN ? AND ? ORDER BY page_number", (material_id, page_start, page_end)).fetchall()
            if not rows:
                raise KeyError("Page not found")
            return [dict(row) for row in rows]

    def extraction_warnings(self, material_ids: list[str]) -> list[dict]:
        """D puts these into the existing ApiEnvelope.meta.warnings field."""
        if len(material_ids) > 20:
            raise ValueError("At most 20 material IDs")
        warnings = [{"code": "STUDY_TEXT_UNREVIEWED", "message": "资料为提取原文，尚未逐页人工校对；数学公式、代码、图表、手写必须对照原 PDF。"}]
        with self._connect() as db:
            for mid in dict.fromkeys(material_ids):
                row = db.execute(f"SELECT m.title,m.extraction_status FROM materials m WHERE material_id=? AND {PUBLIC_FILTER}", (mid,)).fetchone()
                if row is None:
                    raise KeyError("Material not found")
                if row["extraction_status"] == "partial":
                    warnings.append({"code": "STUDY_PARTIAL", "message": f"{row['title']}：部分页没有可检索正文（可能为封面/空白/短页/扫描）；不声称完整正文覆盖。"})
                if db.execute("SELECT 1 FROM pages WHERE material_id=? AND extraction_method='windows_ocr' LIMIT 1", (mid,)).fetchone():
                    warnings.append({"code": "STUDY_OCR_UNREVIEWED", "message": f"{row['title']}：包含未人工校对的 OCR；用于定位，不能直接把识别的公式或代码作为标准答案。"})
        return warnings

    def resolve_download(self, material_id: str, principal=None) -> Path:
        """Original PDF, resolved through catalog allowlist; never arbitrary paths."""
        _ = principal
        with self._connect() as db:
            row = db.execute(f"SELECT m.pdf_ref,m.sha256 FROM materials m WHERE material_id=? AND {PUBLIC_FILTER}", (material_id,)).fetchone()
            if row is None:
                raise KeyError("Material not found")
            ref = row["pdf_ref"]
            root = (REPOSITORY_ROOT / "knowledge/study/sources/year1/pdf").resolve()
            if not ref.startswith("knowledge/study/sources/year1/pdf/") or ":" in ref or "\\" in ref or ".." in Path(ref).parts:
                raise KeyError("Download not available")
            candidate = (REPOSITORY_ROOT / ref).resolve()
            if not candidate.is_relative_to(root) or not candidate.is_file():
                raise KeyError("Download not available")
            return candidate


def main():
    """Local smoke-check CLI, not an Agent endpoint or new MCP service."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--course-id")
    parser.add_argument("--topic")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    library = StudyLibrary(args.database)
    result = library.search_materials({"course_id": args.course_id, "topic": args.topic, "limit": args.limit}) if args.course_id else library.list_courses()
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
