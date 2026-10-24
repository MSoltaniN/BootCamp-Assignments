# فایل انتقال — تکلیف ۵ (Open-Weight Local LLMs)

> **برای ایجنت بعدی**: این سند تنها منبع حقیقت است. اگر چیزی در جای دیگری متناقض بود، این سند مقدم است.
> آخرین به‌روزرسانی: پایان آماده‌سازی + بخش‌های ۱ تا ۵.

---

## ۱. یک پاراگراف خلاصه

تکلیف ۵ از بوتکمپ ایجنت‌های هوش مصنوعی (iCourse / شکرزاد) — ۱۲ بخش، ۱۴۴ زیرسؤال، ۱۰۰ نمره. موضوع: مجوز و منشأ مدل، ظرفیت و هزینه، کوانتیزه‌سازی و GGUF، اجرای واقعی دو quant از `Qwen2.5-0.5B-Instruct` روی llama-server محلی، ارزیابی فارسی/انگلیسی، شبیه‌سازی صف و KV cache، آموزش adapter کم‌رتبه روی یک لایهٔ ۱۶×۸، و گردش کار امن HR با SQLite. تحویل: نوتبوک اجراشده + ZIP شواهد + پاسخ‌های فرم سایت.

---

## ۲. محیط — این را دقیقاً رعایت کن

| مورد         | مقدار                                                                       |
| ------------ | --------------------------------------------------------------------------- |
| ریشهٔ کار    | `c:\Users\pc\source\repos\AI\BootCamp Assignments\5.Open-Weight-Local-LLMs` |
| مفسر پایتون  | `.venv5\Scripts\python.exe`                                                 |
| نسخهٔ پایتون | 3.12.6                                                                      |
| نوع venv     | `--system-site-packages` (بدون نصب محلی)                                    |
| منبع پکیج‌ها | `C:\Users\pc\AppData\Roaming\Python\Python312\site-packages`                |

### ⚠️ نکتهٔ حیاتی دربارهٔ پکیج‌ها

**هیچ پکیجی لوکال نصب نشد و لازم هم نیست.** نسخه‌های موجود از قبل روی سیستم نصب بودند:

```
numpy 2.5.4 | pandas 3.0.6 | matplotlib 3.11.2 | requests 2.34.2 | sqlite3 (stdlib)
```

`requirements-day5.txt` نسخه‌های آینده‌دار دارد (`numpy==2.4.2`, `pandas==3.0.0`, `torch==2.13.0`) که روی PyPI موجود نیستند — **سعی نکن نصبشان کنی**، فقط وقت تلف می‌شود.

`torch` هم لازم نیست: بخش ۱۱ یک لایهٔ خطی ۱۶×۸ است که با numpy و Adam دستی آموزش می‌بیند.

### ⚠️ وضعیت `.venv` (قدیمی)

پوشهٔ `.venv` وجود دارد اما **ناقص/قفل‌شده** است (pip install در آن هرگز تمام نشد). از آن استفاده نکن. اگر خواستی پاکش کنی، اول همهٔ ترمینال‌های باز را ببند چون فایل‌هایش قفل هستند.

### ✅ `.gitignore` آماده است

[`.gitignore`](.gitignore) جلوی ورود ۲٬۲۹۲ MB را به git می‌گیرد. تأییدشده با `git check-ignore`:

| نادیده‌گرفته می‌شود                            | دلیل                                          |
| ---------------------------------------------- | --------------------------------------------- |
| `Day5_Resources/models/*.gguf` (۱٬۱۶۷ MB)      | `download_resources.py` با SHA-256 بازمی‌سازد |
| `Day5_Resources/llama_cpp/` (۱٬۱۲۵ MB)         | از zip بسته استخراج می‌شود                    |
| `Day5_Resources/llama-b*.zip`                  | آرشیو موتور                                   |
| `.venv/`، `.venv5/`                            | محیط‌های پایتون                               |
| `datasets/*.zip`                               | همان محتوای `assignment/source/Day5`          |
| `__pycache__/`، `*.pyc`، `.ipynb_checkpoints/` | زائد                                          |

| ردیابی می‌شود                                         | شامل                                                                |
| ----------------------------------------------------- | ------------------------------------------------------------------- |
| `assignment/source/Day5/` (جز `Day5_Resources` سنگین) | `ASSIGNMENT.md`، `Day5_Datasets/`، `Day5_Grading/`، `Day5_Starter/` |
| `Day5_Resources/resource_manifest.json`               | بخش ۵ آن را می‌خواند (revision و hash)                              |
| `Day5_Run_Output/`                                    | همهٔ آرتیفکت‌های تحویلی                                             |
| `sections/*/answers.md`، `README.md`، `src/`، `out/`  | پاسخ‌ها و کد و نمودارها                                             |
| `docs/`، `lib/`، `work/`                              | اسناد و کتابخانه و ابزار                                            |

> **اگر `Day5_Resources` را پاک کردی**، فقط `download_resources.py` را دوباره اجرا کن — همه‌چیز با همان hash برمی‌گردد.

### الگوی اجرای همهٔ اسکریپت‌ها

```bat
cd "c:\Users\pc\source\repos\AI\BootCamp Assignments\5.Open-Weight-Local-LLMs"
set PYTHONIOENCODING=utf-8 && chcp 65001 >nul && .venv5\Scripts\python.exe sections\sectionNN_x\src\sNN_x.py
```

`set PYTHONIOENCODING=utf-8` **الزامی** است؛ بدون آن، چاپ فارسی روی `cp1256` کرش می‌کند.

---

## ۳. منابع آماده (تأییدشده با hash)

| قلم    | مسیر                                                                             | اندازه           | SHA-256             |
| ------ | -------------------------------------------------------------------------------- | ---------------- | ------------------- |
| Q4_K_M | `assignment/source/Day5/Day5_Resources/models/qwen2.5-0.5b-instruct-q4_k_m.gguf` | ۴۹۱٬۴۰۰٬۰۳۲      | `74a4da8c...d7a9db` |
| Q8_0   | `assignment/source/Day5/Day5_Resources/models/qwen2.5-0.5b-instruct-q8_0.gguf`   | ۶۷۵٬۷۱۰٬۸۱۶      | `ca59ca7f...76844e` |
| موتور  | `assignment/source/Day5/Day5_Resources/llama_cpp/llama-server.exe`               | ۱۹٬۵۷۵٬۶۹۰ (zip) | `1e7c47df...0fc60d` |

نسخهٔ موتور: `0.7.0-dev (build 11696, commit ceefd16da)`
revision مدل: `9217f5db79a29953eb74d5343926648285ec7e67`

**دوباره دانلود نکن** — `download_resources.py` چون فایل‌ها موجودند و hash درست است، کاری نمی‌کند.

---

## ۴. ساختار پوشه‌ها

```
5.Open-Weight-Local-LLMs/
├── assignment/source/Day5/          ← بستهٔ دانشجو (دست نزن)
│   ├── ASSIGNMENT.md                 متن رسمی ۱۴۴ سؤال
│   ├── START_HERE.md
│   ├── Day5_Datasets/                همهٔ fixtureها
│   ├── Day5_Grading/check_submission.py   ← داور نهایی
│   ├── Day5_Starter/download_resources.py
│   └── Day5_Resources/               مدل‌ها + موتور (دانلود شده)
├── datasets/day5-student-pack.zip    آرشیو اصلی
├── docs/                              اسناد کاری (این‌ها را بخوان)
│   ├── 00_roadmap.md                 نقشهٔ راه + مرز شواهد
│   ├── 01_assignment_brief.md        خلاصه + جدول نمره
│   ├── 02_data_map.md                ★★ حیاتی: قراردادهای دقیق checker
│   ├── 03_question_checklist.md      جدول ۱۴۴ زیرسؤال
│   ├── 05_environment.md
│   └── 06_rules_and_risks.md         ★ قواعد سخت + ۶ ریسک
├── lib/
│   ├── day5.py                       مسیرها، hash، GiB/GB، KV، quantile، engine_path()
│   └── gguf.py                       پارسر فقط‌خواندنی GGUF
├── sections/sectionNN_.../           ← یک پوشه به‌ازای هر بخش
│   ├── README.md                     متن رسمی بخش + چک‌لیست گزینه‌ها
│   ├── answers.md                    ★ پاسخ‌ها اینجا
│   ├── src/                          کد
│   └── out/                          نمودار و لاگ (آرتیفکت نهایی → Day5_Run_Output)
├── Day5_Run_Output/                  ★★ آرتیفکت‌های تحویلی، همه در ریشه (بدون زیرپوشه)
├── work/                             اسکریپت‌های ابزار
│   ├── parse_mhtml.py                استخراج تکلیف از MHTML
│   ├── scaffold.py                   ساخت پوشه‌ها و چک‌لیست
│   ├── inspect_data.py               بازرسی ساختار داده‌ها
│   └── check_env.py                  بررسی محیط
└── .venv5/                           محیط کاری (از این استفاده کن)
```

---

## ۵. وضعیت پیشرفت

| بخش               | نمره | وضعیت                                  | خروجی                               |
| ----------------- | ---- | -------------------------------------- | ----------------------------------- |
| ۱ مجوز و منشأ     | ۶    | ✅ **کامل** — ۱۲ پاسخ با دلیل          | `sections/section01_.../answers.md` |
| ۲ معماری و حافظه  | ۶    | ✅ **کامل** — ۱۲ پاسخ با دلیل          | `sections/section02_.../answers.md` |
| ۳ موتور و زیرساخت | ۶    | ✅ **کامل** — ۱۲ پاسخ با دلیل          | `sections/section03_.../answers.md` |
| ۴ ارزیابی و امنیت | ۶    | ✅ **کامل** — ۱۲ پاسخ با دلیل          | `sections/section04_.../answers.md` |
| ۵ ممیزی کاتالوگ   | ۸    | ✅ **کد اجرا شد** — پاسخ‌ها نوشته نشده | ۵ آرتیفکت در `Day5_Run_Output/`     |
| ۶ ظرفیت و هزینه   | ۸    | ⬜ شروع نشده                           | —                                   |
| ۷ کوانتیزه‌سازی   | ۱۰   | ⬜ شروع نشده (پارسر GGUF آماده)        | —                                   |
| ۸ توکنایزر و مدل  | ۱۰   | ⬜ شروع نشده (سرور آماده)              | —                                   |
| ۹ ارزیابی Q4/Q8   | ۱۰   | ⬜ شروع نشده                           | —                                   |
| ۱۰ صف و KV        | ۱۰   | ⬜ شروع نشده                           | —                                   |
| ۱۱ adapter        | ۱۰   | ⬜ شروع نشده                           | —                                   |
| ۱۲ گردش کار HR    | ۱۰   | ⬜ شروع نشده                           | —                                   |

**۲۴ نمره مفهومی تمام شد. ۷۶ نمره عملی باقی است.**

### خروجی‌های واقعی بخش ۵ (برای استفاده در پاسخ‌ها)

```
5.1  raw_rows=13, unique_models=12, full_duplicate=1 (M03)
5.2  clean_rows=12, ids_unique=True
5.3  allow=8, review=3, deny=1   (M05=deny، M07=review، M09=deny، M10=review)
5.4  names_with_A=3 (M04,M05,M10), M04 active/total=0.1
5.5  candidates=[M01,M03,M04,M06], count=4
5.6  accepted=[safe_model.safetensors], hash_failures=[untrusted_model.bin]
5.7  model_revision=9217f5db..., engine=b11696  (⚠️ gguf_matches=0/2 چون قبل از دانلود اجرا شد)
5.8  files=18, total_bytes=233218, all_match=True
5.9  min_ratio=0.041667, min_id=M05
5.10 card_keys=14, evaluation_required=True
5.11 stage2_criteria=5
5.12 all_catalog_models_executed=False
```

> ⚠️ **کار فوری**: بخش ۵ را دوباره اجرا کن تا `5.7_gguf_matches` از `0/2` به `2/2` برود (الان مدل‌ها موجودند).

---

## ۶. مرز شواهد — مهم‌ترین قاعدهٔ کل تکلیف

این را در هر پاسخ تکرار کن. checker و مدرس روی آن حساس هستند.

| وضعیت                  | چه چیزی                                                                                 |
| ---------------------- | --------------------------------------------------------------------------------------- |
| ✅ **واقعاً اجرا شده** | دو quant از `Qwen2.5-0.5B-Instruct`؛ HTTP محلی روی loopback؛ adapter خطی روی لایهٔ ۱۶×۸ |
| 🟡 **شبیه‌سازی**       | صف سرویس، static/continuous batching، KV بلوکی، cache ایزوله (بخش ۱۰)                   |
| ❌ **اجرا نشده**       | fine-tune کامل LLM، QLoRA، vLLM، SGLang، MoE بزرگ                                       |

پس این فیلدها **همیشه** `False` یا `null`:

```
9.12  MoE واقعاً اجرا شد؟          → خیر
9.12  vLLM واقعاً اجرا شد؟         → خیر
10.12 vLLM یا SGLang واقعی اجرا شد؟ → خیر
11.11 QLoRA اجرا شده؟              → خیر
11.12 LLM کامل fine-tune شد؟        → خیر
12.7  ادعای مصونیت مدل داریم؟      → خیر
12.12 تصمیم خودکار HR مجاز است؟    → خیر
```

---

## ۷. قراردادهای سخت checker

`check_submission.py` این‌ها را دقیق بررسی می‌کند. جزئیات کامل در [`docs/02_data_map.md`](docs/02_data_map.md).

### `selection.json`

```json
{
  "selection_split": "dev",
  "test_used_for_selection": false,
  "model_revision": "9217f5db79a29953eb74d5343926648285ec7e67",
  "selected_quant": "q4_k_m",
  "hashes": {
    "qwen2.5-0.5b-instruct-q4_k_m.gguf": "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db",
    "qwen2.5-0.5b-instruct-q8_0.gguf": "ca59ca7f13d0e15a8cfa77bd17e65d24f6844b554a7b6c12e07a5f89ff76844e"
  }
}
```

### `runtime_config.json`

```json
{ "engine": "llama.cpp", "context": 2048, "threads": 4, "network": "loopback" }
```

### `quantization_selection.json`

```json
{
  "bits": 4,
  "group_size": 16,
  "percentile": 100,
  "selection_split": "dev",
  "toy_not_gguf": true
}
```

و کوانتیزه باید **دقیقاً** این الگوریتم باشد تا `quant_test_predictions.npy` تطبیق کند:

```python
blocks = weights.reshape(96, 3, 16)
bounds = np.percentile(np.abs(blocks), percentile, axis=2, keepdims=True)
scales = np.where(bounds > 0, bounds / 7, 1).astype("float32")
reconstructed = (np.clip(np.rint(blocks/scales), -7, 7) * scales).reshape(96, 48)
quant_test_predictions = test @ reconstructed.T   # shape (96, 96)
```

### `selected_adapter.npz`

- کلیدهای `a` با شکل `(16, rank)`، `b` با شکل `(rank, 8)`، `scale` اسکالر
- `scale == 2/rank`
- `allow_pickle=False`

### `adapter_selection.json`

```json
{ "rank": 2, "base_frozen": true, "selection_split": "dev" }
```

### `local_agent.sqlite` — جدول `runs`

```sql
CREATE TABLE runs (
  run_id    TEXT    NOT NULL UNIQUE,
  quant     TEXT    NOT NULL,
  days      INTEGER NOT NULL CHECK (typeof(days)='integer' AND days BETWEEN 0 AND 366),
  policy_id TEXT    NOT NULL,
  approved  INTEGER NOT NULL CHECK (approved = 0)
);
```

قیود باید این‌ها را رد کنند: `run_id` خالی/فاصله/`NULL`، `days=-1`، `days=367`، `approved=1`.
**بدون trigger.**
ردیف نهایی: `days=22`, `policy_id='P-LEAVE'`, `approved=0`.

### `agent_trace.json`

آرایهٔ **دقیقاً ۳ گام** با `step=[1,2,3]`، `trace[0].kind="model_plan"`، `trace[-1].kind="model_extract"`.

### `handoff_manifest.json`

`files` باید مجموعهٔ **دقیقاً این ۱۱ نام** باشد (بدون خودش) با SHA-256 درست:

```
selection.json, runtime_config.json, test_predictions.jsonl, selected_adapter.npz,
adapter_selection.json, adapter_test_predictions.npy, quantization_selection.json,
quant_test_predictions.npy, local_agent.sqlite, agent_trace.json, security_tests.json
```

هر فایل باید مستقیماً در ریشهٔ `Day5_Run_Output/` باشد، symlink نباشد، ≤ ۲۰ MiB.

---

## ۸. الگوریتم‌های ریاضی (بازرسی‌شده با داده‌ها)

### ظرفیت (بخش ۶)

```python
GB  = 10**9
GiB = 2**30

weight_bytes = total_b * 1e9 * weight_bits / 8      # از total_b، نه active_b!
kv_bytes     = 2 * layers * kv_heads * head_dim * 2 * (prompt + max_new) * concurrency
overhead     = 0.12 * weight_bytes                   # در ۶.۱۱ می‌شود 0.20
fits         = total_gib <= capacity_gib - reserved_gib
```

داده‌های کلیدی:
| id | total_b | active_b | layers | kv_heads | head_dim |
|---|---|---|---|---|---|
| M04 | 30.0 | 3.0 | 64 | 8 | 128 |
| M07 | 70.0 | 70.0 | 64 | 8 | 128 |
| M03 | 8.0 | 8.0 | 32 | 8 | 128 |

| hw  | capacity_gib | reserved_gib | bandwidth_gbs | capex_usd |
| --- | ------------ | ------------ | ------------- | --------- |
| H04 | 128          | 24           | 215           | 3000      |
| H07 | 32           | 3            | 1400          | 3500      |

### هزینه (بخش ۶.۹)

```
capex=3000, amortization=36 ماه → 83.33/ماه
power: 140W × 160h = 22.4 kWh × 0.15 = 3.36/ماه
ops = 35/ماه
fixed_monthly = 83.33 + 3.36 + 35 = 121.69

api_per_request = (800×1.0 + 200×3.0)/1e6 = 0.0014
breakeven = ceil(121.69 / 0.0014) = 86922
capacity_monthly = 300 × 160 = 48000   → breakeven خارج از ظرفیت!
```

### آماره‌ها (بخش ۹)

```python
def quantile_linear(xs, q):     # معادل np.quantile پیش‌فرض
    xs = sorted(xs); pos = (len(xs)-1)*q
    lo, hi = floor(pos), ceil(pos)
    return xs[lo] if lo == hi else xs[lo] + (xs[hi]-xs[lo])*(pos-lo)
```

---

## ۹. کارهای باقی‌مانده به ترتیب

| #   | کار                                                    | نمره | وابسته به     |
| --- | ------------------------------------------------------ | ---- | ------------- |
| 1   | اجرای مجدد بخش ۵ (رفع `5.7`)                           | —    | —             |
| 2   | نوشتن `answers.md` بخش ۵ از خروجی واقعی                | ۸    | ۱             |
| 3   | بخش ۶: کد ظرفیت/هزینه → `capacity_recommendation.json` | ۸    | بخش ۵         |
| 4   | بخش ۷: کوانتیزه‌سازی + parse دو GGUF                   | ۱۰   | `lib/gguf.py` |
| 5   | بخش ۸: سرور llama-server + tokenizer + schema          | ۱۰   | منابع ✅      |
| 6   | بخش ۹: ارزیابی Q4/Q8 روی dev، سپس test                 | ۱۰   | بخش ۸         |
| 7   | بخش ۱۰: شبیه‌ساز صف                                    | ۱۰   | بخش ۹         |
| 8   | بخش ۱۱: آموزش adapter                                  | ۱۰   | —             |
| 9   | بخش ۱۲: HR + SQLite + امنیت                            | ۱۰   | بخش ۹         |
| 10  | اجرای checker نهایی                                    | —    | همه           |

### ترتیب اجرای checker

```bat
.venv5\Scripts\python.exe assignment\source\Day5\Day5_Grading\check_submission.py ^
  --submission Day5_Run_Output ^
  --datasets assignment\source\Day5\Day5_Datasets ^
  --output check.json
```

### اجرای سرور (بخش ۸ به بعد)

```bat
assignment\source\Day5\Day5_Resources\llama_cpp\llama-server.exe ^
  --model assignment\source\Day5\Day5_Resources\models\qwen2.5-0.5b-instruct-q4_k_m.gguf ^
  --host 127.0.0.1 --port 8080 --ctx-size 2048 --threads 4 --parallel 1
```

الزام تکلیف: سرور در **هر سلول** با context manager بسته شود (`with server(): ...`) تا در خطا هم پروسه نمیرد.

---

## ۱۰. ده ریسک که نمره می‌خورند

| #   | ریسک                                                     | جلوگیری                                                                       |
| --- | -------------------------------------------------------- | ----------------------------------------------------------------------------- |
| ۱   | ادعای اجرای MoE/vLLM/QLoRA                               | همیشه `False` + توضیح مرز                                                     |
| ۲   | نشت `test` در انتخاب                                     | `test_used_for_selection=false` در همه فایل‌های تصمیم                         |
| ۳   | `schema_valid` ناسازگار با `raw`                         | اگر `raw` = `{"days": int}` → `schema_valid=true` و `predicted_days` همان عدد |
| ۴   | `expected_days` یا `correct` در `test_predictions.jsonl` | ممنوع — checker رد می‌کند                                                     |
| ۵   | آرتیفکت در زیرپوشه                                       | همه در ریشهٔ `Day5_Run_Output/`                                               |
| ۶   | `handoff_manifest` شامل خودش                             | ۱۱ نام، بدون `handoff_manifest.json`                                          |
| ۷   | `weight_bytes` از `active_b`                             | همیشه `total_b`                                                               |
| ۸   | استفاده از `pickle`                                      | `np.load(..., allow_pickle=False)` همه‌جا                                     |
| ۹   | `print` فارسی بدون UTF-8                                 | `set PYTHONIOENCODING=utf-8`                                                  |
| ۱۰  | نصب `numpy==2.4.2` / `torch`                             | نصب نکن — موجود و کافی است                                                    |

---

## ۱۱. اسنادی که باید بخوانی (به ترتیب)

1. [`docs/02_data_map.md`](docs/02_data_map.md) — قراردادهای checker با اعداد بازرسی‌شده
2. [`docs/06_rules_and_risks.md`](docs/06_rules_and_risks.md) — قواعد سخت
3. [`docs/00_roadmap.md`](docs/00_roadmap.md) — نقشهٔ راه
4. `assignment/source/Day5/ASSIGNMENT.md` — متن رسمی (مرجع نهایی)
5. `assignment/source/Day5/Day5_Grading/check_submission.py` — داور واقعی، خودش را بخوان

---

## ۱۲. پاسخ به سؤال «آیا انتقال روی کیفیت خروجی اثر می‌گذارد؟»

**خیر — اما به یک شرط.**

انتقال «اینجا» چیزی از دست نمی‌دهد چون:

- ✅ **همهٔ داده‌ها روی دیسک هستند** — هیچ‌چیز در حافظهٔ من نیست که از دست برود
- ✅ **همهٔ کد نوشته‌شده در فایل است** — `lib/`, `sections/*/src/`, `work/`
- ✅ **همهٔ ۲۴ نمره مفهومی نهایی و مکتوب است** در `answers.md`
- ✅ **منابع با hash تأیید شده‌اند** — همان بایت‌ها، همان نتیجه
- ✅ **محاسبات قطعی‌اند** — بخش‌های ۵، ۶، ۷، ۱۰، ۱۱ روی داده‌های ثابت اجرا می‌شوند و نتیجه‌شان بازتولیدپذیر است

**شرط**: ایجنت بعدی باید [`docs/02_data_map.md`](docs/02_data_map.md) و [`docs/06_rules_and_risks.md`](docs/06_rules_and_risks.md) را بخواند. اگر بدون خواندن شروع کند، ریسک شکست در checker بالاست — نه به‌خاطر از دست رفتن اطلاعات، بلکه به‌خاطر **دوباره کشف کردن** قراردادها.

**تنها نقطهٔ واقعاً غیرقطعی**: بخش‌های ۸ و ۹. latency، `finish_reason`، و خروجی مدل به وضعیت CPU و بار سیستم وابسته‌اند. اگر ایجنت بعدی روی همان ماشین اجرا کند، اعداد مشابه درمی‌آید؛ اگر روی ماشین دیگر، اعداد متفاوت ولی **معتبر** خواهند بود. تکلیف هم صریح گفته «زمان وابسته به پیاده‌سازی با مرجع تطبیق سخت ندارد».

**پس**: کیفیت خروجی به‌خاطر انتقال افت نمی‌کند. کیفیت به خواندن این دو سند و رعایت مرز شواهد بستگی دارد.
