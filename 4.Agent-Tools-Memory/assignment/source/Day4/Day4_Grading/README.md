# راهنمای بررسی محلی

تحویل این نسخه از صفحهٔ سایت با نوت‌بوک و ZIP شواهد است؛ بخش‌های زیر دربارهٔ قرارداد بررسی و تصحیح بستهٔ اصلی‌اند. فایل Word و فرم HTML در این نسخه استفاده نمی‌شوند.

# راهنمای تصحیح روز چهارم

بارم معتبر و متن سؤال در `question_schema.json` همراه همین نسخه است. فایل ارسالی دانشجو نمی‌تواند شناسه و نمرهٔ معتبر را تعیین کند. کلید مفهومی و rubric فقط در پوشهٔ Day4_Reference مدرس است.

## اجرای مستقل پایگاه

SQLite سرویس شبکه و DATABASE_URL نمی‌خواهد. دو فایل واقعی دانشجو را پس از پایان اجرای نوت‌بوک از محیط او خارج کنید و با نسخهٔ مورد اعتماد checker و ورودی‌های اصلی درس بررسی کنید:

```sh
python -I /trusted/Day4_Grading/check_submission.py --root /trusted --application-db /submission/application.sqlite --checkpoint-db /submission/checkpoints.sqlite --output /results/database_check.json
```

مسیرهای مثال باید با محیط اجرا تطبیق داده شوند. `--root` باید ریشهٔ مورد اعتماد مدرس شامل Day4_Datasets باشد، نه نسخه‌ای که دانشجو می‌تواند آن را تغییر دهد. checker از SQL ثابت و اتصال read-only استفاده می‌کند و هیچ کد یا SQL ارسالی دانشجو را اجرا نمی‌کند.

وضعیت و exit code: `passed=0`، `failed=1` و `infrastructure_error=2`. فقدان فایل الزامی یا پایگاه خراب نقص artifact است. مشکل دسترسی فایل میزبان یا نبود وابستگی/ورودی مورد اعتماد نیازمند اصلاح زیرساخت است؛ خودکار نمرهٔ صفر ندهید. passed فقط همین کنترل‌های پایگاه را تأیید می‌کند و تمام ۱۴۴ پاسخ را تصحیح نمی‌کند.

جداول مورد انتظار:

| جدول | ستون‌های لازم |
|---|---|
| memories | tenant, employee_id, memory_key, text, evidence_id, expires_day |
| profiles | tenant, employee_id, version, payload |
| approvals | approval_id, tenant, employee_id, payload_hash, base_version, reviewer, approved |
| writes | idempotency_key به‌عنوان کلید اصلی، tenant, employee_id, payload_hash, version, approval_id با FK به approvals |
| audit | event_id, tenant, employee_id, action, version |
| jobs | event_key به‌عنوان کلید اصلی، status |

فایل دوم schema واقعی `SqliteSaver` شامل جدول checkpoints با thread_id، checkpoint_id، checkpoint و metadata و state غیرخالی را دارد. راه‌حل جایگزین با persistence معتبر باید دستی و با شواهد معادل بررسی شود؛ checker پایه برای این schema مرجع است و تفاوت نام ستون به‌تنهایی نباید نمرهٔ کل پاسخ را صفر کند.

۱۴ کنترل شامل اتصال، integrity، جداول، تعریف و صحت FK، scope، grounding ادعا، رکورد approval، binding نوشتن، قید idempotency، audit، منشأ حافظه، job پایدار و checkpoint است. بررسی هویت زنده یا اثبات مرور انسان از روی این فایل ممکن نیست؛ نقش reviewer در این تمرین fixture برنامه است.

برای سؤال‌های مفهومی ۶۰٪ نمره برای گزینه و ۴۰٪ برای دلیل؛ برای عملی ۶۰٪ برای روش و کد/خروجی قابل بازتولید و ۴۰٪ برای تحلیل. زمان CPU، شناسه‌های تازه، ترتیب معادل و hashهای وابسته به پیاده‌سازی تطبیق رشته‌ای سخت ندارند. accuracy شرطیِ فاقد نمونه باید تعریف‌نشده باشد. برچسب test برای پرکردن فرم از دانشجو خواسته نشده است.

روش کامل ایجنتیک در AGENT_PROTOCOL.md آمده است.
