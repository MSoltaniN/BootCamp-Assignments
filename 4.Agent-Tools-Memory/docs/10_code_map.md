# نقشهٔ کد و شواهد

راهنمای بازبینی: برای هر بخش، از این جدول به کد، خروجی و پاسخ برس.

## قاعدهٔ ساختار

| جای                       | چه چیزی                    | چرا                                                                                          |
| ------------------------- | -------------------------- | -------------------------------------------------------------------------------------------- |
| `Day4_Code/`              | ماژول‌های اجرایی، **مسطح** | `START_HERE.md` این نام‌ها را صریح می‌خواهد؛ `store.py` و `toolset.py` بین چند بخش مشترک‌اند |
| `work/secNN_*/`           | پاسخ و منطق هر بخش         | بازبینی بخش‌به‌بخش بدون خواندن کل پروژه                                                      |
| `work/sec06_12_pipeline/` | هماهنگ‌کنندهٔ اجرا         | بخش‌های ۶ تا ۱۲ به هم وابسته‌اند و ترتیبشان مهم است                                          |
| `Day4_Run_Output/`        | خروجی خام اجرا             | اعداد فرم از اینجا می‌آیند                                                                   |

---

## بخش ۵ — داده و مهندسی context

| قلم    | مسیر                                                                                          |
| ------ | --------------------------------------------------------------------------------------------- |
| کد     | [`work/sec05_data/context_ops.py`](../work/sec05_data/context_ops.py)                         |
| اجرا   | [`work/sec05_data/run_section5.py`](../work/sec05_data/run_section5.py)                       |
| پاسخ   | [`work/sec05_data/answers.py`](../work/sec05_data/answers.py)                                 |
| اعمال  | [`work/sec05_data/apply_section5.py`](../work/sec05_data/apply_section5.py)                   |
| خروجی  | [`Day4_Run_Output/section5.json`](../Day4_Run_Output/section5.json)                           |
| نمودار | [`Day4_Run_Output/coverage_by_department.png`](../Day4_Run_Output/coverage_by_department.png) |
| گزارش  | [`docs/09_section5_report.md`](09_section5_report.md)                                         |

## بخش ۶ — ابزارها و MCP

| قلم            | مسیر                                                                  |
| -------------- | --------------------------------------------------------------------- |
| کد سرور        | [`Day4_Code/mcp_server.py`](../Day4_Code/mcp_server.py)               |
| کد client      | [`Day4_Code/mcp_probe.py`](../Day4_Code/mcp_probe.py)                 |
| schema ابزارها | [`Day4_Code/toolset.py`](../Day4_Code/toolset.py)                     |
| پاسخ           | [`work/sec06_mcp/answers.py`](../work/sec06_mcp/answers.py)           |
| خروجی          | `Day4_Run_Output/sections_6_12.json` → `section6`                     |
| لاگ probe      | [`Day4_Run_Output/mcp_probe.json`](../Day4_Run_Output/mcp_probe.json) |

## بخش ۷ — حلقهٔ ابزار

| قلم   | مسیر                                                                                   |
| ----- | -------------------------------------------------------------------------------------- |
| کد    | [`Day4_Code/agent_lab.py`](../Day4_Code/agent_lab.py)                                  |
| پاسخ  | [`work/sec07_loop/answers.py`](../work/sec07_loop/answers.py)                          |
| خروجی | `section7` + [`Day4_Run_Output/agent_trace.json`](../Day4_Run_Output/agent_trace.json) |

## بخش ۸ — حافظه و تأیید انسانی

| قلم       | مسیر                                                                                                                          |
| --------- | ----------------------------------------------------------------------------------------------------------------------------- |
| کد پایگاه | [`Day4_Code/store.py`](../Day4_Code/store.py)                                                                                 |
| کد گراف   | [`Day4_Code/graph_memory.py`](../Day4_Code/graph_memory.py)                                                                   |
| پاسخ      | [`work/sec08_memory/answers.py`](../work/sec08_memory/answers.py)                                                             |
| پایگاه‌ها | [`application.sqlite`](../Day4_Run_Output/application.sqlite) · [`checkpoints.sqlite`](../Day4_Run_Output/checkpoints.sqlite) |
| checker   | [`Day4_Run_Output/database_check.json`](../Day4_Run_Output/database_check.json)                                               |

## بخش ۹ — مسیریابی

| قلم           | مسیر                                                                        |
| ------------- | --------------------------------------------------------------------------- |
| کد            | [`Day4_Code/router.py`](../Day4_Code/router.py)                             |
| پاسخ          | [`work/sec09_router/answers.py`](../work/sec09_router/answers.py)           |
| تنظیم قفل‌شده | [`locked_router_config.json`](../Day4_Run_Output/locked_router_config.json) |
| پیش‌بینی‌ها   | [`route_predictions.jsonl`](../Day4_Run_Output/route_predictions.jsonl)     |

## بخش ۱۰ — امنیت

| قلم   | مسیر                                                                  |
| ----- | --------------------------------------------------------------------- |
| کد    | [`Day4_Code/security.py`](../Day4_Code/security.py)                   |
| پاسخ  | [`work/sec10_security/answers.py`](../work/sec10_security/answers.py) |
| گزارش | [`redteam_reports.json`](../Day4_Run_Output/redteam_reports.json)     |

## بخش ۱۱ — ارزیابی

| قلم   | مسیر                                                          |
| ----- | ------------------------------------------------------------- |
| کد    | [`Day4_Code/evaluation.py`](../Day4_Code/evaluation.py)       |
| پاسخ  | [`work/sec11_eval/answers.py`](../work/sec11_eval/answers.py) |
| خروجی | `section11`                                                   |

## بخش ۱۲ — انتشار و تحویل

| قلم         | مسیر                                                                |
| ----------- | ------------------------------------------------------------------- |
| کد          | [`Day4_Code/rollout.py`](../Day4_Code/rollout.py)                   |
| پاسخ        | [`work/sec12_rollout/answers.py`](../work/sec12_rollout/answers.py) |
| gate        | [`regression_gate.json`](../Day4_Run_Output/regression_gate.json)   |
| Agent Card  | [`agent_card.json`](../Day4_Run_Output/agent_card.json)             |
| manifest    | [`handoff_manifest.json`](../Day4_Run_Output/handoff_manifest.json) |
| بررسی نهایی | [`handoff_check.json`](../Day4_Run_Output/handoff_check.json)       |
| مرز اجرا    | [`execution_scope.json`](../Day4_Run_Output/execution_scope.json)   |

---

## اجرای کامل

```cmd
.venv\Scripts\python.exe work\sec05_data\run_section5.py
.venv\Scripts\python.exe work\sec06_12_pipeline\run_all.py
.venv\Scripts\python.exe work\sec06_12_pipeline\apply_answers.py
.venv\Scripts\python.exe work\verify_bank.py
```

`mcp_probe.py` باید **قبل** از `run_all.py` اجرا شود تا `section6` نتایج probe زنده را ببیند:

```cmd
.venv\Scripts\python.exe Day4_Code\mcp_probe.py > Day4_Run_Output\mcp_probe.json 2>nul
```

## بازبینی مستقل

```cmd
.venv\Scripts\python.exe assignment\source\Day4\Day4_Grading\check_submission.py ^
  --root assignment\source\Day4 ^
  --application-db Day4_Run_Output\application.sqlite ^
  --checkpoint-db Day4_Run_Output\checkpoints.sqlite ^
  --output Day4_Run_Output\database_check.json
```

نتیجهٔ مورد انتظار: `status=passed` با ۱۴ کنترل موفق.

## بررسی بانک پاسخ

```cmd
.venv\Scripts\python.exe work\verify_bank.py
```

گزارش در `docs/generated/qa/_bank_verify.txt`.
