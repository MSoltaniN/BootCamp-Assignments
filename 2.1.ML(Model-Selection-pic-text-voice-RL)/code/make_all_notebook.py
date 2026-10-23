import io
import json
import os
import re

ANSWERS = r'../answers/answers.md'
SCRIPTS = [
    'section5_bank.py',
    'section6_bike.py',
    'section7_fashion.py',
    'section8_spam.py',
    'section9_audio.py',
    'section10_qlearning.py',
]
OUT = 'all_sections.ipynb'


def md_cell(text):
    return {'cell_type': 'markdown', 'metadata': {},
            'source': text.strip('\n').splitlines(keepends=True)}


def code_cell(text):
    return {'cell_type': 'code', 'execution_count': None, 'metadata': {}, 'outputs': [],
            'source': text.strip('\n').splitlines(keepends=True)}


def parse_percent(src):
    """جداکردن سلول‌ها از قالب jupytext percent"""
    cells, buf, mode = [], [], None

    def flush():
        nonlocal buf, mode
        if mode and buf:
            text = '\n'.join(buf).strip('\n')
            if mode == 'markdown':
                md = '\n'.join(re.sub(r'^# ?', '', ln) for ln in text.splitlines()).strip()
                if md:
                    cells.append(md_cell(md))
            elif text.strip():
                cells.append(code_cell(text.replace('plt.close()', 'plt.show()\nplt.close()')))
        buf, mode = [], None

    for line in src.splitlines():
        if line.startswith('# %%'):
            flush()
            mode = 'markdown' if '[markdown]' in line else 'code'
            continue
        if mode:
            buf.append(line)
    flush()
    return cells


# --- بخش‌های ۱ تا ۴: مستقیم از فایل پاسخ‌ها (فقط همین چهار بخش)
answers = io.open(ANSWERS, encoding='utf-8').read()
parts = re.split(r'(?m)^## ', answers)
concept = []
for p in parts[1:]:
    title = p.splitlines()[0]
    if re.match(r'بخش [۱-۴] ', title):
        concept.append(md_cell('## ' + p.split('\n## بخش')[0].strip('\n')))

cells = []
cells.append(md_cell(
    '# تکلیف ۲-۱ — از انتخاب مدل تا تصویر، متن، صوت و یادگیری تقویتی\n'
    '\n'
    '**نوت‌بوک کامل هر ده بخش** (۵۹ زیرسؤال، ۱۰۰ نمره). بخش‌های ۱ تا ۴ مفهومی‌اند و پاسخ‌شان\n'
    'به‌صورت متن نوشته شده؛ بخش‌های ۵ تا ۱۰ کد اجراشدنی‌اند.\n'
    '\n'
    '| بخش | موضوع | نمره | نوع |\n'
    '|---|---|---|---|\n'
    '| ۱ | نوع یادگیری | ۱۰ | مفهومی (متن) |\n'
    '| ۲ | تشخیص تسک | ۱۰ | مفهومی (متن) |\n'
    '| ۳ | انتخاب مدل | ۱۰ | مفهومی (متن) |\n'
    '| ۴ | خروجی تسک‌های بینایی | ۵ | مفهومی (متن) |\n'
    '| ۵ | طبقه‌بندی دادهٔ بانکی | ۱۴ | کد |\n'
    '| ۶ | رگرسیون تقاضای دوچرخه | ۱۰ | کد |\n'
    '| ۷ | Fashion-MNIST | ۱۴ | کد (PyTorch) |\n'
    '| ۸ | اسپم پیامک | ۱۰ | کد |\n'
    '| ۹ | ارقام گفتاری | ۱۰ | کد |\n'
    '| ۱۰ | Q-learning | ۷ | کد |\n'
    '\n'
    '**پیش‌نیاز:** `numpy`، `pandas`، `scikit-learn`، `matplotlib`، `torch`، `scipy`.\n'
    '\n'
    '**اجرا:** سلول‌ها را از بالا به پایین اجرا کن. مسیر داده‌ها نسبی است\n'
    '(`../Day2_Datasets/...`)، پس نوتب‌بوک را از پوشهٔ `code/` باز کن — سلول بعد همین را\n'
    'به‌طور خودکار بررسی و اصلاح می‌کند.\n'
    '\n'
    '**زمان اجرای کل:** حدود ۱۵ دقیقه روی CPU (بیشترش برای آموزش CNN بخش ۷ است).\n'
    '\n'
    '**نکتهٔ محیطی:** اگر در محیط محدود (ساندباکس) اجرا می‌کنی، `OMP_NUM_THREADS=1` را ست کن؛\n'
    'وگرنه مدل بوستینگ بخش ۵ هنگام ساخت thread pool با خطای دسترسی روی named pipe متوقف می‌شود.\n'
    '\n'
    '> عددها با بذر ثابت (`SEED` / `RANDOM_STATE = 42`) تولید شده‌اند و تکرارپذیرند.\n'
    '> نمودارها هم ذخیره می‌شوند (`out/*.png`) و هم داخل نوتب‌بوک نمایش داده می‌شوند.'))

cells.append(code_cell(
    '%matplotlib inline\n'
    'import os\n'
    'from pathlib import Path\n'
    '\n'
    '# اگر نوتب‌بوک از ریشهٔ پوشهٔ تکلیف اجرا شود، به code/ منتقل می‌شویم\n'
    "if not Path('../Day2_Datasets').exists() and Path('code/../Day2_Datasets').exists():\n"
    "    os.chdir('code')\n"
    "print('cwd:', Path.cwd())\n"
    "assert Path('../Day2_Datasets').exists(), 'نوتب‌بوک را از پوشهٔ code/ اجرا کنید'"))

cells.extend(concept)

def normalize_headings(cells):
    """عنوان بخش‌ها را هم‌سطح می‌کند: '# بخش' → '## بخش'"""
    out = []
    for c in cells:
        if c['cell_type'] == 'markdown':
            text = ''.join(c['source'])
            first = text.splitlines()[0] if text else ''
            if first.startswith('# ') and ('بخش' in first or 'نمودار' in first):
                c = md_cell('#' + text)
        out.append(c)
    return out


for script in SCRIPTS:
    src = io.open(script, encoding='utf-8').read()
    cells.append(md_cell('---'))
    cells.extend(normalize_headings(parse_percent(src)))

nb = {
    'cells': cells,
    'metadata': {
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python', 'version': '3.12'},
    },
    'nbformat': 4,
    'nbformat_minor': 5,
}
with io.open(OUT, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

n_md = sum(1 for c in cells if c['cell_type'] == 'markdown')
print(f'{OUT}: {len(cells)} cells ({n_md} markdown, {len(cells) - n_md} code), '
      f'{os.path.getsize(OUT) / 1024:.0f} KB')
