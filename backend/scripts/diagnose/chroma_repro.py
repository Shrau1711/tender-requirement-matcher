"""Reproduce Chroma's "Error creating hnsw segment reader: Nothing found on disk" with nothing but chromadb and numpy.

Each attempt makes a store in a new folder and does what app.vectorstore.chroma does: for three documents, delete their
old rows, add the new ones and record the document; then it reads back three ways (a filtered fetch, the stored vectors,
a nearest-neighbour query), replaces one document and reads again. At the first error it says which step failed, then
checks whether the store recovers: the same read again at once, after 1, 5 and 30 seconds, with a newly opened client,
and from a separate process. It also prints where the stores were made and whether that folder is synced by OneDrive.
Use it to check a Chroma version or a machine before trusting the store.

Usage: python -m scripts.diagnose.chroma_repro [--attempts 300] [--root <folder for the test stores>]
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import chromadb
import numpy as np
from chromadb.config import Settings

WAITS = (1, 5, 30)  # seconds to wait, one after the other, before reading a failed store again
CLOUD_ATTRIBUTES = {  # Windows file attributes that cloud sync (OneDrive) puts on files and folders
    0x400: "reparse point", 0x1000: "offline", 0x40000: "recall on open", 0x80000: "pinned",
    0x100000: "unpinned", 0x400000: "recall on data access",
}


def put(chunks, docs, doc: str, vectors: np.ndarray) -> None:
    chunks.delete(where={"doc": doc})
    ids = [f"{doc}#{n}" for n in range(len(vectors))]
    chunks.add(ids=ids, embeddings=vectors, metadatas=[{"doc": doc, "n": n} for n in range(len(vectors))])
    docs.upsert(ids=[doc], metadatas=[{"sha256": "x"}], embeddings=[[0.0]])


def steps(chunks) -> list[tuple[str, object]]:
    return [
        ("filtered fetch", lambda: chunks.get(where={"doc": "a"}, include=[])),
        ("stored vectors", lambda: chunks.get(ids=chunks.get(where={"doc": "a"}, include=[])["ids"], include=["embeddings"])),
        ("nearest-neighbour query", lambda: chunks.query(query_embeddings=[[1.0, 0.0, 0.0]], n_results=3, include=["distances"])),
    ]


def open_store(folder: Path):
    client = chromadb.PersistentClient(path=str(folder), settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection("chunks", configuration={"hnsw": {"space": "ip"}}), client.get_or_create_collection("documents")


class Failed(Exception):
    def __init__(self, when: str, step: str, error: Exception, chunks) -> None:
        super().__init__(f"{when}, {step}: {type(error).__name__}: {error}")
        self.step, self.chunks = step, chunks


def reads(chunks, when: str) -> None:
    for name, step in steps(chunks):
        try:
            step()
        except Exception as error:  # the point is to see which step fails, and how
            raise Failed(when, name, error, chunks) from error


def attempt(folder: Path, rng: np.random.Generator) -> None:
    chunks, docs = open_store(folder)
    for doc, size in (("a", 2), ("b", 1), ("c", 1)):
        put(chunks, docs, doc, rng.standard_normal((size, 3)).astype(np.float32))
    reads(chunks, "after the first writes")
    put(chunks, docs, "a", rng.standard_normal((40, 3)).astype(np.float32))
    reads(chunks, "after replacing a document")


def try_step(chunks, step: str) -> str:
    try:
        dict(steps(chunks))[step]()
        return "ok"
    except Exception as error:  # noqa: BLE001 - reported, not raised: this is a diagnosis
        return f"fails ({type(error).__name__}: {str(error)[:90]})"


def recovery(failed: Failed, folder: Path) -> None:
    """Does the failed store recover, with time, with a new client, or in a new process?"""
    print(f"  same client, at once: {try_step(failed.chunks, failed.step)}")
    waited = 0
    for wait in WAITS:
        time.sleep(wait)
        waited += wait
        print(f"  same client, {waited} s later: {try_step(failed.chunks, failed.step)}")
    from chromadb.api.client import SharedSystemClient

    SharedSystemClient.clear_system_cache()  # otherwise Chroma hands back the client it already has for this folder
    print(f"  newly opened client, same process: {try_step(open_store(folder)[0], failed.step)}")
    code = f"from scripts.diagnose.chroma_repro import open_store, try_step; from pathlib import Path; print(try_step(open_store(Path(r'{folder}'))[0], '{failed.step}'))"
    other = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False, cwd=Path(__file__).resolve().parents[2])
    print(f"  separate process: {(other.stdout.strip() or other.stderr.strip()[-200:])}")


def cloud_sync(path: Path) -> str:
    """Whether a folder is inside a OneDrive folder, and which cloud-file attributes it carries (Windows only)."""
    roots = [Path(os.environ[v]) for v in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer") if os.environ.get(v)]
    inside = [str(r) for r in roots if path.resolve().is_relative_to(r.resolve())]
    flags = []
    if platform.system() == "Windows":
        import ctypes

        value = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        flags = [name for bit, name in CLOUD_ATTRIBUTES.items() if value != -1 and value & bit]
    return (f"inside OneDrive ({', '.join(inside)})" if inside else "not inside a OneDrive folder") + (f"; attributes: {', '.join(flags)}" if flags else "; no cloud-file attributes")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--attempts", type=int, default=300)
    ap.add_argument("--root", type=Path, default=None, help="where to make the test stores (default: the system temp folder)")
    args = ap.parse_args()
    base = args.root or Path(tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(dir=base, prefix="chroma_repro_"))
    print(f"chromadb {chromadb.__version__}, Python {platform.python_version()}, {platform.system()} {platform.release()}")
    print(f"stores in {root}: {cloud_sync(root)}")
    print(f"this project: {cloud_sync(Path(__file__).resolve().parents[3])}")
    rng = np.random.default_rng(0)
    try:
        for i in range(1, args.attempts + 1):
            try:
                attempt(root / str(i), rng)
            except Failed as failed:
                print(f"FAILED at attempt {i} of {args.attempts}: {failed}")
                recovery(failed, root / str(i))
                raise SystemExit(1) from None
        print(f"no error in {args.attempts} attempts")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
