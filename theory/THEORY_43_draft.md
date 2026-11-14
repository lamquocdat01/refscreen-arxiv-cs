# THEORY_43 — draft (P0, 16-10-2026)

Topic 43: false positives of reference-verification ("existence") screens on legitimate bibliographies.
Status: Theorem 1 and Theorem 2 stated and proved in full; Theorem 3 and Proposition 4 sketched (full proofs are P1/T09).
Numerical companions: `code/p0_theory_tables.py` → `results/p0_theory_tables.csv/.png` (exact values + Monte Carlo, 5 seeds).

---

## 0. Setting and notation

A *reference* is one entry of a bibliography as seen by a screen (after rendering, extraction and parsing).
Each reference carries a latent label H ∈ {R, F}: R = real (the cited work exists), F = fabricated (does not exist,
e.g. hallucinated by an LLM).

A *registry lookup* (Crossref, OpenAlex, Semantic Scholar, DBLP, arXiv, … or any combination) returns, for each
reference, a resolvability indicator

  Z = 1  if the screen fails to match the reference to a registry record ("unresolved"),
  Z = 0  otherwise.

Parameters (all may depend on a stratum j, see §1.3):

| symbol | meaning |
|---|---|
| π = P(H = F) | prior share of fabricated references (per reference) |
| u = P(Z = 1 \| H = R) | *unresolved rate of real references*: registry non-coverage + extraction/parse loss + identifiers dropped by the rendering style |
| s = P(Z = 1 \| H = F) ≤ 1 | sensitivity of the lookup to fabricated references (s < 1 when a fabricated entry accidentally matches a real record) |
| n | number of references of a paper |
| k | flag threshold of a paper-level rule ("desk-reject if at least k references are unresolved") |

An *existence screen* is a reference-level decision D ∈ {0, 1} (1 = flag) that depends on the data only through Z,
possibly with independent external randomisation: D = 1 with probability a if Z = 1 and with probability b if Z = 0,
0 ≤ b ≤ a ≤ 1. The canonical screen is a = 1, b = 0 (flag exactly the unresolved references).
PPV = P(H = F | D = 1) is the precision of the flags.

Throughout, u > 0 (no registry covers every real work; Section 3 of the paper documents u for each stratum).

---

## 1. Theorem 1 (precision ceiling of existence screens)

**Theorem 1.** For the canonical existence screen (flag ⇔ Z = 1),

  PPV = π s / (π s + (1 − π) u)  ≤  π / (π + (1 − π) u) =: PPV*(π, u).                         (1)

Equality holds iff s = 1. The ceiling PPV* does not depend on the matching algorithm except through u; it is
increasing in π and decreasing in u. More generally, every existence screen (any flag probabilities a, b) with
u ≤ 1/2 satisfies PPV ≤ PPV*(π, u).

*Proof.* By Bayes' rule, P(D = 1, H = F) = π s and P(D = 1, H = R) = (1 − π) u, hence
PPV = πs/(πs + (1 − π)u). The map s ↦ πs/(πs + c) with c = (1 − π)u > 0 has derivative πc/(πs + c)² > 0, so it is
strictly increasing and attains its maximum on s ∈ [0, 1] at s = 1, which gives (1) and the equality case.
Monotonicity in π and u follows from PPV* = 1/(1 + (1 − π)u/π).
Randomised screen: P(D = 1, H = F) = a·πs + b·π(1 − s) and P(D = 1, H = R) = a·(1 − π)u + b·(1 − π)(1 − u).
Hence PPV is a weighted average (weights ∝ a·P(Z = 1) and b·P(Z = 0)) of
PPV₁ = πs/(πs + (1 − π)u) and PPV₀ = π(1 − s)/(π(1 − s) + (1 − π)(1 − u)), so PPV ≤ max(PPV₁, PPV₀).
PPV₁ ≤ PPV*(π, u) by the first part; PPV₀ ≤ π/(π + (1 − π)(1 − u)) (increasing in 1 − s ≤ 1), and
π/(π + (1 − π)(1 − u)) ≤ π/(π + (1 − π)u) ⇔ u ≤ 1 − u ⇔ u ≤ 1/2. ∎

**Corollary 1.1 (required coverage).** A screen can reach precision γ ∈ (0, 1) only if
u ≤ π(1 − γ) / (γ(1 − π)). Example: π = 0.5 %, γ = 0.9 ⇒ u ≤ 0.056 %. A matcher that resolves 99 % of real
references (u = 1 %) has PPV ≤ 33.4 % at π = 0.5 %, whatever its algorithm.

*Proof.* Solve PPV*(π, u) ≥ γ for u. ∎

**Corollary 1.2 (headline, PLAN values).** π = 0.5 %, u = 1.5 % ⇒ PPV ≤ 0.005/(0.005 + 0.995·0.015) = 25.1 %:
at least three flags in four are false, however good the matcher. (Exact values for the lit-derived (π, u) pairs
are printed by `p0_theory_tables.py`; see `results/p0_theory_headlines.json`.)

### 1.3 Stratified form
Let references fall into strata j = 1..J (e.g. bibliography style × identifier present × preprint/archival), with
shares w_j (Σ w_j = 1) and parameters (π_j, u_j, s_j). Then

  PPV = Σ_j w_j π_j s_j / Σ_j w_j (π_j s_j + (1 − π_j) u_j)  ≤  Σ_j w_j π_j / Σ_j w_j (π_j + (1 − π_j) u_j),      (2)

and stratum-wise PPV_j ≤ PPV*(π_j, u_j). If π_j ≡ π (fabrication is independent of the stratum),
PPV ≤ PPV*(π, ū) with ū = Σ_j w_j u_j: the ceiling is governed by the *average* unresolved rate, so a stratum with a
large u_j (e.g. a style that drops DOIs, arXiv-only entries) lowers the precision of the whole screen in proportion to
its share.

*Proof.* (2) is (1) applied to the mixture: numerator and denominator are sums over strata, and each term
w_j π_j s_j ≤ w_j π_j. For π_j ≡ π the right side of (2) equals π/(π + (1 − π)ū). ∎

**Remark (what Thm 1 does not say).** It is a statement about flags, not about papers; paper-level consequences are
Theorem 2. It assumes the decision uses only Z; screens that use extra evidence (author match, venue plausibility)
are covered by Theorem 3, which shows that on un-identified rendered references such extra evidence cannot
separate the two classes either.

---

## 2. Theorem 2 (paper-level false-flag probability and the length effect)

Consider a *legitimate* paper (all n references real, π = 0 for this paper) and the paper-level rule
"flag (desk-reject) iff N ≥ k", where N = Σ_{i=1}^n Z_i is the number of unresolved references.

**Assumption A (conditional independence).** Given the paper, Z_1, …, Z_n are independent Bernoulli(u).

**Theorem 2.** Under Assumption A,

  P(false flag | n, k, u) = P(Bin(n, u) ≥ k) = 1 − Σ_{j=0}^{k−1} C(n, j) u^j (1 − u)^{n−j}.            (3)

(i) (3) is strictly increasing in n (for n ≥ k) and in u ∈ (0, 1), and decreasing in k.
(ii) Poisson approximation: with λ = n u, |P(Bin(n,u) ≥ k) − P(Poi(λ) ≥ k)| ≤ d_TV(Bin(n,u), Poi(λ)) ≤ n u²
     (Le Cam 1960); the sharper Barbour–Hall bound gives ≤ (1 − e^{−λ}) u.
(iii) (Length effect.) Let a population of legitimate papers have bibliography lengths with distribution G. The
     share of flagged papers is Φ_k(G) = E_{n∼G} P(Bin(n, u) ≥ k), and if G_2 stochastically dominates G_1 then
     Φ_k(G_2) ≥ Φ_k(G_1). Hence the *observed prevalence of "papers with ≥ k unresolved references" increases with
     bibliography length even when π = 0*. For k = 1 and n u ≪ 1, Φ_1 ≈ u·E[n]: prevalence is proportional to mean length.
(iv) With m fabricated references (s per reference), N = Bin(n − m, u) + Bin(m, s) (independent), so the paper-level
     true-positive probability is P(Bin(n − m, u) + Bin(m, s) ≥ k).

*Proof.* (3) is the definition of the binomial distribution under Assumption A.
(i) Monotonicity in n: couple N_{n+1} = N_n + Z_{n+1} with Z_{n+1} ≥ 0, so {N_n ≥ k} ⊆ {N_{n+1} ≥ k}; the inclusion is
strict with positive probability ({N_n = k − 1, Z_{n+1} = 1}, probability > 0 when n ≥ k − 1 and 0 < u < 1).
Monotonicity in u: d/du P(Bin(n,u) ≥ k) = n C(n−1, k−1) u^{k−1} (1 − u)^{n−k} > 0 for 0 < u < 1 (standard
identity: the binomial upper tail equals the regularised incomplete beta function I_u(k, n − k + 1)). Decreasing in k:
{N ≥ k + 1} ⊆ {N ≥ k}.
(ii) Le Cam's inequality d_TV(Σ Bernoulli(p_i), Poi(Σ p_i)) ≤ Σ p_i² with p_i = u; the probability of any event, in
particular {≥ k}, differs by at most the total-variation distance. Barbour & Hall (1984): d_TV ≤ (1 − e^{−λ}) λ^{-1} Σ p_i².
(iii) n ↦ P(Bin(n, u) ≥ k) is non-decreasing by (i); the expectation of a non-decreasing function is monotone under
first-order stochastic dominance. For k = 1, 1 − (1 − u)^n = n u + O(n² u²).
(iv) Independence of the Z_i across real and fabricated entries. ∎

**Corollary 2.1 (PLAN numbers; exact values from the script).** u = 1.5 %: n = 50, k = 1 → 53.0 %; n = 50, k = 2 →
17.3 %; survey-length n = 150, k = 2 → 66.0 % (PLAN §2 wrote "67 %"; the exact binomial value is 66.0 % and the
Poisson approximation 65.7 % — quote the exact value; at u = 1.54 % the same cell is 67.4 %, so "66.0 % with
u = 1.54 %" mixes two inputs).
**Caveat on u (from full-text reading, `lit/competitors_43.md`):** the "1.54 %" of Zhao et al. (p. 3) is the pooled
2020–2025 unmatched rate after their third cleaning stage, *not* a pre-LLM baseline (that baseline is only in their
SI, Fig. S2, not read). The lit-derived u therefore spans roughly 0.3 % (implied by the ICLR 2023 ≥1-flag share of
Russinovich et al., pre-ChatGPT submissions; our inversion, see script) to 1.5 % (Zhao stage-3); the P0 pilot
measures u₀ directly, and the headline numbers are printed for both ends.
**Measured u₀ (P0, `results/p0_groundtruth.json`, seed 42).** On the pre-LLM set (arXiv cs.{CL,CR,CV,LG,NI}
2019–2021, 29 papers with a usable bibliography; one paper's \cite keys are absent from its .bib), a title-only screen
(Crossref query.bibliographic → Semantic Scholar match → arXiv title search; match = normalised title similarity ≥ 0.9;
0 failed queries after retries) leaves u₀ = 7.18 % of references unresolved (k = 82, n = 1,142; Wilson 95 %
[5.82, 8.83] %; paper-bootstrap 95 % [4.35, 10.75] %; def. 1). Requiring in addition that the first .bib author surname
appear in the matched record (def. 2) gives u₀ = 13.9 % (k = 115, n = 827, 28 papers; Wilson [11.7, 16.4] %; 315 refs
excluded for missing author lists). The rate is strongly type-dependent: 0.74 % for @inproceedings (k = 3, n = 403),
7.0 % for @article (24/345), 3.55 % for the three academic types pooled (27/760, 23 papers; Wilson [2.45, 5.12] %),
but 32–81 % for @misc/@online/@manual; among certified-real references (identifier resolves and title similarity
≥ 0.9) it is 0.81 % (k = 2, n = 248). The non-indexed tail (software, web pages, reports, non-indexed venues) is part
of what an existence screen sees, so def. 1 on all references is the operative u for Thm 1–2. With π = 0.39 % or
0.5 % it gives a PPV ceiling of 5.2–6.5 % and P(false flag | n = 150, k = 2) = 0.9998; the α = 5 % safe threshold at
n = 150 is k = 17 (def. 1) or k = 29 (def. 2). Both are single-pass keyless-API estimates and are upper-biased relative
to a pipeline with a web-search fallback (Zhao et al.'s Google Scholar step); see
`results/p0_theory_headlines.json` for every (definition × CI end × π) cell.
**Counter-intuitive consequence:** the "≥ 2 flags" threshold does not protect long bibliographies: at u = 1.5 % a
legitimate survey with 150 references is flagged more often than not.

**Corollary 2.2 (testable prediction for E3).** On a corpus of certified-real bibliographies (π = 0), the empirical
flag rate as a function of n must follow (3) with u estimated per stratum; a systematic excess indicates either
dependence (see §2.1) or residual fabricated references.

### 2.1 Relaxing independence (within-paper dependence)
Unresolved references cluster inside a paper (same style drops every DOI; a preprint-heavy author; one broken
`.bib` export). Model this as a mixture: the paper draws U ∼ μ (mean ū), then Z_i are i.i.d. Bernoulli(U) given U
(by de Finetti this covers every exchangeable dependence structure). Then P(false flag) = E_μ f_{n,k}(U) with
f_{n,k}(u) = P(Bin(n, u) ≥ k), and

  f'_{n,k}(u) = n C(n−1, k−1) u^{k−1} (1 − u)^{n−k},

which is decreasing in u for k = 1 and increasing on [0, (k − 1)/(n − 1)] for k ≥ 2. Hence (Jensen):

- **k = 1:** f is concave, so E f(U) ≤ f(ū): the i.i.d. formula (3) evaluated at the mean rate is an **upper bound**
  on the false-flag probability under positive within-paper dependence.
- **k ≥ 2:** f is convex on [0, (k − 1)/(n − 1)]; if μ is supported there, E f(U) ≥ f(ū): formula (3) is a **lower
  bound** — clustering makes multi-flag thresholds *worse* for honest papers, which strengthens the length-effect
  conclusion. (Outside that range the direction is not determined in general; the P1 analysis estimates μ per
  stratum and reports E f(U) directly.)

Within-paper dependence does not affect Theorem 1, which is a per-reference statement (marginal π, u, s).

---

## 3. Theorem 3 (indistinguishability on un-identified rendered references) — SKETCH

Setting: a screen observes Y = (rendered reference string, registry responses) and applies any test φ(Y) ∈ {0, 1}
(1 = "fabricated"). Let S be the stratum of references whose rendered form carries **no resolvable persistent
identifier** (e.g. a style that does not print `doi`; arXiv-only entries rendered without `10.48550/arXiv.<id>`).

**Assumption B (plausible fabrication).** On S, a fabricated reference with plausible metadata induces the same
distribution of Y as a real reference that the registries do not resolve:
P(Y ∈ · | H = F, S) = P(Y ∈ · | H = R, Z = 1, S) =: Q.
(Interpretation: the generator matches the surface statistics of real-but-unindexed references; the registries
return "no match" for both.)

**Theorem 3 (to be proved in full in P1).** Under Assumption B, every test φ satisfies, on S,

  P(φ = 1 | H = R, Z = 1, S) + P(φ = 0 | H = F, S) = 1,

so its false-positive rate on the stratum is FPR_S ≥ u_S·(1 − FNR_S), i.e. FPR_S + FNR_S·u_S ≥ u_S, and on the
unresolved sub-population FPR + FNR = 1 (no better than a coin that ignores the data).
More generally, for any two hypotheses, FPR + FNR ≥ 1 − d_TV(P_R, P_F) (Neyman–Pearson / Le Cam), with equality for
the likelihood-ratio test.

*Proof idea.* On the unresolved part of S both classes have law Q, so E_Q φ is simultaneously the FPR and one minus the
FNR. The general bound is the standard inequality inf_φ (E_{P_R} φ + E_{P_F}(1 − φ)) = 1 − d_TV(P_R, P_F).

**Converse (identifiers separate).** If the rendered reference prints an identifier that the registry resolves and
whose metadata are checked (DOI, `10.48550/arXiv.<id>`), then a real reference resolves with probability 1 − u_id
(u_id = registry outage/typo rate, ≪ u) while a fabricated one resolves only by hijacking a real identifier, which the
metadata check rejects except with probability ε. Thus d_TV ≥ 1 − u_id − ε and FPR + FNR ≤ u_id + ε for the identifier
test: printing a resolvable identifier is what makes the stratum screenable — a **necessary** condition for a
"machine-verifiable bibliography", independent of registry coverage.

Assumptions to state in the paper: B is the worst case (an adversarial or highly fluent generator); it is weakened in
P1 to "TV distance ≤ δ", giving FPR + FNR ≥ 1 − δ.

---

## 4. Proposition 4 (α-safe decision rule; FDR for conference-wide screening) — SKETCH

**(a) Per-paper rule.** For a target false-desk-reject level α, define

  k*(n, u, α) = min{ k ∈ {1, …, n + 1} : P(Bin(n, u) ≥ k) ≤ α }.

It exists (k = n + 1 gives probability 0) and is non-decreasing in n and u (Thm 2(i)). Under Assumption A with true
rate u_true ≤ u, the rule "flag iff N ≥ k*(n, u, α)" desk-rejects a legitimate paper with probability ≤ α
(monotonicity in u). With u estimated from a pre-LLM corpus (presumed π ≈ 0) by a one-sided Clopper–Pearson upper
bound u⁺ at level 1 − δ, the guarantee holds with probability ≥ 1 − δ over the estimation sample.
Stratified version: if the paper's references fall into strata with rates u_j, N is Poisson-binomial; k* is computed
from its exact tail (dynamic programming). Under §2.1 dependence with k ≥ 2, replace f(ū) by E_μ f(U) (more
conservative).

**(b) Conference-wide screening.** For papers i = 1..m with (n_i, N_i), define p_i = P(Bin(n_i, u⁺) ≥ N_i)
(a valid, conservative p-value under H_0: "all references real"). Benjamini–Hochberg at level q controls the
expected share of honest papers among the flagged ones (FDR) at q when the p-values are independent or PRDS; the
Benjamini–Yekutieli correction (q / Σ_{i≤m} 1/i) covers arbitrary dependence. The fixed rules "k = 1" (ACL-style) and
"k = 2" (NeurIPS-style) control neither the per-paper error (Thm 2) nor the FDR when the base rate is low (Thm 1).

Tables k*(n, α) for α ∈ {1 %, 5 %} and u ∈ {0.5, 1, 1.5, 3, 5} %: `results/p0_theory_tables.csv` (table = "k_alpha").

---

## 5. References for the theory section (in `lit/refs.bib`)
Bayes/PPV base-rate argument: Ioannidis (2005). Multiple testing: Benjamini & Hochberg (1995); Storey (2002);
Benjamini & Yekutieli (2001) [to add in P1]. Poisson approximation: Le Cam (1960); Barbour & Hall (1984) [to add in P1].
Empirical parameters (π, u): `theory/params_from_lit.csv` (Zhao et al.; Russinovich et al.; Sakai et al.;
Badalova & Mayr; Culbert et al.).
