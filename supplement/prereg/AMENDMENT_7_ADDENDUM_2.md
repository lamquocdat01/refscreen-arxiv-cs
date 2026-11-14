# PREREG_43 — Amendment 7, Addendum 2 (POST-HOC; procedural deviation from Amendment 7 (a) and Addendum A)

- **Status: POST-HOC procedural deviation.** Written on 2026-11-08. At that time:
  - cascade passes 1–3 of Amendment 7 (a) and Addendum A had run;
  - one OpenAlex probe request with an API key had been sent (2026-11-08T04:16:49Z, see "Probe").
  The addendum is hashed before any further cascade request. `PREREG_AMENDMENT_7.md` (`df36318b…`) and
  `P3E/AMENDMENT_7_ADDENDUM.md` (Addendum A, `10f8b213…`) are not edited.
- **Decision:** LQD, 2026-11-08. An OpenAlex API key was created and is to be used. The set to be asked is extended to
  the academic references of 2024–26, with the same order, threshold and rules, the header stop, and an end date of
  2026-11-12T23:59Z. Academic references of 2019–21 still to be asked come first.
- **Unchanged:**
  - target definition of (a); registered cascade (`ground_truth_p1.resolve_ref`, Amendment 3 order); threshold 0.9;
    def 1 / def 2;
  - read-only reuse of `_derived/43/cache/`; new answers only in `_derived/43/cache_p3e/`;
  - the interval rule for references still unanswered; the "Use" paragraph; H1–H5 definitions and PASS/FAIL rules;
  - from Addendum A: the header budget stop, the RAM rule, and the end date for 2019–21 (2026-11-13T23:59Z).

## Why (reason for the deviation)

1. **Under Addendum A, the 2024–26 cells would be intervals.**
   - 1,412 distinct academic (J/C/P) target references of 2024–26 had no OpenAlex answer: 887 unresolved, 3
     rate-limited, 522 resolved.
   - The exploratory sweep put the full-cascade rate of 2024–26 at about [0.01 %, 2.1 %] (τ = 0.9). That interval
     cannot serve the 2024–26 comparison or the hold-out thresholds, which Amendment 7 (d) 5 names the primary
     calibration result.
   - Without a key (≤ 100 calls per UTC day), asking the 1,412 references would take about 15 days.
2. **The key changes only the budget, not the request.**
   - The request is the same: `filter=title.search`, `per-page=5`, same parameters. The key is added at the session
     level, so the cache key, the stored answer and the matching are identical to the keyless request.
   - The probe below measured the keyed budget: 10,000 credits per UTC day, 10 credits per call, so about 1,000 calls
     per day.
   - The remaining academic set is about 1,583 calls (180 for 2019–21, 1,403 for 2024–26), so it fits in two budget
     days before the end date.
3. **The order still protects against selection by resolvability.**
   - The 2019–21 references are asked first. They are the population of the human-rated sheet (b) and of the in-sample
     headline.
   - Inside each period the registered order is kept: unresolved (group 2), then rate-limited (5), then resolved (6),
     each in its seed-42 permutation.
   - Whatever a budget stop cuts off is cut from the end of that fixed order.

## Probe (one request, 2026-11-08T04:16:49Z, with the key)

- The request was the registered cascade request for the first academic reference of 2019–21, in the registered
  order, that had no stored OpenAlex answer (`2004.06303/gillibrand`). It returned HTTP 200. The answer is stored in
  `cache_p3e/openalex/` with the key removed from the stored URL. It is attributed to pass 4.
- Numeric headers:
  - `X-RateLimit-Cost-USD` 0.001 and `X-RateLimit-Credits-Used` 10;
  - `X-RateLimit-Limit` 10,000 credits per day (`X-RateLimit-Limit-USD` 1.0);
  - `X-RateLimit-Remaining` 9,990 (0.999 USD) after the call;
  - `X-RateLimit-Reset` 70,989 s, i.e. 00:00 UTC.
- The key value is never printed, logged or written. It is read only by `code/p3e_complete_cascade.py` from the
  `.env` file of the topic folder, which is excluded from every package.

## Procedure that replaces the passes and scope rules of Addendum A from pass 4 on

- **Scope.** All academic (J, C, P) target references of (a), both periods, that still lack an answer:
  - 180 of 2019–21;
  - 1,403 of 2024–26 (9 were answered in pass 1).
- **Order.**
  - First the 2019–21 references, in the registered order restricted to them (group 1, then 5, then 6).
  - Then the 2024–26 references, in the registered order restricted to them (group 2, then 5, then 6).
  - Seed-42 permutation inside each group, as registered.
- **Key.** `OPENALEX_API_KEY` is read from `.env` at the start of the run. The request rate stays at ≤ 1 request/s.
  S2 stays keyless at ≤ 1 request per 3 s. Its answers are stored for every scope reference except the
  rate-limited ones.
- **Budget stop (from the header), as in Addendum A.**
  - After every OpenAlex response the pass reads `X-RateLimit-Remaining`. When it falls below the reserve
    R = max(2 × credits per call, 5 % of `X-RateLimit-Limit`), the pass sends no further OpenAlex request. With the
    key, R is 500 credits.
  - A refusal (HTTP 429, or a budget/quota answer) ends OpenAlex asking for that pass.
- **Passes.**
  - Pass 4 starts as soon as this file is hashed.
  - After a budget stop, the next pass starts at the next 00:10 UTC.
  - After a refusal, the next pass starts 60 minutes after the pass ended.
  - A pass asks only scope references that still lack an answer.
- **End.**
  - 2024–26 references are not asked after 2026-11-12T23:59Z.
  - 2019–21 references are not asked after 2026-11-13T23:59Z (Addendum A).
  - Asking ends when every scope reference has an answer, or when both end dates have passed.
- **Not asked:** the non-academic tiers (S, W, B) of both periods. Their cells follow the interval rule of
  Amendment 7 (a): [lower, upper], lower counting still-unanswered references as resolved, upper keeping the registered
  state.

## Reporting

- The academic cells of both periods are exact once the scope is complete. Otherwise the remaining references follow
  the interval rule.
- The headline completed rate, the 2024–26 comparison, the hold-out thresholds and H1–H5 on completed data are
  recomputed when the academic scope of both periods is complete, or at the end dates with intervals.
- The human-rated sheet (b) is drawn as soon as the 2019–21 academic scope is complete. Its pool depends only on the
  2019–21 academic def-1 states.
- In the paper's protocol table, this addendum is part of the Amendment 7 row, stated as: "OpenAlex was completed with
  an API key for the academic references of both periods; non-academic tiers are reported as intervals."
