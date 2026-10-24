from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from zipfile import ZipFile
import hashlib
import json
import requests
import time

root = Path(__file__).resolve().parents[1]
dest = root / 'Day5_Resources'
dest.mkdir(exist_ok=True)
revision = '9217f5db79a29953eb74d5343926648285ec7e67'
base = f'https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/{revision}/'
expected_models={
 'qwen2.5-0.5b-instruct-q4_k_m.gguf':(491400032,'74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db'),
 'qwen2.5-0.5b-instruct-q8_0.gguf':(675710816,'ca59ca7f13d0e15a8cfa77bd17e65d24f6844b554a7b6c12e07a5f89ff76844e'),
 'llama-b11696-bin-win-cpu-x64.zip':(19575690,'1e7c47dff58467540d53e6cf302d83951bcb165afb252c2952ed3872190fc60d')}
items = [(base + name, dest/'models'/name) for name in [
    'qwen2.5-0.5b-instruct-q4_k_m.gguf', 'qwen2.5-0.5b-instruct-q8_0.gguf', 'LICENSE', 'README.md']]
items += [('https://github.com/ggml-org/llama.cpp/releases/download/b11696/llama-b11696-bin-win-cpu-x64.zip',dest/'llama-b11696-bin-win-cpu-x64.zip'),
          ('https://raw.githubusercontent.com/ggml-org/llama.cpp/b11696/LICENSE',dest/'llama-LICENSE'),
          ('https://raw.githubusercontent.com/ggml-org/llama.cpp/b11696/tools/server/README.md',dest/'llama-server-reference.md')]

def fetch(item):
    url, path = item
    path.parent.mkdir(exist_ok=True)
    if not path.exists():
        if path.suffix=='.gguf':
            total=expected_models[path.name][0];size=4*2**20
            chunk_dir=path.parent/(path.stem+'_chunks');chunk_dir.mkdir(exist_ok=True)
            def chunk(index):
                start=index*size;end=min(total-1,start+size-1);p=chunk_dir/str(index)
                if p.exists() and p.stat().st_size==end-start+1:return
                for attempt in range(5):
                    try:
                        r=requests.get(url+f'?download=true&chunk={index}',headers={'Range':f'bytes={start}-{end}'},timeout=(30,90));r.raise_for_status()
                        if len(r.content)!=end-start+1:raise ValueError('Wrong range size.')
                        p.write_bytes(r.content);return
                    except Exception:
                        if attempt==4:raise
                        time.sleep(1)
            with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(chunk,range((total+size-1)//size)))
            with path.with_suffix(path.suffix+'.part').open('wb') as out:
                for index in range((total+size-1)//size):out.write((chunk_dir/str(index)).read_bytes())
        else:
            with requests.get(url,stream=True,timeout=(30,120)) as response:
                response.raise_for_status()
                with path.with_suffix(path.suffix+'.part').open('wb') as out:
                    for chunk in response.iter_content(2**20):out.write(chunk)
        path.with_suffix(path.suffix+'.part').replace(path)
    h=hashlib.sha256()
    with path.open('rb') as inp:
        for chunk in iter(lambda:inp.read(2**20),b''):h.update(chunk)
    if path.name in expected_models:
        expected_size,expected_sha=expected_models[path.name]
        if path.stat().st_size!=expected_size or h.hexdigest()!=expected_sha:raise ValueError('Pinned upstream model checksum mismatch: '+path.name)
    print(path.name,path.stat().st_size,flush=True)
    return {'path':str(path.relative_to(root)).replace('\\','/'),'url':url,'bytes':path.stat().st_size,'sha256':h.hexdigest()}

if __name__ == '__main__':
    import sys
    if '--q4-only' in sys.argv:
        print(fetch(items[0]),flush=True)
        raise SystemExit
    with ThreadPoolExecutor(max_workers=3) as executor: records=list(executor.map(fetch,items))
    with ZipFile(dest/'llama-b11696-bin-win-cpu-x64.zip') as z:z.extractall(dest/'llama_cpp')
    (dest/'resource_manifest.json').write_text(json.dumps({'model_revision':revision,'runtime_release':'b11696','files':records},indent=2),encoding='utf-8')
