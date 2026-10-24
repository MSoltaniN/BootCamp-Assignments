# نقشهٔ راه تکلیف ۵

۱۰۰ نمره | ۱۲ بخش | ۱۴۴ زیرسؤال (۴۸ مفهومی + ۹۶ عملی)

> 📌 **برای شروع از سند انتقال بخوان: [`HANDOFF.md`](HANDOFF.md)** — همهٔ وضعیت، محیط، قراردادها و قدم‌های بعدی آنجاست.

## وضعیت فعلی

| گام                                     | وضعیت                                                           |
| --------------------------------------- | --------------------------------------------------------------- |
| استخراج متن تکلیف از `5_ iCourse.mhtml` | ✅ `work/assignment.json` و `work/assignment_raw.md`            |
| دریافت بستهٔ دانشجو                     | ✅ `datasets/day5-student-pack.zip` → `assignment/source/Day5/` |
| پوشه‌بندی به‌ازای هر بخش                | ✅ `sections/section01..section12`                              |
| چک‌لیست ۱۴۴ زیرسؤال                     | ✅ `docs/03_question_checklist.md`                              |
| محیط پایتون                             | ⏳ `.venv` + `requirements-day5.txt`                            |
| منابع (۲ GGUF + llama-server)           | ⏳ `Day5_Starter/download_resources.py`                         |
| پاسخ مفهومی بخش‌های ۱–۴                 | ⏳                                                              |
| اجرای عملی بخش‌های ۵–۱۲                 | ⏳                                                              |

## مرز شواهد (مهم — در پاسخ‌ها تکرار شود)

طبق `START_HERE.md` و مقدمهٔ تکلیف:

- **اجرا شده در پاسخ مرجع:** دو quant مدل `Qwen2.5-0.5B-Instruct` (Q4_K_M و Q8_0)، HTTP محلی روی loopback، و adapter خطی کم‌رتبه روی یک لایهٔ ۱۶×۸.
- **شبیه‌سازی:** صف سرویس، continuous/static batching، KV بلوکی، cache ایزوله (بخش ۱۰).
- **اجرا نشده:** fine-tune کامل LLM، QLoRA، vLLM، SGLang، MoE بزرگ.

هر ادعای خلاف این مرز در پاسخ‌ها نمرهٔ منفی دارد (checker روی `MoE واقعاً اجرا شد؟` و `vLLM واقعاً اجرا شد؟` حساس است).

## ترتیب اجرا

1. **آماده‌سازی**: venv، نصب requirements، دانلود منابع با بررسی SHA-256.
2. **بخش ۱–۴ (مفهومی، ۲۴ نمره)**: گزینه + دلیل فارسی؛ بدون کد، اما دلیل باید به شواهد/سند ارجاع دهد.
3. **بخش ۵**: ممیزی کاتالوگ → `model_catalog_clean.csv`, `acceptance_plan.json`, `provenance.json`.
4. **بخش ۶**: ظرفیت و هزینه → `capacity_recommendation.json`, `capacity_matrix.csv`.
5. **بخش ۷**: کوانتیزه‌سازی عددی + parse دو GGUF واقعی → `quantization_selection.json`, `quant_test_predictions.npy`, `quantization_report.json`.
6. **بخش ۸**: llama-server واقعی، tokenizer، schema → `runtime_config.json`, `tokenizer_report.json`.
7. **بخش ۹**: ارزیابی Q4 در برابر Q8 روی dev، سپس فقط variant منتخب روی test → `selection.json`, `test_predictions.jsonl`, `evaluation_report.json`, `error_audit.csv`.
8. **بخش ۱۰**: شبیه‌سازی صف → `serving_report.json`, `serving_metrics.csv`.
9. **بخش ۱۱**: آموزش adapter روی `adapter_lab.npz` → `selected_adapter.npz`, `adapter_selection.json`, `adapter_test_predictions.npy`, `adapter_base_test_predictions.npy`, `adapter_report.json`.
10. **بخش ۱۲**: گردش کار HR + SQLite + امنیت → `local_agent.sqlite`, `agent_trace.json`, `security_tests.json`, `handoff_manifest.json`, `release_card.md`.
11. **بازرسی نهایی**: `python Day5_Grading/check_submission.py --submission Day5_Run_Output --datasets Day5_Datasets --output check.json`.

## وابستگی‌های سخت بین بخش‌ها

- بخش ۹ به بخش ۸ وابسته است (`runtime_config.json` و سرور Q4/Q8).
- بخش ۱۰ به بخش ۹ وابسته است (نتایج واقعی غیرهم‌زمان).
- بخش ۱۲ به بخش ۹ (`selection.json`) و بخش ۸ وابسته است.
- `handoff_manifest.json` باید **دقیقاً** همان ۱۲ آرتیفکت `REQUIRED_ARTIFACTS` باشد و hash هر فایل درست باشد.
