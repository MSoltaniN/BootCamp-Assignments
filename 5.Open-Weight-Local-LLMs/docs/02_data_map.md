# نقشهٔ داده‌ها (تأییدشده با بازرسی واقعی فایل‌ها)

مسیر پایه: `assignment/source/Day5/`
همهٔ داده‌ها مصنوعی با `seed=20261017`؛ هیچ سابقهٔ واقعی HR یا قیمت بازار در آن نیست.

## بخش ۵ — ممیزی کاتالوگ

| فایل                                                    | واقعیت بازرسی‌شده                                                                                                                                                                                                                                     |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Day5_Datasets/model_catalog_raw.csv`                   | **۱۳ ردیف**، **۱۲ مدل یکتا**؛ `M03` دو بار تکرار شده (تکرار کامل بایت‌به‌بایت). ستون‌ها: `model_id,name,total_b,active_b,architecture,license_id,commercial_allowed,instruct,context_limit,layers,kv_heads,head_dim,revision,publisher_verified,task` |
| `Day5_Datasets/license_policy.json`                     | `policy_id=exercise-policy-v1`; `auto_allow=["Apache-2.0","MIT"]`; `review=["Community","Custom"]`; `deny=["NonCommercial"]`; `missing="review"`                                                                                                      |
| `Day5_Datasets/artifact_records.jsonl`                  | ۲ ردیف: `safe_model.safetensors` (trusted=true, sha `0712622d…c387f9`) و `untrusted_model.bin` (format=pickle, trusted=false, sha عمداً `0000…0000`)                                                                                                  |
| `Day5_Datasets/artifact_samples/safe_model.safetensors` | ۴۰ بایت                                                                                                                                                                                                                                               |
| `Day5_Datasets/artifact_samples/untrusted_model.bin`    | ۳۰ بایت؛ sha واقعی `a1bf7351…acd5ed` ≠ مقدار انتظاری صفر                                                                                                                                                                                              |
| `Day5_Resources/resource_manifest.json`                 | `model_revision=9217f5db79a29953eb74d5343926648285ec7e67`, `runtime_release=b11696`                                                                                                                                                                   |
| `Day5_Datasets/dataset_manifest.json`                   | شامل path/bytes/sha256؛ خود manifest و README داخل فهرست نیستند                                                                                                                                                                                       |

نکتهٔ کلیدی کاتالوگ: مدل‌های زیر ۳۲۷۶۸ context یا `instruct=False` یا `status≠allow` کاندیدای سؤال ۵.۵ نیستند.

- `license_id` خالی فقط برای `M10` (Orchid-35B-A3B-Unreviewed) که `publisher_verified=False` هم دارد → `review`.

## بخش ۶ — ظرفیت و هزینه

| فایل                     | واقعیت بازرسی‌شده                                                                                                                                                                                                                                     |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `hardware_inventory.csv` | **۸ ردیف**: H01 CPU 16GiB/4 reserve; H02 GPU24 24/2; H03 Unified64 64/12; H04 Unified128 128/24; H05 GPU48 48/4; H06 GPU80 80/8; H07 GPU32 32/3; H08 CPUserver 128/24                                                                                 |
| `workloads.csv`          | **۶ ردیف**: W01(M03,4bit,2048,4,128); W02(M04,4bit,4096,8,256); W03(M05,4bit,8192,4,512); W04(M07,4bit,4096,1,256); W05(M01,8bit,1024,1,64); W06(M06,8bit,8192,8,256)                                                                                 |
| `cost_scenarios.json`    | capex=3000 USD; amortization=36 ماه; hours/month=160; power=140W; electricity=0.15 USD/kWh; ops=35 USD/ماه; input=1.0/1M; output=3.0/1M; 800 input و 200 output به‌ازای هر درخواست; requests_month=[1000,10000,100000,1000000]; capacity=300 req/hour |

قواعد محاسبه (طبق متن تکلیف):

- `GiB = 2**30` بایت، `GB = 10**9` بایت.
- وزن خام از `total_b` (نه `M04.active_b`).
- `KV = 2 (K,V) × layers × kv_heads × head_dim × 2 bytes × (prompt_tokens + max_new_tokens) × concurrency`.
- سربار = ۱۲٪ وزن (در ۶.۱۱ به ۲۰٪ تغییر می‌کند)، مستقل از `reserved_gib` سخت‌افزار.
- `fits ⟺ total_gib <= capacity_gib - reserved_gib`.

## بخش ۷ — کوانتیزه‌سازی

| فایل                                                      | واقعیت بازرسی‌شده                                                                |
| --------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `quantization_lab.npz`                                    | `weights (96,48) float32`; `calibration (384,48)`; `dev (96,48)`; `test (96,48)` |
| `Day5_Resources/models/qwen2.5-0.5b-instruct-q4_k_m.gguf` | ۴۹۱٬۴۰۰٬۰۳۲ بایت، sha `74a4da8c…d7a9db`                                          |
| `Day5_Resources/models/qwen2.5-0.5b-instruct-q8_0.gguf`   | ۶۷۵٬۷۱۰٬۸۱۶ بایت، sha `ca59ca7f…76844e`                                          |

قرارداد checker برای انتخاب کوانتیزه (سخت‌گیرانه — باید دقیقاً رعایت شود):

```json
{"bits": 4, "group_size": 16, "percentile": 100|99|95, "selection_split": "dev", "toy_not_gguf": true}
```

`quant_test_predictions.npy` باید شکل `(96, 96)` داشته باشد و برابر `test @ reconstructed.T` باشد، جایی که:

```python
blocks = weights.reshape(96, 3, 16)
bounds = np.percentile(np.abs(blocks), percentile, axis=2, keepdims=True)
scales = np.where(bounds > 0, bounds / 7, 1).astype("float32")
reconstructed = (np.clip(np.rint(blocks/scales), -7, 7) * scales).reshape(96, 48)
```

## بخش ۸ — توکنایزر و مدل محلی

| فایل                     | واقعیت بازرسی‌شده                                                                                                |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| `tokenizer_probes.jsonl` | **۶ ردیف**؛ `probe_id` یکتا: `english`, `persian`, و ۴ مورد دیگر (کد + دو گزینهٔ Unicode فارسی)                  |
| `local_eval_dev.jsonl`   | **۱۲ ردیف**، ۶ انگلیسی + ۶ فارسی، با `expected_days` عمومی؛ کلیدها: `case_id,family,language,text,expected_days` |

الزامات اجرا: llama-server روی loopback، CPU، ۴ thread، ۱ slot، `context=2048`. هر سلول HTTP باید context manager باشد تا سرور حتی در خطا بسته شود.

## بخش ۹ — ارزیابی Q4 در برابر Q8

| فایل                    | واقعیت بازرسی‌شده                                                        |
| ----------------------- | ------------------------------------------------------------------------ |
| `local_eval_dev.jsonl`  | ۱۲ مورد با برچسب عمومی                                                   |
| `local_eval_test.jsonl` | **۱۲ ردیف بدون `expected_days`**؛ کلیدها: `case_id,family,language,text` |

قرارداد `selection.json` (checker):

```json
{
  "selection_split": "dev",
  "test_used_for_selection": false,
  "model_revision": "9217f5db79a29953eb74d5343926648285ec7e67",
  "selected_quant": "q4_k_m" | "q8_0",
  "hashes": {
    "qwen2.5-0.5b-instruct-q4_k_m.gguf": "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db",
    "qwen2.5-0.5b-instruct-q8_0.gguf": "ca59ca7f13d0e15a8cfa77bd17e65d24f6844b554a7b6c12e07a5f89ff76844e"
  }
}
```

قرارداد `runtime_config.json`: `engine="llama.cpp"`, `context=2048`, `threads=4`, `network="loopback"`.

قرارداد هر ردیف `test_predictions.jsonl`: کلیدهای `case_id, predicted_days, quant, split, raw, language, finish_reason, elapsed_s, prompt_tokens, completion_tokens, schema_valid` — و **نباید** شامل `expected_days` یا `correct` باشد. `elapsed_s > 0`، `prompt_tokens > 0`. اگر `raw` یک JSON با تنها کلید `days` باشد، باید `schema_valid=true` و `predicted_days` برابر همان عدد.

## بخش ۱۰ — صف و KV

| فایل                   | واقعیت بازرسی‌شده                                                                                                       |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `serving_requests.csv` | **۶۰۰ ردیف** مرتب بر `arrival_s`؛ ستون‌ها: `request_id,arrival_s,prompt_tokens,output_tokens,prefix_id,tenant,priority` |

فرض‌های شبیه‌سازی (نه اندازه‌گیری): decode = ۳۵ گام/ثانیه برای هر batch، prefill = ۶۰۰ token/ثانیه تجمیعی، `slot=4`.

## بخش ۱۱ — adapter کم‌رتبه

| فایل                    | واقعیت بازرسی‌شده                                                                                                                           |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `sft_records_raw.jsonl` | **۴۳ ردیف**؛ کلیدها: `pii,prompt,record_id,response,source_group,split`                                                                     |
| `adapter_lab.npz`       | `base_weight (16,8)`; `train_x (512,16)`; `train_y (512,8)`; `dev_x (128,16)`; `dev_y (128,8)`; `test_x (128,16)` — **`test_y` وجود ندارد** |

قرارداد آموزش: پایه منجمد، `scale = alpha/r` با `alpha=2`، Adam، ۲۵۰ epoch، seed ثابت.
قرارداد ذخیره: `selected_adapter.npz` با آرایه‌های `a (16,rank)`, `b (rank,8)`, `scale` (اسکالر) — `allow_pickle=False`.
`adapter_selection.json`: `rank ∈ {1,2,4}`, `base_frozen=true`, `selection_split="dev"`.
`adapter_test_predictions.npy`: شکل `(128,8)` و برابر `test_x @ (base_weight + scale * a @ b)` با `atol=rtol=1e-5`.

## بخش ۱۲ — گردش کار HR

| فایل                     | واقعیت بازرسی‌شده                                                                                                    |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| `hr_policies.jsonl`      | **۳ ردیف**؛ `P-LEAVE` (org-a, days=22), `P-TRAVEL` (org-a, days=null), یک سیاست org-b که نباید با `org-a` خوانده شود |
| `hr_cases.jsonl`         | **۴ ردیف**؛ `expected_tool="get_policy"` برای همه                                                                    |
| `deployment_cases.jsonl` | **۵ ردیف**؛ کلیدها: `auth,case_id,expected,host,redact,remote_code,telemetry`                                        |

قرارداد `local_agent.sqlite` (بسیار سخت‌گیرانه — checker در حافظه هم تست می‌کند):

- جدول `runs` با ستون‌های **دقیقاً**: `run_id TEXT, quant TEXT, days INTEGER, policy_id TEXT, approved INTEGER`
- همهٔ ستون‌ها `NOT NULL`.
- ایندکس یکتای تک‌ستونی روی `run_id`.
- **بدون trigger**.
- قیود باید این‌ها را رد کنند: `run_id` خالی، فاصله، `NULL`، `days=-1`، `days=367`، `approved=1`.
- ردیف نهایی: `days=22`, `policy_id='P-LEAVE'`, `approved=0`, `quant` برابر انتخاب بخش ۹.

قرارداد `agent_trace.json`: آرایهٔ **۳ مرحله‌ای** با `step` برابر `[1,2,3]`؛ `trace[0].kind=="model_plan"`، `trace[-1].kind=="model_extract"`.

- اگر `accepted=true` → `trace[0].plan == {"action":"get_policy","policy_id":"P-LEAVE"}` و `trace[1].kind=="readonly_tool"` با `policy_id="P-LEAVE"`.
- اگر `accepted=false` → `trace[1].kind=="stop"` و `trace[-1].days is None` و `trace[-1].grounded is False`.

قرارداد `handoff_manifest.json`: `assignment="day5"`, `selected_quant`, `days`, `grounded`, و `files` که مجموعهٔ `path` آن **دقیقاً** برابر **۱۱** آرتیفکت زیر است با SHA-256 صحیح (همان `REQUIRED_ARTIFACTS` در checker):

```
selection.json, runtime_config.json, test_predictions.jsonl, selected_adapter.npz,
adapter_selection.json, adapter_test_predictions.npy, quantization_selection.json,
quant_test_predictions.npy, local_agent.sqlite, agent_trace.json, security_tests.json
```

`handoff_manifest.json` **نباید** خودش را در `files` فهرست کند؛ checker با `set(names) != REQUIRED_ARTIFACTS` شکست می‌خورد. نام تکراری هم مردود است. هر فایل باید مستقیماً در ریشهٔ `Day5_Run_Output` باشد (`p.parent == root`)، symlink نباشد و از ۲۰ MiB بزرگ‌تر نباشد.

قرارداد `security_tests.json`: `cross_tenant_injection_blocked=true`, `unknown_tool_and_extra_args_rejected=true`, `model_injection_immunity_claim=false`.
