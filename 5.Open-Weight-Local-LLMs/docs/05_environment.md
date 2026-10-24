# محیط اجرا

## مشخصات میزبان (بررسی‌شده)

| مورد           | مقدار                                                                     |
| -------------- | ------------------------------------------------------------------------- |
| سیستم عامل     | Windows 11                                                                |
| پایتون         | `C:\Python312\python.exe` = **3.12.6**                                    |
| پایتون جایگزین | `C:\Users\pc\AppData\Local\Programs\Python\Python310\python.exe` = 3.10   |
| محیط مجازی     | `5.Open-Weight-Local-LLMs/.venv5` (Python 3.12، `--system-site-packages`) |
| shell پیش‌فرض  | `cmd.exe`                                                                 |

> `START_HERE.md` پایتون ۳٫۱۳ را توصیه کرده است. روی این ماشین ۳٫۱۳ نصب نیست؛ ۳٫۱۲ سازگار است. این تفاوت در `provenance.json` ثبت می‌شود (`python_version`).

## محیط موجود — نیازی به ساخت یا نصب نیست

**هیچ پکیجی لوکال نصب نشد.** `.venv5` با `--system-site-packages` ساخته شده و پکیج‌ها را از نصب سطح‌کاربر می‌خواند:

```
C:\Users\pc\AppData\Roaming\Python\Python312\site-packages
```

نسخه‌های نصب‌شده و آماده:

| پکیج       | نسخه   |
| ---------- | ------ |
| numpy      | 2.5.4  |
| pandas     | 3.0.6  |
| matplotlib | 3.11.2 |
| requests   | 2.34.2 |
| sqlite3    | stdlib |

### چرا `requirements-day5.txt` نصب نمی‌شود

فایل رسمی نسخه‌های آینده‌دار دارد که روی PyPI موجود نیستند:

```
numpy==2.4.2      ← موجود نیست
pandas==3.0.0     ← موجود نیست
torch==2.13.0     ← موجود نیست
matplotlib==3.10.8
requests==2.34.2  ← موجود
nbformat==5.10.4
nbclient==0.10.2
ipykernel==6.30.1
```

تلاش برای نصبشان فقط وقت تلف می‌کند. نسخه‌های موجود سازگار و کافی‌اند.

**دربارهٔ `torch`:** لازم نیست. تنها جایی که «شبکهٔ عصبی» آموزش می‌بیند بخش ۱۱ است و آن یک لایهٔ خطی ۱۶×۸ با **numpy** و Adam دستی است (طبق متن: «adapter واقعاً روی یک لایهٔ خطی ۱۶×۸ آموزش می‌بیند»). نصب `torch` فقط ۲+ گیگابایت اضافه می‌کند.

### وضعیت `.venv` قدیمی

پوشهٔ `.venv` وجود دارد اما ناقص و قفل‌شده است (نصب pip در آن هرگز تمام نشد). **از آن استفاده نکن.** برای حذفش اول همهٔ ترمینال‌ها را ببند.

### نکتهٔ الزامی هنگام اجرا

```bat
set PYTHONIOENCODING=utf-8 && chcp 65001 >nul
```

بدون این، چاپ فارسی روی `cp1256` کرش می‌کند.

### کرنل نوتبوک (اختیاری)

```bat
.venv5\Scripts\python.exe -m ipykernel install --user --name bootcamp-day5 --display-name "Day5"
```

## منابع مدل و موتور — از قبل دانلود شده

| قلم                                 | اندازه           | SHA-256                                                            |
| ----------------------------------- | ---------------- | ------------------------------------------------------------------ |
| `qwen2.5-0.5b-instruct-q4_k_m.gguf` | ۴۹۱٬۴۰۰٬۰۳۲ بایت | `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db` |
| `qwen2.5-0.5b-instruct-q8_0.gguf`   | ۶۷۵٬۷۱۰٬۸۱۶ بایت | `ca59ca7f13d0e15a8cfa77bd17e65d24f6844b554a7b6c12e07a5f89ff76844e` |
| `llama-b11696-bin-win-cpu-x64.zip`  | ۱۹٬۵۷۵٬۶۹۰ بایت  | `1e7c47dff58467540d53e6cf302d83951bcb165afb252c2952ed3872190fc60d` |

revision ثابت مدل: `9217f5db79a29953eb74d5343926648285ec7e67`
release موتور: `b11696`
نسخهٔ نصب‌شده: `0.7.0-dev (build 11696, commit ceefd16da)`

دوباره دانلود نکن — `download_resources.py` چون فایل‌ها موجودند و hash درست است، کاری نمی‌کند.

خروجی در `assignment/source/Day5/Day5_Resources/`:

- `models/*.gguf`
- `llama_cpp/llama-server.exe`
- `resource_manifest.json`

**مسیر موتور روی ویندوز:** `assignment/source/Day5/Day5_Resources/llama_cpp/llama-server.exe`
برای Linux/macOS باید `LLAMA_SERVER_PATH` به یک `llama-server` بومی سازگار تنظیم شود.

## اجرای سرور (بخش ۸ به بعد)

```bat
assignment\source\Day5\Day5_Resources\llama_cpp\llama-server.exe ^
  --model assignment\source\Day5\Day5_Resources\models\qwen2.5-0.5b-instruct-q4_k_m.gguf ^
  --host 127.0.0.1 --port 8080 --ctx-size 2048 --threads 4 --parallel 1
```

بررسی سلامت:

```bat
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/v1/models
```

> الزام تکلیف: `--host 127.0.0.1` (loopback)، `--ctx-size 2048`، `--threads 4`، `--parallel 1`. این‌ها همان مقادیری هستند که checker در `runtime_config.json` می‌خواهد. در هر سلول نوتبوک سرور باید با context manager بسته شود.

## حافظهٔ لازم

- دو GGUF روی هم ≈ ۱٫۱۷ GB روی دیسک.
- RAM آزاد توصیه‌شده: ≈ ۲ GB به‌علاوهٔ محیط پایتون و داده‌ها.

## بازرسی محیط

```bat
set PYTHONIOENCODING=utf-8 && chcp 65001 >nul && .venv5\Scripts\python.exe work\check_env.py
```

## اجرای checker نهایی

```bat
.venv5\Scripts\python.exe assignment\source\Day5\Day5_Grading\check_submission.py ^
  --submission Day5_Run_Output ^
  --datasets assignment\source\Day5\Day5_Datasets ^
  --output check.json
```

> `START_HERE.md` مسیر `--datasets Day5_Datasets` را فرض کرده که یعنی اجرا از داخل `assignment/source/Day5`. اگر از ریشهٔ پوشهٔ تکلیف اجرا می‌کنید، مسیر کامل را بدهید (همان بالا).
