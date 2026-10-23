# چهار فایل تحویلی — مشخصات دقیق

فایل‌ها ابتدا در `deliverables/` ساخته می‌شوند، بعد در چهار کارت صفحهٔ تکلیف بارگذاری می‌شوند.
نام فایل‌ها را عوض نکن؛ بررسی خودکار و ایجنت روی همین نام‌ها و همین ساختار کار می‌کنند.

---

## ۱. `notebook.ipynb` — نوت‌بوک اجراشده

| قلم | الزام |
|---|---|
| ساختار | برای هر ۱۴۴ زیرسؤال **سه سلول**، به ترتیب: Markdown عنوان + Code + Markdown تحلیل |
| عنوان سلول اول | `زیرسؤال ۵٫۳` (بخش و شماره با ارقام فارسی و جداکنندهٔ `٫`) |
| زبان کد | انگلیسی، قابل اجرا، با چاپ خروجی |
| زبان تحلیل | فارسی راست‌به‌چپ |
| اجرا | `Restart Kernel & Run All` پیش از ذخیره، تا خروجی‌ها در فایل بمانند |
| بذر | `20261015` |
| راز | هیچ کلید/توکن واقعی، هیچ مسیر شخصی |

**چرا عنوان مهم است:** تصحیح‌کننده سلول‌ها را با همین عنوان پیدا می‌کند و عددهای سایت را با خروجی همان سلول تطبیق می‌دهد. عنوان نداشته باشد ⇒ بخش عملی آن سؤال کم‌نمره می‌شود.

---

## ۲. `day3.sqlite` — دیتابیس

### قرارداد جدول‌ها (از `grading/README.md`)

| جدول | ستون‌های لازم |
|---|---|
| `users` | `user_id, role, tenant` |
| `cases` | `case_id, owner_id, topic, summary` |
| `sessions` | `session_id, owner_id, case_id, idempotency_key` |
| `messages` | `message_id, session_id, content` |
| `documents` | `doc_id, version, content_hash` |
| `chunks` | `chunk_id, doc_id, content, embedding, model_id, model_revision` |

### کلیدهای خارجی لازم

- `cases.owner_id` → `users.user_id`
- `sessions.owner_id` → `users.user_id`
- `sessions.case_id` → `cases.case_id`
- `messages.session_id` → `sessions.session_id`
- `chunks.doc_id` → `documents.doc_id`

### دادهٔ لازم

| قلم | مقدار |
|---|---|
| کاربر | دقیقاً ۲۰ |
| پرونده | دقیقاً ۱۲۰ |
| سند | دست‌کم ۲۴ |
| chunk | دست‌کم ۲۴ (و دست‌کم برابر تعداد سند) |
| بردار | ۳۸۴ عدد `float32` به‌صورت BLOB یا JSON آرایه — همه متناهی |
| `model_id` و `model_revision` | برای همهٔ chunkها پرشده |

### ایندکس و یکتایی

- ایندکس روی `cases.owner_id`
- یکتایی روی `sessions.idempotency_key`
- یکتایی روی `documents.doc_id`

### بررسی خودکار — `grading/check_day3_db.py`

```powershell
python grading\check_day3_db.py day3.sqlite
```

| کد خروج | وضعیت | معنا |
|---|---|---|
| `0` | `passed` | همهٔ بررسی‌ها سبز |
| `1` | `failed` | دست‌کم یک بررسی قرمز |
| `2` | `error` | فایل خوانا نیست (خالی، بزرگ‌تر از ۸۰MB، یا SQLite نیست) |

بررسی‌های انجام‌شده به ترتیب: `sqlite_file_ok`، `integrity_ok`، `schema_*` (شش جدول)، `seed_users`، `seed_cases`، `seed_documents`، `seed_chunks`، `no_orphan_cases`، `no_orphan_chunks`، `foreign_keys_declared`، `owner_index`، `idempotency_unique`، `documents_unique`، `embedding_dimensions`، `embedding_metadata_present`، `fk_rejects_orphan_case`، `transaction_rollback`.

گزارش در `database_check.json` ذخیره می‌شود. **همین بررسی پس از ارسال روی فایل بارگذاری‌شده اجرا می‌شود** و عددهایی که در سؤال‌های ۶٫۱۲ و ۱۲٫۹ می‌نویسی با آن مقایسه می‌شوند — گزارش خودت جایگزینش نیست.

بررسی‌گر فایل را فقط **می‌خواند**: روی یک کپی در حافظه چند آزمون می‌نویسد و برمی‌گرداند؛ هیچ کدی از فایل تو اجرا نمی‌شود.

---

## ۳. `test_predictions.jsonl` — پیش‌بینی بازیابی (سؤال ۹٫۷)

یک خط JSON برای **هر پرسش test** (۳۰ خط):

```json
{"query_id": "QR-5080cee2b3923962", "ranked_doc_ids": ["PEP-0498", "PEP-0343", "PEP-0572"]}
```

| الزام | توضیح |
|---|---|
| `query_id` | باید دقیقاً با `query_id` یکی از ردیف‌های `split == "test"` در `queries.jsonl` یکی باشد |
| `ranked_doc_ids` | **سه سند متمایز**، به ترتیب رتبه، با شناسهٔ `doc_id` (مثل `PEP-0008`) |
| تکرار سند در یک ردیف | ممنوع |
| برچسب | هیچ برچسبی در فایل نگذار؛ gold نزد مدرس است |
| تولید | فقط **پس از قفل تنظیمات** روی dev |

---

## ۴. `answerability_predictions.jsonl` — تصمیم پاسخ‌پذیری (سؤال ۹٫۱۰)

یک خط JSON برای **هر پرسش test** (۳۰ خط):

```json
{"query_id": "QR-5080cee2b3923962", "score": 0.63, "accepted": true}
```

| الزام | توضیح |
|---|---|
| `score` | بیشترین cosine بازیابی dense برای همان پرسش (عدد اعشاری) |
| `accepted` | `true`/`false` بر اساس **آستانهٔ ثابت انتخاب‌شده روی dev** |
| آستانه | بعد از ساخت فایل عوض نشود؛ false accept / false reject با gold سنجیده می‌شود |

---

## چک‌لیست پیش از ارسال

- [ ] نوت‌بوک با `Restart Kernel & Run All` اجرا و ذخیره شده (خروجی‌ها موجودند).
- [ ] هر ۱۴۴ سلول عنوان `زیرسؤال N٫M` دارد و ترتیب Markdown/Code/Markdown رعایت شده.
- [ ] عددهای نوشته‌شده در سایت با خروجی نوت‌بوک یکی‌اند.
- [ ] `python grading\check_day3_db.py day3.sqlite` وضعیت `passed` و کد خروج `0` می‌دهد.
- [ ] `day3.sqlite` شامل ۲۰ کاربر و ۱۲۰ پرونده و بردار ۳۸۴بعدی برای همهٔ chunkهاست.
- [ ] `test_predictions.jsonl` ۳۰ خط و هر خط سه سند متمایز دارد.
- [ ] `answerability_predictions.jsonl` ۳۰ خط دارد و آستانه‌اش با dev انتخاب شده.
- [ ] جست‌وجوی `TEST-ONLY-SECRET` فقط در جای fixture است، نه در خروجی نهایی.
- [ ] هیچ `C:\Users\...`، رمز، توکن یا API key در هیچ فایلی نیست.
- [ ] گزارش نهایی سه دستهٔ «واقعاً اجراشده / fixture / اجرانشده» را دارد.
