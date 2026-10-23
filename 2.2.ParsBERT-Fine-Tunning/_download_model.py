import os, ssl, sys, time, urllib.request

DEST = r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning\model\bert-fa-zwnj-base"
os.makedirs(DEST, exist_ok=True)

FILES = ["config.json", "vocab.txt", "tokenizer.json", "tokenizer_config.json",
         "special_tokens_map.json", "pytorch_model.bin"]

BASE = "https://huggingface.co/HooshvareLab/bert-fa-zwnj-base/resolve/main/"
ctx = ssl.create_default_context()

for name in FILES:
    out = os.path.join(DEST, name)
    url = BASE + name

    # skip if already complete
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            total = int(r.headers.get("Content-Length", 0))
    except Exception as e:
        print("HEAD failed", name, e, flush=True)
        total = 0

    if os.path.exists(out) and total and os.path.getsize(out) == total:
        print("SKIP", name, total, flush=True)
        continue

    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120, context=ctx) as r, open(out + ".part", "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        got = 0
        last = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if got - last > 50 * (1 << 20):
                last = got
                print(f"  {name}: {got/1e6:.0f}/{total/1e6:.0f} MB", flush=True)
    os.replace(out + ".part", out)
    print(f"DONE {name} {os.path.getsize(out)} bytes in {time.time()-t0:.1f}s", flush=True)

print("ALL DONE", flush=True)
