"""Install only the two verified small acoustic models into a fresh QA volume.

Run with model-archives mounted read-only at /archives and only qa_models at /models.
No application data, accounts, API credentials or large language models are read.
"""
import hashlib
import json
import os
from pathlib import Path
import zipfile

EXPECTED = {
    'vosk-model-small-en-us-0.15': '30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498',
    'vosk-model-small-cn-0.22': '3af8b0e7e0f835ae9d414ce5df580237a3cfb08d586c9fbbb0f7ff29ad5b14ba',
}

def require(condition, message):
    if not condition:raise ValueError(message)


def main():
    source, destination = Path('/archives'), Path('/models')
    require(source.is_dir() and destination.is_dir(), 'Missing explicit model mounts')
    rows = json.loads((source/'models-manifest.json').read_text('utf-8'))
    require({row['model'] for row in rows} == set(EXPECTED), 'Unexpected acoustic models')
    for row in rows:
        name = row['model']
        archive = source/(name+'.zip')
        require(hashlib.sha256(archive.read_bytes()).hexdigest() == EXPECTED[name] == row['archiveSha256'], 'Acoustic model SHA256 mismatch')
        with zipfile.ZipFile(archive) as z:
            require(sum(x.file_size for x in z.infolist()) < 250*1024*1024, 'Model expansion limit exceeded')
            for item in z.infolist():
                target = (destination/item.filename).resolve()
                require(target.is_relative_to(destination) and item.filename.startswith(name+'/'), 'Invalid model archive path')
                require((item.external_attr >> 16) & 0o170000 != 0o120000, 'Model symlink refused')
            z.extractall(destination)
        require((destination/name/'am/final.mdl').is_file(), 'Missing acoustic model')
    (destination/'models-manifest.json').write_text(json.dumps(rows,indent=2),'utf-8')
    for item in [destination, *destination.rglob('*')]:
        os.chown(item,10001,10001)
        item.chmod(0o755 if item.is_dir() else 0o644)
    print(json.dumps({'smallAcousticModels':len(rows),'verifiedSha256':True,'userDataImported':False}))


if __name__=='__main__':main()
