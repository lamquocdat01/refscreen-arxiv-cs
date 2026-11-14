# PREREG_43 — Amendment 7, Addendum A (POST-HOC; procedural deviation from Amendment 7 (a))

- **Status: POST-HOC procedural deviation.** Written on 2026-11-08, after cascade passes 1 and 2 of Amendment 7 (a)
  (2026-11-07) and after one OpenAlex probe request (2026-11-08T03:38:36Z, see "Probe" below). It is hashed before
  any further cascade request. `PREREG_AMENDMENT_7.md` (`df36318b…`) is not edited; this addendum replaces only the
  sentence on passes in (a) ("**Passes:** at most 3. …") and adds the stopping and scope rules below.
- **Decision:** LQD, 2026-11-08 (instruction to continue keyless). Verbatim:
  "mỗi ngày UTC 1 lượt sau 00:10Z, keyless, chỉ academic (J/C/P) kỳ 2019–21; dừng trước khi chạm hạn mức (theo
  header); kết thúc khi tập này hoàn tất hoặc tới 13-11 23:59Z. Kỳ 2024–26 và tầng S/W/B không hỏi thêm, báo dạng
  khoảng [cận dưới, cận trên]". Order of asking, similarity threshold and resolve rules are unchanged.
- **Unchanged:** `PREREG_43.md`, `manual_protocol.md`, Amendments 1–7 and every rule of Amendment 7 (a) other than the
  passes sentence: target definition, order of asking (groups 1–6, seed-42 permutation inside a group), registered
  cascade (`ground_truth_p1.resolve_ref`, Amendment 3 order), threshold 0.9, def 1 / def 2, read-only reuse of
  `_derived/43/cache/`, new answers only in `_derived/43/cache_p3e/`, the interval rule for unanswered references,
  the "Use" paragraph, H1–H5 definitions and PASS/FAIL rules.

## Why (reason for the deviation)

1. **The binding limit is the keyless daily budget, not memory.** In pass 1 (2026-11-07T10:25Z) and pass 2
   (12:33Z) OpenAlex refused the first request with HTTP 429. Both passes fell on the same UTC day, so the second
   could not help: the keyless budget is per IP and per UTC day and resets at 00:00 UTC. Pass 3 was scheduled for
   2026-11-08T00:10Z. It never started, because the waiting process had ended (the log stops at "waiting 642 min").
   Free RAM was 7.4 GB and 5.5 GB at the ends of passes 1 and 2. Memory was not the cause.
2. **Probe (one request, 2026-11-08T03:38:36Z, keyless, made on LQD's instruction before this addendum).** The
   request was the registered cascade request (`filter=title.search:<normalised title>`, `per-page=5`) for the first
   reference of group 1 in the registered order that had no stored OpenAlex answer (`2109.04255/fiering1967streamflow`).
   - Its answer (HTTP 200) is stored in `cache_p3e/openalex/` and is used like any other stored answer.
   - Headers returned:
     - `X-RateLimit-Cost-USD: 0.001` and `X-RateLimit-Credits-Used: 10` per call;
     - `X-RateLimit-Limit: 1000` credits per day, which is `X-RateLimit-Limit-USD: 0.1`;
     - `X-RateLimit-Remaining: 830`, or `X-RateLimit-Remaining-USD: 0.083`, after the call;
     - `X-RateLimit-Reset: 73282` s, which is 00:00 UTC.
   - The keyless budget is therefore **at most 100 title-filter calls per UTC day per IP**. The 170 credits already
     used before the probe on 2026-11-08 came from other traffic on the same IP.
   - Log: `P3E/oa_probe.jsonl`, `P3E/P3E_LOG.md`.
3. **The full target set cannot be finished.**
   - 6,181 distinct target references (6,187 rows) still lack an OpenAlex answer, apart from 65 answered in pass 1.
     That would take about 60 budget-days.
   - The academic references of 2019–21 need 263 more calls:
     - 291 distinct references (293 rows; J/C/P), of which 28 were answered in pass 1;
     - that leaves 154 unresolved (group 1) and 109 resolved (group 6);
     - this is 3–4 budget-days, and fits before 2026-11-14 (the Amendment-7 date for option A of (b)).
   - 2019–21 academic is the cell behind the headline rate (H1, u_A in sample). It is also the population of the
     human-rated sheet of (b).
4. No API key is used (LQD decision). Running keyless is a resource limit, not a choice that depends on any result.

## Procedure that replaces the passes sentence of Amendment 7 (a)

- **Scope of further asking ("subset").** Target references of (a) with period 2019–21 **and** tier J, C or P: 291
  distinct references (154 group 1 unresolved, 137 group 6 resolved, 0 rate-limited; 28 of the resolved already
  answered). No other target reference is asked again.
- **Order.** It is the registered order of (a) restricted to the subset: group 1, then group 5 (empty), then group 6,
  with the seed-42 permutation inside each group. References that already have an answer are skipped.
- **Passes.**
  - One pass per UTC day, starting at or after 00:10 UTC.
  - Pass 3 starts on 2026-11-08, after this file is hashed. The 2026-11-08 budget is already partly spent; see the
    probe.
  - A pass asks only subset references that still lack an answer.
  - OpenAlex is keyless at ≤ 1 request/s. S2 is keyless at ≤ 1 request per 3 s; for the subset, S2 answers are
    already stored.
- **Budget stop (from the header).**
  - After every OpenAlex response the pass reads `X-RateLimit-Remaining` and the credits per call
    (`X-RateLimit-Credits-Used`).
  - When the remaining credits fall below the reserve R = max(2 × credits per call, 5 % of `X-RateLimit-Limit`),
    which is 50 credits at the probed values, the pass sends no further OpenAlex request that day and ends.
  - A refusal (HTTP 429 or a budget/quota 402/403) still ends OpenAlex asking for the day, as in Amendment 1.
  - A reference not reached that day is asked on the next day's pass. It is never recorded as answered by the
    budget stop.
- **End.** Asking ends when every subset reference has an OpenAlex answer, or at 2026-11-13T23:59Z, whichever comes
  first. No pass starts after that time, and a running pass is stopped at it.
- **Memory.** Free RAM is logged at the start and end of every pass. A value below 6 GB is reported to LQD. It is never
  a reason to skip or shorten a pass.
- **Resume.** `p3e_complete_cascade.py --seed 42 --resume` replays recorded passes from the caches (no request). The
  pass in which each reference was answered is kept in `P3E/cascade_answered.json`, so replay does not re-attribute
  answers.

## Reporting

- **2024–26, all tiers, and the non-academic tiers (S, W, B) of 2019–21 are not asked further.** That is 5,890
  distinct target references. Every cell that contains still-unanswered references is reported with the interval of
  Amendment 7 (a): [lower, upper], where lower counts those references as resolved and upper keeps their registered
  state. The interval is never merged into the point estimate.
- **2019–21 academic.** Once the subset is complete, its cells are exact. If the end date comes first, the remaining
  subset references follow the same interval rule.
- The headline completed rate (u_A, 2019–21) and H1–H5 on completed data are recomputed only when the subset is
  complete, or at the end date with intervals.
- In the paper, this deviation is part of the Amendment 7 row of the protocol table. It is stated as: "OpenAlex was
  completed for the 2019–21 academic references only; elsewhere intervals are reported."
