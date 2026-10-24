# THEORY_43 — v3 (P2 final: backend headlines, dispersion, paper-level α-safe rules)

Topic 43: false positives of reference-existence screens on legitimate bibliographies.
v1 (`THEORY_43_draft.md`, P0) treats u as one number. P0 measured u to depend strongly on the entry type: 0.74 % for
@inproceedings, 32–81 % for @misc/@online/@manual (pre-LLM, def. 1, seed 42). v2 therefore makes every statement a
function of the paper's **tier mix**.
- Tiers are those of `PREREG_43.md` §2: J journal, C conference, P preprint, B book, S software/dataset, W web/other.
- A = J ∪ C ∪ P is the academic tier.
- Numerical companion: `code/p1_theory_tables.py` → `results/p1_theory_*` (measured u_s, π ∈ {0.39 %, 0.5 %}, MC 5 seeds).

**v3 (P2, 21-10-2026).** Changes against v2, all numbers from `code/p2_theory_final.py --seed 42`
(`results/p2_theory_final.csv`, `results/numbers.json`, `results/numbers.tex`):
- Corollary 1′.3: the two headline PPV ceilings, by backend set (§1).
- Proposition 2‴: dispersion of the flag count, with a variance bound valid under any cross-tier correlation (§2).
- Proposition 4″: paper-level α-safe rules that remain valid under between-paper heterogeneity (§4).
- H5 is recorded as FAIL with its diagnosis (§4.H5). Measured P2 numbers are in §9.

Status (v2): Thm 1′, Thm 2′, Thm 3 and Prop 4′ are stated and proved below. 19-10-2026: Thm 3 proof written out in full
(variational TV bound, tightness, recall trade-off), Thm 3′ (tier mixture), Prop 3.1 (identifiers), Prop 4′ (a′)/(a″)
(simultaneous bounds; α-safety relative to the backend set). 20-10-2026 evening: measured numbers from the main
(non-interim) run10 ground truth in §8; §7 updated to the main run.

---

## 0. Setting (unchanged from v1 except for tiers)

**References and observations.**
- Each reference has a latent label H ∈ {R (real), F (fabricated)} and a tier T ∈ {J, C, P, B, S, W}.
- The screen observes Z = 1 when the registry lookup fails to resolve the reference.

**Per-tier parameters.**
- u_s = P(Z = 1 | H = R, T = s): the unresolved rate of real references in tier s.
- s_s = P(Z = 1 | H = F, T = s) ≤ 1: sensitivity.
- π_s = P(H = F | T = s): fabrication rate.

**Mix of a bibliography.**
- A bibliography of length n has tier counts n_s (Σ n_s = n) and mix w_s = n_s / n.
- Mixture rates: ū(w) = Σ_s w_s u_s and π(w) = Σ_s w_s π_s.

---

## 1. Theorem 1′ (PPV ceiling under a tier mixture)

**Theorem 1′.** Let a reference population have mix w. For the canonical existence screen (flag ⇔ Z = 1),

  PPV = Σ_s w_s π_s s_s / Σ_s w_s (π_s s_s + (1 − π_s) u_s)  ≤  Σ_s w_s π_s / Σ_s w_s (π_s + (1 − π_s) u_s).   (1′)

If π_s ≡ π, the bound equals PPV*(π, ū(w)) = π / (π + (1 − π) ū(w)).

*Proof.* By Bayes' rule over the joint law of (T, H, Z), using π_s s_s ≤ π_s in the numerator, the map
x ↦ x/(x + c) is increasing in x for c > 0. If π_s ≡ π, the denominator becomes π + (1 − π) Σ w_s u_s. ∎

**Corollary 1′.1 (two bibliographies, same π).** Let w, w′ be two mixes with ū(w) ≥ ū(w′). Then:
- PPV*(π, ū(w)) ≤ PPV*(π, ū(w′));
- the false-flag odds (1 − PPV*)/PPV* = (1 − π) ū / π are **linear** in ū;
- moving a share δ of references from tier a to tier b changes ū by δ (u_b − u_a).

Consequence: take u_W − u_A of the order of 30 percentage points (P0, pre-LLM, def. 1). Then every extra
percentage point of web / software references raises the false-flag odds by (1 − π)·0.01·0.30/π ≈ 0.6 at
π = 0.5 %. For comparison, the odds of an all-academic bibliography with u_A = 1 % are ≈ 2.0.
P1 (main, full cascade, 2019-21): u_W − u_A = 61.75 − 2.11 = 59.6 points, so each extra point of web references
adds ≈ 1.19 to the odds at π = 0.5 %, against odds ≈ 4.2 for an all-academic bibliography at u_A = 2.11 % (§8).

*Proof.* PPV* is decreasing in ū (v1, Thm 1). The odds identity is algebra; the shift identity is linearity of ū in w. ∎

**Corollary 1′.2 (restricting the screen to the academic tier).**

*Assumption F_A.* All fabricated references fall in A, i.e. π_s = 0 for s ∉ A. This is the "paper-like
hallucination" assumption; its empirical status is discussed in §5.

Then the screen that flags only unresolved A references has ceiling

  PPV*_A = π_A / (π_A + (1 − π_A) u_A),  π_A = π / w_A,

and PPV*_A ≥ PPV*(π, ū(w)) whenever u_A ≤ ū(w).

*Proof.* Within A the fabrication rate is π w / w_A = π / w_A. Apply (1′) to the single stratum A. The comparison
holds because π_A ≥ π and u_A ≤ ū (both maps are monotone). ∎

**Corollary 1′.3 (the backend set fixes the ceiling; the two headline numbers).** u_A is a property of the
screen's backend set, not of the bibliography (P1 Figure 1; `results/p1_backend_table.csv`). For the same 10,973
legitimate academic references (2019–21, def 1), with the paper-bootstrap 95 % CI of u_A carried through the
decreasing map u ↦ PPV*(π, u):

| Backend set | u_A [CI] | PPV*_A, π = 0.39 % | PPV*_A, π = 0.5 % |
|---|---|---|---|
| Crossref-only | 30.2 % [27.7, 32.6] | **1.3 %** [1.2, 1.4] | 1.6 % [1.5, 1.8] |
| Full cascade (+S2) | 2.11 % [1.64, 2.58] | **15.7 %** [13.2, 19.3] | 19.2 % [16.3, 23.5] |

So, at a fabrication rate of 0.39 %, at most about 1 flag in 78 is a fabrication under a Crossref-only screen, and
at most about 1 in 6 under the full cascade. The ratio of the false-flag odds is u_A(Crossref) / u_A(full) ≈ 14.

*Proof.* (1′) with the measured u_A. PPV* is strictly decreasing in u, so the interval endpoints map to the reverse
endpoints. ∎

---

## 2. Theorem 2′ (paper-level false-flag probability, Poisson-binomial form)

Consider a legitimate paper (π = 0) with tier counts (n_s). Under Assumption A′ (conditional independence given the
paper), N = Σ_s N_s with independent N_s ∼ Bin(n_s, u_s); N is Poisson-binomial with λ = Σ_s n_s u_s = n ū(w).

**Theorem 2′.**

  P(false flag | n, k, w, u) = P(Σ_s Bin(n_s, u_s) ≥ k)                                        (3′)

has the following properties.

**(i) Monotonicity.** (3′) is non-decreasing in every n_s and in every u_s. For fixed n, moving one reference from
tier a to tier b with u_b ≥ u_a does not decrease it. In particular, of two papers with the same n and the same π,
the one with more S/W references is flagged at least as often.

**(ii) Poisson approximation.**

  |P(N ≥ k) − P(Poi(λ) ≥ k)| ≤ λ⁻¹(1 − e^{−λ}) Σ_s n_s u_s² ≤ Σ_s n_s u_s²

(Le Cam 1960; Barbour & Hall 1984).

**(iii) Chernoff bound.** For k > λ, P(N ≥ k) ≤ e^{−λ} (e λ / k)^k. For k = 1 the probability is computed exactly:
P(N ≥ 1) = 1 − Π_s (1 − u_s)^{n_s}, with 1 − e^{−λ} ≤ P(N ≥ 1) ≤ min(1, λ).

**(iv) Pooled u versus tiered u (Hoeffding 1956, Thm 4).** Let B ∼ Bin(n, ū) have the same mean as N.
- If k ≥ λ + 1, then P(N ≥ k) ≤ P(B ≥ k).
- If k ≤ λ, then P(N ≥ k) ≥ P(B ≥ k).

So the pooled-u formula of v1 *over*-states the false-flag probability in the upper tail (thresholds above the
expected count). It *under*-states it for thresholds at or below the expected count.

**(v) Length effect.** For a population of legitimate papers whose tier counts are drawn from a law G,
Φ_k(G) = E_G P(N ≥ k) is monotone under coordinate-wise stochastic dominance of (n_s). If the mix w is held
fixed, it is increasing in n.

*Proof.*
- (3′) is the definition of N under A′.
- (i) Couple N_s(n_s + 1) = N_s(n_s) + Z with Z ≥ 0. Couple a Bernoulli(u_a) below a Bernoulli(u_b) by a common
  uniform variable, so the sum increases pointwise and {N ≥ k} grows.
- (ii) Le Cam's inequality for sums of independent Bernoulli(p_i): d_TV ≤ Σ p_i², here with p_i = u_s repeated n_s
  times. The sharper factor is the Barbour–Hall bound.
- (iii) Markov's inequality applied to e^{θN}, with E e^{θN} = Π (1 + u_i(e^θ − 1)) ≤ exp(λ(e^θ − 1)). Choose
  θ = log(k/λ). The k = 1 form follows from independence and 1 − x ≤ e^{−x}.
- (iv) Hoeffding (1956), Theorem 4: for c ≥ n p̄, P(S ≤ c) ≥ P(B ≤ c); for c ≤ n p̄ − 1, P(S ≤ c) ≤ P(B ≤ c).
  Set c = k − 1.
- (v) By (i) the integrand is coordinate-wise non-decreasing, and expectations of such functions are monotone under
  stochastic dominance. ∎

**Remark (dependence).** The v1 §2.1 mixture argument carries over tier by tier. If paper-level heterogeneity
U_s ∼ μ_s is added, the k = 1 formula at the mean is an upper bound, and for k ≥ 2 it is a lower bound on the convex
range (Jensen). H5 in the PREREG tests (3′) against the observed π = 0 corpus; a systematic excess is evidence of
within-paper dependence.

**Proposition 2‴ (dispersion of the flag count).**

*Setting.* Let paper i carry its own unresolved rates U_{i,s}, with E U_{i,s} = u_s. Assume N_{i,s} | U_{i,s} ∼
Bin(n_{i,s}, U_{i,s}) (conditional independence within a tier; Assumption A′ is the special case U_{i,s} ≡ u_s).
Let ρ_s = Var(U_{i,s}) / (u_s (1 − u_s)) be the intra-paper correlation (ICC) of tier s.

*Claim.*
- (a) Var(N_{i,s}) = n_{i,s} u_s (1 − u_s) (1 + (n_{i,s} − 1) ρ_s). This is at least the binomial variance, with
  equality iff ρ_s = 0 or n_{i,s} ≤ 1.
- (b) Whatever the correlation between tiers,
  Var(N_i) ≤ V_i := (Σ_s √Var(N_{i,s}))².
  If the tiers are uncorrelated given the paper, Var(N_i) = Σ_s Var(N_{i,s}) ≥ V0_i := Σ_s n_{i,s} u_s (1 − u_s),
  the Poisson-binomial variance.
- (c) (Cantelli) For t > 0, P(N_i ≥ E N_i + t) ≤ Var(N_i) / (Var(N_i) + t²).

*Proof.*
- (a) Law of total variance:
  Var N = E Var(N | U) + Var E(N | U) = E[nU(1 − U)] + n² Var U = n u(1 − u) − n Var U + n² Var U.
  Insert Var U = ρ u(1 − u).
- (b) Var(Σ X_s) = Σ_{s,t} Cov(X_s, X_t) ≤ Σ_{s,t} σ_s σ_t = (Σ σ_s)² (Cauchy–Schwarz). The second statement is
  (a) with ρ_s ≥ 0.
- (c) Cantelli's one-sided Chebyshev inequality. ∎

*Consequence for rules.* Every rule calibrated on Bin(n_{i,s}, u_s) (Thm 2′, Prop 4′) is calibrated on the variance
V0_i. If ρ_s > 0, the true false-flag probability above the mean can be larger. The P1/P2 data show this: on the
299 legitimate papers of 2019–21, Σ_i (N_{A,i} − λ_i)² equals **3.3 ×** Σ_i V0_i under the full cascade and **5.6 ×**
under Crossref-only, but only **0.55 ×** (full) and 0.66 × (Crossref-only) of Σ_i V_i with the fitted ICCs (§9).
So the Poisson-binomial variance is too small, and the Cauchy–Schwarz beta-binomial bound is conservative.

---

## 3. Theorem 3 (indistinguishability without identifiers; separation with them)

**Setting.**
- Let S be a set of references whose rendered form carries no resolvable persistent identifier.
- A screen observes Y: the rendered string, any metadata it extracts, and every registry or web response it obtains.
  It applies an arbitrary (possibly randomised) test φ(Y) ∈ [0, 1] (1 = "fabricated").
- Notation:
  - P_F = law of Y | H = F, S;
  - P_{R,1} = law of Y | H = R, Z = 1, S (real but unresolved);
  - u_S = P(Z = 1 | H = R, S).
- Recall and false-positive rate on S (φ may be randomised, so both are expectations):
  - TPR_S = E[φ(Y) | H = F, S] = E_{P_F} φ;
  - FPR_S = E[φ(Y) | H = R, S];
  - PPV_S = P(H = F | flag, S) = π_S TPR_S / (π_S TPR_S + (1 − π_S) FPR_S), defined when TPR_S > 0.

**Assumption B_δ (plausible fabrication).** d_TV(P_F, P_{R,1}) ≤ δ, where d_TV(P, Q) = sup_A |P(A) − Q(A)|. With
δ = 0 a fabricated reference looks exactly like a real one that no registry knows. With δ > 0 a residual signal
remains, e.g. implausible venues or author–title combinations.

**Theorem 3 (indistinguishability).** Under B_δ, every test φ: Y → [0, 1] satisfies on S

  FPR_S ≥ u_S · (TPR_S − δ)₊,                                                                    (4)

and consequently, with fabrication rate π_S on S and TPR_S > 0,

  PPV_S ≤ π_S TPR_S / (π_S TPR_S + (1 − π_S) u_S (TPR_S − δ)₊).                                 (5)

(a) For δ = 0 the right side of (5) equals PPV*(π_S, u_S) = π_S / (π_S + (1 − π_S) u_S), whatever the test. Thm 1's
ceiling therefore holds for **every** screen on S, including screens that use authors, venues, web search or LLM
judgement — not only for resolvability-based ones.
(b) The bound is attained: the canonical screen φ₀ = 1{Z = 1} has FPR_S = u_S and TPR_S = s_S, so for δ = 0 and
s_S = 1, (4) and (5) hold with equality. No screen on S beats the canonical one in PPV at full recall.
(c) Trade-off form: for any target recall r ∈ (δ, 1], every test with TPR_S ≥ r has FPR_S ≥ u_S (r − δ). Lowering
the false-positive rate below u_S (r − δ) is possible only by giving up recall.

*Proof.*
1. *Variational bound.* Let P, Q have densities p, q with respect to μ = P + Q. For φ with values in [0, 1],
   E_P φ − E_Q φ = ∫ φ (p − q) dμ ≤ ∫_{p > q} (p − q) dμ = P(p > q) − Q(p > q) ≤ d_TV(P, Q),
   because φ ≤ 1 where p − q > 0 and φ ≥ 0 where p − q ≤ 0. Applying the same argument to 1 − φ gives the
   absolute value: |E_P φ − E_Q φ| ≤ d_TV(P, Q).
2. *Real-unresolved references are flagged almost as often as fabricated ones.* By step 1 with P = P_F, Q = P_{R,1}
   and B_δ: E_{P_{R,1}} φ ≥ E_{P_F} φ − δ = TPR_S − δ. Since E_{P_{R,1}} φ ≥ 0, also E_{P_{R,1}} φ ≥ (TPR_S − δ)₊.
3. *Law of total expectation over Z.* Given H = R and S,
   FPR_S = u_S E[φ | R, Z = 1, S] + (1 − u_S) E[φ | R, Z = 0, S] ≥ u_S E_{P_{R,1}} φ,
   because φ ≥ 0. Together with step 2 this is (4).
4. *PPV.* By Bayes' rule, PPV_S = π_S TPR_S / (π_S TPR_S + (1 − π_S) FPR_S). For fixed TPR_S > 0 the map
   x ↦ a / (a + b x) (a, b > 0) is decreasing in x, so inserting the lower bound (4) for FPR_S gives (5).
5. *(a)* For δ = 0, (TPR_S − δ)₊ = TPR_S and TPR_S cancels from (5).
   *(b)* φ₀ is a function of Y because Y contains every registry response, and Z is defined by those responses.
   E[φ₀ | R, S] = P(Z = 1 | R, S) = u_S and E[φ₀ | F, S] = s_S; with s_S = 1 the right side of (4) is u_S.
   *(c)* is (4) with TPR_S ≥ r and the monotonicity of (·)₊. ∎

*Remark (what B_δ does and does not assume).* B_δ compares fabricated references with real references that the
registries miss, not with all real references. It is therefore weak where fabrications imitate the long tail
(grey literature, workshop papers, non-English venues) and strong where they imitate famous papers, which a registry
would resolve. δ is not identified from our data. The PPV bound (5) is reported at δ = 0 and as a function of δ.

**Theorem 3′ (tier mixture).** Let S be split into tiers s with shares w_s, unresolved rates u_s and B_{δ_s} holding
tier-wise. Then, for every test, FPR_S ≥ Σ_s w_s u_s (TPR_s − δ_s)₊. With TPR_s ≡ TPR and δ_s ≡ δ this is
ū(w) (TPR − δ)₊, so the ceiling of Thm 1′ (pooled π) holds for every screen.

*Proof.* Apply (4) in each tier and average with weights w_s (law of total expectation over T). ∎

**Proposition 3.1 (separation with identifiers).**

*Setting.* Let S′ be references whose rendered form prints an identifier (DOI or 10.48550/arXiv.<id>). Let I be the
event "the printed identifier resolves and the registry metadata match the rendered metadata (title similarity
≥ τ and first author)".

*Assumptions.*
- (a) P(I^c | H = R, S′) ≤ u_id: registry outage, typo or style corruption of the identifier.
- (b) P(I | H = F, S′) ≤ ε: a fabricated reference passes only by copying a real identifier together with that
  record's metadata, and is then a mis-citation, not a non-existent work.

*Claim.*
- The identifier test φ_id = 1 − 1_I has FPR ≤ u_id and TPR ≥ 1 − ε.
- d_TV(P_{F,S′}, P_{R,S′}) ≥ 1 − u_id − ε, so B_δ fails on S′ for every δ < 1 − u_id − ε.
- PPV_{S′} ≥ π (1 − ε) / (π (1 − ε) + (1 − π) u_id).

*Proof.* FPR = P(I^c | R, S′) ≤ u_id and TPR = P(I^c | F, S′) ≥ 1 − ε by (a) and (b). Taking A = I^c in the
definition of d_TV gives d_TV ≥ P_F(I^c) − P_R(I^c) ≥ (1 − ε) − u_id. For the PPV, the map (t, f) ↦ πt / (πt + (1 − π) f)
is increasing in t and decreasing in f; insert t ≥ 1 − ε and f ≤ u_id. ∎

*Measured u_id.* The render experiment gives two related rates on certified-real references rendered with the
DOI-printing style (`results/p1_screen_fp.csv`): the identifier route alone fails for 3.2 % (column `idonly`; this
includes references whose identifier was not printed or not extracted), and the identifier route followed by the
title cascade fails for 0.043 % (column `union`). The second is the rate that matters for a screen that uses printed
identifiers.

*Interpretation.*
- Without an identifier the problem is information-theoretically hard: no test can push the false-positive rate below
  u_S × recall.
- With an identifier, the error rates are bounded by u_id and ε, quantities controlled by the registries rather than by
  coverage.
- Printing resolvable identifiers is therefore the condition that makes a bibliography machine-verifiable. The render
  experiment (E2) measures how often common styles erase them.
- **Identifier erasure:** IEEEtran.bst v1.14 has no DOI field; in the pilot it printed 20.3 % of .bib DOIs (only
  through URL fields), versus 74.5 % for the DOI patch and 100 % for elsarticle-num (n = 192 refs, 30 papers).

---

## 4. Proposition 4′ (tier-wise α-safe desk-reject rule)

**(a) Rule.** Count only unresolved academic references, N_A = Σ_{s∈A} Bin(n_s, u_s). Let u⁺_s be upper confidence
bounds (paper-level bootstrap 97.5 % quantile; the bootstrap is used because references cluster within papers and
Clopper–Pearson assumes independence). Define

  k*_A(n_A, α) = min{ k : P(Σ_{s∈A} Bin(n_s, u⁺_s) ≥ k) ≤ α }.

Under A′ and u_s ≤ u⁺_s, the rule "desk-reject iff N_A ≥ k*_A" rejects a legitimate paper with probability ≤ α. If
the bounds hold simultaneously with probability ≥ 1 − δ over the estimation sample, the guarantee holds with that
probability.

*Proof.* Monotonicity of (3′) in each u_s (Thm 2′(i)), then the definition of k*_A. ∎

**(a′) Simultaneous bounds.** The guarantee needs u_s ≤ u⁺_s for all s ∈ A at once. With per-tier upper bounds at
level 1 − δ/|A| (|A| = 3), Bonferroni gives simultaneous coverage ≥ 1 − δ. Default in the scripts: the 97.5 %
paper-bootstrap quantile per tier (individual coverage). Simultaneous coverage of the estimation step is therefore
an assumption of the rules below, not a computed guarantee.

**(a″) α-safety is relative to the backend set.** u_s and hence k*_A depend on the backends of the screen
(Crossref-only vs the full cascade, `results/p1_backend_table.csv`). A rule calibrated on the full cascade is not
α-safe for a Crossref-only screen: by Thm 2′(i), u_s(Crossref-only) ≥ u_s(full) implies
P(N_A ≥ k | Crossref-only) ≥ P(N_A ≥ k | full). The scripts report k*_A for both scenarios.

**(b) What it costs.** Under F_A (all fabrications in A) the recall loss from ignoring S/W/B flags is zero. Without
F_A the loss equals the share of fabricated references outside A. It must be reported, and is measured where a
labelled set of fabricated references exists (P1 recall sets).

**(c) Comparison on the corpus (PREREG §7, line 5).** For the 2019–2021 corpus (π ≈ 0), the script reports the
number of papers flagged under each rule, by field:
- k = 1 on all tiers (ACL-style);
- k = 2 on all tiers (NeurIPS-style);
- k*_A at α ∈ {0.05, 0.01}.

**(d) Conference-wide screening.** As in v1 §4(b), with the per-paper p-value p_i = P(N_A,i ≥ observed | u⁺) and
BH / BY over papers.

**Proposition 4″ (paper-level α-safe rules under heterogeneity).**

*Setting.*
- The setting of Prop 2‴ on the academic tier A = {J, C, P}.
- Paper i has counts n_{i,s} and flag count N_{A,i} = Σ_{s∈A} N_{i,s}.
- u⁺_s and ρ⁺_s are upper bounds on u_s and ρ_s: the paper-bootstrap 97.5 % quantiles.
- α ∈ (0, 1).

*Rules* (all thresholds are per paper, through n_{i,s}):

- **R1 (estimation margin only).** k¹_i = min{k : P(PoiBin(n_{i,s}, u⁺_s) ≥ k) ≤ α}.
  It sets δ_s = u⁺_s − u_s, and it is Prop 4′ evaluated per paper.
- **R2 (heterogeneity quantile).** Let q_s be the (1 − α/(2|A|)) quantile of the Beta law with mean u⁺_s and ICC
  ρ⁺_s. Then k²_i = min{k : P(PoiBin(n_{i,s}, q_s) ≥ k) ≤ α/2}.
- **R3 (Cantelli).** Set λ⁺_i = Σ_s n_{i,s} u⁺_s and V⁺_i = (Σ_s √(n_{i,s} u⁺_s (1 − u⁺_s)(1 + (n_{i,s} − 1) ρ⁺_s)))².
  Then k³_i = ⌈λ⁺_i + √(V⁺_i (1 − α)/α)⌉.

*Claims.*
- **(i) R1.** If U_{i,s} ≤ u⁺_s for all s ∈ A (the paper's own rates are below the corpus bound) and A′ holds within
  the paper, then P(N_{A,i} ≥ k¹_i | U_i) ≤ α.
  - Without that condition there is no guarantee. Under heterogeneity, the population false-reject rate is
    E P(N ≥ k¹ | U) and can exceed α.
- **(ii) R2.** If, for each s, U_{i,s} ∼ Beta with mean ≤ u⁺_s and ICC ≤ ρ⁺_s, and the quantile is monotone in
  these, then P(legitimate paper i is rejected) ≤ α. No assumption is made on the dependence across tiers.
- **(iii) R3.** If E N_{A,i} ≤ λ⁺_i and Var N_{A,i} ≤ V⁺_i, then P(N_{A,i} ≥ k³_i) ≤ α.
  - No distributional assumption is needed beyond the two moments.
  - By Prop 2‴(b), Var N_{A,i} ≤ V⁺_i holds under any cross-tier correlation, given the tier moments.

*Proof.*
- (i) Given U_i, N_{A,i} is Poisson-binomial with rates U_{i,s} ≤ u⁺_s. Thm 2′(i) gives monotonicity in each rate;
  then use the definition of k¹_i.
- (ii) Let E = {∃ s ∈ A : U_{i,s} > q_s}. By the union bound and the quantile choice, P(E) ≤ |A| · α/(2|A|) = α/2.
  On E^c, the rates are ≤ q_s, and by (i) with q_s in place of u⁺_s, P(N ≥ k²_i | U_i) ≤ α/2. So
  P(N ≥ k²_i) ≤ P(E) + E[P(N ≥ k²_i | U_i) 1_{E^c}] ≤ α/2 + α/2.
- (iii) Prop 2‴(c) with t = k³_i − E N ≥ √(V⁺ (1 − α)/α) gives P ≤ V / (V + t²) ≤ V⁺ / (V⁺ + V⁺ (1 − α)/α) = α. ∎

*Measured (§9, 299 legitimate papers of 2019–21).*
- **R1 is not α-safe:** at α = 0.05 (full cascade) it rejects 19/299 = 6.4 % [Wilson 4.1, 9.7] of the legitimate
  papers; at α = 0.01 it rejects 12/299 = 4.0 % [2.3, 6.9].
  - MC under the fitted beta-binomial model (5 seeds × 20,000 papers): 5.2 % and 2.5 %.
  - Under Crossref-only: 12.7 % and 7.0 %.
- **R2 and R3 are α-safe on the data:**
  - R2: 0/299 at both α, in both scenarios.
  - R3: 1/299 at α = 0.05 (full) and 0/299 otherwise. MC ≤ 0.03 %.
- **The price is the threshold.** For the median paper (n_A = 32, full cascade, α = 0.05):
  - k¹ = 5, k² = 19, k³ = 15;
  - under Crossref-only: 12, 27, 32.
  - The cost of these thresholds in recall must be read together with the recall table.

**§4.P Policy conclusion 1 (desk-reject thresholds).** Numbers: 299 legitimate papers of 2019–21 (def 1), seed 42,
`results/p2_theory_final.csv`.

- **(a) A threshold with only an estimation margin is not α-safe.**
  - R1 sets δ = the upper CI bound of u_s, i.e. a margin for estimation error only.
  - At nominal α = 0.05 (full cascade) it rejects 19/299 = 6.4 % [Wilson 4.1, 9.7] of the legitimate papers; MC
    under the fitted beta-binomial gives 5.2 %. At α = 0.01 it rejects 12/299 = 4.0 % [2.3, 6.9].
  - Under Crossref-only the rates are 12.7 % and 7.0 %.
  - The cause is Prop 2‴: unresolved references concentrate in a minority of papers (ICC 0.045–0.082 on A). The
    observed dispersion is 3.3× the Poisson-binomial variance.
- **(b) Thresholds that are α-safe need k = 15–19; so "≥ 2 flags" cannot be calibrated with today's backends.**
  - The rules that remain α-safe under heterogeneity are R2 (Beta quantile) and R3 (Cantelli). For the median paper
    (n_A = 32, full cascade, α = 0.05) they need k = 19 and 15. Across the five typical papers the range is
    8–27 / 6–20; under Crossref-only it is 11–57 / 14–76.
  - For the same papers, k = 2 lies below every α-safe threshold. P1 measured what this means: the k = 2 rule flags
    142/299 = 47.5 % of legitimate papers even with the full cascade.
  - Hence no α-safe rule built on the current backend sets resembles the deployed "≥ 1" or "≥ 2 non-existent
    references" policies. The margin needed to absorb between-paper heterogeneity is an order of magnitude larger than
    the number of flags these policies act on.
- **(c) Printed identifiers are the necessary condition for an α-safe rule with small k** (consequence of Thm 3 and
  Prop 3.1).
  - Without an identifier, no test can push FPR below u_S × recall (Thm 3). So small-k rules are out of reach
    whatever the screen does.
  - With an identifier, a screen that checks the printed identifier first and falls back to the title cascade flags
    a real reference only when both routes fail. In the render experiment (certified-real references, DOI-printing
    style with identifiers kept, union screen, GROBID) this rate is 0.043 % (1/2,323; paper-bootstrap upper bound
    0.185 %). The identifier route alone fails for 3.2 % (74/2,325), mostly because the identifier is not printed or
    not extracted, so the title fallback matters. (Correction of 24-10-2026: the P2 version of this paragraph used the
    IEEEtran strip cell, 0.26 %, which carries no printed identifier.)
  - Setting u_s to this rate for every academic tier, with u⁺ = 0.185 % and the full-cascade ρ⁺_s (conservative, since
    no ICC is measurable from one flag), the median paper (n_A = 32) needs k = 6 (R2) and k = 3 (R3) at α = 0.05,
    against 19 and 15 without identifiers. Across the five papers this is 4–9 and 2–5 (§9).
  - Under conditional independence, P(N_A ≥ 2) = 0.009 % at n_A = 32 (0.16 % at u⁺). With the conservative
    dispersion, the Cantelli bound for k = 2 is 0.093 at n_A = 32, so k = 2 is not certified at α = 0.05 even then.
  - **Caveat:** the rate rests on a single flag and is measured on certified-real references, which already resolved
    by identifier once. It is a lower bound for identifiers in the wild (typos, style corruption).

*Policy conclusion 1.* A desk-reject rule that counts "non-existent" references is α-safe only at thresholds far above
the 1–2 used in practice, unless the references carry resolvable identifiers. Requiring printed DOIs or arXiv ids,
or a style that prints them, is the precondition for any small-k rule. It is not a cosmetic recommendation.

**H5 (PREREG §5).**
- **Result:** FAIL, kept as registered. Under (3′), with per-paper LOO u_s, all tiers and k = 2, the prediction for
  the tertiles T2/T3 lies outside the Wilson CI in all three scenarios.
- **Diagnosis** (P1, exploratory):
  - (b) the reference sets on the u_s side and on the flag side are identical: PASS;
  - (a) per-paper n_{i,s}: FAIL;
  - (c) leave-one-out: FAIL (LOO equals the full sample, so the failure is not leakage);
  - the beta-binomial (Thm 2″) also FAILs at T3.
- **What it means:** the mean count is predicted correctly; the spread is not. This is Prop 2‴: observed dispersion
  is 3.3× the Poisson-binomial value. ICC (+S2): J 0.082, C 0.045, P 0.073, B 0.314, W 0.354.

---

## 5. Open points (to resolve before CP-B2)

- **F_A.** No source in `theory/params_from_lit.csv` reports the tier of fabricated references. Badalova & Mayr's test
  set and the GPTZero NeurIPS list are candidates for a count.
- **Mixed fabrication rates.** If π_s differs across tiers, Corollary 1′.1 must use the general form of (1′).
- **Bonferroni k*_A.** Prop 4′ (a′) needs 99.17 % paper-bootstrap quantiles per academic tier; not computed. Prop 4″ R2/R3 supersede it: they use per-tier 97.5 % bounds and control α by a union bound over the heterogeneity event instead (the estimation-coverage event is separate and is stated as an assumption).
- **Monotonicity of the Beta quantile in (mean, ICC)** (Prop 4″(ii)) is checked numerically on the grid used, not proved in general.
- **δ in Thm 3.** Not identified from our data; report (5) as a function of δ.

## 6. References (theory)

Le Cam (1960); Barbour & Hall (1984); Hoeffding (1956) "On the distribution of the number of successes in independent
trials", Ann. Math. Statist. 27:713–721; Benjamini & Hochberg (1995); Benjamini & Yekutieli (2001); Ioannidis (2005).
To be added to `lit/refs.bib` with verified DOIs in P1.

---

## 7. EXPLORATORY — Theorem 2″ (beta-binomial paper heterogeneity), draft 20-10-2026

**Status: exploratory.** Not preregistered and not an amendment. H5 (PREREG §5) is tested on (3′) only, and its
verdict stands. Companion: `code/p1_h5_betabinom.py` → `results/[interim/]p1_h5_betabinom.{json,csv}`.

**Model (A″).** Paper i draws a tier-wise rate U_is ∼ Beta(a_s, b_s), independently across tiers and papers. Given
U_is, its n_is references in tier s are unresolved independently with probability U_is. Hence
N_is ∼ BetaBin(n_is, a_s, b_s), with
- mean n_is μ_s, where μ_s = a_s / (a_s + b_s);
- ICC ρ_s = 1 / (a_s + b_s + 1);
- variance n_is μ_s(1 − μ_s)[1 + (n_is − 1)ρ_s].

φ_s = 1 + (n̄_s − 1)ρ_s is the variance inflation at the mean per-paper count n̄_s.

**Theorem 2″ (draft).** Under A″ and π = 0,

  P(false flag | n_i, k) = P(Σ_s BetaBin(n_is, a_s, b_s) ≥ k),                                (3″)

and the following hold.

(i) If ρ_s → 0 with μ_s = u_s fixed, (3″) reduces to (3′).

(ii) For k = 1, (3″) ≤ (3′) at u_s = μ_s, because E[(1 − U)^n] ≥ (1 − μ)^n by Jensen.
- More generally, the paper-level count is a mixed binomial.
- For thresholds at or below its mean, overdispersion lowers P(N ≥ k) relative to (3′); for thresholds well above it,
  overdispersion raises P(N ≥ k). This is a mean-preserving spread of the paper rate.

(iii) A shared paper effect across tiers (U_is = g_s(V_i)) adds positive cross-tier covariance and widens the spread
further. A″ is the special case of no sharing.

*Proof sketch.*
- (i) Beta(μ/ρ′, (1 − μ)/ρ′) concentrates at μ as ρ′ → 0.
- (ii) x ↦ (1 − x)^n is convex. For general k, P(N ≥ k | U) is convex in U on the lower region and concave on the
  upper region of the binomial mean, and the result follows by integration under the Beta mixing law.
- A full statement with explicit crossing points is TODO before CP-B2. ∎

**Estimation.**
- (μ_s, ρ_s) are fitted by MLE per tier over 2019-21 papers.
- Overdispersion is tested by an LR test of ρ_s = 0; the null is on the boundary, so the reference is a 50:50
  χ²₀ : χ²₁ mixture.
- The CI for ρ_s is a paper bootstrap (B = 200, seed 42).
- Prediction uses leave-one-paper-out fits, as in H5, compared per n-tertile with the Wilson 95 % CI.
- The exploratory verdict uses the same rule as H5: monotone, and every tertile prediction inside its CI.

**Interim result (20-10, `results/interim/`, def 1, 2019-21, 299 papers):**
- Overdispersion is present in every tier with n̄ > 2 (LR p < 1e-6), except S, where u ≈ 98 % and ρ̂ = 0.
- Under +DBLP:

  | Tier | ρ̂ (ICC) | 95 % CI |
  |---|---|---|
  | J | 0.092 | 0.045–0.144 |
  | C | 0.025 | 0.011–0.041 |
  | P | 0.055 | 0.000–0.141 |
  | B | 0.203 | 0.088–0.323 |
  | W | 0.276 | 0.206–0.340 |

- Thm 2″ moves the k = 2 predictions toward the observed shares, but only partly. Under +DBLP:
  - T2: 0.792 → 0.762, against an observed 0.646 [0.548, 0.734]. Still outside the CI.
  - T3: 0.903 → 0.866, against an observed 0.800 [0.711, 0.867]. Just inside the CI.
- Exploratory verdict: FAIL.
- Cross-tier Spearman correlations of per-paper rates under +DBLP are ≈ 0 (J–C 0.04, J–W 0.03, C–W 0.00).
  Model (iii), a shared paper effect, is therefore not supported as the explanation either.
- The remaining gap points to a mixture across the n-tertiles: mid-length papers resolve better than the pooled tier
  rates imply. This is open.

**Main result (20-10 evening, `results/p1_h5_betabinom.{json,csv}`, run10 ground truth, B = 200, seed 42).**
Same 12,599 refs / 299 papers on the rate side and the flag side (`results/p1_h5_diag.json`, `same_set: true`).
- Full cascade (+S2), ρ̂ by tier:

  | Tier | u pooled | ρ̂ (ICC) | 95 % CI | φ |
  |---|---|---|---|---|
  | J | 3.73 % | 0.082 | 0.036–0.163 | 1.97 |
  | C | 1.35 % | 0.045 | 0.018–0.076 | 1.85 |
  | P | 1.01 % | 0.073 | 0.000–0.222 | 1.43 |
  | B | 16.4 % | 0.314 | 0.129–0.451 | 1.48 |
  | S | 98.4 % | 0 | 0–0.065 | 1.00 |
  | W | 61.8 % | 0.354 | 0.294–0.416 | 2.62 |

- k = 2, observed vs (3′) LOO vs (3″):

  | Scenario | Tertile | Observed [Wilson] | (3′) | (3″) [boot] |
  |---|---|---|---|---|
  | +S2 | T1 | 0.400 [0.309, 0.498] | 0.421 | 0.383 [0.353, 0.413] |
  | +S2 | T2 | 0.515 [0.418, 0.611] | 0.630 | 0.574 [0.537, 0.604] |
  | +S2 | T3 | 0.510 [0.413, 0.606] | 0.763 | 0.688 [0.651, 0.719] |
  | +DBLP | T2 | 0.646 [0.548, 0.734] | 0.791 | 0.761 |
  | +DBLP | T3 | 0.800 [0.711, 0.867] | 0.903 | 0.866 |
  | Crossref-only | T2 | 0.970 [0.915, 0.990] | 1.000 | 0.998 |

- Under +S2 the observed share is flat from T2 to T3 (51/99 vs 51/100), so even the observed sequence is not
  monotone; (3″) brings T2 inside the CI but leaves T3 outside. Exploratory verdict: FAIL (all scenarios, k = 1, 2, 3
  except Crossref-only k = 1).
- Cross-tier Spearman correlations of per-paper rates (+S2): J–C 0.16 (281 papers), J–W 0.15, C–W 0.02, C–P 0.08.
  A weak shared paper effect exists for J–C/J–W under the full cascade, but it widens the spread (model (iii)) and
  cannot explain predictions that are too high.
- Per-paper u_A (+S2) quantiles P10/P25/P50/P75/P90 = 0 / 0 / 0 / 2.8 / 8.0 %: more than half the papers have no
  unresolved academic reference; the unresolved references concentrate in a minority of papers.

---

## 8. Measured numbers (P1 main, 20-10-2026; `results/p1_theory_headlines.json`, `p1_alpha_rules.csv`)

Def 1, rates from 2019-21 citing papers (π ≈ 0), 10,973 academic refs / 297 papers, paper-bootstrap CI (B = 1000,
seed 42). MC check: 5 seeds × 20,000 papers, max |MC − exact| / se = 1.16.

| Scenario | u_A [CI] | PPV*_A (π = 0.39 %) | PPV*_A (π = 0.5 %) | P(ff) n=50, k=2 | P(ff) n=150, k=2 | k*_A(n=150), α = 0.05 / 0.01 |
|---|---|---|---|---|---|---|
| Crossref-only | 30.2 % [27.7, 32.6] | 1.3 % | 1.6 % | ≈ 1.000 | 1.000 | 56 / 60 |
| +DBLP | 4.03 % [3.38, 4.75] | 8.9 % | 11.1 % | 0.604 | 0.985 | 11 / 13 |
| +S2 (full) | 2.11 % [1.64, 2.58] | 15.7 % | 19.2 % | 0.285 | 0.827 | 7 / 9 |

PPV*_A is the pooled-π ceiling (1′) on tier A; under F_A it is 17.3 % / 21.1 % (+S2). P(ff) is Bin(n, u_A) ≥ k, i.e.
an all-academic bibliography of length n; the field-mix curves of Thm 2′ are in `p1_theory_tables.csv` (pff_vs_n).

Rules on the 299 papers of 2019-21 (PREREG §7 line 5), papers flagged:

| Scenario | k = 1 (all tiers) | k = 2 (all tiers) | k*_A, α = 0.05 | k*_A, α = 0.01 |
|---|---|---|---|---|
| Crossref-only | 298 (99.7 %) | 286 (95.7 %) | 38 (12.7 %) | 21 (7.0 %) |
| +DBLP | 249 (83.3 %) | 199 (66.6 %) | 21 (7.0 %) | 12 (4.0 %) |
| +S2 (full) | 198 (66.2 %) | 142 (47.5 %) | 19 (6.4 %) | 12 (4.0 %) |

H5 (PREREG §5, (3′) LOO per paper, all tiers, k = 2): FAIL in all three scenarios (table in §7).

---

## 9. Measured numbers, P2 (21-10-2026; `results/p2_theory_final.csv`, `results/numbers.json`)

**Inputs.** 2019–21, def 1, 299 legitimate papers. u_s and u⁺_s are taken from the backend table. ρ_s and ρ⁺_s come
from the exploratory beta-binomial fit (`p1_h5_betabinom.json`, B = 200).

| Tier | u_s full [u⁺_s] | ρ_s full [ρ⁺_s] | u_s Crossref-only [u⁺_s] | ρ_s Crossref-only [ρ⁺_s] |
|---|---|---|---|---|
| J | 3.73 % [4.91 %] | 0.082 [0.163] | 18.45 % [21.16 %] | 0.086 [0.117] |
| C | 1.35 % [1.82 %] | 0.045 [0.076] | 27.67 % [30.01 %] | 0.114 [0.149] |
| P | 1.01 % [2.04 %] | 0.073 [0.222] | 66.92 % [71.36 %] | 0.143 [0.181] |

**Dispersion (Prop 2‴).** Σ (N − λ)² is the observed squared deviation; V0 is the Poisson-binomial variance; V is the
beta-binomial variance with the Cauchy–Schwarz cross-tier bound.

| Scenario | Σ (N − λ)² | Σ V0 | Σ V | ratio to V0 | ratio to V |
|---|---|---|---|---|---|
| Full | 741.6 | 224.4 | 1341.2 | 3.30 | 0.55 |
| Crossref-only | 11,355.9 | 2,046.1 | 17,188.5 | 5.55 | 0.66 |

**Legitimate papers rejected** (k / 299 [Wilson 95 %]; MC = beta-binomial model, 5 seeds × 20,000):

| Scenario | α | R1 (CI margin) | R2 (Beta quantile) | R3 (Cantelli) |
|---|---|---|---|---|
| Full | 0.05 | 19 (6.4 %) [4.1, 9.7]; MC 5.2 % | 0 [0, 1.3]; MC 0 | 1 (0.3 %) [0.06, 1.9]; MC 0.03 % |
| Full | 0.01 | 12 (4.0 %) [2.3, 6.9]; MC 2.5 % | 0 [0, 1.3] | 0 [0, 1.3] |
| Crossref-only | 0.05 | 38 (12.7 %) [9.4, 17.0]; MC 10.8 % | 0 [0, 1.3] | 0 [0, 1.3] |
| Crossref-only | 0.01 | 21 (7.0 %) [4.6, 10.5]; MC 5.7 % | 0 [0, 1.3] | 0 [0, 1.3] |

**Thresholds k_i for 5 typical papers** (n_A at the 10/25/50/75/90 % quantiles of the 299 papers; α = 0.05, then α = 0.01):

| n_A | Full: R1 / R2 / R3 | Crossref-only: R1 / R2 / R3 |
|---|---|---|
| 11 | 3 / 8 / 6 · 3 / 10 / 12 | 6 / 11 / 14 · 7 / 12 / 28 |
| 19 | 3 / 12 / 8 · 3 / 16 / 16 | 16 / 20 / 32 · 17 / 20 / 58 |
| 32 | 5 / 19 / 15 · 6 / 25 / 31 | 12 / 27 / 32 · 14 / 30 / 63 |
| 47 | 4 / 18 / 13 · 5 / 25 / 27 | 21 / 42 / 56 · 23 / 46 / 109 |
| 66 | 5 / 27 / 20 · 6 / 37 / 44 | 28 / 57 / 76 · 31 / 63 / 146 |

- k is not monotone in n_A across these five papers. The reason is that each threshold depends on the paper's own
  J/C/P mix: a paper with more journal references gets a higher k at the same n_A, because u_J and ρ_J are the
  largest of the three tiers.
- A threshold larger than n_A (Crossref-only, R3) means the paper can never be rejected.

**Identifier scenario (§4.P (c)).**
- **Superseded 24-10-2026:** the table below is the P2 version (u_id = 0.26 %, IEEEtran strip). The corrected scenario
  (u = 0.043 %, u⁺ = 0.185 %, DOI-printing style, identifiers kept) is in `results/p2_theory_final.csv` (tables
  `k_identifier`, `p_two_flags_identifier`) and §4.P (c).
- Inputs: u_id = 0.26 % (6/2,316) and u⁺_id = 0.60 % for every academic tier; ρ⁺_s as in the full cascade
  (conservative).
- Same five papers as above.
- P(N ≥ 2) is the Poisson-binomial value at u_id, with the value at u⁺_id in brackets.

| n_A | α = 0.05: R1 / R2 / R3 | α = 0.01: R1 / R2 / R3 | P(N ≥ 2) [at u⁺] | Cantelli bound, k = 2 |
|---|---|---|---|---|
| 11 | 2 / 5 / 3 | 2 / 8 / 5 | 0.04 % [0.19 %] | 0.053 |
| 19 | 2 / 8 / 4 | 2 / 14 / 9 | 0.11 % [0.58 %] | 0.159 |
| 32 | 2 / 11 / 6 | 3 / 18 / 12 | 0.32 % [1.6 %] | 0.276 |
| 47 | 2 / 12 / 7 | 3 / 20 / 14 | 0.67 % [3.3 %] | 0.377 |
| 66 | 3 / 16 / 9 | 3 / 28 / 21 | 1.3 % [6.0 %] | 0.602 |
