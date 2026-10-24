# بستهٔ شواهد — تکلیف ۴

## بازتولید

از ریشهٔ پروژه (جایی که `Day4_Code/` هست):

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install --no-cache-dir -r assignment\source\Day4\requirements-day4.txt
.venv\Scripts\python.exe work\sec06_12_pipeline\run_all.py        # بخش‌های ۶ تا ۱۲
.venv\Scripts\python.exe work\sec05_data\run_section5.py          # بخش ۵
.venv\Scripts\python.exe assignment\source\Day4\Day4_Grading\check_submission.py ^
    --application-db Day4_Run_Output\application.sqlite ^
    --checkpoint-db Day4_Run_Output\checkpoints.sqlite ^
    --output Day4_Run_Output\database_check.json
```

اجرای بخش‌های ۶ تا ۱۲ حدود ۲۰ ثانیه طول می‌کشد. `--root` را دستی تنظیم نکنید؛
مقدار پیش‌فرض همان `assignment/source/Day4` است که `Day4_Datasets/` را پیدا می‌کند.

## محتوا

| مسیر | توضیح |
|---|---|
| `application.sqlite` | پایگاه کاربرد با شش جدول: memories، profiles، approvals، writes، audit، jobs |
| `checkpoints.sqlite` | checkpoint پایدار LangGraph (پایگاه جدا) |
| `database_check.json` | نتیجهٔ checker همراه، **۱۴ از ۱۴** موفق |
| `full_evidence.json` | همهٔ اعداد بخش‌های ۵ تا ۱۲ در یک سند |
| `route_predictions.jsonl` | ۸۰ پیش‌بینی آزمون مسیریاب قفل‌شده |
| `locked_router_config.json` | پیکربندی قفل‌شده (تنظیم فقط با dev) |
| `agent_trace.json` | رد اجرای حلقه |
| `agent_card.json` | کارت ایجنت با ۱۰ فیلد الزامی |
| `execution_scope.json` | تفکیک اجراشدهٔ واقعی / fixture / اجرانشده |
| `redteam_reports.json` | ده خانوادهٔ تهدید و کنترل هرکدام |
| `regression_gate.json` | دروازهٔ کیفیت روی dev |
| `handoff_manifest.json` | SHA-256 و اندازهٔ فایل‌های کلیدی |
| `handoff_check.json` | جمع‌بندی تحویل |
| `section5.json` / `sections_6_12.json` | خروجی عددی بخش‌ها |
| `code/` | ماژول‌های `Day4_Code` و خط‌لولهٔ `work` |
| `docs/` | مستندات فارسی، شامل نقشهٔ کد و گزارش بخش‌ها |

## نکات صادقانه

- تصمیم‌گیر و لاگ‌ها **fixture** هستند؛ هیچ LLM زنده‌ای اجرا نشده است
  (`execution_scope.json`).
- A2A و احراز هویت سازمانی پیاده نشده‌اند و ادعا هم نمی‌شوند.
- آزمون جفت‌شدهٔ test **معنادار نیست** (بازهٔ ۹۵٪ شامل صفر است) و همین‌طور گزارش شده.
- `checker_passed` در `handoff_manifest.json` مقدار `null` دارد، چون بررسی معتبر
  باید با نسخهٔ خودِ مدرس اجرا شود.
- هیچ رمز، توکن یا API key واقعی در این بسته نیست.

## اعتبارسنجی

`SHA256SUMS.txt` هش همهٔ اعضای بسته را دارد.
