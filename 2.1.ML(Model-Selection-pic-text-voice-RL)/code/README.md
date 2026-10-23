# کد تکلیف ۲-۱

## نوت‌بوک جامع

**`all_sections.ipynb`** — همهٔ ده بخش در یک نوت‌بوک: بخش‌های ۱ تا ۴ به‌صورت متن/جدول و بخش‌های ۵ تا ۱۰ کد اجراشدنی با نمودار درون‌خطی. برای ساخت دوبارهٔ آن (بعد از تغییر اسکریپت‌ها یا فایل پاسخ‌ها):

```powershell
python make_all_notebook.py
```

## نوت‌بوک‌ها و اسکریپت‌های جداگانه

| فایل | کاربرد |
|---|---|
| `section5_bank.py` | بخش ۵ — طبقه‌بندی روی دادهٔ بانکی |
| `section5_bank.ipynb` | همان کد به‌صورت نوت‌بوک سلول‌به‌سلول، با توضیح فارسی |
| `section6_bike.py` | بخش ۶ — رگرسیون و مهندسی ویژگی برای تقاضای دوچرخه |
| `section6_bike.ipynb` | نوت‌بوک بخش ۶ |
| `section7_fashion.py` | بخش ۷ — MLP و CNN روی Fashion-MNIST (PyTorch) |
| `section7_fashion.ipynb` | نوت‌بوک بخش ۷ |
| `section8_spam.py` | بخش ۸ — تشخیص پیامک اسپم (TF-IDF + LR/NB/LinearSVC) |
| `section8_spam.ipynb` | نوت‌بوک بخش ۸ |
| `make_notebook.py` | تبدیل هر اسکریپت به نوت‌بوک (قالب jupytext percent) |
| `leak_demo.py` | نمایش عددی نشت `duration` در بخش ۵: با ستون ← ROC-AUC ۰٫۸۹۷، بدون ستون ← ۰٫۶۶۳ |
| `out/` | نمودارها، فایل‌های JSON نتایج و لاگ اجراها |

## اجرا

```powershell
cd "2.1.ML(Model-Selection-pic-text-voice-RL)/code"
python section5_bank.py
python section6_bike.py
python section7_fashion.py
python section8_spam.py
python section9_audio.py
python section10_qlearning.py
```

مسیر داده نسبی است (`../Day2_Datasets/...`)، پس از همین پوشه اجرا کن. خروجی‌ها در `out/` بازنویسی می‌شوند.

ساخت نوت‌بوک از اسکریپت:

```powershell
python make_notebook.py section7_fashion.py
```

## پیش‌نیاز

`scikit-learn ≥ 1.4` (اینجا ۱٫۹٫۱)، `torch ≥ 2.0` (اینجا ۲٫۱۴٫۱+cpu)، به‌همراه `pandas`، `numpy`، `matplotlib`. همه سیستمی نصب شده‌اند؛ نیازی به `PYTHONPATH` نیست.

## نکتهٔ محیطی

اگر اسکریپت را از داخل سندباکس اجرا می‌کنی (مثل محیط همین تکلیف):

- برای بخش‌های ۵ و ۶ `OMP_NUM_THREADS=1` را ست کن. در غیر این صورت `HistGradientBoosting` تلاش می‌کند یک `ThreadPool` بسازد و با `PermissionError: [WinError 5]` روی ساخت named pipe شکست می‌خورد.
- بخش ۷ به این تنظیم نیاز ندارد (torch از OpenMP استفاده می‌کند نه `multiprocessing`). اگر کند بود، `torch.set_num_threads(...)` را کم کن.

```powershell
$env:OMP_NUM_THREADS = '1'
```

## زمان اجرا (CPU، ۱۲ رشته)

- بخش ۵: حدود ۲ دقیقه
- بخش ۶: کمتر از ۱ دقیقه
- بخش ۷: حدود ۹ دقیقه (MLP ۷۰ ثانیه + CNN ۴۵۵ ثانیه)
- بخش ۸: چند ثانیه
- بخش ۹: حدود ۲ دقیقه (استخراج ویژگی ۲ ثانیه + دو آموزش CNN ~۴۵ ثانیه‌ای)

## نتیجهٔ بازتولید

با بذر ثابت (`RANDOM_STATE` / `SEED = 42`) عددها تکرارپذیرند:

- **بخش ۵:** آستانه ۰٫۱۴۵، هزینهٔ اعتبارسنجی ۲٬۸۷۲، PR-AUC آزمون ۰٫۴۷۲۹، ROC-AUC آزمون ۰٫۶۱۰۱
- **بخش ۶:** MAE اعتبارسنجی ۴۲٫۲۲، MAE آزمون ۴۹٫۳۹، RMSE آزمون ۷۲٫۹۸ (با هدف پواسون: ۳۹٫۶۳ روی اعتبارسنجی)
- **بخش ۷:** MLP اعتبارسنجی ۰٫۹۰۲۵ · CNN اعتبارسنجی ۰٫۹۲۶۲ · آزمون ۰٫۹۱۵۱ و Macro-F1 ۰٫۹۱۴۷
- **بخش ۸:** NB بهترین Macro-F1 اعتبارسنجی ۰٫۹۶۶ · آستانه ۰٫۱۶ · آزمون Precision ۰٫۹۳۵ و Recall ۰٫۹۱۰
- **بخش ۹:** SVM تصادفی ۰٫۹۹۳۲ و گویندهٔ جدید ۰٫۶۳۴۸ · CNN تصادفی ۰٫۹۸۳۳ و گویندهٔ جدید ۰٫۶۲۷۹
- **بخش ۱۰:** سیاست آموخته‌شده پاداش ۰٫۹۵ و موفقیت ۱۰۰٪ · عامل تصادفی −۱٫۰۱۱۵ و ۳٫۵٪
