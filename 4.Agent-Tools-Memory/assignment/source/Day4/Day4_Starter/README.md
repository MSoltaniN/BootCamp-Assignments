# شروع پیاده‌سازی روز چهارم

این پوشه راهنمای ساخت کد شماست. صورت تمرین و نام فایل دادهٔ مربوط به هر بخش در ASSIGNMENT.md و صفحهٔ تکلیف سایت آمده است. کد کامل پاسخ مرجع فقط در بستهٔ مدرس قرار دارد.

ساختار پیشنهادی پیاده‌سازی:

- `Day4_Code/agent_lab.py`: principal، سه ابزار خواندنی، اعتبارسنجی profile، حلقهٔ محدود و ذخیره‌سازی.
- `Day4_Code/mcp_server.py`: سرور با سه ابزار و یک resource و یک prompt، با stdio و SDK رسمی MCP.
- `Day4_Code/mcp_probe.py`: client مستقل برای کشف قابلیت و اجرای فراخوانی‌های مجاز و نامجاز.
- `Day4_Run_Output`: خروجی‌های ساخته‌شده توسط نوت‌بوک شما.

سه ابزار پایه: `get_employee(employee_id)`، `get_department_context(department)` و `get_evidence(employee_id)`. آرگومان tenant یا نقش مدیر از مدل دریافت نشود؛ scope از principal قابل اعتماد برنامه بیاید. برای POC می‌توانید principal مصنوعی و fixture تصمیم‌گیر داشته باشید ولی آن را احراز هویت یا LLM زنده معرفی نکنید.

خروجی پروفایل شامل employee_id، department، claims با skill و evidence_id و quote، limitations و decision=skills_inventory_only است. رکورد نامعتبر باید خطای مشخص بدهد. ساخت تصمیم استخدام یا حقوق در دامنهٔ تمرین نیست.

برای آداپتور مدل، رابط `next_action(employee_id, observations)` پیشنهاد می‌شود. خروجی tool شامل kind، name و arguments و خروجی نهایی شامل kind و text است. می‌توانید تصمیم‌گیر قطعی کنترل‌شده بسازید تا حلقه و failureها بدون سرویس پولی آزمایش شوند. آداپتور قابل جایگزینی LLM و مرز اجراشده/اجرانشده را در تحویل توضیح دهید.

SQLite این تمرین نیاز به سرویس شبکه ندارد. نام جدول‌های لازم برای checker در Day4_Grading/README.md آمده است. پس از تولید پایگاه، checker را از فرایند جدا اجرا کنید. پاسخ عددی بدون کد و شواهد یا JSON گزارش به‌تنهایی کافی نیست.
