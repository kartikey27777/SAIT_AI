import time
import threading
import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://saitjbp.in"

PAGES = [
    ("home", "/page/home"),
    ("about-us", "/page/about-us"),
    ("academics", "/page/academics"),
    ("beyond-academics", "/page/beyond_academics"),
    ("admissions", "/page/admission-tab"),
    ("student-affairs", "/page/student-affairs"),
    ("placements", "/page/placements"),
    ("facilities", "/page/facilites"),
    ("fee-structure", "/page/fee-structure"),
    ("contact-us", "/page/contact-us"),
]

NEWS_PATHS = [
    "/read/download-admission-form-for-2026",
    "/read/our-success-stories",
    "/read/fdp-program",
]

WEBSITE_TAGS = ["website", "college"]

_sync_status = {"status": "idle", "progress": "", "pages": [], "last_run": ""}


def _strip_dom_stuff(html):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "iframe", "nav", "footer", "header"]):
        tag.decompose()

    for tag in soup.find_all(attrs={"class": ["sidebar", "menu", "copyright", "topbar"]}):
        tag.decompose()

    main = soup.find("main") or soup.find(id="content") or soup.find(class_="content")
    if main:
        soup = main

    text = soup.get_text("\n")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    text = "\n".join(lines)

    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text


def _fetch_text(client, path):
    url = BASE_URL + path if path.startswith("/") else path
    resp = client.get(url, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    return _strip_dom_stuff(resp.text)


def _index_one(client, name, path, tags):
    from backend.services.chunking import create_chunks
    from backend.services.embeddings import generate_embeddings
    from backend.services.store_vectors import store_chunks

    text = _fetch_text(client, path)
    if len(text) < 60:
        return {"name": name, "path": path, "chars": len(text), "chunks": 0, "error": "too little text"}

    chunks = create_chunks(text)
    embeddings = generate_embeddings(chunks)
    store_chunks(chunks, embeddings, name, tags=tags)

    return {"name": name, "path": path, "chars": len(text), "chunks": len(chunks)}


def _delete_existing(tags):
    from backend.services.qdrant_client import get_qdrant_client
    from qdrant_client.models import Filter, FieldCondition, MatchAny

    client = get_qdrant_client()
    try:
        client.delete(
            collection_name="documents_v2",
            points_selector=Filter(
                must=[FieldCondition(key="tags", match=MatchAny(any=tags))]
            ),
        )
    except Exception:
        pass


def run_sync_in_thread():
    def job():
        global _sync_status
        _sync_status = {"status": "running", "progress": "starting", "pages": [], "last_run": ""}
        try:
            with httpx.Client(base_url=BASE_URL, headers={"User-Agent": "SAIT-AI-Sync/1.0"}, timeout=30) as client:
                _delete_existing(WEBSITE_TAGS)
                names = [slug for slug, _ in PAGES]
                _sync_status["progress"] = "wiping old college data"
                for slug, path in PAGES:
                    _sync_status["progress"] = f"fetching {slug}"
                    try:
                        result = _index_one(client, slug, path, WEBSITE_TAGS)
                        names.remove(slug)
                        _sync_status["pages"].append(result)
                    except Exception as e:
                        _sync_status["pages"].append({"name": slug, "path": path, "error": str(e)})

                for path in NEWS_PATHS:
                    slug = "news-" + path.rstrip("/").split("/")[-1]
                    _sync_status["progress"] = f"fetching {slug}"
                    try:
                        result = _index_one(client, slug, path, WEBSITE_TAGS)
                        names.append(slug)
                        _sync_status["pages"].append(result)
                    except Exception as e:
                        _sync_status["pages"].append({"name": slug, "path": path, "error": str(e)})

            _sync_status["progress"] = "done"
            _sync_status["status"] = "done"
            _sync_status["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            _sync_status["status"] = "error"
            _sync_status["progress"] = str(e)

    threading.Thread(target=job, daemon=True).start()


def get_status():
    return _sync_status