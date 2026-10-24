# بخش ۷ — ورود اسناد و حفظ منشأ (۱۰ نمره)

## چه چیزی ساخته می‌شود

زنجیرهٔ «فایل خام → chunk با منشأ کاراکتری → رکورد در SQLite»، بدون اختراع metadata.

| ماژول | نقش |
|---|---|
| `manifest.py` | تطبیق manifest با فایل‌ها و بررسی SHA-256 |
| `pdf_ingest.py` | خواندن صفحه‌به‌صفحه با `pypdf` و علامت‌زدن PDF بدون متن |
| `rst_meta.py` | استخراج عنوان، شناسه، نسخه و بخش‌ها از RST |
| `chunker.py` | chunk حداکثر ۲۲۰ توکن با هم‌پوشانی ۴۰، با tokenizer **همان مدل embedding** |
| `provenance.py` | بازسازی `start/end` و آزمون hash، ساخت `chunk_id` پایدار |
| `dedupe.py` | رفع تکرار دقیق با کلید مناسب |
| `policy_ingest.py` | چهار سیاست مصنوعی با `access`/`tenant` و نسخهٔ archived |
| `artifact.py` | ساخت `chunks.jsonl` + fingerprint |

## ورودی

- `datasets/01_Corpus/manifest.csv` (۲۴ سند، نسخه `b80c7bf8…`)، `raw/pep-*.rst`، `pdf_fixtures/*.pdf`
- `datasets/03_Application/policies.jsonl` (LAB-PUBLIC، LAB-T0، LAB-T1، LAB-OLD)

## زیرسؤال‌ها

۷٫۱ تطبیق manifest و hash (۲۴ از ۲۴) · ۷٫۲ دو PDF و علامت‌زدن سند تصویری · ۷٫۳ metadata و اتصال نمونه به مسیر/URL اصلی · ۷٫۴ chunking ۲۲۰/۴۰ و توزیع طول · ۷٫۵ بازسازی متن و خطای منشأ صفر · ۷٫۶ پایداری `chunk_id` · ۷٫۷ جداسازی نسخه‌ها بدون دست‌زدن به فایل اصلی · ۷٫۸ رفع تکرار · ۷٫۹ مقایسهٔ ۱۱۰/۲۲۰/۴۴۰ و ریسک truncation · ۷٫۱۰ چهار سیاست با metadata فیلتر پیش از top-k · ۷٫۱۱ UPSERT در `chunks` · ۷٫۱۲ artifact با hash و تعداد

## خروجی این پوشه

`artifacts/chunks.jsonl` · `artifacts/ingest_fingerprint.json` (نسخهٔ مدل، اندازهٔ chunk، هم‌پوشانی، hash corpus)

## تعریف انجام‌شده

- `text[start:end]` برای **همهٔ** chunkها دقیقاً با متن ذخیره‌شده یکی است (خطای منشأ = ۰).
- دو اجرای متوالی chunking، همان `chunk_id`ها را می‌دهد.
- `scan_only_fixture.pdf` بی‌صدا ایندکس نشده و به‌عنوان «نیازمند OCR» علامت خورده.
- chunk نسخهٔ قدیم و جدید یک سند هیچ شناسهٔ مشترکی ندارند.

## تله‌ها

- **سقف ۲۵۶ توکن مدل** با chunk ۲۲۰ توکنی؛ اگر شمارش با tokenizer مدل نباشد، truncation پنهان می‌شود.
- chunk ۴۴۰ توکنی از سقف می‌گذرد؛ در ۷٫۹ تعدادشان را صریح گزارش کن و پنهان نکن.
- منشأ یعنی «بازهٔ کاراکتری در متن اصلی»، نه «شمارهٔ خط» یا «شمارهٔ پاراگراف».
- `chunk_id` باید به (سند، نسخه، بازه، محتوا) وابسته باشد؛ فقط به شمارهٔ ترتیب نه.

وضعیت: ⬜ شروع نشده
