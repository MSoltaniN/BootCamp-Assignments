# بخش ۱۱ — گردش کار LangGraph و پاسخ مستند (۱۰ نمره)

## چه چیزی ساخته می‌شود

یک `StateGraph` **واقعی** با گرهای که مجوز را پیش از هر ابزار می‌سنجد و پاسخ را فقط از شواهد بازیابی‌شده می‌سازد. تولید پاسخ در مرجع، **baseline استخراجی قطعی** است: هیچ ادعای اجرای LLM پولی یا ورود Google زنده نداریم.

| ماژول | نقش |
|---|---|
| `state.py` | قرارداد state: `query, user, case, route, evidence, history, answer, trace` — per-request و بدون secret |
| `nodes/auth.py` | بررسی مالکیت در SQLite **پیش از** هر واکشی؛ مسیر `deny` بدون evidence/history |
| `nodes/router.py` | مسیریابی با fallback؛ `clarify` و `unsupported` بدون جستجوی خصوصی |
| `tools/history.py` | تاریخچهٔ پرونده با کوئری پارامتری + owner check |
| `tools/research.py` | شواهد عمومی یا tenant مجاز فقط |
| `nodes/generate.py` | پاسخ ساختاریافتهٔ استخراجی در سه حالت `general` / `rag` / `both` |
| `nodes/validate.py` | اعتبارسنجی استناد: ID واقعی، وجود quote، و در حالت استخراجی برابری claim و quote |
| `graph.py` | سیم‌کشی گراف و `invoke` با ثبت trace |
| `cache.py` | کلید کش با user، tenant، مدل، corpus، prompt version |
| `telemetry.py` | رویداد کمینه با correlation ID مشترک و metadata پاک‌سازی‌شده |

## ورودی

- `01_Corpus` و `03_Application/policies.jsonl` (شواهد و مجوز)
- `06_Robustness/attacks.jsonl` (۳۰ حمله) و `06_Robustness/answer_candidates.jsonl` (۴ کاندید: `GOOD`، `UNKNOWN_ID`، `MISSING_CITATION`، `BAD_QUOTE`)

## زیرسؤال‌ها

۱۱٫۱ قرارداد state (secret = ۰) · ۱۱٫۲ node ورود و deny غیرمالک · ۱۱٫۳ مسیریابی با fallback · ۱۱٫۴ ابزار تاریخچه و محدودیت research · ۱۱٫۵ پاسخ ساختاریافته و سه حالت · ۱۱٫۶ validator روی چهار کاندید · ۱۱٫۷ claim ناسازگار با quote · ۱۱٫۸ گراف نهایی و trace · ۱۱٫۹ درخواست غیرمالک از کل گراف · ۱۱٫۱۰ سی حمله و سلامت مرز داده/دستور · ۱۱٫۱۱ کلید کش · ۱۱٫۱۲ رویداد کمینه و trace بدون متن خصوصی

## خروجی

`artifacts/traces/*.json` (trace هر درخواست) · `artifacts/attack_report.json` · `artifacts/graph_topology.md`

## تعریف انجام‌شده

- در trace درخواست غیرمالک **هیچ** `history` یا `research` نیست و درخواست بعدی مالک سالم اجرا می‌شود.
- `general` در baseline استخراجی صریحاً abstain می‌کند (ناتوانی تولید آزاد را نشان می‌دهد).
- از ۳۰ حمله، نشت secret آزمایشی = ۰ و فراخوانی LLM زنده = ۰.
- تغییر هر یک از پنج جزء کلید کش، `miss` می‌دهد.

## تله‌ها

- تاریخچهٔ خصوصی منبع پژوهشی عمومی نیست؛ نباید cite شود.
- validator ساختاری ممکن است claim ناسازگار را قبول کند؛ شرط برابری در حالت استخراجی لازم است.
- state اولیه نباید secret داشته باشد و نباید بین درخواست‌ها مشترک باشد.
- نتیجهٔ این بخش «نرخ مقاومت LLM زنده» نیست؛ فقط همین مسیر و همین fixtureها را می‌سنجد.

وضعیت: ⬜ شروع نشده
