"""Bounded live-source and logo audit; reports identifiers, never URLs or credentials.

A media header confirms a short sample only. Timeouts/access errors stay inconclusive.
"""
import argparse
import collections
import concurrent.futures
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def identity(url):
    return hashlib.sha256(url.encode()).hexdigest()


def catalog(path):
    rows, row, source = [], None, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if key == "canal":
            row = {"name": value, "sources": []}
            rows.append(row)
            source = None
        elif row is not None and key == "fonte":
            source = {"url": value}
            row["sources"].append(source)
        elif source is not None and key in ("agente", "referer"):
            source[key] = value
        elif row is not None and key in ("logo", "categoria"):
            row[key] = value
    return rows


def media(data):
    if len(data) > 377 and any(data[offset] == data[offset + 188] == data[offset + 376] == 0x47 for offset in range(min(188, len(data) - 376))):
        return True
    return len(data) >= 12 and data[4:8] in (b"ftyp", b"styp", b"moof", b"sidx")


def probe(url, headers=None, logo=False, depth=0):
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "IPTVibe/LiveAudit", "Range": "bytes=0-16383", **(headers or {})})
        with urllib.request.urlopen(request, timeout=5) as response:
            data = response.read(16384)
            resolved = response.geturl()
        if logo:
            image = data.startswith((b"\x89PNG", b"\xff\xd8", b"GIF8", b"RIFF")) or b"<svg" in data[:1024]
            return {"status": "image" if image else "non_image"}
        if media(data):
            return {"status": "media_header"}
        text = data.decode("utf-8", errors="replace").lstrip("\ufeff\r\n ")
        if text.startswith("#EXTM3U"):
            if re.search(r'#EXT-X-KEY:.*METHOD=(?!NONE)', text):
                return {"status": "encrypted_manifest"}
            if depth >= 2:
                return {"status": "manifest_only"}
            child = next((line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")), None)
            if not child:
                match = re.search(r'#EXT-X-MAP:.*URI="([^"]+)"', text)
                child = match.group(1) if match else None
            if not child:
                return {"status": "empty_manifest"}
            result = probe(urllib.parse.urljoin(resolved, child), headers, depth=depth + 1)
            if result["status"] == "media_header":
                return result
            return {"status": "manifest_child_unavailable", "child_status": result["status"]}
        if "<MPD" in text[:2048]:
            return {"status": "dash_manifest"}
        if text.lower().startswith(('<!doctype html', '<html', '<head', '<body', '{"', '[{"')):
            return {"status": "non_media"}
        return {"status": "unknown_binary"}
    except urllib.error.HTTPError as error:
        return {"status": "http_error", "code": error.code}
    except Exception as error:
        # Exception text may include the requested URL. Do not serialize it.
        return {"status": "network_inconclusive", "error_type": type(error).__name__}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog")
    parser.add_argument("output")
    parser.add_argument("--workers", type=int, default=32)
    args = parser.parse_args()
    rows = catalog(args.catalog)
    jobs = {}
    for row in rows:
        for source in row["sources"]:
            url = source["url"]
            headers = {}
            if source.get("agente"):
                headers["User-Agent"] = source["agente"]
            if source.get("referer"):
                headers["Referer"] = source["referer"]
            # A URL with different required headers is a separate request.
            key = identity(url + json.dumps(headers, sort_keys=True))
            jobs[key] = (url, headers, False)
            source["audit_id"] = key
        if row.get("logo"):
            key = identity(row["logo"])
            jobs[key] = (row["logo"], {}, True)
            row["logo_audit_id"] = key
    locks = collections.defaultdict(lambda: threading.BoundedSemaphore(8))
    results = {}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    def run(item):
        key, (url, headers, logo) = item
        with locks[urllib.parse.urlsplit(url).netloc]:
            result = probe(url, headers, logo)
        result["url_id"] = identity(url)
        result["kind"] = "logo" if logo else "source"
        return key, result
    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run, item) for item in jobs.items()]
        for future in concurrent.futures.as_completed(futures):
            key, result = future.result()
            results[key] = result
            if len(results) % 100 == 0 or len(results) == len(jobs):
                report = {"completed": len(results), "total": len(jobs), "elapsed_seconds": round(time.monotonic() - started), "counts": dict(collections.Counter(r["status"] for r in results.values()))}
                print(json.dumps(report), flush=True)
                output.with_suffix(".progress.json").write_text(json.dumps(report), encoding="utf-8")
                output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    summary = []
    for row in rows:
        summary.append({"name": row["name"], "category": row.get("categoria", ""), "sources": [s["audit_id"] for s in row["sources"]], "logo": row.get("logo_audit_id")})
    output.with_suffix(".channels.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
