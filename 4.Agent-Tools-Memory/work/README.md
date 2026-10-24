# فضای کار پاسخ‌دهی

این پوشه کد مشترک و اسکریپت‌های اجرای بخش‌ها را نگه می‌دارد. کد داخل نوت‌بوک کوتاه می‌ماند و منطق سنگین اینجاست.

## ساختار

```
work/
├─ common/                 کد مشترک، در نوت‌بوک ایمپورت می‌شود
│  ├─ paths.py             مسیرهای استاندارد (بدون مسیر مطلق)
│  ├─ data.py              بارگذاری همهٔ ۱۶ فایل داده با کش
│  └─ principal.py         principal قابل اعتماد و اعمال scope
├─ sec05_data/             بخش ۵ — آماده‌سازی داده و context
├─ sec06_mcp/              بخش ۶ — ابزارها و MCP
├─ sec07_loop/             بخش ۷ — حلقهٔ محدود
├─ sec08_memory/           بخش ۸ — SQLite و تأیید انسانی
├─ sec09_routing/          بخش ۹ — مسیریاب
├─ sec10_security/         بخش ۱۰ — ده آزمون تهدید
├─ sec11_eval/             بخش ۱۱ — معیارها و span
├─ sec12_rollout/          بخش ۱۲ — gate و تحویل
└─ smoke_test.py           آزمون سلامت داده‌ها و بانک سؤال
```

## استفاده در نوت‌بوک

```python
import sys
from pathlib import Path

ROOT = Path.cwd()
while not (ROOT / "assignment").exists() and ROOT != ROOT.parent:
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "work"))

from common import paths, data, principal

paths.ensure_output_dirs()
people = data.people()
```

## آزمون سلامت

```cmd
python work\smoke_test.py
```

باید همهٔ موارد `ok` باشند و در پایان `ALL CHECKS PASSED` چاپ شود.

## قاعدهٔ مسیر

هیچ مسیر مطلقی در کد نباشد. همه‌چیز از `common.paths` بیاید تا نوت‌بوک هم روی سیستم مدرس اجرا شود.
