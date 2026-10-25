"""Explicit download of small Apache-2.0 Vosk acoustic models; no LLM/RAG weights."""
import argparse,hashlib,json,urllib.request,zipfile,subprocess,shutil
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--languages',nargs='+',choices=['en','zh'],default=['en','zh']);args=p.parse_args();root=Path(args.directory).resolve();root.mkdir(parents=True,exist_ok=True);manifest=[]
    for lang in args.languages:
        name='vosk-model-small-cn-0.22' if lang=='zh' else 'vosk-model-small-en-us-0.15';url='https://alphacephei.com/vosk/models/'+name+'.zip';archive=root/(name+'.zip')
        if not (root/name/'am/final.mdl').is_file():
            if not archive.exists() or not zipfile.is_zipfile(archive):
                print('Downloading small acoustic model '+lang,flush=True)
                temporary=archive.with_suffix('.download')
                if shutil.which('curl'):
                    subprocess.run(['curl','--fail','--location','--connect-timeout','20','--max-time','600','--retry','2','--max-filesize',str(100*1024*1024),'--output',str(temporary),url],check=True)
                else:
                    with urllib.request.urlopen(url,timeout=30) as response,temporary.open('wb') as stream:
                        size=0
                        while data:=response.read(65536):
                            size+=len(data)
                            if size>100*1024*1024:raise ValueError('Unexpected model size')
                            stream.write(data)
                if not zipfile.is_zipfile(temporary):raise ValueError('Incomplete model download')
                temporary.replace(archive)
            with zipfile.ZipFile(archive) as z:
                if sum(x.file_size for x in z.infolist())>250*1024*1024:raise ValueError('Model expands beyond limit')
                for x in z.infolist():
                    target=(root/x.filename).resolve()
                    if not target.is_relative_to(root) or not x.filename.startswith(name+'/'):raise ValueError('Invalid model archive path')
                z.extractall(root)
        manifest.append({'language':lang,'model':name,'url':url,'license':'Apache-2.0','archiveSha256':hashlib.sha256(archive.read_bytes()).hexdigest() if archive.is_file() else 'archive not retained'})
    (root/'models-manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8');print('Small acoustic models ready',flush=True)
if __name__=='__main__':main()
