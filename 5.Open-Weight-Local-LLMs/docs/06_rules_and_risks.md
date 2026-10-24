# قواعد، قراردادها و ریسک‌ها

## قواعد سخت تکلیف

1. **انتخاب فقط با train/dev.** برچسب `test` و پاسخ مرجع در بسته نیست. هر تنظیمی که با `test` انتخاب شود نمرهٔ آن سؤال را از دست می‌دهد.
2. **فیلد معیار خصوصی را «خصوصی» بنویس.** سه جای مشخص: سؤال ۹.۶ (accuracy خصوصی)، سؤال ۱۱.۹ (MSE test خصوصی).
3. **هیچ رمز یا API key واقعی در فایل‌ها نگذار.**
4. **وزن مدل، باینری و دیتاست مشترک را در ZIP پاسخ تکرار نکن.** سقف هر پیوست ۲۵ MiB و مجموع ۵۰ MiB.
5. **هیچ سؤال اجباری نیست؛** سؤال خالی نمره نمی‌گیرد، اما ادعای خلاف شواهد جریمه دارد.
6. **fail-closed را ثبت کن.** اگر مدل شکست خورد، `null` بگذار — خروجی ساختگی نساز.

## قواعد ساختاری که checker اعمال می‌کند

| مورد                           | قاعده                                                                                                                                                                                                                                           |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `selection.json`               | `selection_split="dev"` و `test_used_for_selection=false` و `model_revision` برابر `9217f5db79a29953eb74d5343926648285ec7e67` و `hashes` دقیقاً همان دو SHA                                                                                     |
| `runtime_config.json`          | `engine="llama.cpp"`, `context=2048`, `threads=4`, `network="loopback"`                                                                                                                                                                         |
| `test_predictions.jsonl`       | شناسه‌ها یکتا و کامل برابر `local_eval_test.jsonl`؛ هر ردیف بدون `expected_days`/`correct`; `predicted_days` عدد صحیح یا `null` در `[0,366]`؛ `finish_reason ∈ {stop,length}`؛ `elapsed_s>0`؛ `prompt_tokens>0`؛ `schema_valid` با `raw` سازگار |
| `selected_adapter.npz`         | `a (16,rank)`, `b (rank,8)`, `scale == 2/rank`؛ بدون pickle                                                                                                                                                                                     |
| `adapter_test_predictions.npy` | شکل `(128,8)` برابر `test_x @ (base_weight + scale*a@b)`                                                                                                                                                                                        |
| `quantization_selection.json`  | `bits=4`, `group_size=16`, `percentile ∈ {100,99,95}`, `selection_split="dev"`, `toy_not_gguf=true`                                                                                                                                             |
| `quant_test_predictions.npy`   | شکل `(96,96)` برابر `test @ reconstructed.T`                                                                                                                                                                                                    |
| `local_agent.sqlite`           | جدول `runs` با ۵ ستون دقیق، همه `NOT NULL`، ایندکس یکتا روی `run_id`، بدون trigger، قیود در حافظه هم فعال                                                                                                                                       |
| `agent_trace.json`             | دقیقاً ۳ گام با `step=[1,2,3]` و `kind[0]="model_plan"`, `kind[-1]="model_extract"`                                                                                                                                                             |
| `handoff_manifest.json`        | `files` مجموعهٔ دقیقاً ۱۱ آرتیفکت با SHA-256 درست؛ بدون خودش                                                                                                                                                                                    |
| `security_tests.json`          | سه فلگ مشخص                                                                                                                                                                                                                                     |

## ریسک‌های اصلی

### ریسک ۱ — ادعای اجرای چیزی که اجرا نشده

checker روی `MoE واقعاً اجرا شد؟`، `vLLM واقعاً اجرا شد؟`، `QLoRA اجرا شده؟` حساس است. اگر `True` بنویسی و شواهد نباشد، رد می‌شوی. **همیشه `False` با توضیح مرز.**

### ریسک ۲ — نشت برچسب در انتخاب

`test_used_for_selection` باید `false` باشد. حتی اگر مدل با Q8 روی test بهتر بود، انتخاب باید بر اساس dev باشد.

### ریسک ۳ — `schema_valid` ناسازگار با `raw`

اگر `raw` یک JSON با تنها کلید `days` و مقدار صحیح باشد، `schema_valid` **باید** `true` و `predicted_days` برابر همان عدد باشد. اگر `raw` ناقص است، `schema_valid=false` و `predicted_days=null`.

### ریسک ۴ — قفل SQLite

`days` باید `INTEGER` و فقط ۲۲ پذیرفته شود (چون `P-LEAVE` روزهای ۲۲ دارد). مقدار ۲۳ یا ۱۴ رد می‌شود. `approved` همیشه `0`.

### ریسک ۵ — مسیر آرتیفکت‌ها

همهٔ آرتیفکت‌ها باید مستقیماً در ریشهٔ `Day5_Run_Output/` باشند، نه در زیرپوشه. پوشه‌های `sections/*/out/` فقط برای سازمان‌دهی کار هستند؛ فایل نهایی باید در ریشه کپی شود.

### ریسک ۶ — محیط

`requirements-day5.txt` نسخه‌های آینده‌دار دارد (`numpy==2.4.2`, `pandas==3.0.0`, `torch==2.13.0`) که ممکن است روی PyPI موجود نباشند. اگر `pip install` شکست خورد:

- `numpy`, `pandas`, `matplotlib`, `requests`, `nbformat`, `nbclient`, `ipykernel` را بدون پین نصب کن.
- `torch` فقط برای بخش ۱۱ لازم نیست (پیاده‌سازی دستی با numpy کافی است) — طبق متن، adapter با numpy آموزش می‌بیند.

## محدودیت checker

طبق خروجی خودش:

- کد دانشجو اجرا نمی‌شود.
- فقط سازگاری آرتیفکت‌ها را بررسی می‌کند، نه اثبات inference واقعی.
- مدرس در محیط ایزوله دوباره اجرا می‌کند و استدلال را جدا نمره می‌دهد.
