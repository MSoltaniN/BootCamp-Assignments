# تحویل‌دادنی‌ها

## دو قلم ارسالی

| قلم             | مسیر                              | سقف    |
| --------------- | --------------------------------- | ------ |
| نوت‌بوک اجراشده | `deliverables/Day4_Student.ipynb` | ۲۵ MiB |
| ZIP شواهد       | `deliverables/day4-evidence.zip`  | ۲۵ MiB |

مجموع هر دو: **حداکثر ۵۰ MiB**.

پاسخ‌های متنی در فرم سایت نوشته می‌شوند. فرم HTML آفلاین و JSON خروجی آن لازم نیست.

---

## محتوای الزامی ZIP شواهد

بر اساس `START_HERE.md` و `ASSIGNMENT.md`:

### ۱. کد

| فایل                      | نقش                                                              |
| ------------------------- | ---------------------------------------------------------------- |
| `Day4_Code/agent_lab.py`  | principal، سه ابزار، اعتبارسنجی پروفایل، حلقهٔ محدود، ذخیره‌سازی |
| `Day4_Code/mcp_server.py` | سرور MCP با سه ابزار + یک resource + یک prompt (stdio)           |
| `Day4_Code/mcp_probe.py`  | client مستقل برای کشف قابلیت و آزمون مجاز/نامجاز                 |
| `Day4_Code/*.py`          | ماژول‌های بخشی که در نوت‌بوک ایمپورت شده‌اند                     |

### ۲. پایگاه‌ها (واقعی، اجرا‌شده)

| فایل                                 | محتوای الزامی                                                                               |
| ------------------------------------ | ------------------------------------------------------------------------------------------- |
| `Day4_Run_Output/application.sqlite` | جدول‌های `memories`، `profiles`، `approvals`، `writes`، `audit`، `jobs`                     |
| `Day4_Run_Output/checkpoints.sqlite` | schema واقعی `SqliteSaver` با `checkpoints(thread_id, checkpoint_id, checkpoint, metadata)` |

### ۳. گزارش‌های JSON

| فایل                        | بخش                            |
| --------------------------- | ------------------------------ |
| `database_check.json`       | خروجی اجرای مستقل checker      |
| `agent_trace.json`          | مسیر حلقهٔ ابزار               |
| `locked_router_config.json` | تنظیمات مسیریاب، پس از قفل شدن |
| `full_evidence.json`        | شواهد کامل ارزیابی             |
| `handoff_manifest.json`     | فهرست تحویل                    |
| `handoff_check.json`        | بررسی نهایی سازگاری            |

### ۴. پیش‌بینی‌ها

| فایل                      | قاعده                                                       |
| ------------------------- | ----------------------------------------------------------- |
| `route_predictions.jsonl` | برای **همهٔ ۸۰** درخواست `test`، هر شناسه **دقیقاً یک‌بار** |

### ۵. بازاجرا

| فایل                   | نقش                                                   |
| ---------------------- | ----------------------------------------------------- |
| `README.md`            | روش بازاجرا: نصب، ترتیب اجرا، توضیح مرز واقعی/fixture |
| `requirements.txt`     | وابستگی‌های دقیق                                      |
| `execution_scope.json` | تفکیک اجرای واقعی / fixture / اجرانشده                |

### ۶. گزارش ده آزمون امنیتی

ده خانوادهٔ تهدید، هر کدام با ورودی، نتیجه و تصمیم دفاعی. خروجی ماشین‌خوان + تحلیل.

---

## نقشهٔ بخش به خروجی

| بخش | نمره | بسته‌های داده                        | خروجی اصلی                                                      |
| --- | ---- | ------------------------------------ | --------------------------------------------------------------- |
| ۱   | ۶    | —                                    | ۱۲ گزینه + دلیل                                                 |
| ۲   | ۶    | —                                    | ۱۲ گزینه + دلیل                                                 |
| ۳   | ۶    | —                                    | ۱۲ گزینه + دلیل                                                 |
| ۴   | ۶    | —                                    | ۱۲ گزینه + دلیل                                                 |
| ۵   | ۸    | `01_HR`, `02_Context`, `03_Requests` | آمار داده، تخصیص بودجه، شاخص scope، پروفایل مستند               |
| ۶   | ۸    | `01_HR`, `05_Tools`                  | `mcp_server.py`, `mcp_probe.py`, گزارش قابلیت                   |
| ۷   | ۱۰   | `05_Tools`                           | حلقهٔ محدود، `agent_trace.json`                                 |
| ۸   | ۱۰   | `04_Memory`                          | `application.sqlite`, `checkpoints.sqlite`                      |
| ۹   | ۱۰   | `03_Requests`, `01_HR`               | مسیریاب، `locked_router_config.json`, `route_predictions.jsonl` |
| ۱۰  | ۱۰   | `06_Security`                        | ده آزمون تهدید                                                  |
| ۱۱  | ۱۰   | `07_Evaluation`, `03_Requests`       | معیارها، `full_evidence.json`، تحلیل span                       |
| ۱۲  | ۱۰   | `08_Rollout`, `Day4_Grading`         | `regression_gate.json`, `handoff_*`, `execution_scope.json`     |

---

## جدول‌های پایگاه (قرارداد `checker`)

از `Day4_Grading/README.md`:

| جدول        | ستون‌های لازم                                                                                                      |
| ----------- | ------------------------------------------------------------------------------------------------------------------ |
| `memories`  | `tenant`, `employee_id`, `memory_key`, `text`, `evidence_id`, `expires_day`                                        |
| `profiles`  | `tenant`, `employee_id`, `version`, `payload`                                                                      |
| `approvals` | `approval_id`, `tenant`, `employee_id`, `payload_hash`, `base_version`, `reviewer`, `approved`                     |
| `writes`    | `idempotency_key` (**PK**), `tenant`, `employee_id`, `payload_hash`, `version`, `approval_id` (**FK → approvals**) |
| `audit`     | `event_id`, `tenant`, `employee_id`, `action`, `version`                                                           |
| `jobs`      | `event_key` (**PK**), `status`                                                                                     |

فایل checkpoint: جدول `checkpoints` با `thread_id`، `checkpoint_id`، `checkpoint`، `metadata` و `state` غیرخالی.

---

## ۱۴ کنترل پایگاه

checker این کنترل‌ها را بررسی می‌کند:

1. اتصال به پایگاه
2. یکپارچگی (`PRAGMA integrity_check`)
3. وجود جدول‌ها
4. تعریف FK
5. صحت FK
6. رعایت scope
7. grounding ادعا
8. رکورد `approval`
9. binding نوشتن به approval
10. قید idempotency
11. ثبت `audit`
12. منشأ حافظه
13. پردازش پایدار `job`
14. checkpoint

> `passed` فقط همین ۱۴ کنترل را تأیید می‌کند، نه ۱۴۴ پاسخ را.

---

## کدهای خروجی checker

| کد  | معنا                   | برخورد                     |
| --- | ---------------------- | -------------------------- |
| `0` | `passed`               | قبول                       |
| `1` | `failed`               | نمرهٔ مرتبط کم می‌شود      |
| `2` | `infrastructure_error` | اصلاح محیط؛ خودکار صفر نده |

---

## چه چیزی در ZIP **نباشد**

- وزن مدل و فایل باینری بزرگ
- دیتاست مشترک (`Day4_Datasets` را تکرار نکن)
- پاسخ مرجع مدرس
- `.venv/`، `__pycache__/`، `node_modules/`
- رمز، توکن یا API key واقعی
- فایل‌های موقت و کش

---

## روش ساخت ZIP

```cmd
cd 4.Agent-Tools-Memory
powershell Compress-Archive -Path Day4_Code,Day4_Run_Output,README.md,requirements.txt,execution_scope.json -DestinationPath deliverables\day4-evidence.zip -Force
```

پیش از ارسال حجم را بررسی کن:

```cmd
powershell "(Get-Item deliverables\day4-evidence.zip).Length / 1MB"
```

---

## ترتیب اجرای نوت‌بوک

برای اینکه خروجی‌ها در نوت‌بوک دیده شوند:

1. محیط را فعال کن
2. kernel `Bootcamp Day4` را انتخاب کن
3. `Restart & Run All`
4. بررسی کن هیچ سلولی خطا ندارد
5. پایگاه‌ها و JSONها را در `Day4_Run_Output/` ببین
6. `checker` را **جدا** اجرا کن:

```cmd
python assignment\source\Day4\Day4_Grading\check_submission.py --root assignment\source\Day4 --application-db Day4_Run_Output\application.sqlite --checkpoint-db Day4_Run_Output\checkpoints.sqlite --output Day4_Run_Output\database_check.json
```

7. `database_check.json` را هم در ZIP بگذار
