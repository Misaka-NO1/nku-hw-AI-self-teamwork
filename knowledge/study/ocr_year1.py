"""Render sparse/scanned pages and recognize locally with Windows Chinese OCR."""
import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdftoppm", type=Path, required=True)
    parser.add_argument("--work", type=Path, default=ROOT / "dist/study-ocr")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    backlog = json.loads((ROOT / "knowledge/study/library/ingestion-report.json").read_text(encoding="utf-8"))["ocr_backlog"]
    cache_path = args.work / "ocr-cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8-sig")) if cache_path.exists() else {}
    pending = [row for row in backlog if not cache.get(row["material_id"] + ":" + str(row["page"]), {}).get("text")]

    def render(row):
        key = row["material_id"] + ":" + str(row["page"])
        prefix = args.work / (row["material_id"] + f"-p{row['page']:04d}")
        png = prefix.with_suffix(".png")
        if not png.exists():
            subprocess.run([str(args.pdftoppm), "-f", str(row["page"]), "-l", str(row["page"]), "-singlefile", "-scale-to", "2000", "-png", str(ROOT / row["pdf_ref"]), str(prefix)], check=True, capture_output=True)
        return {"key": key, "path": str(png.resolve())}

    with ThreadPoolExecutor(max_workers=4) as pool:
        manifest = list(pool.map(render, pending))
    print(f"Rendered {len(manifest)} pages for offline OCR", flush=True)
    manifest_path = args.work / "ocr-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    batch_cache = args.work / "ocr-batch.json"
    if manifest:
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "knowledge/study/ocr_windows.ps1"), "-Manifest", str(manifest_path), "-Output", str(batch_cache)], check=True)
        cache.update(json.loads(batch_cache.read_text(encoding="utf-8-sig")))
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OCR cache: {cache_path}; rerun build_year1.py with --ocr-cache", flush=True)


if __name__ == "__main__":
    main()
