# تکلیف ۴ — معماری ایجنت، ابزار، حافظه و انتشار کنترل‌شده

بوت‌کمپ ماینینگ داده · iCourse · روز چهارم

| قلم     | مقدار                       |
| ------- | --------------------------- |
| بخش‌ها  | ۱۲                          |
| زیرسؤال | ۱۴۴                         |
| نمره    | ۱۰۰                         |
| مهلت    | بدون مهلت                   |
| تحویل   | نوت‌بوک اجراشده + ZIP شواهد |

---

## وضعیت پروژه

| مرحله                                    | وضعیت                                         |
| ---------------------------------------- | --------------------------------------------- |
| استخراج صورت سؤال از `4_ iCourse.mhtml`  | ✅ ۱۴۴ سؤال، ۱۰۰ نمره                         |
| دانلود و استخراج بستهٔ دانشجو            | ✅ ۱۹۸ KB                                     |
| صحت‌سنجی SHA-256 داده‌ها                 | ✅ ۱۶/۱۶                                      |
| تطبیق فرم سایت با `question_schema.json` | ✅ ۰ اختلاف                                   |
| بانک سؤال غنی‌شده                        | ✅ `docs/generated/question_bank.json`        |
| استخراج اسلایدهای جلسهٔ ۴                | ✅ ۲۸ اسلاید، متن بازخوانی‌شده                |
| مستندسازی                                | ✅ ۹ فایل در `docs/`                          |
| محیط پایتون (venv)                       | ✅ همهٔ ۱۱ بسته نصب و import شدند             |
| محیط پایتون (گلوبال)                     | ✅ نصب شد برای تمرین‌های بعدی                 |
| kernel ژوپیتر                            | ✅ `Bootcamp Day4` ثبت شد                     |
| آزمون سلامت داده                         | ✅ `work/smoke_test.py` — همهٔ ۴۰+ بررسی قبول |
| **بخش‌های ۱ تا ۴ (۴۸ سؤال، ۲۴ نمره)**    | ✅ **کامل — ۰ خطا در اعتبارسنجی گزینه‌ها**    |
| بخش‌های ۵ تا ۱۲ (۹۶ سؤال، ۷۶ نمره)       | ⏳ نیازمند کد و اجرا                          |

---

## ساختار

```
4.Agent-Tools-Memory/
├─ 4_ iCourse.mhtml              صفحهٔ ذخیره‌شدهٔ تکلیف (منبع اولیه)
├─ README.md                     همین فایل
├─ assignment/source/Day4/       بستهٔ دانشجو، استخراج‌شده
├─ datasets/                     آرشیو اصلی
├─ docs/                         مستندات و خروجی‌های خودکار
├─ scripts/                      ابزار استخراج و صحت‌سنجی
├─ work/                          فضای کار پاسخ‌دهی
├─ Day4_Code/                    ماژول‌های پایتون (ساخته می‌شود)
├─ Day4_Run_Output/              پایگاه‌ها و JSON (ساخته می‌شود)
└─ deliverables/                 بستهٔ نهایی ارسال
```

---

## مستندات

| فایل                                                         | محتوا                                     |
| ------------------------------------------------------------ | ----------------------------------------- |
| [`docs/00_roadmap.md`](docs/00_roadmap.md)                   | نقشهٔ راه، ترتیب اجرا، وضعیت              |
| [`docs/01_assignment_brief.md`](docs/01_assignment_brief.md) | خلاصهٔ صورت تکلیف و قاعدهٔ نمره           |
| [`docs/02_data_map.md`](docs/02_data_map.md)                 | نقشهٔ کامل ۸ پوشهٔ داده + واژه‌نامه       |
| [`docs/03_rules_and_risks.md`](docs/03_rules_and_risks.md)   | ۱۰ قاعدهٔ سخت، دام‌های داده و مفهومی      |
| [`docs/04_environment.md`](docs/04_environment.md)           | محیط، وابستگی‌ها، اسکریپت‌ها              |
| [`docs/05_deliverables.md`](docs/05_deliverables.md)         | تحویل‌دادنی‌ها، جدول‌های پایگاه، ۱۴ کنترل |

### خروجی‌های خودکار

| فایل                                                                       | محتوا                     |
| -------------------------------------------------------------------------- | ------------------------- |
| [`docs/generated/questions.md`](docs/generated/questions.md)               | چک‌لیست فارسی هر ۱۴۴ سؤال |
| [`docs/generated/answer_key.md`](docs/generated/answer_key.md)             | فرم آینه‌ای برای پر کردن  |
| [`docs/generated/question_bank.json`](docs/generated/question_bank.json)   | مرجع ماشین‌خوان پاسخ‌دهی  |
| [`docs/generated/assignment_text.txt`](docs/generated/assignment_text.txt) | متن کامل صفحه             |
| `docs/generated/qa/`                                                       | گزارش‌های صحت‌سنجی        |

---

## شروع سریع

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r assignment\source\Day4\requirements-day4.txt
python -m ipykernel install --user --name bootcamp-day4
```

بازسازی همهٔ خروجی‌های مستندات:

```cmd
python scripts\extract_assignment.py && python scripts\probe_datasets.py && python scripts\reconcile_schema.py && python scripts\probe_notebook.py && python scripts\build_question_bank.py && python scripts\verify_extraction.py
```

---

## نکتهٔ اصلی تکلیف

سه جملهٔ کلیدی که کل نمره را شکل می‌دهد:

1. **۶۰٪ نمرهٔ عملی از کد و خروجی است، نه از عدد.** عدد بدون شواهد اجرایی ارزشی ندارد.
2. **fixture مجاز است، دروغ نه.** SQLite، MCP و گراف باید واقعاً اجرا شوند؛ تصمیم‌گیر و reviewer می‌توانند fixture باشند — به شرط اعلام صریح.
3. **`Day4_Code` و `Day4_Run_Output` در بسته نیستند.** باید خودت بسازی و `checker` را جدا اجرا کنی.
