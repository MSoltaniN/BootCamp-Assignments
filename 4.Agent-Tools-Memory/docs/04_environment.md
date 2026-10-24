# محیط اجرا

## نیازمندی‌ها

| قلم      | مقدار                                                             |
| -------- | ----------------------------------------------------------------- |
| پایتون   | ۳٫۱۲٫۶ نصب‌شده (تکلیف ۳٫۱۳ پیشنهاد می‌کند؛ نسخهٔ فعلی سازگار است) |
| سیستم    | Windows 11                                                        |
| Shell    | `cmd.exe`                                                         |
| دیتابیس  | SQLite محلی — بدون سرویس شبکه و بدون رمز                          |
| Docker   | لازم نیست                                                         |
| LLM پولی | لازم نیست — fixture قطعی مجاز است                                 |

## وابستگی‌ها

فایل رسمی: `assignment/source/Day4/requirements-day4.txt`

| بسته                          | نسخه   | نقش                           |
| ----------------------------- | ------ | ----------------------------- |
| `numpy`                       | 2.4.2  | محاسبات برداری                |
| `pandas`                      | 3.0.0  | DataFrame و CSV               |
| `matplotlib`                  | 3.10.8 | نمودار (پوشش ۵٫۱۲، تحلیل ۱۱)  |
| `scikit-learn`                | 1.8.0  | TF-IDF، مسیریاب، معیارها      |
| `pydantic`                    | 2.14.1 | schema ابزار و اعتبارسنجی     |
| `mcp`                         | 2.3.0  | SDK رسمی MCP برای stdio       |
| `langgraph`                   | 1.2.15 | گراف و حلقه                   |
| `langgraph-checkpoint-sqlite` | 3.1.2  | `SqliteSaver` برای checkpoint |
| `nbformat`                    | 5.10.4 | ساخت و بازخوانی نوت‌بوک       |
| `nbclient`                    | 0.10.2 | اجرای برنامه‌ای نوت‌بوک       |
| `ipykernel`                   | 6.30.1 | kernel                        |

## راه‌اندازی

از ریشهٔ پروژه (`4.Agent-Tools-Memory`):

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install --no-cache-dir -r assignment\source\Day4\requirements-day4.txt
.venv\Scripts\python.exe -m ipykernel install --name bootcamp-day4 --display-name "Bootcamp Day4"
```

> **چرا `--no-cache-dir`؟** روی ویندوز، اگر چند `pip` هم‌زمان اجرا شوند روی قفل کش مشترک قفل می‌کنند و بعد از آن هر نصب بی‌صدا معلق می‌ماند. دور زدن کش این مشکل را حل می‌کند.

### نصب گلوبال (اختیاری)

پکیج‌ها روی پایتون سیستم هم نصب شده‌اند تا در تمرین‌های بعدی بدون فعال‌سازی venv در دسترس باشند:

```cmd
python -m pip install --no-cache-dir numpy pandas matplotlib scikit-learn pydantic mcp langgraph langgraph-checkpoint-sqlite nbformat nbclient ipykernel
```

### وضعیت واقعی نصب‌شده

| بسته                          | نسخهٔ pin | نسخهٔ نصب‌شده                       | وضعیت                                |
| ----------------------------- | --------- | ----------------------------------- | ------------------------------------ |
| `numpy`                       | 2.4.2     | **2.5.4**                           | pin در دسترس نبود، آخرین نسخه نصب شد |
| `pandas`                      | 3.0.0     | **3.0.0** (venv) / 3.0.6 (global)   | ✅                                   |
| `matplotlib`                  | 3.10.8    | **3.10.8** (venv) / 3.11.2 (global) | ✅                                   |
| `scikit-learn`                | 1.8.0     | **1.8.0** (venv) / 1.9.1 (global)   | ✅                                   |
| `pydantic`                    | 2.14.1    | **2.14.1**                          | ✅                                   |
| `mcp`                         | 2.3.0     | **2.3.0**                           | ✅                                   |
| `langgraph`                   | 1.2.15    | **1.2.15** (venv) / 1.2.17 (global) | ✅                                   |
| `langgraph-checkpoint-sqlite` | 3.1.2     | **3.1.2**                           | ✅                                   |
| `nbformat`                    | 5.10.4    | **5.10.4**                          | ✅                                   |
| `nbclient`                    | 0.10.2    | **0.10.2**                          | ✅                                   |
| `ipykernel`                   | 6.30.1    | **7.4.0** (venv)                    | pin در دسترس نبود                    |

نسخه‌های بالاتر از pin هیچ API استفاده‌شده در تکلیف را نمی‌شکنند. اگر بازتولید دقیق نسخه‌های pin لازم شد، روی پایتون ۳٫۱۳ امتحان کن.

## بررسی سلامت

```cmd
python -c "import numpy, pandas, sklearn, pydantic, mcp, langgraph; print('core ok')"
python -c "import sqlite3; print('sqlite', sqlite3.sqlite_version)"
python -c "from langgraph.checkpoint.sqlite import SqliteSaver; print('saver ok')"
```

## ساختار پوشه‌ها

```
4.Agent-Tools-Memory/
├─ 4_ iCourse.mhtml                  صفحهٔ ذخیره‌شدهٔ تکلیف (منبع اصلی)
├─ assignment/
│  └─ source/Day4/                   بستهٔ دانشجو، استخراج‌شده
│     ├─ ASSIGNMENT.md               صورت سؤال رسمی (۱۲۱۶ خط)
│     ├─ START_HERE.md               راهنمای شروع
│     ├─ Day4_Datasets/              ۸ پوشهٔ داده
│     ├─ Day4_Grading/               checker + schema + پروتکل
│     └─ Day4_Starter/               نوت‌بوک قالب + README
├─ datasets/
│  └─ day4-student-pack.zip          آرشیو اصلی (۱۹۸ KB)
├─ docs/
│  ├─ 00_roadmap.md                  نقشهٔ راه
│  ├─ 01_assignment_brief.md         خلاصهٔ صورت تکلیف
│  ├─ 02_data_map.md                 نقشهٔ داده‌ها
│  ├─ 03_rules_and_risks.md          قواعد و دام‌ها
│  ├─ 04_environment.md              همین فایل
│  ├─ 05_deliverables.md             تحویل‌دادنی‌ها
│  └─ generated/                     خروجی خودکار اسکریپت‌ها
│     ├─ assignment_text.txt         متن کامل صفحه
│     ├─ questions.json              بانک خام از سایت
│     ├─ questions.md                چک‌لیست فارسی
│     ├─ question_bank.json          بانک غنی‌شده (مرجع پاسخ‌دهی)
│     ├─ answer_key.md               فرم آینه‌ای برای پر کردن
│     └─ qa/                         گزارش‌های صحت‌سنجی
├─ scripts/                          ابزار استخراج و بررسی
├─ work/                             فضای کار پاسخ‌دهی
├─ Day4_Code/                        ماژول‌های پایتون (خودمان می‌سازیم)
├─ Day4_Run_Output/                  پایگاه‌ها و JSON خروجی
└─ deliverables/                     بستهٔ نهایی ارسال
```

## اسکریپت‌های موجود

| اسکریپت                          | کار                                |
| -------------------------------- | ---------------------------------- |
| `scripts/extract_assignment.py`  | رمزگشایی MHTML و استخراج ۱۴۴ سؤال  |
| `scripts/verify_extraction.py`   | گزارش سلامت بانک سؤال              |
| `scripts/probe_datasets.py`      | پروفایل داده + تطبیق SHA-256       |
| `scripts/reconcile_schema.py`    | تطبیق فرم سایت با schema مدرس      |
| `scripts/probe_notebook.py`      | نقشهٔ ۴۴۵ سلول نوت‌بوک             |
| `scripts/build_question_bank.py` | ادغام نهایی و ساخت `answer_key.md` |

اجرای همه:

```cmd
python scripts\extract_assignment.py && python scripts\probe_datasets.py && python scripts\reconcile_schema.py && python scripts\probe_notebook.py && python scripts\build_question_bank.py && python scripts\verify_extraction.py
```

## نکتهٔ کنسول ویندوز

کنسول پیش‌فرض `cp1256` است و فارسی را چاپ نمی‌کند. اسکریپت‌ها به همین دلیل خروجی متنی را در فایل‌های UTF-8 می‌نویسند، نه در `stdout`. اگر خواستی فارسی در ترمینال ببینی:

```cmd
chcp 65001
```
