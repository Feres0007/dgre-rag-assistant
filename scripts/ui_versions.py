"""Snapshot, verify and restore only owned UI files; never touch corpus/history."""
import argparse
import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def owned(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or path.parts[0] not in ('app', '.streamlit'):
        raise ValueError('Chemin hors interface : '+name)
    return path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(root=ROOT):
    folder=root/'backups/ui'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    folder.mkdir(parents=True)
    manifest={'files':{},'created':datetime.now().isoformat()}
    with zipfile.ZipFile(folder/'interface.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for base in ('app','.streamlit'):
            for path in sorted((root/base).rglob('*')):
                if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
                name=path.relative_to(root).as_posix();data=path.read_bytes()
                archive.writestr(name,data);manifest['files'][name]=digest(data)
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    verify(folder)
    return folder


def verify(folder):
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(folder/'interface.zip') as archive:
        if set(archive.namelist())!=set(manifest['files']):raise ValueError('Archive différente du manifeste')
        for name,expected in manifest['files'].items():
            owned(name)
            if digest(archive.read(name))!=expected:raise ValueError('Empreinte invalide : '+name)
    return manifest


def restore(folder,root=ROOT,delivery=None):
    manifest=verify(folder)
    new_files=[]
    if delivery:
        new_files=json.loads(delivery.read_text(encoding='utf-8')).get('new_files',[])
        for name in new_files:owned(name)
    # Reject symlinks escaping the selected workspace before any write/delete.
    for name in list(manifest['files'])+new_files:
        target=(root/str(owned(name))).resolve()
        if not target.is_relative_to(root.resolve()):raise ValueError('Chemin hors espace de travail')
    with zipfile.ZipFile(folder/'interface.zip') as archive:
        for name in manifest['files']:
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(archive.read(name))
    for name in new_files:
        if name not in manifest['files']:(root/name).unlink(missing_ok=True)
    for name,expected in manifest['files'].items():
        if digest((root/name).read_bytes())!=expected:raise ValueError('Restauration incomplète')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['snapshot','verify','restore'])
    parser.add_argument('--backup',type=Path)
    parser.add_argument('--target',type=Path,default=ROOT)
    parser.add_argument('--delivery',type=Path)
    args=parser.parse_args()
    if args.action=='snapshot':print(snapshot(args.target.resolve()))
    else:
        if not args.backup:parser.error('--backup obligatoire')
        if args.action=='verify':verify(args.backup);print('Sauvegarde vérifiée')
        else:
            restore(args.backup,args.target.resolve(),args.delivery);print('Interface restaurée et vérifiée')


if __name__=='__main__':main()
