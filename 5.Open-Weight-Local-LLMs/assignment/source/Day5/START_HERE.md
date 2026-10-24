# شروع تکلیف ۵

موضوع: مجوز و منشأ مدل، ظرفیت و هزینه، کوانتیزه‌سازی، اجرای واقعی دو quant محلی، ارزیابی فارسی و انگلیسی، صف و KV cache شبیه‌سازی‌شده، adapter کم‌رتبهٔ آموزشی و گردش کار امن HR.

۱. ZIP را کامل استخراج کن و Python 3.13 و یک محیط مجازی آماده کن. از ریشهٔ همین پوشه اجرا کن:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements-day5.txt
python -m ipykernel install --user --name bootcamp-day5
```

۲. صورت سؤال‌ها در ASSIGNMENT.md و صفحهٔ تکلیف سایت یکسان است. Student_Template.ipynb در Day5_Starter را باز کن و kernel محیط بالا را انتخاب کن. برای هر زیرسؤال عنوان «زیرسؤال N.M»، کد انگلیسی با خروجی اجرا و تحلیل فارسی راست‌به‌چپ را نگه دار. کدها و خروجی‌های لازم را در خود نوت‌بوک نشان بده؛ اگر ماژول جدا نوشتی در ZIP شواهد هم بگذار.

۳. پاسخ‌ها را در فرم داخل سایت بنویس؛ ذخیرهٔ پیش‌نویس و ارسال نهایی از همان صفحه است. نوت‌بوک اجراشده و ZIP شواهد، هرکدام حداکثر ۲۵ MiB و در مجموع حداکثر ۵۰ MiB، را در دو کارت پیوست بارگذاری کن. فرم HTML آفلاین و JSON خروجی آن برای این نسخه لازم نیست. هیچ سؤال اجباری نیست و سؤال خالی نمره ندارد.

۴. هر مفهومی ۶۰٪ گزینه با کد و ۴۰٪ دلیل دارد؛ هر عملی ۶۰٪ روش، کد و خروجی و ۴۰٪ تحلیل دارد. ایجنت، پاسخ و کد/خروجی نوت‌بوک و گزارش‌های ZIP را می‌خواند؛ کد تو اجرا نمی‌شود. گزارش checker خودت مدرک مستقل اجرای درست نیست. checker همراه برای بررسی محلی است و مدرس برای راستی‌آزمایی باید نسخهٔ مورد اعتماد خودش را استفاده کند.

۵. انتخاب مدل و تنظیمات فقط با train/dev است. برچسب‌های test، پاسخ مرجع و داده‌های خصوصی مدرس در این بسته نیست. فیلد معیار خصوصی را «خصوصی» بنویس. هیچ رمز یا API key واقعی در تحویل نگذار. وزن مدل، باینری و دیتاست مشترک را در ZIP پاسخ تکرار نکن.

مرز اجرای پاسخ مرجع: دو quant مدل Qwen2.5-0.5B-Instruct و HTTP محلی و adapter خطی آموزشی در پاسخ مرجع اجرا شده‌اند؛ صف و KV cache شبیه‌سازی‌اند و fine-tune کامل LLM، QLoRA، vLLM و MoE بزرگ اجرا نشده‌اند.

## منابع و شواهد روز پنجم

برای دریافت منابع ثابت و بررسی SHA-256، از ریشهٔ بسته اجرا کن:

```sh
python Day5_Starter/download_resources.py
```

دو GGUF روی هم حدود ۱٫۱۷ GB هستند؛ دریافت فقط هنگام آماده‌سازی لازم است. منابع از revision ثابت ناشر دریافت می‌شوند. موتور همراه دانلود برای Windows x64 است. در Linux/macOS یک llama-server بومی سازگار آماده و LLAMA_SERVER_PATH را تنظیم کن. inference روی loopback انجام می‌شود؛ حدود ۲ GB RAM آزاد به‌علاوهٔ محیط پایتون و داده‌ها توصیهٔ آزمایش است و زمان اجرا به دستگاه بستگی دارد. کتابخانهٔ PyTorch مطابق محیط خودت لازم است؛ این بسته fine-tune کامل LLM نیست.

در ZIP شواهد، کد و README بازاجرا، selection.json، runtime_config.json، test_predictions.jsonl، selected_adapter.npz، adapter_selection.json، adapter_test_predictions.npy، adapter_base_test_predictions.npy، quantization_selection.json، quant_test_predictions.npy، local_agent.sqlite، agent_trace.json، security_tests.json، handoff_manifest.json و سایر گزارش‌های عملی را بگذار. rawهای dev و خطاهای مدل را برای مرور نگه دار. Student_Template.ipynb و قراردادها در Day5_Starter هستند؛ Day5_Code/local_lab.py مرجع مدرس است و همراه بستهٔ دانشجو نیست.

```sh
python Day5_Grading/check_submission.py --submission Day5_Run_Output --datasets Day5_Datasets --output check.json
```

برچسب‌های test و adapter_test_y خصوصی‌اند. در سؤال‌های ۹.۶ و ۱۱.۹ مقدار خصوصی را «خصوصی» بنویس؛ فایل prediction و روش قابل بازتولید را تحویل بده. fail-closed درست را ثبت کن و برای جایگزینی شکست مدل، خروجی ساختگی تولید نکن.
