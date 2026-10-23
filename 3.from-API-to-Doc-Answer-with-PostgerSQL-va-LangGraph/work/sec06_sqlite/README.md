# بخش ۶ — دیتابیس SQLite و قیود داده (۸ نمره)

## چه چیزی ساخته می‌شود

`day3.sqlite` در ریشهٔ پروژه، از صفر و بازتولیدپذیر. Docker و PostgreSQL لازم نیست؛ کتابخانهٔ استاندارد `sqlite3` کافی است.

| ماژول | نقش |
|---|---|
| `migrate.py` | ساخت شش جدول قراردادی + کلیدهای خارجی + ایندکس و یکتایی‌ها |
| `seed.py` | ۲۰ کاربر و ۱۲۰ پرونده به‌شکل idempotent از `datasets/03_Application` |
| `probe_fk.py` | رد شدن پرونده با مالک ناموجود و سالم‌ماندن اتصال بعد از خطا |
| `probe_tx.py` | rollback کامل تراکنش جلسه+پیام ناسازگار |
| `authz.py` | منطق مالکیت: مالک، admin، دانشجوی دیگر |
| `tokens.py` | اعتبارسنجی ID token با `PyJWT` (signature، issuer، audience، expiry) |
| `sanitize.py` | پاک‌سازی بازگشتی metadata |

## ورودی

- `datasets/03_Application/users.csv` (۲۰ کاربر) و `cases.jsonl` (۱۲۰ پرونده)
- `datasets/03_Application/policies.jsonl` (۴ سیاست)
- `grading/check_day3_db.py` و `grading/README.md` (قرارداد)

## قرارداد

| جدول | ستون‌های لازم |
|---|---|
| `users` | `user_id, role, tenant` |
| `cases` | `case_id, owner_id, topic, summary` |
| `sessions` | `session_id, owner_id, case_id, idempotency_key` |
| `messages` | `message_id, session_id, content` |
| `documents` | `doc_id, version, content_hash` |
| `chunks` | `chunk_id, doc_id, content, embedding, model_id, model_revision` |

## زیرسؤال‌ها

۶٫۱ اتصال + `PRAGMA foreign_keys=ON` + `sqlite_version()` (اینجا: ۳٫۴۵٫۳) · ۶٫۲ ساخت جدول‌ها و seed · ۶٫۳ رد مالک ناموجود · ۶٫۴ rollback · ۶٫۵ کوئری پارامتری در برابر SQL injection · ۶٫۶ جدول مالک/دیگران/مدیر · ۶٫۷ ایندکس `owner_id` و `EXPLAIN QUERY PLAN` · ۶٫۸ UPSERT دوباره بدون افزایش تعداد · ۶٫۹ اعتبارسنجی توکن (issuer نامعتبر و منقضی) · ۶٫۱۰ scope و ویژگی کوکی · ۶٫۱۱ پاک‌سازی راز (نتیجهٔ هدف: صفر) · ۶٫۱۲ اجرای بررسی‌گر و `database_check.json`

## خروجی این پوشه

`artifacts/database_check.json` · `artifacts/db_probes.json` · اسکریپت‌های migration/seed که در نوت‌بوک هم می‌آیند

## تعریف انجام‌شده

- `python grading\check_day3_db.py day3.sqlite` → `status: passed` و کد خروج `0`.
- همهٔ اتصال‌ها `PRAGMA foreign_keys=ON` دارند (بدون آن، FK اعمال نمی‌شود).
- `sessions.idempotency_key` و `documents.doc_id` یکتا هستند و `cases.owner_id` ایندکس دارد.

## تله‌ها

- **بررسی‌گر روی `chunks` بردار ۳۸۴بعدی می‌خواهد**؛ اگر دیتابیس را پیش از بخش ۸ نهایی اعلام کنی، `embedding_dimensions` و `embedding_metadata_present` قرمز می‌شوند. دیتابیس را با بردارهای واقعی بخش ۸ کامل کن.
- `PRAGMA foreign_keys` در هر اتصال جدید باید دوباره روشن شود.
- بررسی‌گر فایل را فقط می‌خواند؛ گزارش خودت جای نتیجهٔ آن را نمی‌گیرد (۶٫۱۲ و ۱۲٫۹).

وضعیت: ⬜ شروع نشده
