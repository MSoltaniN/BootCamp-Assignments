# خلاصهٔ تکلیف ۵

**عنوان:** مدل‌های باز و اجرای محلی، ارزیابی و گردش کار امن
**منبع:** `5_ iCourse.mhtml` (snapshot از `shokrzad.com/ai/icourse/ai-agents-bootcamp/missions/2413a0be-...`)
**بستهٔ دانشجو:** `day5-student-pack.zip` (۳۰۶٫۷ کیلوبایت) → `assignment/source/Day5/`

## ساختار نمره

| گروه    | بخش‌ها              | نوع                                    | نمره    |
| ------- | ------------------- | -------------------------------------- | ------- |
| مفهومی  | ۱، ۲، ۳، ۴          | گزینه + دلیل، هر کدام ۱۲ زیرسؤال × ۰٫۵ | **۲۴**  |
| عملی    | ۵، ۶                | ۱۲ زیرسؤال × (۰٫۵ و ۱)                 | **۱۶**  |
| عملی    | ۷، ۸، ۹، ۱۰، ۱۱، ۱۲ | ۱۲ زیرسؤال × (۰٫۵ و ۱)                 | **۶۰**  |
| **جمع** |                     |                                        | **۱۰۰** |

## وزن‌دهی هر سؤال

- **مفهومی:** ۶۰٪ گزینهٔ درست + ۴۰٪ دلیل. گزینهٔ درست بدون دلیل نمرهٔ کامل نمی‌گیرد.
- **عملی:** ۶۰٪ روش + کد + خروجی واقعی، ۴۰٪ تحلیل فارسی. کد بدون تحلیل یا تحلیل بدون خروجی نمرهٔ کامل نمی‌گیرد.

## ساختار تحویل

| قلم                              | محدودیت                    |
| -------------------------------- | -------------------------- |
| پاسخ‌های متنی                    | در فرم سایت، ذخیرهٔ خودکار |
| `Student_Template.ipynb` اجراشده | ≤ ۲۵ MiB                   |
| `day5_evidence.zip`              | ≤ ۲۵ MiB                   |
| مجموع                            | ≤ ۵۰ MiB                   |

در نوتبوک، برای هر زیرسؤال **سه سلول** با عنوان «زیرسؤال N.M»:

1. صورت سؤال
2. کد انگلیسی + خروجی اجرا
3. تحلیل فارسی راست‌به‌چپ

## آرتیفکت‌های ZIP شواهد

از `START_HERE.md` و `check_submission.py`:

```
selection.json
runtime_config.json
test_predictions.jsonl
selected_adapter.npz
adapter_selection.json
adapter_test_predictions.npy
adapter_base_test_predictions.npy
quantization_selection.json
quant_test_predictions.npy
quantization_report.json
local_agent.sqlite
agent_trace.json
security_tests.json
handoff_manifest.json
model_catalog_clean.csv
acceptance_plan.json
provenance.json
capacity_recommendation.json
evaluation_report.json
error_audit.csv
serving_report.json
adapter_report.json
```

همچنین: `README` بازاجرا، raw پاسخ‌های dev، خطاهای مدل، `dataset_manifest` بررسی‌شده.

## ۱۲ بخش در یک نگاه

| #   | بخش                                | نمره | داده‌های اصلی                                                                                      | خروجی کلیدی                                                                                             |
| --- | ---------------------------------- | ---- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| ۱   | مجوز و منشأ و انتخاب مدل           | ۶    | —                                                                                                  | گزینه + دلیل                                                                                            |
| ۲   | معماری و حافظه و کوانتیزه‌سازی     | ۶    | —                                                                                                  | گزینه + دلیل                                                                                            |
| ۳   | انتخاب موتور و زیرساخت             | ۶    | —                                                                                                  | گزینه + دلیل                                                                                            |
| ۴   | ارزیابی و تنظیم و امنیت اجرای محلی | ۶    | —                                                                                                  | گزینه + دلیل                                                                                            |
| ۵   | ممیزی کاتالوگ و زنجیرهٔ تأمین      | ۸    | `model_catalog_raw.csv`, `license_policy.json`, `artifact_records.jsonl`, `resource_manifest.json` | `model_catalog_clean.csv`, `acceptance_plan.json`, `provenance.json`                                    |
| ۶   | ظرفیت و هزینه                      | ۸    | `hardware_inventory.csv`, `workloads.csv`, `cost_scenarios.json`                                   | `capacity_recommendation.json`                                                                          |
| ۷   | کوانتیزه‌سازی و GGUF               | ۱۰   | `quantization_lab.npz`, دو GGUF                                                                    | `quantization_selection.json`, `quant_test_predictions.npy`, `quantization_report.json`                 |
| ۸   | توکنایزر و تولید متن               | ۱۰   | `tokenizer_probes.jsonl`, `local_eval_dev.jsonl`, Q4                                               | `runtime_config.json`                                                                                   |
| ۹   | ارزیابی Q4 در برابر Q8             | ۱۰   | `local_eval_dev.jsonl`, `local_eval_test.jsonl`                                                    | `selection.json`, `test_predictions.jsonl`, `evaluation_report.json`, `error_audit.csv`                 |
| ۱۰  | صف و KV و cache                    | ۱۰   | `serving_requests.csv`                                                                             | `serving_report.json`                                                                                   |
| ۱۱  | adapter کم‌رتبه                    | ۱۰   | `sft_records_raw.jsonl`, `adapter_lab.npz`                                                         | `selected_adapter.npz`, `adapter_selection.json`, `adapter_test_predictions.npy`, `adapter_report.json` |
| ۱۲  | گردش کار HR                        | ۱۰   | `hr_policies.jsonl`, `hr_cases.jsonl`, `deployment_cases.jsonl`                                    | `local_agent.sqlite`, `agent_trace.json`, `security_tests.json`, `handoff_manifest.json`                |

## سه اصل حاکم بر کل تکلیف

1. **صداقت دربارهٔ مرز شواهد.** هر جا چیزی اجرا نشده، `False` یا `null` بگذار. ادعای بیش از شواهد در checker و در نمرهٔ تحلیل جریمه دارد.
2. **جداسازی انتخاب از ارزیابی.** تنظیمات فقط با train/dev؛ test یک بار و در پایان.
3. **مرز اعتماد در کد، نه در متن.** خروجی مدل داده است نه دستور؛ dispatcher کنترل دسترسی را اعمال می‌کند.
