# محیط اجرا

## چه چیزی لازم است

| قلم | مقدار |
|---|---|
| پایتون | ۳٫۱۲٫۶ روی این دستگاه (بسته با ۳٫۱۳ آزموده شده؛ CPU کافی است) |
| دیتابیس | SQLite 3.45.3 — کتابخانهٔ استاندارد `sqlite3`؛ Docker و PostgreSQL لازم نیست |
| مدل | `sentence-transformers/all-MiniLM-L6-v2`، نسخهٔ `1110a243…`، ۳۸۴ بعد، سقف ۲۵۶ توکن، Apache-2.0 |
| اینترنت | فقط برای نصب بسته‌ها و یک‌بار دانلود مدل؛ بعد از آن آفلاین |

## برپاسازی

```powershell
cd "C:\Users\pc\source\repos\AI\BootCamp Assignments\3.from-API-to-Doc-Answer-with-PostgerSQL-va-LangGraph"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\provision.ps1
```

اسکریپت این کارها را انجام می‌دهد:

1. ساخت venv در **ریشهٔ workspace** با نام `.venv-day3` (مسیر کوتاه) و لینک آن به‌صورت junction داخل پروژه با نام `.venv`.
2. نصب pip داخل venv (بدون pip همراه، چون ensurepip در این محیط شکست می‌خورد).
3. نصب نسخه‌های قفل‌شدهٔ `requirements.txt` (فقط wheel).
4. نصب `jupyterlab` و `huggingface_hub`.
5. دانلود مدل embedding و بررسی SHA-256 همهٔ فایل‌هایش با manifest.

اجرای دوباره بی‌خطر است: venv موجود دوباره استفاده می‌شود.

**چرا venv بیرون از پوشهٔ پروژه است؟** این ویندوز مسیرهای بلند (>۲۶۰ نویسه) را پشتیبانی نمی‌کند و `torch` فایل‌های مجوز را در درختی با عمق ~۱۴۰ نویسه نصب می‌کند. با venv داخل این پوشه، نصب با `WinError 206` می‌شکند. مسیر کوتاه `.venv-day3` این را حل می‌کند و junction باعث می‌شود همهٔ دستورهای مستند همچنان با `.\.venv\Scripts\python.exe` کار کنند.

## بررسی

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\check_env.py --encode
```

خروجی: نسخهٔ پایتون، نسخهٔ SQLite، وضعیت هر کتابخانه، تطبیق فایل‌های مدل با manifest، و یک آزمون encode واقعی (بعد، norm، ابعاد). گزارش در `artifacts/env_report.json`.

## وضعیت اندازه‌گیری‌شده روی این دستگاه

خروجی `python scripts\check_env.py --encode` (گزارش کامل: `artifacts/env_report.json`):

| قلم | مقدار |
|---|---|
| پایتون | 3.12.6 در venv |
| SQLite | 3.45.3 |
| torch | 2.13.0+cpu |
| بقیهٔ بسته‌ها | همه در نسخهٔ قفل‌شده، بدون MISSING |
| فایل‌های مدل | ۱۱ از ۱۱ با hash مطابق manifest |
| بارگذاری مدل | ۰٫۱۹ ثانیه |
| encode یک جمله | ۱۶٫۲ میلی‌ثانیه |
| بعد خروجی | ۳۸۴ |
| norm بعد از normalize | ۱٫۰ |
| سقف توکن مدل | ۲۵۶ (tokenizer و `max_seq_length` یکی) |

## نسخه‌های قفل‌شده

| بسته | نسخهٔ قفل‌شده |
|---|---|
| numpy | 2.4.2 |
| pandas | 3.0.0 |
| scipy | 1.17.0 |
| scikit-learn | 1.8.0 |
| torch | 2.13.0 (CPU) |
| matplotlib | 3.10.8 |
| sentence-transformers | 6.1.0 |
| transformers | 5.19.0 |
| fastapi | 0.143.1 |
| httpx | 0.28.1 |
| uvicorn | 0.54.0 |
| langgraph | 1.2.15 |
| pydantic | 2.14.1 |
| PyJWT | 2.10.1 |
| pypdf | 6.15.0 |
| nbformat | 5.10.4 |
| nbclient | 0.10.2 |
| ipykernel | 6.30.1 |

## مدل embedding

```python
from huggingface_hub import snapshot_download
path = snapshot_download("sentence-transformers/all-MiniLM-L6-v2",
                         revision="1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
                         local_dir="resources/embedding_model")
```

معادل اسکریپتی: `python scripts\download_model.py`. این فایل فایل‌ها را با `resources/embedding_model_manifest.json` تطبیق می‌دهد و در صورت ناسازگاری خطا می‌دهد.

نکتهٔ مهم: مدل **انگلیسی** است و corpus و پرسش‌ها هم انگلیسی‌اند. کیفیت فارسی در این تمرین سنجیده نمی‌شود؛ تحلیل‌ها فارسی نوشته می‌شوند.

## دیتابیس

```powershell
python grading\check_day3_db.py day3.sqlite
```

| کد خروج | وضعیت |
|---|---|
| 0 | `passed` |
| 1 | `failed` |
| 2 | `error` (فایل خوانا نیست) |

## تلهٔ این محیط: sandbox فایل

در محیط DSH با سیاست `workspace-write`، پوشه‌ای که `tempfile.mkdtemp()` می‌سازد برای همان فرایند قابل نوشتن نیست. نتیجه: `python -m venv`، `pip` و `huggingface_hub` با `PermissionError: [Errno 13]` می‌شکنند.

سه شیم کوچک این را حل می‌کند (روی ماشین عادی بی‌اثرند):

| فایل | کار |
|---|---|
| `scripts/sandbox_compat.py` | `tempfile.mkdtemp` را با نسخهٔ `os.makedirs` جایگزین می‌کند |
| `scripts/sandbox_pip.py` | pip را با همان شیم اجرا می‌کند |
| `scripts/sandbox_run.py` | هر اسکریپت دلخواه را با همان شیم اجرا می‌کند |

نکته: `TMP`/`TEMP` هم باید به مسیری داخل workspace اشاره کند (`..\.tmp-day3\pip`، بیرون از پوشهٔ پروژه)، وگرنه نوشتن در پوشهٔ موقت سیستم رد می‌شود.

عارضهٔ جانبی: پوشه‌هایی که این شیم در پوشهٔ موقت می‌سازد، ACL خود را از دست می‌دهند و بعداً قابل حذف نیستند. به همین دلیل پوشهٔ موقت بیرون از پروژه نگه داشته می‌شود و یک پوشهٔ خالی `artifacts\tmpcc3976y1` (بازماندهٔ تشخیص اولیه) ممکن است باقی بماند؛ بی‌خطر و در `.gitignore` است.

## اگر شکست خورد

| نشانه | علت محتمل | کار |
|---|---|---|
| `WinError 206` هنگام نصب torch | مسیر بلند (MAX_PATH) | venv را در مسیر کوتاه بساز؛ `.venv-day3` در ریشهٔ workspace همین کار را می‌کند |
| `No module named pip` در venv | نصب pip انجام نشده | `python scripts\sandbox_pip.py install --target <venv>\Lib\site-packages pip` |
| `PermissionError: [Errno 13]` در pip | `TMP` بیرون از پروژه | `$env:TMP` و `$env:TEMP` را به `artifacts\pip-tmp` بده |
| resolver دقیقه‌ها ۱۰۰٪ CPU | backtracking روی sdist | `--only-binary :all:` و نصب گروهی؛ `langgraph` را جدا نصب کن |
| مدل بارگذاری نمی‌شود | دانلود ناقص | `python scripts\download_model.py` و تطبیق hash |
| `embedding_dimensions` در بررسی‌گر | chunkها بردار ندارند | بخش ۸ را کامل کن و UPSERT بزن |
