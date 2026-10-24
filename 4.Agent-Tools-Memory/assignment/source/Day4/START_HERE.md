# شروع تکلیف ۴

موضوع: معماری ایجنت و Workflow، مهندسی context، ابزارهای محدود و MCP واقعی، حلقهٔ محدود، حافظهٔ پایدار و تأیید انسانی، مسیریابی، دفاع چندلایه، ارزیابی و انتشار کنترل‌شده.

۱. ZIP را کامل استخراج کن و Python 3.13 و یک محیط مجازی آماده کن. از ریشهٔ همین پوشه اجرا کن:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements-day4.txt
python -m ipykernel install --user --name bootcamp-day4
```

۲. صورت سؤال‌ها در ASSIGNMENT.md و صفحهٔ تکلیف سایت یکسان است. Student_Template.ipynb در Day4_Starter را باز کن و kernel محیط بالا را انتخاب کن. برای هر زیرسؤال عنوان «زیرسؤال N.M»، کد انگلیسی با خروجی اجرا و تحلیل فارسی راست‌به‌چپ را نگه دار. کدها و خروجی‌های لازم را در خود نوت‌بوک نشان بده؛ اگر ماژول جدا نوشتی در ZIP شواهد هم بگذار.

۳. پاسخ‌ها را در فرم داخل سایت بنویس؛ ذخیرهٔ پیش‌نویس و ارسال نهایی از همان صفحه است. نوت‌بوک اجراشده و ZIP شواهد، هرکدام حداکثر ۲۵ MiB و در مجموع حداکثر ۵۰ MiB، را در دو کارت پیوست بارگذاری کن. فرم HTML آفلاین و JSON خروجی آن برای این نسخه لازم نیست. هیچ سؤال اجباری نیست و سؤال خالی نمره ندارد.

۴. هر مفهومی ۶۰٪ گزینه با کد و ۴۰٪ دلیل دارد؛ هر عملی ۶۰٪ روش، کد و خروجی و ۴۰٪ تحلیل دارد. ایجنت، پاسخ و کد/خروجی نوت‌بوک و گزارش‌های ZIP را می‌خواند؛ کد تو اجرا نمی‌شود. گزارش checker خودت مدرک مستقل اجرای درست نیست. checker همراه برای بررسی محلی است و مدرس برای راستی‌آزمایی باید نسخهٔ مورد اعتماد خودش را استفاده کند.

۵. انتخاب مدل و تنظیمات فقط با train/dev است. برچسب‌های test، پاسخ مرجع و داده‌های خصوصی مدرس در این بسته نیست. فیلد معیار خصوصی را «خصوصی» بنویس. هیچ رمز یا API key واقعی در تحویل نگذار. وزن مدل، باینری و دیتاست مشترک را در ZIP پاسخ تکرار نکن.

مرز اجرای پاسخ مرجع: SQLite، MCP و گراف در پاسخ مرجع واقعاً اجرا شده‌اند؛ تصمیم‌گیر مدل، هویت reviewer و لاگ‌های مقایسه fixture هستند و LLM زنده اجرا نشده است.

## اجرا و شواهد روز چهارم

SQLite سرویس شبکه و رمز نمی‌خواهد. MCP از SDK رسمی با stdio استفاده می‌کند. LLM پولی لازم نیست؛ fixture قطعی مجاز است و باید صریحاً آن را ثبت کنی. راهنمای ابزارها و قرارداد principal در Day4_Starter/README.md و schema پایگاه در Day4_Grading/README.md است.

از ریشهٔ بسته، دو فایل ساخته‌شدهٔ خودت را محلی بررسی کن (مسیر خروجی‌ها را در صورت نیاز عوض کن):

```sh
python Day4_Grading/check_submission.py --root . --application-db Day4_Run_Output/application.sqlite --checkpoint-db Day4_Run_Output/checkpoints.sqlite --output Day4_Run_Output/database_check.json
```

در ZIP شواهد، کدهای خودت، README بازاجرا، application.sqlite، checkpoints.sqlite، database_check.json، route_predictions.jsonl برای همهٔ test، locked_router_config.json، agent_trace.json و گزارش‌های ساخته‌شدهٔ بخش‌های ۵ تا ۱۲ (به‌خصوص full_evidence.json، handoff_manifest.json و handoff_check.json) را بگذار. همهٔ گزارش‌های عملی و ده آزمون امنیتی لازم‌اند. نسخهٔ مدرس Day4_Code و Day4_Run_Output را عمداً همراه بسته منتشر نمی‌کند؛ این خروجی‌ها و ماژول‌ها را خودت بساز.
