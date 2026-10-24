# راهنمای شروع دانشجو

۱. ASSIGNMENT.md را بخوانید و Student_Template.ipynb را تکمیل کنید. هر زیرسؤال سه سلول دارد: توضیح و صورت سؤال فارسی RTL، کد و کامنت انگلیسی، تحلیل فارسی RTL.

۲. وابستگی‌های requirements-day5.txt را نصب و منابع مشترک را استخراج کنید، یا `python Day5_Starter/download_resources.py` را بزنید. منابع بیش از یک گیگابایت‌اند. دو GGUF و موتور از URL و revision و hash ثابت دریافت می‌شوند. باینری همراه Windows x64 است؛ برای سیستم دیگر متغیر LLAMA_SERVER_PATH را به llama-server بومی سازگار تنظیم کنید.

۳. کد خود را در نوت‌بوک یا Day5_Code خودتان بنویسید. فایل مرجع local_lab.py مخصوص مدرس است. پیشنهاد ساخت ماژول شامل توابع زیر است؛ نام تابع اجباری نیست ولی قرارداد محاسبه باید رعایت شود:

| جزء | قرارداد |
|---|---|
| loader | خواندن CSV/JSONL/NPZ بدون pickle و اعتبارسنجی manifest |
| memory estimator | وزن total_b، سربار ۱۲٪، FP16 KV و رزرو سیستم با واحدهای روشن |
| toy quantizer | signed متقارن گروهی، scale برای گروه صفر امن، round و clip و pack واقعی |
| local runtime | اجرای process محدود به loopback، health check، timeout و cleanup در finally |
| client | /tokenize و /v1/chat/completions با schema و ثبت raw و usage و clock کلاینت |
| evaluator | پوشش همهٔ case_idها، تفکیک صحت و schema، انتخاب فقط با dev |
| adapter | پایهٔ منجمد و دو ماتریس rank محدود، انتخاب checkpoint با dev و ذخیرهٔ آرایهٔ عددی |
| HR dispatcher | فقط get_policy با policy_id؛ tenant از principal نرم‌افزار، هیچ ابزار حقوق یا استخدام |
| store | SQLite جدول runs با کلید یکتای تک‌ستونی و NOT NULL و منع تصمیم خودکار |

## فایل‌های لازم ZIP شواهد

کد و README بازاجرا به‌اضافهٔ selection.json، runtime_config.json، test_predictions.jsonl، selected_adapter.npz، adapter_selection.json، adapter_test_predictions.npy، quantization_selection.json، quant_test_predictions.npy، local_agent.sqlite، agent_trace.json، security_tests.json و handoff_manifest.json را تحویل دهید. raw predictionهای dev و خروجی آزمون auth و trace و مدل را هم برای review نگه دارید. وزن‌ها و باینری و دیتاست مشترک را در پاسخ دوباره نگذارید.

جدول SQLite به نام runs دارای ستون‌های `run_id TEXT`، `quant TEXT`، `days INTEGER`، `policy_id TEXT` و `approved INTEGER` است. همه NOT NULL؛ run_id یکتای مستقل و غیرخالی، days در بازهٔ ۰ تا ۳۶۶، approved همیشه صفر. فقط پاسخ grounded سیاست P-LEAVE با days=22 ذخیره می‌شود. اگر مدل fail-closed شد، جدول خالی و دلیل در trace و handoff ثبت شود؛ خروجی ساختگی نسازید. کد امن و تحلیل درست شکست، جدا از کیفیت مدل سنجیده می‌شوند.

در predictionهای test هر ردیف دارای case_id، language، split=test، quant، predicted_days با عدد صحیح یا null، schema_valid، raw، elapsed_s، prompt_tokens، completion_tokens و finish_reason باشد. expected_days و correct در این فایل نباشند. test gold لازم نیست و فیلدهای خصوصی فرم با «خصوصی» پر شوند.

بردارهای adapter با shapeهای a=(16,rank) و b=(rank,8) و scale=2/r ذخیره شوند. test prediction آن شکل ۱۲۸×۸ و خروجی quant شکل ۹۶×۹۶ دارد. scaler و rank و clipping را روی test تنظیم نکنید.

