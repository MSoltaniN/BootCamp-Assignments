# بستهٔ شواهد — تکلیف ۴

## بازتولید

از ریشهٔ پروژه (جایی که `Day4_Code/` هست):

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install --no-cache-dir -r assignment\source\Day4\requirements-day4.txt
.venv\Scripts\python.exe work\sec06_12_pipeline\run_all.py        # بخش‌های ۶ تا ۱۲
.venv\Scripts\python.exe work\sec05_data\run_section5.py          # بخش ۵
.venv\Scripts\python.exe assignment\source\Day4\Day4_Grading\check_submission.py ^
    --application-db Day4_Run_Output\application.sqlite ^
    --checkpoint-db Day4_Run_Output\checkpoints.sqlite ^
    --output Day4_Run_Output\database_check.json
```

اجرای بخش‌های ۶ تا ۱۲ حدود ۲۰ ثانیه طول می‌کشد. `--root` را دستی تنظیم نکنید؛
مقدار پیش‌فرض همان `assignment/source/Day4` است که `Day4_Datasets/` را پیدا می‌کند.

## محتوا

| مسیر | توضیح |
|---|---|
| `application.sqlite` | پایگاه کاربرد با شش جدول: memor