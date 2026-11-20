"""Prepare a portable deployment folder; does not modify the active corpus."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[1]
target = root / 'livrables' / 'DGRE_Entreprise_20261012'
if target.exists():
    raise SystemExit(f'Already exists: {target}')
target.mkdir(parents=True)
release = json.loads((root / 'data/active.json').read_text(encoding='utf-8'))['release_id']
for name in ('active.json', 'registry.json'):
    dest = target / 'data' / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / 'data' / name, dest)
shutil.copytree(root / 'data/releases' / release, target / 'data/releases' / release)
shutil.copytree(root / 'data/models', target / 'data/models', ignore=shutil.ignore_patterns('.locks', '*.lock', '*.incomplete'))
records = json.loads((root / 'data/registry.json').read_text(encoding='utf-8'))
for record in records:
    path = root / record['relative_path']
    if hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() != record['sha256']:
        raise SystemExit(f'Source hash mismatch: {path}')
    dest = target / record['relative_path']
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
shutil.copy2(Path(sys.argv[1]), target / 'dgre-rag-image.tar')
print(target)
