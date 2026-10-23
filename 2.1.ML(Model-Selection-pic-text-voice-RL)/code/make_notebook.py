import json, os, re, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else 'section5_bank.py'
DST = os.path.splitext(SRC)[0] + '.ipynb'

lines = open(SRC, encoding='utf-8').read().splitlines()

cells = []
buf, mode = [], None


def flush():
    global buf, mode
    if mode is None or not buf:
        buf, mode = [], None
        return
    text = '\n'.join(buf).strip('\n')
    if mode == 'markdown':
        md = '\n'.join(re.sub(r'^# ?', '', l) for l in text.splitlines()).strip()
        cells.append({'cell_type': 'markdown', 'metadata': {},
                      'source': md.splitlines(keepends=True)})
    else:
        cells.append({'cell_type': 'code', 'execution_count': None, 'metadata': {},
                      'outputs': [], 'source': text.splitlines(keepends=True)})
    buf, mode = [], None


for line in lines:
    if line.startswith('# %%'):
        flush()
        mode = 'markdown' if '[markdown]' in line else 'code'
        continue
    if mode is not None:
        buf.append(line)

flush()

nb = {
    'cells': cells,
    'metadata': {
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python', 'version': '3.12'},
    },
    'nbformat': 4,
    'nbformat_minor': 5,
}
with open(DST, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f'{DST}: {len(cells)} cells '
      f'({sum(1 for c in cells if c["cell_type"] == "markdown")} md, '
      f'{sum(1 for c in cells if c["cell_type"] == "code")} code), '
      f'{os.path.getsize(DST)} bytes')
