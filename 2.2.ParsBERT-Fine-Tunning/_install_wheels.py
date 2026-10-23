"""Download wheels straight from PyPI and unpack into a target dir (no pip)."""
import json, os, ssl, sys, time, urllib.request, zipfile

DEST = r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning\.pkgs"
CACHE = r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning\_wheels"
os.makedirs(DEST, exist_ok=True)
os.makedirs(CACHE, exist_ok=True)
CTX = ssl.create_default_context()

PY_MINOR = 12
PLATS = ["win_amd64"]


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        return json.load(r)


def _minor(tag):
    """cp312 -> 12, cp39 -> 9"""
    try:
        return int(tag[3:])
    except ValueError:
        return None


def wheel_rank(filename):
    """Lower is better; None if incompatible. Handles cp3xx / abi3 / py3 wheels."""
    if not filename.endswith(".whl"):
        return None
    parts = filename[:-4].split("-")
    if len(parts) < 5:
        return None
    pytag, abitag, plattag = parts[-3], parts[-2], parts[-1]

    if plattag == "any":
        return 100 if pytag in ("py3", "py2.py3") else None
    if plattag not in PLATS:
        return None

    target = f"cp3{PY_MINOR}"
    if abitag == "abi3":
        # abi3 wheels work on this interpreter and newer
        m = _minor(pytag)
        return 10 if (m is not None and m <= PY_MINOR) else None
    if abitag == target and pytag in (target, "py3"):
        return 5
    if abitag == "none" and pytag in (target, "py3"):
        return 20
    return None


def _vkey(v):
    out = []
    for part in v.replace("-", ".").split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        out.append(int(num) if num else -1)
    return tuple(out)


def pick(pkg, version=None, prefer=None):
    data = fetch_json(f"https://pypi.org/pypi/{pkg}/json")
    if version:
        versions = [version]
    else:
        versions = [v for v in data["releases"] if re.fullmatch(r"[0-9]+(\.[0-9]+)*", v)]
        versions.sort(key=_vkey, reverse=True)

    for ver in versions:
        files = data["releases"].get(ver) or (data["urls"] if ver == data["info"]["version"] else [])
        cands = []
        for f in files:
            if f.get("packagetype") != "bdist_wheel":
                continue
            r = wheel_rank(f["filename"])
            if r is None:
                continue
            bonus = -50 if (prefer and prefer in f["filename"]) else 0
            cands.append((r + bonus, f["filename"], f["url"], f["size"], ver))
        if cands:
            cands.sort(key=lambda x: x[0])
            return cands[0]
    raise RuntimeError(f"no compatible wheel for {pkg}=={version}")


def download(url, name):
    path = os.path.join(CACHE, name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180, context=CTX) as r, open(path + ".part", "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    os.replace(path + ".part", path)
    return path


def unpack(path, dest):
    with zipfile.ZipFile(path) as z:
        for member in z.infolist():
            name = member.filename
            if name.endswith("/"):
                continue
            # skip scripts dir: not needed, avoids bin clutter
            target = os.path.join(dest, name)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(member) as src, open(target, "wb") as out:
                out.write(src.read())


PACKAGES = [
    ("filelock", "4.2.4"), ("packaging", "26.3"), ("typing_extensions", "4.16.0"),
    ("pyyaml", "6.0.3"), ("tqdm", "4.70.1"), ("regex", "2026.9.29"),
    ("requests", "2.34.2"), ("urllib3", "2.8.0"), ("charset_normalizer", "3.5.2"),
    ("idna", "3.20"), ("certifi", "2026.10.19"),
    ("huggingface_hub", "0.36.0"), ("safetensors", "0.8.0"),
    ("tokenizers", "0.22.1"), ("transformers", "4.57.1"),
    ("contourpy", "1.4.0"), ("cycler", "0.12.1"), ("fonttools", "4.67.0"),
    ("kiwisolver", "1.5.1"), ("pillow", "13.0.0"), ("pyparsing", "3.3.3"),
    ("matplotlib", "3.11.2"),
]

t_start = time.time()
for pkg, ver in PACKAGES:
    try:
        rank, fname, url, size, resolved = pick(pkg, ver)
        p = download(url, fname)
        unpack(p, DEST)
        print(f"OK   {pkg:18} {resolved:12} {fname}", flush=True)
    except Exception as e:
        print(f"FAIL {pkg:18} {type(e).__name__}: {str(e)[:160]}", flush=True)

print(f"elapsed {time.time()-t_start:.1f}s", flush=True)
