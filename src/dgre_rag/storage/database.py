from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from dgre_rag.config import data_dir


def uid(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:32]


def dump(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(temp, path)


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def build_fingerprint():
    """All extraction dependencies, schemas and configuration; never credentials."""
    from dgre_rag.config import root
    package=Path(__file__).parents[1]
    files=sorted(p for p in package.rglob('*') if p.suffix in ('.py','.sql','.txt'))
    hashes={p.relative_to(package).as_posix():file_hash(p) for p in files}
    for p in sorted((root()/'config').glob('*.yaml')):
        hashes['config/'+p.name]=file_hash(p)
    payload=json.dumps(hashes,sort_keys=True).encode()
    return {'sha256':hashlib.sha256(payload).hexdigest(),'files':hashes,'schema_version':2}


def initialize(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(Path(__file__).with_name("001_initial.sql").read_text(encoding="utf-8"))
    db.executescript('''
    CREATE TABLE page_inventory(document_id TEXT REFERENCES documents, page_pdf INTEGER,
      page_printed TEXT, width REAL, height REAL, rotation INTEGER, family TEXT,
      state TEXT, tables_found INTEGER, observations INTEGER DEFAULT 0, reason TEXT,
      PRIMARY KEY(document_id,page_pdf));
    CREATE TABLE table_extractions(source_id TEXT PRIMARY KEY REFERENCES sources,
      rows_json TEXT, geometry_json TEXT, state TEXT, reason TEXT);
    CREATE TABLE observation_context(observation_id TEXT PRIMARY KEY REFERENCES observations,
      missing_days INTEGER DEFAULT 0, note TEXT, table_source_id TEXT REFERENCES sources);
    CREATE TABLE run_metadata(key TEXT PRIMARY KEY,value TEXT);
    CREATE INDEX idx_obs_quality ON observations(quality_status);
    CREATE INDEX idx_selections_observation ON observation_selections(observation_id);
    CREATE VIEW published_observations AS
      SELECT o.*, e.canonical_name, c.missing_days, c.note, c.table_source_id
      FROM observation_selections s JOIN observations o USING(observation_id)
      JOIN entities e USING(entity_id) LEFT JOIN observation_context c USING(observation_id)
      WHERE o.quality_status='validated';
    ''')
    db.executescript(Path(__file__).with_name('002_robustness.sql').read_text(encoding='utf-8'))
    return db


def active_release() -> str | None:
    pointer = data_dir() / "active.json"
    if not pointer.exists():
        return None
    return json.loads(pointer.read_text(encoding="utf-8"))["release_id"]


def release_path(release_id: str | None = None) -> Path:
    release_id = release_id or active_release()
    if not release_id:
        raise ValueError("NO_RELEASE")
    if not all(c.isalnum() or c in "-_" for c in release_id):
        raise ValueError("INVALID_RELEASE")
    path = data_dir() / "releases" / release_id
    if not (path / "database.sqlite").is_file():
        raise ValueError("RELEASE_MISSING")
    return path


@contextmanager
def connect(release_id: str | None = None):
    path = release_path(release_id) / "database.sqlite"
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        db.close()


def integrity(db):
    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("DATABASE_INTEGRITY")
    missing = db.execute('''SELECT count(*) FROM observations o WHERE quality_status='validated'
      AND NOT EXISTS (SELECT 1 FROM observation_evidence e WHERE e.observation_id=o.observation_id)''').fetchone()[0]
    if missing:
        raise ValueError("MISSING_EVIDENCE")
    invalid = db.execute('''SELECT count(*) FROM sources s JOIN page_inventory p USING(document_id,page_pdf)
      WHERE x0<0 OR y0<0 OR x1>p.width+1 OR y1>p.height+1''').fetchone()[0]
    if invalid:
        raise ValueError("INVALID_BBOX")


def publish(run_id: str, label: str = "corpus", activate: bool = True) -> str:
    if not all(c.isalnum() or c in "-_" for c in run_id + label):
        raise ValueError("INVALID_IDENTIFIER")
    src = data_dir() / "runs" / run_id / "database.sqlite"
    with sqlite3.connect(src) as db:
        integrity(db)
        if db.execute("SELECT value FROM run_metadata WHERE key='validated'").fetchone() != ('true',):
            raise ValueError("VALIDATION_REQUIRED")
        metadata=dict(db.execute('SELECT key,value FROM run_metadata'))
        documents=[dict(zip(('document_id','sha256'),r)) for r in db.execute('SELECT document_id,sha256 FROM documents')]
        from dgre_rag.ingestion.pipeline import campaign
        campaigns={campaign(dict(zip(('original_name','edition'),r))) for r in db.execute('SELECT original_name,edition FROM documents')}
        default_campaign=next(iter(campaigns)) if len(campaigns)==1 else None
    rid = label + "-" + file_hash(src)[:12]
    dest = data_dir() / "releases" / rid
    previous=release_path() if active_release() else None
    if not dest.exists():
        staging = data_dir() / "releases" / (".staging-" + uuid.uuid4().hex)
        staging.mkdir(parents=True)
        shutil.copy2(src, staging / "database.sqlite")
        dump(staging / "manifest.json", {"release_id": rid, "run_id": run_id,
             "database_sha256": file_hash(src), "created": datetime.now(timezone.utc).isoformat(),
             "index_mode": "lexical", "extractor_version": "0.2.0",
             "documents":documents,"build":json.loads(metadata.get('build','{}')),
             "default_period":{'start':str(default_campaign[0]),'end':str(default_campaign[1])} if default_campaign else None})
        os.replace(staging, dest)
    if previous and previous!=dest and (previous/'index.json').exists() and not (dest/'index.json').exists():
        # Reuse vectors only when the entire chunk catalogue is byte-for-byte identical.
        with sqlite3.connect(previous/'database.sqlite') as old, sqlite3.connect(dest/'database.sqlite') as new:
            same=old.execute('SELECT * FROM chunks ORDER BY chunk_id').fetchall()==new.execute('SELECT * FROM chunks ORDER BY chunk_id').fetchall()
        if same:
            index=json.loads((previous/'index.json').read_text(encoding='utf-8'))
            if file_hash(previous/index['file'])==index['sha256']:
                shutil.copy2(previous/index['file'],dest/index['file'])
                index.update(release_id=rid,database_sha256=file_hash(src))
                dump(dest/'index.json',index)
    if activate:
        restore(rid)
    return rid


def backup(release_id: str | None = None) -> Path:
    src = release_path(release_id)
    dest = data_dir() / "backups" / (src.name + "-" + datetime.now().strftime("%Y%m%d%H%M%S"))
    shutil.copytree(src, dest)
    return dest


def restore(release_id: str):
    path = release_path(release_id)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if file_hash(path / "database.sqlite") != manifest["database_sha256"]:
        raise ValueError("RELEASE_HASH_MISMATCH")
    with sqlite3.connect(path / "database.sqlite") as db:
        integrity(db)
    if (path/'index.json').exists():
        index=json.loads((path/'index.json').read_text(encoding='utf-8'))
        if index['release_id']!=release_id or index['database_sha256']!=manifest['database_sha256'] or file_hash(path/index['file'])!=index['sha256']:
            raise ValueError('INDEX_VERSION_MISMATCH')
    dump(data_dir() / "active.json", {"release_id": release_id})
