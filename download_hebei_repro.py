#!/usr/bin/env python3
"""Download and safely verify the complete Hebei temporal-batch reproduction bundle."""
from pathlib import Path
import argparse,json,hashlib,urllib.request,tarfile,zipfile,stat,sys
ROOT=Path(__file__).resolve().parent

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--workdir',type=Path,default=Path('hebei_repro'));ap.add_argument('--payload',type=Path,help='Use an already-downloaded Release data/model tar.gz');a=ap.parse_args()
    cfg=json.loads((ROOT/'HEBEI_ASSETS.json').read_text());code=ROOT/cfg['code']['name'];assert code.is_file() and code.stat().st_size==cfg['code']['bytes'] and sha(code)==cfg['code']['SHA256'],'Code ZIP missing or SHA mismatch'
    dest=a.workdir.resolve();assert not dest.exists(),'Choose a fresh --workdir; existing files are never overwritten'
    if a.payload:payload=a.payload.resolve()
    else:
        cache=ROOT/'.hebei_downloads';cache.mkdir(exist_ok=True);payload=cache/cfg['payload']['name'];part=payload.with_suffix(payload.suffix+'.part')
        if not payload.exists():
            url=f"https://github.com/{cfg['repository']}/releases/download/{cfg['release_tag']}/{cfg['payload']['name']}"
            start=part.stat().st_size if part.exists() else 0
            req=urllib.request.Request(url,headers={'User-Agent':'hebei-repro-downloader',**({'Range':f'bytes={start}-'} if start else {})})
            with urllib.request.urlopen(req,timeout=120) as response:
                assert not start or response.status==206,'Server did not accept resume; supply --payload or choose a fresh download cache'
                with part.open('ab' if start else 'xb') as out:
                    count=start;next_print=count+64*1024*1024
                    while chunk:=response.read(4*1024*1024):
                        out.write(chunk);count+=len(chunk)
                        if count>=next_print:print(f'Downloaded {count:,}/{cfg["payload"]["bytes"]:,} bytes',flush=True);next_print=count+64*1024*1024
            assert part.stat().st_size==cfg['payload']['bytes'] and sha(part)==cfg['payload']['SHA256'],'Data/model archive SHA mismatch'
            part.rename(payload)
    assert payload.is_file() and payload.stat().st_size==cfg['payload']['bytes'] and sha(payload)==cfg['payload']['SHA256'],'Payload SHA mismatch'
    with zipfile.ZipFile(code) as z:
        seen=set();total=0
        for item in z.infolist():
            p=Path(item.filename);assert not item.is_dir() and not p.is_absolute() and '..' not in p.parts and item.filename not in seen and not stat.S_ISLNK(item.external_attr>>16)
            seen.add(item.filename);total+=item.file_size
        assert total<=10*1024*1024
        dest.mkdir(parents=True,exist_ok=False)
        for item in z.infolist():
            p=dest/item.filename;p.parent.mkdir(parents=True,exist_ok=True);p.open('xb').write(z.read(item))
    manifest=json.loads((dest/'PAYLOAD_MANIFEST.json').read_text());expected={'original_snapshot/'+n:v for n,v in manifest['files'].items()}
    with tarfile.open(payload,'r:gz') as t:
        members=t.getmembers();seen=set();total=0
        for item in members:
            p=Path(item.name);assert item.isfile() and not item.issym() and not item.islnk() and not p.is_absolute() and '..' not in p.parts and item.name not in seen
            assert item.name in expected and item.size==expected[item.name]['bytes'];seen.add(item.name);total+=item.size
        assert seen==set(expected) and len(members)==cfg['payload_regular_members'] and total==cfg['full_payload_uncompressed_bytes'] and total<=2*1024**3
        for item in members:
            p=dest/item.name;assert dest in p.resolve().parents and not p.exists();p.parent.mkdir(parents=True,exist_ok=True)
            h=hashlib.sha256()
            with p.open('xb') as out:
                f=t.extractfile(item)
                while chunk:=f.read(4*1024*1024):out.write(chunk);h.update(chunk)
            assert h.hexdigest()==expected[item.name]['SHA'],item.name
    print(f'Complete bundle verified: {len(expected)} data/model/source files in {dest}')
    print(f'Next: {sys.executable} -m pip install -r {dest}/requirements-replay.txt')
    print(f'Then: {sys.executable} {dest}/reproduce.py replay --seed 42 --output replay42')

if __name__=='__main__':main()
