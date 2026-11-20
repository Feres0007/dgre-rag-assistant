"""Hash and zip the prepared delivery, excluding runtime test logs."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

root = Path(__file__).resolve().parents[1]
folder = root / 'livrables/DGRE_Entreprise_20261012'
destination = Path(sys.argv[1])
if destination.exists():
    raise SystemExit(f'Refusing to overwrite: {destination}')
excluded = {'data/query_logs', 'data/page_cache', 'data/ui'}
files = [p for p in sorted(folder.rglob('*')) if p.is_file()
         and not any(p.relative_to(folder).as_posix().startswith(x + '/') for x in excluded)
         and p.name != 'MANIFEST_SHA256.json']
manifest = {}
for path in files:
    with path.open('rb') as stream:
        manifest[path.relative_to(folder).as_posix()] = {
            'bytes': path.stat().st_size,
            'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}
manifest_path = folder / 'MANIFEST_SHA256.json'
manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
files.append(manifest_path)
with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
    for path in files:
        archive.write(path, f'DGRE_Entreprise/{path.relative_to(folder).as_posix()}')
with zipfile.ZipFile(destination) as archive:
    assert archive.testzip() is None
    for name, record in manifest.items():
        with archive.open('DGRE_Entreprise/' + name) as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == record['sha256'], name
with destination.open('rb') as stream:
    checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
result = {'archive': str(destination), 'bytes': destination.stat().st_size,
          'sha256': checksum, 'files': len(files), 'crc_and_sha256': 'passed'}
(root / 'reports/enterprise_bundle.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
