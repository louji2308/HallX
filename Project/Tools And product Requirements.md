# ProofCite-Local — Sponsor, Compute, Open-Source and Zero-Cost Build Research

**Research date:** 24 October 2026  
**Project source of truth:** `IDEA.md` — ProofCite-Local, Syntax Error 2026, RadixArk & Lexsi Labs Local LLM Track, Problem Statement #3: Grounded answers and fewer hallucinations.  
**Budget constraint:** No additional payment to any provider. Existing Google AI Pro benefits may be used, but no pay-as-you-go upgrades, paid model APIs, paid GPU rental, or hidden billing dependencies.

## 1. Executive decision

The best fit for ProofCite-Local is to use the official sponsor tools for the jobs they already solve, rather than building replacements during the hackathon:

- **SGLang** is the required inference/serving engine. Run the base model and trained adapters through SGLang; use XGrammar for the JSON shape, RadixAttention where it helps repeated prefixes, and the Multi-LoRA path only after it passes a runtime smoke test.
- **CuratorKIT** should produce provenance-tracked synthetic examples, record rejected samples, and support adaptive recovery.
- **AlignTune** should own the training stages and custom verifiable reward. Run its advice/config checks before allocating GPU time, then preserve every completed stage as a separate checkpoint.
- **AuditKIT** should score the baseline and each completed checkpoint on matched, frozen evidence and write comparison artifacts. Keep model-only scores separate from post-validator system scores.

The most useful compute strategy is **Google AI Pro Colab allocation + Kaggle's free weekly GPU quota**, with every long process checkpointed to persistent storage. Google AI Pro currently lists 200 Colab compute units (CCUs) per month and access to higher-powered accelerators subject to availability; Kaggle documents a free weekly GPU quota that is usually 30 hours, with variation by demand. Neither resource is unlimited or guaranteed.

**No public Syntax Error 2026 page I found promises participant GPU/API credits.** The event's prize page shows a $7,513 prize pool, including a $990 RadixArk Local LLM Track prize, but it does not say that the prize value is a compute-credit allowance or specify the payment form. Plan with zero event credits.

**Critical compatibility risk:** SGLang `v0.5.22`, the version pinned by the project specification, currently documents Python 3.11+ and CUDA 13. The available Colab/Kaggle runtime must be checked before starting model training. The SGLang release notes say `v0.5.19` was the last release with a CUDA 12 lane. Do not silently downgrade the pinned version; first test the required version and record the outcome.

**Critical licensing risk:** CuratorKIT's LSAL v1.1 and AuditKIT's LSAL v1.2 are explicitly source-available, non-commercial licenses rather than OSI-approved open-source licenses. That may fit individual research/hobby experimentation, subject to the exact terms, but it is not a safe assumption for future commercial SaaS or a revenue-generating product. AuditKIT's license also contains a written acknowledgement/permission requirement for organizations in certain use cases. Do not remove license notices or assume the tools are commercially reusable merely because they are publicly hosted on GitHub.

---

## 2. Syntax Error 2026: sponsor and credit findings

### 2.1 Official event facts

- Official event period: **23–25 October 2026**. The published schedule lists the end at **25 October 2026, 9:00 AM IST**.
- The organizer says students across India are eligible; the event is online for students outside IIT Roorkee and offline for IIT Roorkee students. Team size is listed as 1–4.
- The organizer's public FAQ currently says judging information will be provided shortly. The numerical judging weights in `IDEA.md` are therefore a **provisional planning rubric**, not official percentages.
- Prize page: **$7,513 total**, comprising $6,023 under the main Syntax Error pool, $990 for the RadixArk Local LLM Track, and $500 for the FP Launchpad Functional Programming Track. The prize page gives prize values but does not, by itself, establish that the award is a cash payment or a compute-credit allocation.
- Public sponsor list: IMC (title); RadixArk and SGLang (platinum); CodeCrafters, SSOJet, Flora, FP Launchpad (gold); Devfolio, AssemblyAI, n8n and Lexsi (silver); Jane Street (swag).

Sources: [official overview](https://syntax-error-6.devfolio.co/overview), [official prizes](https://syntax-error-6.devfolio.co/prizes), [official schedule](https://syntax-error-6.devfolio.co/schedule), [SDSLabs organizer site and FAQ](https://hackathon.sdslabs.co/).

### 2.2 What each sponsor contributes to this project

| Sponsor/tool | Project relevance | Best use | Credit finding |
|---|---|---|---|
| **RadixArk / SGLang** | Direct, central track fit | Required inference/serving engine; constrained JSON; base/adapter serving; performance measurements | The official page lists a $990 track prize. I found no public event promise of GPU hours, API credits, or free hosting. |
| **Lexsi Labs / CuratorKIT** | Direct | Grounded synthetic data generation, per-sample provenance, quality gates, rejected-sample diagnostics, recovery | Public source access is available under LSAL v1.1, but the license is non-commercial/source-available. No general-purpose GPU-credit allocation found for this event. |
| **Lexsi Labs / AlignTune** | Direct | RAFT/SFT, DPO, Dr. GRPO and a custom verifiable reward | Its own source code is MIT-licensed; third-party/bundled components have their own licenses, documented in the repository. No compute credits found for this event. |
| **Lexsi Labs / AuditKIT** | Direct | Deterministic RAG checks, reproducible run fingerprints, model comparison and regression analysis | LSAL v1.2 is non-commercial/source-available. No event credit allocation found. |
| AssemblyAI | Not needed for the core design | Speech/audio input only if the product later expands to that modality | No need to introduce an external speech API into this document-grounding project. No Syntax Error credit promise found. |
| n8n | Optional, not necessary | General workflow automation | Avoid adding a separate orchestration layer unless it removes a measured blocker; it does not replace required CuratorKIT/AlignTune/AuditKIT/SGLang calls. No Syntax Error credit promise found. |
| SSOJet, Flora, CodeCrafters, IMC, Jane Street, FP Launchpad, Devfolio | Mostly unrelated to the core inference/training path | Use only if a specific feature or official award requirement makes one relevant | No relevant GPU or model-training credit offer was confirmed from the event pages reviewed. |

**Finding:** The four sponsor-aligned tools are already the most valuable “free leverage” available. Do not add unrelated APIs simply because they are sponsors: it increases integration surface, can introduce usage limits, and weakens the local-first/no-paid-dependency story.

### 2.3 What is and is not a credit

- **Not confirmed:** Syntax Error-specific Hugging Face credits, Colab CCUs, GPU hours, Gemini API credits, AssemblyAI credits, or RadixArk hosted inference credits.
- **Confirmed outside the event:** Google AI Pro's published Colab and Google Developer Program benefits (Section 3 below).
- **Potential but not guaranteed:** Kaggle's experimental extra-GPU promotion requires linking/verification of an active **Colab Pro/Pro+** subscription. The published terms do not clearly promise that a Google AI Pro entitlement is automatically treated as a Colab Pro subscription. Try the link flow, but count any additional GPU hours only after they appear in the Kaggle quota UI.

A separate upcoming **Lexsi AI Safety and Alignment Hackathon** (not Syntax Error) advertises $20 in Hugging Face credits for eligible registered teams that join its Discord, with additional credits for shortlisted teams. It has its own rules, deadline and model requirements; those credits are **not** Syntax Error credits. The page says Hugging Face may ask for a payment method to redeem the coupon. If you do not want to provide a payment method or risk an overage, skip that route. Source: [Lexsi hackathon site](https://hackathon.lexsi.ai/).

---

## 3. Google AI Pro: what you can use without buying anything else

The India-facing Google AI plans page currently lists the following Google AI Pro benefits:

1. **200 Colab compute units per month**.
2. Access to more powerful Colab accelerators and longer runtimes, subject to availability and the dynamic Colab limits.
3. **$10 monthly Google Cloud credits** through Google Developer Program benefits, after the relevant benefit is linked/available to the account.
4. **5 TB Google storage** on the India-facing plan page, useful for model checkpoints, datasets, logs and research artifacts.

Sources: [Google AI plans in India](https://one.google.com/intl/en_in/about/google-ai-plans/), [Google AI Pro benefits](https://support.google.com/googleone/answer/14534406?hl=en), [Colab FAQ — Google AI plans and resource limits](https://research.google.com/colaboratory/faq.html), [Google's Colab/AI plan announcement, 22 Sep 2026](https://developers.googleblog.com/colab-is-now-part-of-your-google-ai-plan/).

### 3.1 How to verify the Colab entitlement

- Sign in to Colab using the **same Google account** that has the active, paid Google AI Pro plan.
- Open **Settings → Subscription** in Colab and check that the AI plan benefit is recognized and the compute balance is visible.
- Do not assume a free trial qualifies; Google's FAQ states premium Colab benefits are for eligible paid Google AI plans, not storage-only plans or free trials.
- If the 200 CCUs do not appear, treat them as **not yet available to this runtime/account** until verified. The official announcement described a rollout across supported countries, and account linking/rollout issues can occur.
- Do not purchase Colab Pro or Pay As You Go to fix a missing entitlement. Use the free-tier fallback or stop and investigate support/eligibility.

### 3.2 How to interpret 200 CCUs

CCUs are a **compute balance, not 200 GPU hours**. Consumption depends on the accelerator selected and can change. Google explicitly says GPU type, VM lifetime, usage limits and availability are dynamic. The practical rule is to check the balance before and after a short pilot, then forecast from the measured consumption of that pilot. Do not estimate a long run from guessed CCU-per-hour rates.

Google AI Pro does not guarantee a particular GPU model or unlimited uninterrupted execution. Do not assume Colab will keep a long training job alive simply because the plan is paid. Checkpoint frequently, avoid leaving unnecessary GPU runtimes active, and use CPU for preprocessing, validation, dataset formatting and statistics whenever possible.

### 3.3 What to do with the $10 Google Cloud credits

Treat the cloud credits as a separate benefit from Colab CCUs. They are not a promise of free Colab training time. Google Cloud services can be metered, and adding a billing account or using a service beyond its credited amount can expose you to charges. Given the explicit **no additional payments** rule, the safest plan is to **not depend on Google Cloud VMs, paid Vertex AI inference or metered hosting** for this project. Use Colab and Kaggle directly. If you later decide to use an existing credit, first confirm the exact service is covered and that there is no path to an out-of-pocket bill; a budget alert alone is not a hard spending cap.

---

## 4. Kaggle + Colab: zero-extra-cost compute plan

### 4.1 Kaggle's normal free notebook resources

Kaggle's current notebook documentation lists, at the time of writing:

- Up to **12 hours per CPU/GPU session** (TPU sessions are listed at 9 hours).
- **20 GB** auto-saved `/kaggle/working` storage, with separate scratch space that is not preserved after the session.
- About **29–30 GB system RAM** in the documented CPU/GPU notebook types.
- GPU options can include **one NVIDIA P100** or **two NVIDIA T4 GPUs**. Which runtime is available can vary; free GPU availability can queue during busy periods.
- GPU quota: the official GPU tips page says **30 GPU hours per week, or sometimes higher depending on demand and resources**.

Sources: [Kaggle notebook technical specifications](https://www.kaggle.com/docs/notebooks), [Kaggle GPU usage tips](https://www.kaggle.com/docs/efficient-gpu-usage).

### 4.2 Colab-to-Kaggle extra GPU-hour promotion

Kaggle documents an experimental promotion of **15 additional GPU hours per week for Colab Pro subscribers** and **30 additional hours per week for Colab Pro+ subscribers**. The published steps are to open a Kaggle Notebook and choose **File → Link to Colab**, then verify the active Colab subscription. The extra hours do not consume Colab CCUs. The promotion can be modified or ended by Kaggle.

Sources: [Kaggle's current notebook docs](https://www.kaggle.com/docs/notebooks), [Kaggle's promotion announcement](https://www.kaggle.com/product-announcements/575468).

**Important qualification for your subscription:** Google's new AI Pro plan now unlocks premium Colab benefits, but Kaggle's promotion language still explicitly names Colab Pro/Pro+. There is not enough published evidence to promise that Google AI Pro alone qualifies for those additional Kaggle hours. Try the link once; do not buy a separate Colab subscription; do not count the extra hours unless Kaggle actually shows the increased quota.

### 4.3 Recommended division of work

| Workload | First choice | Why |
|---|---|---|
| CPU-only preprocessing, source canonicalization, split generation, hashing, test writing | Local laptop CPU or Colab CPU | No GPU is needed; preserve scarce GPU quota. |
| Training pilot and the first SFT checkpoint | Colab with the best available accelerator within the existing 200 CCU balance | Paid AI Pro provides premium Colab access, subject to availability, and Drive is convenient for checkpoint persistence. |
| Two independent generator/judge models for CuratorKIT | Kaggle **T4×2 if actually offered**, or serialized/quantized endpoints if only one GPU is available | The project has two different local model weights; a single endpoint cannot pretend to hot-swap model weights by changing a model-name string. |
| DPO/Dr. GRPO | Run the `aligntune advise estimate` first, then use whichever eligible runtime gives the best measured VRAM/time profile | RL rollouts are the highest compute risk. Keep these as later milestones. |
| Final matched-evidence evaluation and statistics | CPU for deterministic checks/statistics; GPU only for generation | Most offset, ACL, freshness, JSON and statistical work does not require GPU. |
| Long-term checkpoints and raw artifacts | Google Drive as the canonical store; optionally publish non-sensitive adapters/logs to a public Hugging Face repository | Notebook disks are temporary. Never rely solely on `/content` or Kaggle scratch storage. |

**Storage rule:** Save checkpoints, adapter configs, tokenizer/version metadata, dataset split manifests, SHA-256 checksums, audit JSON, raw model generations and logs outside the ephemeral runtime after each milestone. Keep data and model artifacts separate so you can resume without repeating synthesis or training.

---

## 5. High-risk compatibility and licensing decisions to resolve first

### 5.1 SGLang v0.5.22 may not match the runtime's CUDA environment

The official SGLang `v0.5.22` release is dated 19 October 2026 and says it requires **Python 3.11 or newer**. Its current installation page says SGLang requires **CUDA 13**, and identifies `v0.5.19` as the last release with a CUDA 12 installation lane.

Sources: [SGLang v0.5.22 release](https://github.com/sgl-project/sglang/releases), [SGLang installation guide](https://docs.sglang.ai/get_started/install.html), [SGLang quickstart](https://docs.sglang.ai/get_started/quickstart.html).

Before running any expensive stage, record:

- `python --version`
- `nvidia-smi` output and visible GPU memory
- `torch.__version__` and `torch.version.cuda`
- installed `sglang` version
- whether the pinned `Qwen/Qwen3-4B-Instruct-2507` server starts and answers one schema-constrained request

Run this smoke test on both candidate environments if possible. The runtime's displayed CUDA toolkit version and the driver/runtime capabilities are related but not interchangeable; test the real SGLang launch path. If v0.5.22 does not work, do not silently substitute a different serving engine or version. Confirm which SGLang versions the track actually requires, document the blocker, then choose a version contingency deliberately.

### 5.2 Do not place every toolkit in one unconstrained Python environment

The current AuditKIT repository's dependency notes specifically warn that its SGLang extra is not needed to evaluate an HTTP-served SGLang model, and that SGLang, vLLM and the Transformers extra do not always co-resolve safely in one Python environment. The current default branch's package metadata also differs from the version pinned by `IDEA.md` (the file currently shows AuditKIT `1.1.3`, while the project blueprint pins `1.0.0`).

Source: [AuditKIT repository](https://github.com/Lexsi-Labs/AuditKIT), especially its current `pyproject.toml` and README.

Recommended boundary:

- **SGLang environment:** run the pinned model server and expose its local OpenAI-compatible HTTP endpoint.
- **CuratorKIT environment:** send generation and judging requests to the separate local SGLang endpoints; keep source-to-canonical-text mapping in project code.
- **AlignTune training environment:** use the chosen TRL/Unsloth backend and pin all dependencies. Do not casually upgrade `torch`, `transformers`, `trl`, `peft` or `bitsandbytes` midway through training.
- **AuditKIT environment:** evaluate the HTTP API using its API backend/requests integration instead of installing an unnecessary in-process SGLang or vLLM dependency into the same environment.

Use the exact versions from `IDEA.md` for a reproducible hackathon run unless a documented, tested incompatibility makes a decision necessary. Current main branches are useful for documentation but may have moved beyond the project's pinned APIs. Verify imports, CLI options and expected return shapes in a small smoke test.

### 5.3 Hardware feasibility: Qwen3-4B, the second judge and RL

The intended base model is `Qwen/Qwen3-4B-Instruct-2507`; its model card lists 4.0 billion parameters and an Apache-2.0 license. It supports a long native context window, but the project does not need to train at that maximum length. Training at 256K tokens would be an avoidable VRAM/time risk.

Source: [official Qwen3-4B-Instruct-2507 model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).

Recommended operating rules (starting points, not benchmark claims):

- Use LoRA/QLoRA through the AlignTune-supported backend and keep `lora_r=16` as the project's initial planned rank.
- Start with the smallest context that still preserves the intended multi-chunk evidence test; test around 2K tokens first, and increase only if evidence bundles are truncated or the memory profile permits it.
- Start with micro-batch 1, gradient checkpointing and quantized loading if supported by the tested backend; add gradient accumulation rather than raising the per-step batch first.
- Use the tool's `aligntune advise estimate` and a tiny pilot to determine actual duration/VRAM before training the target corpus. Record observed resources, not guessed performance.
- A 4B QLoRA run is a plausible target on a 16 GB T4 with careful settings, but it is **not guaranteed** until the precise backend, context, CUDA and dependency set has passed a smoke test.
- `DPO` is a later stage; `Dr. GRPO` with multiple rollouts is the largest time/VRAM risk. Never let it erase a working SFT checkpoint.
- On a single 16 GB GPU, two separate full-precision models (Qwen3-4B generator and Llama-3.2-3B judge) may not fit simultaneously once framework overhead and KV cache are included. Use Kaggle T4×2 if offered, carefully validated quantization, or the blueprint's serialized orchestration option. Keep generator and judge weights genuinely separate; do not route both names to a single-model endpoint.

---

## 6. Open-source repositories and tools worth reusing

These choices are selected because they reduce work in the exact pipeline in `IDEA.md`. “Open-source” below is used in its proper licensing sense; CuratorKIT and AuditKIT are marked separately because their current licenses are source-available/non-commercial.

### 6.1 Required stack — use official implementations instead of rebuilding them

#### A. SGLang — local inference, schema-constrained output and adapter serving

- Repository: [sgl-project/sglang](https://github.com/sgl-project/sglang)
- Primary docs: [structured outputs](https://docs.sglang.ai/advanced_features/structured_outputs.html), [LoRA serving](https://github.com/sgl-project/sglang/blob/main/docs/docs/advanced_features/lora.mdx), [quickstart](https://docs.sglang.ai/get_started/quickstart.html).
- Use native `json_schema`/XGrammar output constraints for the `ProofEnvelope` generation schema. The model must not be allowed to manufacture authoritative character offsets: it returns source identifiers and a quoted span; server code verifies the exact quote and calculates offsets from canonical source text.
- Run one baseline before training. Then benchmark the same fixed prompt/evidence input across available variants. Keep RadixAttention prefix ordering stable, but measure cache-on/cache-off latency rather than claiming a speedup from the feature name.
- Do not enable adapter overlap loading by default; the project's own design notes correctly call for benchmarking it because small batches can get slower.

#### B. CuratorKIT — curation and data provenance

- Repository/docs: [CuratorKIT](https://github.com/Lexsi-Labs/CuratorKIT), [documentation](https://lexsi-labs.github.io/CuratorKIT/).
- The repository includes notebooks for SFT data generation from a PDF, DPO preference pairs, GRPO rollouts, multi-source ingestion, deduplication, adaptive recovery, adversarial generation, hygiene, and filtered-vs-unfiltered fine-tuning.
- Use the provenance artifacts it already emits: manifest, `lexsi_provenance.json`, rejected samples with reasons, dataset card and checksums. These save significant implementation time and fit the project's lineage requirement.
- Explicitly configure the local generator and independent local judge endpoints. Do not rely on a single `generation_task` value to run every type of dataset task; invoke distinct configs for the needed task types.
- Keep the canonical source text immutable. If you clean a derived training view or pseudonymize values, retain an explicit map so offsets still refer to the same canonical text.
- License note: current repository says LSAL v1.1, free for research, education and non-commercial use; commercial use requires a separate license. The optional `[pdf]` extra installs MinerU, whose license is AGPL-3.0. Avoid the heavy optional PDF stack at the start unless layout-sensitive PDF parsing is truly needed.

#### C. AlignTune — training lifecycle

- Repository/docs: [AlignTune](https://github.com/Lexsi-Labs/aligntune), [docs](https://aligntune.lexsi.ai/).
- Use `aligntune advise estimate` and config validation before starting a GPU run; these checks are useful even if you do not yet have a GPU attached.
- Reuse `create_raft_trainer`, the documented DPO and Dr. GRPO path, backend selection, checkpoint/export utilities and custom reward registry. Register the project's custom reward using the API path specified in the blueprint, not a guessed top-level alias.
- The current repository documents 40+ algorithm/example notebooks and Colab demos across SFT, RAFT, DPO, GRPO, distillation and other methods. Use those as learning examples, but pin dependencies to the project's environment and confirm the notebook's model/version matches the chosen model. Do not blindly copy a notebook that uses vLLM as its final serving engine; the hackathon blueprint requires SGLang for core inference/serving.
- License note: AlignTune's own code is MIT, but its repository explicitly calls out third-party components and separate licenses. Preserve `THIRD_PARTY_LICENSES.md` and verify the actual install/bundle you use.

#### D. AuditKIT — evaluation and regression artifacts

- Repository/docs: [AuditKIT](https://github.com/Lexsi-Labs/AuditKIT), [documentation](https://auditkit.lexsi.ai/).
- Use `evaluate()` for an individual run and `compare_models()` for matched baseline/trained comparisons; retain raw per-sample output as well as aggregates and fingerprints.
- The blueprint's seven deterministic RAG dimensions are especially relevant: `citation_support`, `abstention`, `numeric_accuracy`, `freshness`, `acl_compliance`, `evidence_set_recall`, and `context_retention`. Use its documented directions and confirm each metric runs on the pinned version.
- Treat substring/offset correctness and semantic entailment as distinct checks. A quote can be an exact substring yet fail to entail the claim (“quote stuffing”). Human-label a small judge-quality slice before trusting the encoder/LLM judge as ground truth.
- Keep AuditKIT's training/validation regression feedback separate from test data. Only training-source units may be used for any repair synthesis; the held-out test split must remain untouched.
- License note: current repository says LSAL v1.2 (source-available, non-commercial). Its current license includes a written acknowledgement/permission path for certain organizational uses. The current main branch also shows a newer package version than `IDEA.md`'s pin, so pin deliberately and verify API compatibility.

### 6.2 Useful supporting repositories

| Tool/repository | Best use in this project | Why it reduces work | Caution |
|---|---|---|---|
| [Unsloth notebooks](https://github.com/unslothai/notebooks) | Learn/validate Qwen-family LoRA, DPO and GRPO training configuration on Colab/Kaggle | Provides many reproducible training/RL examples and model-family notebooks | Use as a reference for memory settings and backend behavior; AlignTune remains the project's training interface and SGLang remains its serving engine. Re-check the model/version in each notebook. |
| [Qwen3 model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) and [Qwen3 training guide](https://github.com/QwenLM/Qwen3) | Base model setup, tokenizer/chat template, model restrictions and citation | Prevents mistakes in model ID, template, license and context configuration | A 256K maximum context does not mean the training job should use 256K. |
| [pdfplumber](https://github.com/jsvine/pdfplumber) / [pdfminer.six](https://github.com/pdfminer/pdfminer.six) | Extract machine-generated PDFs while keeping per-character positions and page geometry | `pdfplumber` exposes character-level coordinates; this helps map verified text spans to a rendered PDF | It works best on machine-generated rather than scanned PDFs; OCR is a separate problem. Its license is MIT. |
| [Mozilla PDF.js](https://github.com/mozilla/pdf.js) | Front-end PDF rendering/text layer for the reviewer pane | Mature open-source PDF viewer; can support page navigation and highlighted text once source offsets are mapped to text items | An absolute character offset in normalized text is not automatically a PDF rectangle. Store page/text-item/coordinate mappings during extraction and test line breaks/hyphenation. |
| [Hugging Face TRL](https://github.com/huggingface/trl) | Understand low-level SFT/DPO/GRPO behavior underlying common training examples | Helps diagnose trainer-side arguments and algorithms when reading AlignTune examples | Use it underneath AlignTune only as intended; do not create a second independent training path without documenting why. |
| [sentence-transformers](https://github.com/UKPLab/sentence-transformers) | Embeddings for near-duplicate detection and a small dense retrieval baseline | Mature library already used by embedding-based curation workflows | For a tiny controlled corpus, start with BM25/TF-IDF before adding an embedding service or vector database. |
| [OWASP LLM Prompt Injection guidance](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) | Security cases and server-side security rules | Provides a recognised framing for adversarial text embedded in retrieved documents | Prompt instructions alone are not an ACL or security boundary. Enforce ACLs before retrieval and again before displaying citations. |

### 6.3 PDF extraction choice: avoid unnecessary complexity at the start

The product requires exact character-span citations and click-to-highlight behavior. That requires more than asking an LLM to return `char_start` and `char_end`.

Recommended approach:

1. Extract a canonical normalized text representation, with stable `doc_id`, version, page IDs, chunk IDs and source metadata.
2. Keep a mapping from each canonical text range back to the extracted PDF page and text-run/character coordinates. `pdfplumber` can expose page-level character positions for machine-generated PDFs; a PDF.js text layer can then navigate/highlight the relevant rendered text.
3. Have the model return a quote and source identifiers only. Verify quote containment and uniqueness on the server, compute the offsets there, then resolve them through the mapping. If the quote occurs multiple times or cannot be mapped reliably, return an ambiguity/diagnostic rather than a fabricated highlight.
4. Test repeated boilerplate, Unicode normalization, ligatures, split words, line breaks, multi-page paragraphs, tables, and near-duplicate policy versions.

Start with `pdfplumber` rather than `CuratorKIT[pdf]`/MinerU. This reduces installation weight and avoids bringing an AGPL PDF stack into the first prototype unnecessarily. If scanned documents or highly complex layouts later become central, assess OCR/layout tools separately and review their license.

---

## 7. Implementation priorities — preserve the product, sequence the risk

This is a prioritization plan, **not a change to the features or thesis in `IDEA.md`**. Each milestone is saved independently so later stages cannot erase a working result.

### P0 — Track-compliance and environment smoke tests

1. Record the actual Colab/Kaggle GPU, VRAM, Python version, CUDA/PyTorch versions and exact dependency versions.
2. Launch the pinned SGLang version with the selected base model; send one schema-constrained request and save the request, output and server logs.
3. Verify one CuratorKIT run against local generator/judge endpoints, one AlignTune configuration check and one AuditKIT evaluation using actual tool calls.
4. Write a `track_manifest.yaml`, version manifest and `THIRD_PARTY_NOTICES.md`; save SHA-256 fingerprints. No fake calls, mocked final results, or unrecorded dependency upgrades.

**Gate:** Do not begin long training until SGLang is actually serving the selected model on a no-cost runtime and the project has a persistent checkpoint path.

### P1 — Evidence contract and deterministic validator (CPU-first)

Implement and test the `ProofEnvelope` contract and five states: `SUPPORTED`, `PARTIAL`, `MISSING`, `CONFLICTED`, `STALE`. Keep the five chunk-triage labels from `IDEA.md`. The model emits claims, quote text and source/version identifiers; server code computes offsets and checks:

- exact quote containment and unique match;
- schema/required-field validity;
- numeric consistency;
- document version freshness and supersession;
- ACL filtering before retrieval and citation-ownership validation before display;
- prompt-injection handling with retrieved text treated as untrusted data.

The validator must fail closed. XGrammar controls syntax; it does not establish that a claim is entailed by its quote.

### P2 — Small, fully auditable source corpus

Use synthetic, public-safe documents rather than real confidential customer documents. Build a small set of versioned policies/runbooks with deliberately designed near-miss cases, missing schedules, active conflicts, superseded policies, unauthorized document metadata and embedded adversarial instructions. Split by document family **before** synthetic-data generation. Write the source unit IDs and split hashes once and enforce the locked test boundary.

Start with a small development smoke set. Do not use held-out test questions/answers in training or adaptive recovery. Expand to the planned 240-case OOD challenge only after the end-to-end pipeline is stable; smoke-test subsets are not official final benchmark results.

### P3 — CuratorKIT data curation

- Begin with a small batch of answerable and unanswerable cases; inspect accepted and rejected samples manually.
- Verify `manifest.json`, `lexsi_provenance.json`, `rejected.jsonl`, `diagnostic_summary.json`, `dataset_card.md` and checksums.
- Ensure the raw synthetic-data baseline and CuratorKIT-gated/recovered data have comparable token budgets for the intended ablation.
- Use separate task configs/outputs for QA/RAFT, DPO preference pairs and GRPO rollouts; do not assume one run generates every format.

### P4 — AlignTune training in three saved milestones

- **M1:** `DA-RAFT`/SFT first. Save the adapter, trainer config, run logs and AuditKIT result before moving on.
- **M2:** DPO on the project's adversarial preference pairs. Save it separately and compare against M1.
- **M3:** Dr. GRPO only after the prior stages and pilot have passed. Begin with the intended hard subset and rollout group, measure real duration and VRAM, and preserve the preceding adapter if the run fails or cannot finish.

Use `aligntune advise estimate` first. Never claim that a training stage ran if only a configuration or notebook was prepared. If there is insufficient time, the honest stopping point is the latest completed checkpoint and measured evidence—not a fabricated four-way showdown.

### P5 — AuditKIT comparison and closed loop

- Compare base, raw-SFT, curated-SFT and each actually completed trained checkpoint on **identical frozen evidence**.
- Report pre-validator model-only metrics and post-validator system metrics separately.
- Preserve per-case results, missing/unscored cases, fingerprints, config hashes, random seeds and confidence intervals when the pinned tool actually supports the chosen paired/clustered bootstrap unit.
- Only use training-source units for new data synthesis. Validation can identify failure categories, but validation examples should not be copied into the training set. The test set is strictly read-only.
- Run the `cmp.regressed()` → CuratorKIT recovery path using validation-derived failure categories only; then re-evaluate the repaired model on the untouched test split.

### P6 — UI and judge experience

Keep the planned split-pane workbench with Reviewer Mode and ML Auditor Mode. The reviewer flow should prioritise the five evidence states, claim cards, click-to-highlight spans, missing-premise/conflict cards and escalation. The auditor flow should show versioned checkpoints, raw versus post-validator output, audit metrics and lineage artifacts.

Use a lightweight visual layer only after the source/citation behavior is correct. A visually polished PDF highlight that points to the wrong text is a reliability failure. If live GPU availability is unreliable during the demo, show **clearly labeled saved-run artifacts** as a fallback; do not pretend a replay is a live inference.

---

## 8. Zero-payment guardrails

Use these project rules so a notebook or deployment cannot silently turn into a bill:

1. **No paid model endpoints:** no OpenAI/Anthropic/OpenRouter/Gemini API calls for generation, judging, training or evaluation. Use the required local SGLang endpoints.
2. **No new subscriptions:** do not buy Colab Pro/Pro+, compute-unit top-ups, hosted GPU hours, private model hosting or vector-database subscriptions.
3. **No paid GCP infrastructure by default:** do not create a paid GPU VM, managed serving endpoint, or always-on service. The $10 credit is not required to complete the prototype.
4. **No accidental charge path:** do not enable pay-as-you-go or automatic top-ups. If a platform requires a payment method and you cannot verify that the workflow stays within the included credit, do not use that path.
5. **Quota gate before every long job:** record remaining Colab CCUs and Kaggle weekly GPU hours; run a short pilot; estimate total cost in CCUs/hours from measured consumption. Stop if insufficient.
6. **Checkpoint early:** save after data curation and after every training milestone. Write logs and metadata alongside the adapter.
7. **Use CPU whenever possible:** parsing, deterministic validation, data split checks, schema checks, hashes, bootstrapping and report generation should not reserve a GPU.
8. **No confidential documents in third-party notebook/AI assistant prompts:** use synthetic policies for the hackathon corpus. Mounting Drive or sharing notebook output can expose files; publish only intentionally public artifacts.
9. **Do not publish proprietary or license-restricted code as your own:** keep third-party notices and license files in the repo; check the actual versions used.
10. **No fabricated performance figures:** TTFT, cache-hit rate, abstention F1, citation support, confidence intervals, GPU usage and training duration remain `TBD` until produced by logs from real runs.

---

## 9. Risk register and decision rules

| Risk | Impact | Detection | Decision rule |
|---|---|---|---|
| SGLang v0.5.22 does not run on the available CUDA runtime | Blocks mandatory local serving | Install/launch smoke test before training | Resolve a compatible runtime first; do not quietly replace SGLang or claim the pinned version worked if it did not. |
| Colab CCU balance is missing or smaller than expected | Planned training cannot complete in Colab | Settings → Subscription and a short pilot | Use only verified balance; continue CPU work or Kaggle free quota. Never purchase more. |
| Kaggle offers only one 16 GB GPU | Generator/judge concurrency may OOM | Inspect actual accelerator and `nvidia-smi` | Try two T4s if offered; otherwise quantize/serialize as the blueprint permits and document the exact setup. |
| Python dependency collision across SGLang, AlignTune and AuditKIT | Hard-to-debug installs or broken serving | Install each pinned environment separately and run small import/API tests | Use separate environments/services and HTTP API boundaries; avoid blind `pip install -U`. |
| CuratorKIT/AuditKIT license conflicts with commercial future | Could force a paid license or code replacement | Read exact LSAL terms; preserve notices | Treat the hackathon as a research prototype. Before commercialization, obtain written permission or replace restricted components with independently implemented permissively licensed alternatives. |
| PDF normalized offsets do not map cleanly to display | Wrong citation highlight undermines core value | Character-coordinate mapping tests | Store page/text-run geometry; fail with a diagnostic when mapping is ambiguous. |
| RL stage consumes quota and destroys the submission timeline | No usable model checkpoint at deadline | `aligntune advise estimate`, pilot duration and checkpoint test | Run M1, save it, then M2, then M3 only if time/compute allows. |
| Judge model agrees with the generator's hallucinations | False confidence in curation/reward/evaluation | Human-labeled judge-quality slice and cross-family review | Use a genuinely separate model family and report judge agreement/limitations; deterministic checks remain independent. |
| Test leakage through self-healing | Inflated benchmark results | Split hashes, provenance checks, tests for feedback-loop boundaries | Test data is read-only; recovery uses train-source units and validation-derived failure categories only. |

---

## 10. Immediate execution checklist

Use the following as the first operational checklist. It does not change the intended feature list; it orders the most failure-prone prerequisites first.

- [ ] Confirm Google AI Pro is recognized in Colab and the monthly CCU balance is visible.
- [ ] Open a Kaggle notebook; inspect the exact GPU type, VRAM, remaining quota and internet/download access. Try **File → Link to Colab** once and check whether extra quota appears—do not assume it will.
- [ ] Run the SGLang `v0.5.22` compatibility smoke test on the selected free runtime before training.
- [ ] Confirm the selected Qwen3-4B model loads and returns a valid XGrammar-constrained `ProofEnvelope` JSON response.
- [ ] Confirm generator and judge are actually separate model weights/endpoints; measure whether both fit or must be serialized.
- [ ] Run one CuratorKIT curation job and inspect its provenance/rejection artifacts.
- [ ] Run AlignTune's advice/config validation and a tiny training pilot before a full M1 run.
- [ ] Run one AuditKIT evaluation and save its fingerprinted raw result.
- [ ] Save all artifacts to persistent storage, verify hashes, and write down actual versions/hardware.
- [ ] Build the reviewer flow around one real supported answer and one real `MISSING`, `CONFLICTED`, `STALE` or injection case; label any saved-run demo output accurately.

Given the published 25 October 09:00 IST deadline, do not spend the remaining build window chasing an expensive or fragile multi-stage run until SGLang and the evidence validator work end to end.

---

## 11. Sources checked

### Official Syntax Error 2026 sources

- [Syntax Error 2026 overview](https://syntax-error-6.devfolio.co/overview)
- [Syntax Error 2026 prizes](https://syntax-error-6.devfolio.co/prizes)
- [Syntax Error 2026 schedule](https://syntax-error-6.devfolio.co/schedule)
- [SDSLabs organizer site and FAQ](https://hackathon.sdslabs.co/)

### Google compute/subscription sources

- [Google AI plans — India](https://one.google.com/intl/en_in/about/google-ai-plans/)
- [Google AI Pro benefits](https://support.google.com/googleone/answer/14534406?hl=en)
- [Colab FAQ — resource limits and Google AI plans](https://research.google.com/colaboratory/faq.html)
- [Google's 22 September 2026 announcement that Colab is part of Google AI plans](https://developers.googleblog.com/colab-is-now-part-of-your-google-ai-plan/)
- [Kaggle notebook technical specifications and Colab Pro GPU promotion](https://www.kaggle.com/docs/notebooks)
- [Kaggle efficient GPU usage guidance](https://www.kaggle.com/docs/efficient-gpu-usage)
- [Kaggle promotion announcement](https://www.kaggle.com/product-announcements/575468)
- [Google Developer Program benefits](https://developers.google.com/profile/help/benefits?hl=en)

### Required toolchain and supporting repositories

- [SGLang release list](https://github.com/sgl-project/sglang/releases)
- [SGLang installation](https://docs.sglang.ai/get_started/install.html)
- [SGLang quickstart](https://docs.sglang.ai/get_started/quickstart.html)
- [SGLang structured outputs](https://docs.sglang.ai/advanced_features/structured_outputs.html)
- [CuratorKIT repository](https://github.com/Lexsi-Labs/CuratorKIT)
- [CuratorKIT documentation](https://lexsi-labs.github.io/CuratorKIT/)
- [CuratorKIT LSAL v1.1 license](https://github.com/Lexsi-Labs/CuratorKIT/blob/main/LICENSE.md)
- [AlignTune repository](https://github.com/Lexsi-Labs/aligntune)
- [AlignTune third-party license inventory](https://github.com/Lexsi-Labs/aligntune/blob/main/THIRD_PARTY_LICENSES.md)
- [AuditKIT repository](https://github.com/Lexsi-Labs/AuditKIT)
- [AuditKIT license](https://github.com/Lexsi-Labs/AuditKIT/blob/main/LICENSE.md)
- [Unsloth training notebooks](https://github.com/unslothai/notebooks)
- [Qwen3-4B-Instruct-2507 model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
- [Qwen3 documentation repository](https://github.com/QwenLM/Qwen3)
- [pdfplumber repository/license](https://github.com/jsvine/pdfplumber)
- [Mozilla PDF.js](https://github.com/mozilla/pdf.js)
- [OWASP LLM01 — Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)

### Separate, upcoming Lexsi event (not a Syntax Error benefit)

- [Lexsi AI Safety and Alignment Hackathon](https://hackathon.lexsi.ai/) — separate dates, model requirements, HF credits and redemption terms.

---

## Final conclusion

The practical zero-extra-payment route is **Colab's verified Google AI Pro compute balance plus Kaggle's free GPU hours**, storing checkpoints persistently and spending GPU time only on real training/inference. The sponsor tools already remove much of the work, so the contribution should be the measured, auditable integration: frozen-evidence comparisons, exact quote/span verification, five-state abstention, provenance, ACL/freshness safeguards and an honest CuratorKIT → AlignTune → SGLang → AuditKIT feedback loop.

The two decisions to resolve before any long run are **(1) does SGLang v0.5.22 launch on the actual CUDA 13-compatible free runtime, and (2) does the selected GPU have sufficient memory for the independent generator/judge arrangement?** The two decisions to resolve before product commercialization are **(1) the non-commercial LSAL terms for CuratorKIT/AuditKIT and (2) the licenses of bundled training dependencies**. Keep the hackathon prototype within the reviewed terms, and design the long-term product so restricted evaluation/curation libraries can be replaced if a commercial license is not an option.
