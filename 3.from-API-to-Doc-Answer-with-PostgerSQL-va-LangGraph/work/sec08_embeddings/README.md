# بخش ۸ — بردارسازی و بازیابی چندمسیره (۱۲ نمره)

## چه چیزی ساخته می‌شود

سه مسیر بازیابی (lexical، dense، hybrid) روی بردارهای واقعی مدل محلی، با ذخیره و بازخوانی دقیق از SQLite.

| ماژول | نقش |
|---|---|
| `model.py` | بارگذاری مدل محلی از `resources/embedding_model`، ثبت نسخه/بعد/سقف، hash فایل‌ها |
| `encode.py` | `batch encode` + `L2 normalize`، گزارش شکل ماتریس و normها |
| `similarity.py` | cosine صریح و dot نرمال‌شده، تفاوت similarity/distance |
| `lexical.py` | TF-IDF با unigram/bigram، رتبه‌بندی در سطح سند |
| `dense.py` | جستجوی دقیق روی بردارهای بازخوانی‌شده از SQLite |
| `fuse.py` | RRF با ثابت ۶۰ |
| `acl.py` | فیلتر مجوز **پیش از** top-k |
| `context.py` | ساخت context حداکثر ۷۰۰ توکن با گزارش شواهد منتخب/حذف‌شده |
| `latency.py` | p50/p95 پس از warm-up؛ زمان cold جدا |

## ورودی

- `resources/embedding_model` (۳۸۴ بعد، سقف ۲۵۶ توکن، `all-MiniLM-L6-v2` نسخه `1110a243…`)
- `artifacts/chunks.jsonl` از بخش ۷
- `datasets/03_Application/policies.jsonl` برای آزمون ACL
- ۱۲ پرسش train برای سنجش تأخیر

## زیرسؤال‌ها

۸٫۱ نسخه/مجوز/بعد/سقف و hash فایل‌های مدل · ۸٫۲ encode دسته‌ای و norm · ۸٫۳ cosine در دو فرم · ۸٫۴ baseline TF-IDF و top-3 سند · ۸٫۵ dense و مقایسه با baseline · ۸٫۶ ترکیب RRF · ۸٫۷ ذخیرهٔ BLOB و UPSERT · ۸٫۸ بازخوانی دقیق و بازتولید top-1 · ۸٫۹ ACL پیش از top-k (نشت tenant = ۰) · ۸٫۱۰ context ۷۰۰ توکنی · ۸٫۱۱ p50/p95 سه مسیر · ۸٫۱۲ رد ایندکس ناسازگار با fingerprint

## خروجی این پوشه

`artifacts/retrieval_report.json` · `artifacts/index_fingerprint.json` (مدل، نسخه، بعد، تنظیم chunk، hash chunks) · جدول `chunks` پر شده در `day3.sqlite`

## تعریف انجام‌شده

- بردار بازخوانی‌شده از SQLite با بردار اصلی یکسان است (بیشترین خطای بازخوانی ~۰).
- جستجوی دقیق روی دادهٔ بازخوانی‌شده همان top-1 محلی را بازمی‌گرداند.
- کاربر tenant `T-0` هیچ سیاست داخلی `T-1` نمی‌بیند؛ مسیر admin جدا سنجیده می‌شود.
- scoreهای lexcial و dense هم‌مقیاس فرض نمی‌شوند؛ ترکیب با رتبه انجام می‌شود.

## تله‌ها

- مدل انگلیسی است و corpus انگلیسی؛ پرسش فارسی به این بخش نده.
- بردار ذخیره‌شده با نسخهٔ دیگر مدل = بازیابی بی‌سر و صدا خراب (۸٫۱۲).
- `cosine distance = 1 - cosine similarity`؛ جهت مرتب‌سازی را برعکس نکن.
- زمان cold embedding را با warm قاطی نکن (۸٫۱۱).

وضعیت: ⬜ شروع نشده
