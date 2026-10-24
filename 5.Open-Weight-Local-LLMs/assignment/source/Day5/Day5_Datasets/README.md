# فرهنگ دادهٔ روز پنجم

همهٔ داده‌های این پوشه مصنوعی و با seed=20261017 ساخته شده‌اند؛ هیچ سابقهٔ واقعی HR یا قیمت بازار در آن نیست. مدل‌های واقعی و مجوزشان در پوشهٔ جداگانهٔ Day5_Resources قرار دارند.

| بخش | فایل | grain و معنی |
|---|---|---|
| ۵ | model_catalog_raw.csv | یک مدل ساختگی در هر ردیف؛ ۱۳ ردیف شامل یک تکرار کامل، ۱۲ مدل یکتا؛ total_b و active_b میلیارد پارامتر |
| ۵ | license_policy.json | policy آموزشی allow/review/deny؛ اطلاعات حقوقی واقعی خانواده‌های مدل نیست |
| ۵ | artifact_records.jsonl و artifact_samples | دو نمونهٔ بایتی غیرقابل اجرای آموزشی برای hash؛ وزن واقعی نیستند |
| ۶ | hardware_inventory.csv | هشت گزینهٔ ساختگی؛ ظرفیت و رزرو GiB، bandwidth بر حسب GB/s ده‌دهی، توان W و قیمت USD |
| ۶ | workloads.csv | شش سناریو؛ prompt_tokens و max_new_tokens برای هر درخواست، concurrency تعداد درخواست فعال، weight_bits دقت ایده‌آل وزن |
| ۶ | cost_scenarios.json | قیمت و توان و حجم درخواست ساختگی؛ ماه با ۱۶۰ ساعت فعالیت، استهلاک ۳۶ماهه |
| ۷ | quantization_lab.npz | weights با شکل ۹۶×۴۸ و outlier؛ calibration با ۳۸۴ نمونه و dev و test هرکدام ۹۶×۴۸؛ هیچ دادهٔ مدل واقعی نیست |
| ۸ | tokenizer_probes.jsonl | شش ورودی ثابت انگلیسی، فارسی، کد و تفاوت Unicode؛ probe_id یکتا |
| ۹ | local_eval_dev.jsonl | ۱۲ QA با برچسب expected_days عمومی؛ شش انگلیسی و شش فارسی؛ هر case یک خانوادهٔ مستقلِ شناسه‌گذاری‌شده |
| ۹ | local_eval_test.jsonl | ۱۲ QA بدون expected_days؛ شناسه و متن نرمال‌شده با dev اشتراک ندارند؛ gold فقط مدرس |
| ۱۰ | serving_requests.csv | ۶۰۰ ورود مرتب؛ arrival_s از مبدأ سناریو، prompt/output token، tenant و prefix_id؛ لاگ runtime واقعی نیست |
| ۱۱ | sft_records_raw.jsonl | ۴۳ جفت prompt-response شامل PII مصنوعی، خالی و تکرار؛ split و source_group برای ممیزی |
| ۱۱ | adapter_lab.npz | پایهٔ ۱۶×۸؛ train با ۵۱۲ و dev و test هرکدام ۱۲۸ نمونهٔ ۱۶ویژگی؛ train_y و dev_y عمومی، test_y خصوصی |
| ۱۲ | hr_policies.jsonl | سه سیاست؛ دو org-a و یک org-b؛ days در سیاست مرخصی واقعیت منبع است و برای grounding استفاده می‌شود |
| ۱۲ | hr_cases.jsonl | چهار سناریو و expected_tool برای سنجش اقدام؛ هیچ تصمیم استخدام واقعی نیست |
| ۱۲ | deployment_cases.jsonl | پنج پیکربندی policy با نتیجهٔ آموزشی مورد انتظار؛ penetration test واقعی نیست |
| همه | dataset_manifest.json | مسیر نسبی، تعداد بایت و SHA-256 ورودی‌ها؛ خود manifest و README داخل فهرست نیستند |

شناسه‌های split جای بررسی متن را نمی‌گیرند. نبود تکرار دقیق به معنی تعمیم گسترده نیست؛ QAها عمداً ساده و موضوعی‌اند. برچسب پاسخ در dev برای تنظیم و در test فقط برای مدرس است. رشتهٔ متن سیاست test حاوی واقعیت لازم برای پاسخ است، ولی مقدار خروجی gold جدا عرضه نمی‌شود.

در روابط ظرفیت، GB=10^9 بایت و GiB=2^30 بایت است. KV با دو مؤلفهٔ K و V، تعداد لایه، KV head و head dimension، دو بایت FP16، کل prompt+output و concurrency محاسبه شود. وزن از total_b به دست می‌آید. سربار و رزرو سخت‌افزار مستقل‌اند.
