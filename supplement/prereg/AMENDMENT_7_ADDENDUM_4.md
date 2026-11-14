# PREREG_43 — Amendment 7, Addendum 4 (POST-HOC; procedural deviation from Addendum 2)

- **Status: POST-HOC procedural deviation.** Written on 2026-11-09. At that time:
  - cascade passes 1–5 of Amendment 7 (a), Addendum A and Addendum 2 had run;
  - pass 6 had not started (scheduled for 2026-11-10T00:10Z);
  - one academic target reference still lacked an answer: `2504.01380/alderlake-micro` (2024–26, tier C, rate-limited,
    the failing backend being Semantic Scholar).
  The addendum is hashed before `code/p3e_complete_cascade.py` is changed for it and before any further cascade request.
  `PREREG_AMENDMENT_7.md` (`df36318b…`), `P3E/AMENDMENT_7_ADDENDUM.md` (Addendum A, `10f8b213…`),
  `P3E/AMENDMENT_7_ADDENDUM_2.md` (Addendum 2, `e4c9f26b…`) and `PREREG_AMENDMENT_8.md` (`4498a062…`) are not edited.
- **Decision:** LQD, 2026-11-09. A Semantic Scholar API key was obtained and is to be used by the cascade from pass 6 on.
- **Unchanged:** every request of the cascade (URL, parameters), the order, the 0.9 threshold, def 1 / def 2, the header
  budget stop, the RAM rule, the pass schedule, the end dates, the scope, and every other rule of Addendum 2. OpenAlex is
  not affected.

## What changes

The sentence of Addendum 2, "S2 stays keyless at ≤ 1 request per 3 s", is replaced from pass 6 on by:

- Semantic Scholar is asked with the API key, sent only as the header `x-api-key`.
- The request rate stays at ≤ 1 request/s. The interval used is 1.5 s per request (LQD, 2026-11-09).
- The key is read from `.env` of the topic folder at the start of the run. It is never printed, logged or stored.
- The key is not part of any cache key or stored URL: a stored answer is the same as that of the keyless request.
- Section (H) of Amendment 8 follows "the order, threshold and rules of Addendum 2" and uses the same code. This
  replacement therefore applies to (H) as well.

## Why (reason for the deviation)

The reason is that of Addendum 2 for OpenAlex: the key changes the budget, not the request. The URL, the parameters, the
matching and the stored answer are the same as for the keyless request. Without the key Semantic Scholar refused most
requests of the shared pool.

## Requests already sent without the key

Pass 5 (2026-11-09T09:05:14Z–09:22:36Z) sent 63 Semantic Scholar requests without the key, of which 59 were refused with
HTTP 429. This was what Addendum 2 prescribed, and these requests are not a deviation. Their stored answers are kept.

## Reporting

In the paper's protocol table this addendum is part of the Amendment 7 row, stated as: "Semantic Scholar was queried with an
API key from the sixth pass on."
