# تکلیف ۳ — از API تا پاسخ مستند (PostgreSQL / LangGraph)

<p dir="rtl" align="right">

این پوشه، فضای کار کامل «تکلیف ۳» بوت‌کمپ عامل‌های هوشمند است: صورت تکلیف، هفت مجموعه دادهٔ رسمی، مدل embedding، بررسی‌گر دیتابیس، و ساختار پوشه‌ای که کار ۱۲ بخش و ۱۴۴ زیرسؤال را قابل پیگیری می‌کند.

نکتهٔ مهم: عنوان تکلیف از PostgreSQL نام می‌برد، اما نسخهٔ اجرایی این تمرین روی **یک فایل SQLite** به نام `day3.sqlite` است. Docker، PostgreSQL و رمز لازم نیست.

</p>

## نقشهٔ پوشه‌ها

| مسیر | چیست |
|---|---|
| `START_HERE.md` | راهنمای رسمی بستهٔ دانشجو (دست‌نخورده) |
| `requirements.txt` | نسخه‌های قفل‌شدهٔ کتابخانه‌ها، همان‌طور که در بسته آمده |
| `.env.example` | الگوی متغیرهای محیطی؛ هیچ راز واقعی داخلش نیست |
| `assignment/` | صورت تکلیف: MHTML ذخیره‌شدهٔ صفحه، PDF، متن استخراج‌شده، و zip اصلی |
| `datasets/` | هفت مجموعه دادهٔ تکلیف + دو PDF آزمایشی |
| `resources/` | مدل embedding (`all-MiniLM-L6-v2` نسخهٔ ثابت) و manifest با hash هر فایل |
| `grading/` | `check_day3_db.py` — همان بررسی‌گری که پس از ارسال روی فایل دیتابیس اجرا می‌شود |
| `work/` | کار عملی؛ یک پوشه برای هر بخش ۵ تا ۱۲ (بخش‌های ۱–۴ مفهومی‌اند و در `docs/07` پاسخ داده می‌شوند) |
| `artifacts/` | خروجی‌های میانی: فهرست داده، `chunks.jsonl`، گزارش‌ها، لاگ‌ها |
| `deliverables/` | چهار فایل نهایی که در سایت بارگذاری می‌شوند |
| `docs/` | نقشهٔ راه، چک‌لیست ۱۴۴ سؤال، نقشهٔ داده، محیط، قواعد و ریسک‌ها |
| `scripts/` | ابزارهای مقدماتی: فهرست‌گیری داده، ساخت ایندکس سؤال‌ها، برپاسازی محیط، دانلود مدل |

## وضعیت

| مرحله | وضعیت |
|---|---|
| دریافت داده و صورت تکلیف | ✅ انجام شد |
| صحت‌سنجی SHA-256 هر ۲۴ سند corpus | ✅ ۲۴ از ۲۴ |
| فهرست‌گیری هر هفت مجموعه | ✅ `artifacts/data_inventory.json` |
| ایندکس ۱۴۴ زیرسؤال + چک‌لیست | ✅ `docs/03_question_checklist.md` |
| نقشهٔ راه و مقدمه‌چینی اجرایی | ✅ `docs/00_roadmap.md` |
| محیط پایتون + مدل embedding | ✅ `artifacts/env_report.json` (مدل ۱۱ از ۱۱ فایل، encode واقعی ۳۸۴ بعد) |
| ۱۴۴ پاسخ | ⬜ ۰ از ۱۴۴ |

## از کجا شروع کنم

```powershell
cd "C:\Users\pc\source\repos\AI\BootCamp Assignments\3.from-API-to-Doc-Answer-with-PostgerSQL-va-LangGraph"

# ۱) محیط (یک‌بار؛ الان آماده است)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\provision.ps1

# ۲) صحت محیط: نسخه‌ها + مدل + یک encode واقعی
.\.venv\Scripts\Activate.ps1
python scripts\check_env.py --encode

# ۳) صحت داده
python scripts\inventory.py

# ۴) ایندکس سؤال‌ها و چک‌لیست را بازتولید کن
python scripts\build_question_index.py

# ۵) دیتابیس خودت را پیش از ارسال بیازما
python grading\check_day3_db.py day3.sqlite
```

## چهار فایل تحویلی

| فایل | محتوا | جزئیات |
|---|---|---|
| `notebook.ipynb` | نوت‌بوک اجراشده با سه سلول برای هر زیرسؤال | `docs/04_deliverables.md` |
| `day3.sqlite` | دیتابیس با جدول‌های قراردادی، ۲۰ کاربر، ۱۲۰ پرونده، بردار ۳۸۴بعدی | `docs/04_deliverables.md` |
| `test_predictions.jsonl` | یک خط برای هر پرسش test: `query_id` + سه سند رتبه‌دار | `docs/04_deliverables.md` |
| `answerability_predictions.jsonl` | یک خط برای هر پرسش test: `query_id` + `score` + `accepted` | `docs/04_deliverables.md` |

## چند قاعدهٔ طلایی

1. **بذر مرجع `20261015`** — هر جا تصادفی‌سازی هست، همین بذر.
2. **تنظیمات فقط با train/dev انتخاب می‌شوند** و پیش از ساختن فایل‌های test قفل می‌شوند. آستانه را با test تغییر نده.
3. **عدد سایت = عدد خروجی نوت‌بوک.** هر عددی که در فرم می‌نویسی باید همان باشد که سلول چاپ می‌کند.
4. **هیچ راز واقعی** در نوت‌بوک، JSON یا فایل دیتابیس ننویس. `TEST-ONLY-SECRET` فقط fixture است.
5. **بیش از شواهد ادعا نکن.** در گزارش نهایی، «واقعاً اجراشده»، «fixture» و «اجرا‌نشده» را جدا بنویس.

