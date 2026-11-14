# THEORY_43 — v4 (P3D: erratum to v3 after the independent proof check)

Topic 43: false positives of reference-existence screens on legitimate bibliographies.

**v4 (P3D, 07-11-2026).** v3 plus all 12 items of `P1/PROOF_CHECK_43.md` (e), recorded in `P3D/ERRATUM_43.md`. This is an erratum: no change to the pre-registration, H1–H5, their verdicts or the data. New numbers come from `code/p3d_theory_fix.py --seed 42` (`results/p3d_theory_fix.{csv,json}`). Sections 0–4, 8 and 9 are printed in Supplement S1.

**Numbering (CP0R question 9).** One Theorem, the rest Propositions; the same numbers are used in the article.

| v4 and article | v3 | Items of the proof check |
|---|---|---|
| Proposition 1 (PPV), Corollaries 1.1–1.3 | Thm 1′, Cor 1′.1–1′.3 | m1, m2, m3 |
| Proposition 2, part A (distribution of the flag count) | Thm 2′ | m4, m5, m6, m7 |
| Proposition 2, part B (dispersion) | Prop 2‴ | m8 |
| Theorem 1 (the u_S factor), Corollary T (tier mixture) | Thm 3, Thm 3′ | m9, m10, M7 |
| Proposition 3 (identifiers) | Prop 3.1 | M1 |
| Lemma 4.0 (tier-wise rule under independence) | Prop 4′ | m11, M5 |
| Proposition 4 (rules R1, R2, R3) | Prop 4″ | M2, M3, M4, m12 |
| §7 exploratory beta-binomial model | Thm 2″ | m7 |

**Tiers** are those of `PREREG_43.md` §2: J journal, C conference, P preprint, B book, S software or dataset, W web or other. A = J ∪ C ∪ P is the academic tier.

---

## 0. Setting

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

**Notation.** δ is used only for the total-variation radius of Assumption B_δ. η is the miscoverage of the estimation step. u⁻_s and u⁺_s are the lower and upper paper-bootstrap 95 % bounds of u_s (the 2.5 % and 97.5 % quantiles), and ρ⁺_s is the upper bound of ρ_s.

---

## 1. Proposition 1 (PPV ceiling under a tier mixture)

*Source.* This is the positive predictive value of Bayes' rule (Ioannidis 2005); HALLMARK §E.1 prints the same closed form as a function of prevalence and compares verifiers with it. What is added here is the tier mixture and the measured u, which make the ceiling a property of the set of data sources a screen queries.

**Proposition 1.** Let a reference population have mix w. For the canonical existence screen (flag ⇔ Z = 1), when the denominator on the left is positive,

  PPV = Σ_s w_s π_s s_s / Σ_s w_s (π_s s_s + (1 − π_s) u_s)  ≤  Σ_s w_s π_s / Σ_s w_s (π_s + (1 − π_s) u_s).   (1)

If π_s ≡ π, the bound equals PPV*(π, ū(w)) = π / (π + (1 − π) ū(w)).

*Proof.* By Bayes' rule over the joint law of (T, H, Z). Using π_s s_s ≤ π_s in the numerator and in the denominator at once, the map x ↦ x/(x + c) is increasing in x for c ≥ 0 and x + c > 0. If π_s ≡ π, the denominator becomes π + (1 − π) Σ w_s u_s. ∎

**Corollary 1.1 (two bibliographies, same π).** Let w, w′ be two mixes with ū(w) ≥ ū(w′). Then:
- PPV*(π, ū(w)) ≤ PPV*(π, ū(w′));
- the false-flag odds (1 − PPV*)/PPV* = (1 − π) ū / π are **linear** in ū;
- moving a share ν of references from tier a to tier b changes ū by ν (u_b − u_a).

Consequence, on the main 2019–21 run under the full cascade: u_W − u_A = 61.75 − 2.11 = 59.6 points, so each extra point of web references adds ≈ 1.19 to the odds at π = 0.5 %, against odds ≈ 4.2 for an all-academic bibliography at u_A = 2.11 % (§8). This assumes the same π in the tier moved to and from.

*Proof.* PPV* is decreasing in ū. The odds identity is algebra; the shift identity is linearity of ū in w. ∎

**Corollary 1.2 (restricting the screen to the academic tier).**

*Assumption F_A.* All fabricated references fall in A, i.e. π_s = 0 for s ∉ A. Assume also π ≤ w_A, w_A > 0, and π_s ≡ π_A on A (otherwise read u_A with (1 − π_s) weights).

Then the screen that flags only unresolved A references has ceiling

  PPV*_A = π_A / (π_A + (1 − π_A) u_A),  π_A = π / w_A,

and PPV*_A ≥ PPV*(π, ū(w)) whenever u_A ≤ ū(w).

*Proof.* Within A the fabrication rate is π / w_A. Apply (1) to the single stratum A. The comparison holds because π_A ≥ π and u_A ≤ ū (both maps are monotone). The condition u_A ≤ ū is not needed under F_A: the restricted screen has the same numerator and a denominator smaller by Σ_{s∉A} w_s u_s. ∎

**Corollary 1.3 (the set of data sources fixes the ceiling; the two headline numbers).** Given the field and the period, u_A depends on the data sources the screen queries; it is a property of (set of data sources, field, period), measured here on one field and two periods (`results/p1_backend_table.csv`). For the same 10,973 legitimate academic references (2019–21, def 1), with the paper-bootstrap 95 % CI of u_A carried through the decreasing map u ↦ PPV*(π, u), and with the pooled π (not π_A = π/w_A, which §8 gives under F_A):

| Backend set | u_A [CI] | PPV*(π, u_A), π = 0.39 % | PPV*(π, u_A), π = 0.5 % |
|---|---|---|---|
| Crossref-only | 30.2 % [27.7, 32.6] | **1.3 %** [1.2, 1.4] | 1.6 % [1.5, 1.8] |
| Full cascade (+S2) | 2.11 % [1.64, 2.58] | **15.7 %** [13.2, 19.3] | 19.2 % [16.3, 23.5] |

So, at a fabrication rate of 0.39 %, at most about 1 flag in 78 is a fabrication under a Crossref-only screen, and at most about 1 in 6 under the full cascade. The ratio of the false-flag odds is u_A(Crossref) / u_A(full) ≈ 14.

*Proof.* (1) with the measured u_A. PPV* is strictly decreasing in u, so the interval endpoints map to the reverse endpoints. ∎

---

## 2. Proposition 2 (distribution and dispersion of the flag count)

*Source.* Part A collects standard properties of Poisson-binomial sums (coupling; Le Cam 1960; Barbour & Hall 1984; Chernoff; Hoeffding 1956). Part B is the beta-binomial variance, Cauchy–Schwarz on a covariance sum, and Cantelli's inequality.

### Part A: under independence

Consider a legitimate paper (π = 0) with tier counts (n_s). Under Assumption A′ (conditional independence given the paper), N = Σ_s N_s with independent N_s ∼ Bin(n_s, u_s); N is Poisson-binomial with λ = Σ_s n_s u_s = n ū(w).

  P(false flag | n, k, w, u) = P(Σ_s Bin(n_s, u_s) ≥ k)                                        (3)

has the following properties.

**(i) Monotonicity.** (3) is non-decreasing in every n_s and in every u_s. For fixed n, moving one reference from tier a to tier b with u_b ≥ u_a does not decrease it. Two papers can be compared this way only if one is obtained from the other by such moves. A paper with more S/W references is not always flagged more often: with u_W = 0.618, u_J = 0.0373 and u_P = 0.0101, the paper 1 W + 50 P has P(N ≥ 1) = 0.770 and the paper 51 J has 0.856.

**(ii) Poisson approximation.**

  |P(N ≥ k) − P(Poi(λ) ≥ k)| ≤ λ⁻¹(1 − e^{−λ}) Σ_s n_s u_s² ≤ Σ_s n_s u_s²

(Le Cam 1960; Barbour & Hall 1984).

**(iii) Chernoff bound.** For k > λ, P(N ≥ k) ≤ e^{−λ} (e λ / k)^k. For k = 1 the probability is computed exactly:
P(N ≥ 1) = 1 − Π_s (1 − u_s)^{n_s}, with 1 − e^{−λ} ≤ P(N ≥ 1) ≤ min(1, λ).

**(iv) Pooled u versus tiered u (Hoeffding 1956, Thm 4).** Let B ∼ Bin(n, ū) have the same mean as N.
- If k ≥ λ + 1, then P(N ≥ k) ≤ P(B ≥ k).
- If k ≤ λ, then P(N ≥ k) ≥ P(B ≥ k).

So the pooled form over-states the false-flag probability at thresholds k ≥ λ + 1, and under-states it at thresholds k ≤ λ. Nothing is claimed for λ < k < λ + 1.

**(v) Length effect.** For a population of legitimate papers whose tier counts are drawn from a law G, Φ_k(G) = E_G P(N ≥ k) is monotone in the usual multivariate stochastic order of (n_s): if a coupling with n′_s ≥ n_s for every s exists, then Φ_k(G′) ≥ Φ_k(G). Dominance of the marginals alone is not enough. If the mix w is held fixed, Φ_k is non-decreasing along the values of n for which every n w_s is an integer.

*Proof.*
- (3) is the definition of N under A′.
- (i) Couple N_s(n_s + 1) = N_s(n_s) + X with X ≥ 0. Couple a Bernoulli(u_a) below a Bernoulli(u_b) by a common uniform variable, so the sum increases pointwise and {N ≥ k} grows. The example is direct computation.
- (ii) Le Cam's inequality for sums of independent Bernoulli(p_i): d_TV ≤ Σ p_i², here with p_i = u_s repeated n_s times. The sharper factor is the Barbour–Hall bound.
- (iii) Markov's inequality applied to e^{θN}, with E e^{θN} = Π (1 + u_i(e^θ − 1)) ≤ exp(λ(e^θ − 1)). Choose θ = log(k/λ). The k = 1 form follows from independence and 1 − x ≤ e^{−x}.
- (iv) Hoeffding (1956), Theorem 4, with (b, c) = (0, k − 1) and (k, n). Set c = k − 1.
- (v) By (i) the integrand is non-decreasing in every coordinate, and expectations of such functions are monotone under the coupling. ∎

**Remark (dependence).** If paper-level heterogeneity U_s is added, and the U_s are independent or positively associated across tiers, then E Π_s (1 − U_s)^{n_s} ≥ Π_s E(1 − U_s)^{n_s} ≥ Π_s (1 − u_s)^{n_s}, so the k = 1 formula at the mean is an upper bound. With negatively dependent U_s this can fail. No statement is made for k ≥ 2. H5 in the pre-registration tests (3) against the observed π = 0 corpus; a systematic excess is evidence of within-paper dependence.

### Part B: dispersion under heterogeneity

*Setting.* Let paper i carry its own unresolved rates U_{i,s}, with E U_{i,s} = u_s. Assume N_{i,s} | U_{i,s} ∼ Bin(n_{i,s}, U_{i,s}) (conditional independence within a tier; Assumption A′ is the special case U_{i,s} ≡ u_s). Let ρ_s = Var(U_{i,s}) / (u_s (1 − u_s)) be the intra-paper correlation (ICC) of tier s, with ρ_s := 0 when u_s ∈ {0, 1}.

*Claim.*
- (a) Var(N_{i,s}) = n_{i,s} u_s (1 − u_s) (1 + (n_{i,s} − 1) ρ_s). This is at least the binomial variance, with equality iff ρ_s = 0 or n_{i,s} ≤ 1.
- (b) Whatever the correlation between tiers, Var(N_i) ≤ V_i := (Σ_s √Var(N_{i,s}))². If Cov(N_{i,s}, N_{i,t}) = 0 for s ≠ t (for example, counts conditionally independent given U_i and Cov(U_{i,s}, U_{i,t}) = 0), then Var(N_i) = Σ_s Var(N_{i,s}) ≥ V0_i := Σ_s n_{i,s} u_s (1 − u_s), the Poisson-binomial variance.
- (c) (Cantelli) For t > 0, P(N_i ≥ E N_i + t) ≤ Var(N_i) / (Var(N_i) + t²).

*Proof.*
- (a) Law of total variance: Var N = E Var(N | U) + Var E(N | U) = E[nU(1 − U)] + n² Var U = n u(1 − u) − n Var U + n² Var U. Insert Var U = ρ u(1 − u).
- (b) Var(Σ X_s) = Σ_{s,t} Cov(X_s, X_t) ≤ Σ_{s,t} σ_s σ_t = (Σ σ_s)² (Cauchy–Schwarz). The second statement is (a) with ρ_s ≥ 0.
- (c) Cantelli's one-sided Chebyshev inequality. ∎

*Consequence for rules.* Every rule calibrated on Bin(n_{i,s}, u_s) is calibrated on the variance V0_i. If ρ_s > 0, the true false-flag probability above the mean can be larger. The data agree with this: on the 299 legitimate papers of 2019–21, Σ_i (N_{A,i} − λ_i)² equals **3.3 ×** Σ_i V0_i under the full cascade and **5.6 ×** under Crossref-only, but only **0.55 ×** (full) and 0.66 × (Crossref-only) of Σ_i V_i with the fitted ICCs (§9). The rates λ_i use in-sample u_s.

---

## 3. Theorem 1 (the u_S factor)

*Source.* The mathematics is the standard variational total-variation bound (the Le Cam / Neyman–Pearson two-point argument) plus a law of total expectation. What it adds is the comparison of fabrications with real-but-unresolved references, which gives the factor u_S.

**Setting.**
- Let S be a set of references whose rendered form carries no resolvable persistent identifier.
- A screen observes Y: the rendered string, any metadata it extracts, and every registry or web response it obtains. It applies an arbitrary (possibly randomised) test φ(Y) ∈ [0, 1] (1 = "fabricated").
- Notation:
  - P_F = law of Y | H = F, S;
  - P_{R,1} = law of Y | H = R, Z = 1, S (real but unresolved);
  - u_S = P(Z = 1 | H = R, S).
- Recall and false-positive rate on S (φ may be randomised, so both are expectations):
  - TPR_S = E[φ(Y) | H = F, S] = E_{P_F} φ;
  - FPR_S = E[φ(Y) | H = R, S];
  - PPV_S = P(H = F | flag, S) = π_S TPR_S / (π_S TPR_S + (1 − π_S) FPR_S), defined when TPR_S > 0.

**Assumption B_δ (plausible fabrication).** d_TV(P_F, P_{R,1}) ≤ δ, where d_TV(P, Q) = sup_A |P(A) − Q(A)|. With δ = 0 a fabricated reference looks exactly like a real one that no registry knows. With δ > 0 a residual signal remains, e.g. implausible venues or author–title combinations.

**Theorem 1.** Under B_δ, every test φ: Y → [0, 1] satisfies on S

  FPR_S ≥ u_S · (TPR_S − δ)₊,                                                                    (4)

and consequently, with fabrication rate π_S on S and TPR_S > 0,

  PPV_S ≤ π_S TPR_S / (π_S TPR_S + (1 − π_S) u_S (TPR_S − δ)₊).                                 (5)

(a) For δ = 0 the right side of (5) equals PPV*(π_S, u_S) = π_S / (π_S + (1 − π_S) u_S), whatever the test. Under B_0, the ceiling of Proposition 1 therefore holds for **every** screen on S, including screens that use authors, venues, web search or LLM judgement, not only for resolvability-based ones.

(b) Attainment: the canonical screen φ₀ = 1{Z = 1} has FPR_S = u_S and TPR_S = s_S, so for δ = 0 (4) and (5) hold with equality; see the remark on s_S below.

(c) Trade-off form: for any target recall r ∈ (δ, 1], every test with TPR_S ≥ r has FPR_S ≥ u_S (r − δ). Lowering the false-positive rate below u_S (r − δ) under B_δ is possible only by giving up recall.

*Proof.*
1. *Variational bound.* Let P, Q have densities p, q with respect to μ = P + Q. For φ with values in [0, 1], E_P φ − E_Q φ = ∫ φ (p − q) dμ ≤ ∫_{p > q} (p − q) dμ = P(p > q) − Q(p > q) ≤ d_TV(P, Q), because φ ≤ 1 where p − q > 0 and φ ≥ 0 where p − q ≤ 0. Applying the same argument to 1 − φ gives the absolute value: |E_P φ − E_Q φ| ≤ d_TV(P, Q).
2. *Real-unresolved references are flagged almost as often as fabricated ones.* By step 1 with P = P_F, Q = P_{R,1} and B_δ: E_{P_{R,1}} φ ≥ E_{P_F} φ − δ = TPR_S − δ. Since E_{P_{R,1}} φ ≥ 0, also E_{P_{R,1}} φ ≥ (TPR_S − δ)₊.
3. *Law of total expectation over Z.* Given H = R and S, FPR_S = u_S E[φ | R, Z = 1, S] + (1 − u_S) E[φ | R, Z = 0, S] ≥ u_S E_{P_{R,1}} φ, because φ ≥ 0. Together with step 2 this is (4).
4. *PPV.* By Bayes' rule, PPV_S = π_S TPR_S / (π_S TPR_S + (1 − π_S) FPR_S). For fixed TPR_S > 0 the map x ↦ a / (a + b x) (a, b > 0) is decreasing in x, so inserting the lower bound (4) for FPR_S gives (5).
5. *(a)* For δ = 0, (TPR_S − δ)₊ = TPR_S and TPR_S cancels from (5). *(b)* φ₀ is a function of Y because Y contains every registry response, and Z is defined by those responses. E[φ₀ | R, S] = P(Z = 1 | R, S) = u_S and E[φ₀ | F, S] = s_S. *(c)* is (4) with TPR_S ≥ r and the monotonicity of (·)₊. ∎

*Remark (a hidden consequence of B_δ).* Z is a function of Y, so P_{R,1}(Z = 1) = 1 and P_F(Z = 1) = s_S. Hence B_δ implies s_S ≥ 1 − δ. In particular B_0 forces s_S = 1: under B_0 no fabrication in S resolves. With δ > 0 and s_S < 1 the canonical screen attains neither (4) nor (5).

*Remark (what B_δ does and does not assume).* B_δ compares fabricated references with real references that the registries miss, not with all real references. It is therefore weak where fabrications imitate the long tail (grey literature, workshop papers, non-English venues) and strong where they imitate famous papers, which a registry would resolve. δ is not identified from our data. The PPV bound (5) is reported at δ = 0 and as a function of δ. Every δ-free statement below is conditional on B_0.

**Corollary T (tier mixture).** Let S be split into tiers s with shares w_s, unresolved rates u_s and B_{δ_s} holding tier-wise. Then, for every test,

  FPR_S ≥ Σ_s [w_s (1 − π_s) / Σ_t w_t (1 − π_t)] u_s (TPR_s − δ_s)₊.

The weights are conditional on the reference being real; they equal w_s when π_s ≡ π. With π_s ≡ π, TPR_s ≡ TPR and δ_s ≡ δ the bound is ū(w) (TPR − δ)₊, so under B_0 the pooled-π ceiling of Proposition 1 holds for every screen.

*Proof.* Apply (4) in each tier and average over T given H = R (law of total expectation). ∎

**Proposition 3 (identifiers).**

*Source.* The first two claims are one-line error bounds and the two-point lower bound on total variation; separation is read from Theorem 1.

*Setting.* Let S′ be references whose rendered form prints an identifier (DOI or 10.48550/arXiv.<id>). Let I be the event "the printed identifier resolves and the registry metadata match the rendered metadata (title similarity ≥ τ and first author)".

*Assumptions.*
- (a) P(I^c | H = R, S′) ≤ u_id: registry outage, typo or style corruption of the identifier.
- (b) P(I | H = F, S′) ≤ ε: a fabricated reference passes only by copying a real identifier together with that record's metadata, and is then a mis-citation, not a non-existent work.

*Claim.*
1. The identifier test φ_id = 1 − 1_I has FPR ≤ u_id and TPR ≥ 1 − ε, and PPV_{S′} ≥ π (1 − ε) / (π (1 − ε) + (1 − π) u_id).
2. d_TV(P_{F,S′}, P_{R,S′}) ≥ 1 − u_id − ε. This compares fabricated references with all real references. B_δ concerns real references that are unresolved, so nothing follows about B_δ.
3. *Separation through Theorem 1.* If the lookup that defines Z includes the identifier route, then I ⊂ {Z = 0}, so u_{S′} = P(Z = 1 | H = R, S′) ≤ u_id. Whatever δ is on S′, the bound (4) on S′ is then at most u_id (TPR − δ)₊: the lower limit on the false-positive rate shrinks with u_id.
4. *Union screen.* The screen φ_∪ that flags only when the identifier route and the title cascade both fail satisfies φ_∪ ≤ φ_id pointwise, so FPR(φ_∪) ≤ FPR(φ_id) and TPR(φ_∪) ≤ TPR(φ_id). Assumption (b) does not bound TPR(φ_∪) from below: a fabrication whose title is within τ of a real record passes the title route.

*Proof.* FPR = P(I^c | R, S′) ≤ u_id and TPR = P(I^c | F, S′) ≥ 1 − ε by (a) and (b). Taking A = I^c in the definition of d_TV gives d_TV ≥ P_F(I^c) − P_R(I^c) ≥ (1 − ε) − u_id. For the PPV, the map (t, f) ↦ πt / (πt + (1 − π) f) is increasing in t and decreasing in f; insert t ≥ 1 − ε and f ≤ u_id. Claim 3: Z = 1 implies I^c, and Theorem 1 applies on S′ whenever B_δ holds there. Claim 4: φ_∪ = φ_id · 1{title route fails}. ∎

*Measured rates.* The render experiment gives two related rates on certified-real references rendered with the DOI-printing style (`results/p1_screen_fp.csv`).
- The identifier route alone fails for 3.2 % (column `idonly`; this includes references whose identifier was not printed or not extracted). This is the rate that goes with the guarantee TPR ≥ 1 − ε of claim 1.
- The identifier route followed by the title cascade fails for 0.043 % (column `union`). This is the false-positive rate of the union screen. It carries no guarantee on recall (claim 4).

*Interpretation.*
- Under B_0 and without an identifier, no test can push the false-positive rate below u_S × recall. Under B_δ the limit is u_S × (recall − δ).
- With an identifier, the error rates of φ_id are bounded by u_id and ε, quantities controlled by the registries rather than by coverage.
- The render experiment (E2) measures how often common styles erase identifiers. **Identifier erasure:** IEEEtran.bst v1.14 has no DOI field; in the pilot it printed 20.3 % of .bib DOIs (only through URL fields), versus 74.5 % for the DOI patch and 100 % for elsarticle-num (n = 192 refs, 30 papers).

---

## 4. Decision rules

**Lemma 4.0 (tier-wise rule under independence).** Count only unresolved academic references, N_A = Σ_{s∈A} Bin(n_s, u_s). Let u⁺_s be upper confidence bounds (paper-level bootstrap 97.5 % quantile; the bootstrap is used because references cluster within papers and Clopper–Pearson assumes independence). Define

  k*_A((n_s)_{s∈A}, α) = min{ k : P(Σ_{s∈A} Bin(n_s, u⁺_s) ≥ k) ≤ α }.

The threshold depends on the vector (n_s), not only on n_A; k = n_A + 1 always satisfies the condition, so the minimum exists. Under A′ and u_s ≤ u⁺_s, the rule "desk-reject iff N_A ≥ k*_A" rejects a legitimate paper with probability ≤ α. If the bounds hold simultaneously with probability ≥ 1 − η over the estimation sample, the guarantee holds with that probability.

*Proof.* Monotonicity of (3) in each u_s (Proposition 2(i)), then the definition of k*_A. ∎

**Simultaneous bounds.** The guarantee needs u_s ≤ u⁺_s for all s ∈ A at once. With per-tier upper bounds at level 1 − η/|A| (|A| = 3), Bonferroni gives simultaneous coverage ≥ 1 − η. The scripts use the 97.5 % paper-bootstrap quantile per tier (individual coverage). Simultaneous coverage of the estimation step is therefore an assumption of the rules below, not a computed guarantee.

**α-safety is relative to the set of data sources.** u_s and hence k*_A depend on the sources the screen queries. A rule calibrated on the full cascade is not α-safe for a Crossref-only screen: by Proposition 2(i), u_s(Crossref-only) ≥ u_s(full) pointwise, since adding sources can only resolve more, and so P(N_A ≥ k | Crossref-only) ≥ P(N_A ≥ k | full).

**What it costs.** Under F_A (all fabrications in A) the recall loss from ignoring S/W/B flags is zero. Without F_A the loss equals the share of fabricated references outside A.

**Conference-wide screening.** The per-paper p-values p_i = P(N_{A,i} ≥ observed | u⁺) are valid only under A′, which the data refute; BH or BY over them inherits the problem of R1 below.

**Proposition 4 (paper-level rules under heterogeneity).**

*Source.* The rules are direct applications of Proposition 2, a union bound, and Cantelli's inequality.

*Setting.*
- The setting of Proposition 2, part B, on the academic tier A = {J, C, P}.
- Paper i has counts n_{i,s} and flag count N_{A,i} = Σ_{s∈A} N_{i,s}.
- u⁻_s, u⁺_s and ρ⁺_s are bounds on u_s and ρ_s: paper-bootstrap 95 % bounds.
- α ∈ (0, 1).

*Rules* (all thresholds are per paper, through n_{i,s}):

- **R1 (estimation margin only).** k¹_i = min{k : P(PoiBin(n_{i,s}, u⁺_s) ≥ k) ≤ α}. It adds only the margin u⁺_s − u_s, and it is Lemma 4.0 evaluated per paper.
- **R2 (heterogeneity quantile).** Let q_s = sup_{μ ≤ u⁺_s, ρ ≤ ρ⁺_s} Q(μ, ρ), where Q(μ, ρ) is the (1 − α/(2|A|)) quantile of the Beta law with mean μ and ICC ρ. Then k²_i = min{k : P(PoiBin(n_{i,s}, q_s) ≥ k) ≤ α/2}.
- **R3 (Cantelli).** Set λ⁺_i = Σ_s n_{i,s} u⁺_s and V⁺_i = (Σ_s √(n_{i,s} v⁺_s (1 + (n_{i,s} − 1) ρ⁺_s)))², with v⁺_s = max_{u ∈ [u⁻_s, u⁺_s]} u(1 − u), which equals ¼ if the interval contains ½. Then k³_i = ⌈λ⁺_i + √(V⁺_i (1 − α)/α)⌉.

*Properties of Q.* At fixed ρ, Q is increasing in μ: Beta(a, c − a) with c fixed is increasing in a in likelihood-ratio order, because the density ratio is proportional to (x/(1 − x))^{a′ − a}. So the sup in R2 sits at μ = u⁺_s. At fixed μ, Q is **not** monotone in ρ: as ρ → 1 the law tends to Bernoulli(μ), so the quantile at level p tends to 0 whenever p < 1 − μ. At μ = 0.185 % and level 0.99167 it peaks at 0.0657 for ρ ≈ 0.140 and then falls (`results/p3d_theory_fix.csv`, table `q_sup`). This is why q_s is defined as a sup and not at (u⁺_s, ρ⁺_s).

*Claims.*
- **(i) R1.** If U_{i,s} ≤ u⁺_s for all s ∈ A (the paper's own rates are below the corpus bound) and A′ holds within the paper, then P(N_{A,i} ≥ k¹_i | U_i) ≤ α. Without that condition there is no guarantee: under heterogeneity, the population false-reject rate is E P(N ≥ k¹ | U) and can exceed α.
- **(ii) R2.** Suppose that, for each s, U_{i,s} ∼ Beta with mean ≤ u⁺_s and ICC ≤ ρ⁺_s, and that the counts N_{i,s} are conditionally independent across tiers given U_i. Then P(legitimate paper i is rejected) ≤ α. No assumption is made on the joint law of (U_{i,s})_s.
- **(iii) R3.** If u_s ∈ [u⁻_s, u⁺_s] and ρ_s ≤ ρ⁺_s for each s, then E N_{A,i} ≤ λ⁺_i and Var N_{A,i} ≤ V⁺_i under any cross-tier correlation, and P(N_{A,i} ≥ k³_i) ≤ α. No distributional assumption is needed beyond the two moments.

*Proof.*
- (i) Given U_i, N_{A,i} is Poisson-binomial with rates U_{i,s} ≤ u⁺_s. Proposition 2(i) gives monotonicity in each rate; then use the definition of k¹_i.
- (ii) Let E = {∃ s ∈ A : U_{i,s} > q_s}. Since q_s ≥ Q(μ_s, ρ_s) for the paper's true (μ_s, ρ_s), P(U_{i,s} > q_s) ≤ α/(2|A|), so P(E) ≤ α/2 by the union bound. On E^c, the rates are ≤ q_s, and by (i) with q_s in place of u⁺_s, P(N ≥ k²_i | U_i) ≤ α/2. So P(N ≥ k²_i) ≤ P(E) + E[P(N ≥ k²_i | U_i) 1_{E^c}] ≤ α/2 + α/2.
- (iii) E N ≤ λ⁺ is linearity. By Proposition 2 part B(a), each tier variance is at most n v⁺_s (1 + (n − 1) ρ⁺_s), because u_s(1 − u_s) ≤ v⁺_s on the interval; part B(b) then gives Var N ≤ V⁺. Part B(c) with t = k³_i − E N ≥ √(V⁺ (1 − α)/α) gives P ≤ V / (V + t²) ≤ V⁺ / (V⁺ + V⁺ (1 − α)/α) = α. ∎

*Measured (§9, 299 legitimate papers of 2019–21). All bounds u⁺_s and ρ⁺_s were estimated on these same 299 papers, so every rate in this block is in-sample.*
- **R1 at α = 0.01 and under Crossref-only exceeds α:**
  - full cascade, α = 0.01: 12/299 = 4.0 % [Wilson 2.3, 6.9], one-sided exact binomial p = 6 × 10⁻⁵;
  - Crossref-only: α = 0.05, 12.7 % (38/299); α = 0.01, 7.0 % (21/299); both p < 10⁻⁶.
- **R1 at α = 0.05 under the full cascade is consistent with excess, but does not demonstrate it:** 19/299 = 6.4 % [Wilson 4.1, 9.7], one-sided p = 0.17; the interval contains 5 %. MC under the fitted beta-binomial model (5 seeds × 20,000 papers): 5.2 %, and 2.5 % at α = 0.01.
- **R2 and R3:** R2 rejects 0/299 at both α, in all three source sets; R3 rejects 1/299 at α = 0.05 (full) and 0/299 otherwise; MC ≤ 0.03 %. These counts are nearly tautological, since k² and k³ exceed almost every observed count on the same papers. They show that the rules are not violated in sample; they are no independent evidence of validity.
- **The price is the threshold.** For the median paper (n_A = 32, full cascade, α = 0.05): k¹ = 5, k² = 19, k³ = 15; under Crossref-only: 12, 27, 32.

**§4.P Policy conclusion 1 (desk-reject thresholds).** Numbers: 299 legitimate papers of 2019–21 (def 1), seed 42, `results/p3d_theory_fix.csv`.

- **(a) A threshold with only an estimation margin is not α-safe at α = 0.01 or for a Crossref-only screen.**
  - R1 adds only the margin u⁺_s − u_s.
  - The established cells are those listed above: α = 0.01 (full cascade) and both Crossref-only cells. The headline cell, α = 0.05 under the full cascade (19/299 = 6.4 % [4.1, 9.7], p = 0.17), is consistent with excess but does not demonstrate it.
  - The excess is consistent with the fitted ICC > 0 (0.045–0.082 on A), and Proposition 2 part B shows why a positive ICC inflates the tail: unresolved references concentrate in a minority of papers. The observed dispersion is 3.3× the Poisson-binomial variance.
- **(b) Thresholds with a guarantee under heterogeneity need k = 15–19 for a median paper; so "≥ 2 flags" is not calibrated with today's source sets.**
  - For the median paper (n_A = 32, full cascade, α = 0.05) R2 and R3 need k = 19 and 15. Across the five typical papers the range is 8–27 / 6–20; under Crossref-only it is 11–57 / 14–77.
  - R2 and R3 are sufficient, not necessary: they stack upper bounds, and the empirical shares show how loose they are.
  - For the same papers, k = 2 lies below every threshold with a guarantee. The k = 2 rule on all reference types flags 142/299 = 47.5 % of legitimate papers even with the full cascade.
- **(c) Printed identifiers are sufficient to lower the thresholds under the measured u_id, and they are the only route we measured.**
  - Theorem 1 does not make them necessary: by (4) a small FPR can also come from a small u_S (better coverage, which is what the cascade does: 30 % → 2 %) or from a large δ (fabrications that are detectably implausible).
  - Under B_0 and without an identifier, no test can push FPR below u_S × recall.
  - With an identifier, a screen that checks the printed identifier first and falls back to the title cascade flags a real reference only when both routes fail. In the render experiment (certified-real references, DOI-printing style with identifiers kept, union screen, GROBID) this rate is 0.043 % (1/2,323; paper-bootstrap upper bound 0.185 %). This rate carries no guarantee on recall (Proposition 3, claim 4).
  - Setting u_s to this rate for every academic tier, with u⁺ = 0.185 % and the full-cascade ρ⁺_s (an assumption: no ICC is measurable from one flag), the median paper (n_A = 32) needs k = 6 (R2) and k = 3 (R3) at α = 0.05, against 19 and 15 without identifiers. Across the five papers this is 4–9 and 2–5 (§9).
  - Under conditional independence, P(N_A ≥ 2) = 0.009 % at n_A = 32 (0.16 % at u⁺). With the assumed dispersion, the Cantelli bound for k = 2 is 0.093 at n_A = 32, so k = 2 is not certified at α = 0.05 even then.
  - **The identifier-only pair is the one with the guarantee TPR ≥ 1 − ε.** The identifier route alone fails for 3.2 % (74/2,325; upper bound 5.8 %), mostly because the identifier was not printed or not extracted. With that rate the median paper needs k = 5 / 20 / 17 (R1 / R2 / R3), no lower than without identifiers. So on our render chain the low thresholds rest on the union screen, and a screen that wants the recall guarantee first needs identifiers that are reliably printed and extracted.
  - **Caveat:** the union rate rests on a single flag and is measured on certified-real references, which already resolved by identifier once. It is a lower bound for identifiers in the wild (typos, style corruption).

*Policy conclusion 1.* A desk-reject rule that counts "non-existent" references has a guarantee under the measured heterogeneity only at thresholds far above the 1–2 used in practice. Printed identifiers checked first are sufficient to bring those thresholds down under the measured u_id, and they are the only route we measured; better coverage or detectably implausible fabrications could also lower the bound of Theorem 1. A small threshold reached this way bounds false rejects, not recall.

**H5 (pre-registration §5).**
- **Result:** FAIL, kept as registered. Under (3), with per-paper LOO u_s, all tiers and k = 2, the prediction for the tertiles T2/T3 lies outside the Wilson CI in all three scenarios.
- **Diagnosis** (exploratory):
  - (b) the reference sets on the u_s side and on the flag side are identical: PASS;
  - (a) per-paper n_{i,s}: FAIL;
  - (c) leave-one-out: FAIL (LOO equals the full sample, so the failure is not leakage);
  - the beta-binomial variant (§7) also FAILs at T3.
- **What it means:** the mean count is predicted correctly; the spread is not. Observed dispersion is 3.3× the Poisson-binomial value, consistent with the fitted ICC > 0 (+S2): J 0.082, C 0.045, P 0.073, B 0.314, W 0.354.

---

## 5. Open points

- **F_A.** No source in `theory/params_from_lit.csv` reports the tier of fabricated references. Badalova & Mayr's test set and the GPTZero NeurIPS list are candidates for a count.
- **Mixed fabrication rates.** If π_s differs across tiers, Corollary 1.1 must use the general form of (1).
- **Bonferroni k*_A.** Simultaneous coverage needs 99.17 % paper-bootstrap quantiles per academic tier; not computed. R2/R3 use per-tier 97.5 % bounds and control α by a union bound over the heterogeneity event; the estimation-coverage event is separate and stated as an assumption.
- **δ in Theorem 1.** Not identified from our data; report (5) as a function of δ.

## 6. References (theory)

Le Cam (1960); Barbour & Hall (1984); Hoeffding (1956) "On the distribution of the number of successes in independent trials", Ann. Math. Statist. 27:713–721; Benjamini & Hochberg (1995); Benjamini & Yekutieli (2001); Ioannidis (2005); HALLMARK (2026) §E.1.

---

## 7. EXPLORATORY — beta-binomial paper heterogeneity (v3: Thm 2″, draft 20-10-2026)

**Status: exploratory, and not a theorem.** Not preregistered and not an amendment. H5 is tested on (3) only, and its verdict stands. Companion: `code/p1_h5_betabinom.py` → `results/p1_h5_betabinom.{json,csv}`.

**Model (A″).** Paper i draws a tier-wise rate U_is ∼ Beta(a_s, b_s), independently across tiers and papers. Given U_is, its n_is references in tier s are unresolved independently with probability U_is. Hence N_is ∼ BetaBin(n_is, a_s, b_s), with mean n_is μ_s, where μ_s = a_s / (a_s + b_s); ICC ρ_s = 1 / (a_s + b_s + 1); variance n_is μ_s(1 − μ_s)[1 + (n_is − 1)ρ_s]. φ_s = 1 + (n̄_s − 1)ρ_s is the variance inflation at the mean per-paper count n̄_s.

**Statements that hold under A″ and π = 0.** P(false flag | n_i, k) = P(Σ_s BetaBin(n_is, a_s, b_s) ≥ k) (3″).
- (i) If ρ_s → 0 with μ_s = u_s fixed, (3″) reduces to (3).
- (ii) For k = 1, (3″) ≤ (3) at u_s = μ_s, because E[(1 − U)^n] ≥ (1 − μ)^n by Jensen. **The v3 statement for general k ("at or below the mean, overdispersion lowers P(N ≥ k)") is deleted (erratum item 11):** it has no explicit crossing points and is not used in the article.

**Estimation.**
- (μ_s, ρ_s) are fitted by MLE per tier over 2019-21 papers.
- Overdispersion is tested by an LR test of ρ_s = 0; the null is on the boundary, so the reference is a 50:50 χ²₀ : χ²₁ mixture.
- The CI for ρ_s is a paper bootstrap (B = 200, seed 42).
- Prediction uses leave-one-paper-out fits, as in H5, compared per n-tertile with the Wilson 95 % CI.
- The exploratory verdict uses the same rule as H5: monotone, and every tertile prediction inside its CI.

**Main result (20-10 evening, `results/p1_h5_betabinom.{json,csv}`, run10 ground truth, B = 200, seed 42).** Same 12,599 refs / 299 papers on the rate side and the flag side (`results/p1_h5_diag.json`, `same_set: true`).

| Tier | u pooled | ρ̂ (ICC) | 95 % CI | φ |
|---|---|---|---|---|
| J | 3.73 % | 0.082 | 0.036–0.163 | 1.97 |
| C | 1.35 % | 0.045 | 0.018–0.076 | 1.85 |
| P | 1.01 % | 0.073 | 0.000–0.222 | 1.43 |
| B | 16.4 % | 0.314 | 0.129–0.451 | 1.48 |
| S | 98.4 % | 0 | 0–0.065 | 1.00 |
| W | 61.8 % | 0.354 | 0.294–0.416 | 2.62 |

| Scenario | Tertile | Observed [Wilson] | (3) | (3″) [boot] |
|---|---|---|---|---|
| +S2 | T1 | 0.400 [0.309, 0.498] | 0.421 | 0.383 [0.353, 0.413] |
| +S2 | T2 | 0.515 [0.418, 0.611] | 0.630 | 0.574 [0.537, 0.604] |
| +S2 | T3 | 0.510 [0.413, 0.606] | 0.763 | 0.688 [0.651, 0.719] |
| +DBLP | T2 | 0.646 [0.548, 0.734] | 0.791 | 0.761 |
| +DBLP | T3 | 0.800 [0.711, 0.867] | 0.903 | 0.866 |
| Crossref-only | T2 | 0.970 [0.915, 0.990] | 1.000 | 0.998 |

Under +S2 the observed share is flat from T2 to T3 (51/99 vs 51/100), so even the observed sequence is not monotone; (3″) brings T2 inside the CI but leaves T3 outside. Exploratory verdict: FAIL (all scenarios, k = 1, 2, 3 except Crossref-only k = 1). Cross-tier Spearman correlations of per-paper rates (+S2): J–C 0.16 (281 papers), J–W 0.15, C–W 0.02, C–P 0.08. Per-paper u_A (+S2) quantiles P10/P25/P50/P75/P90 = 0 / 0 / 0 / 2.8 / 8.0 %: more than half the papers have no unresolved academic reference.

---

## 8. Measured numbers, main run (`results/p1_theory_headlines.json`, `results/p1_alpha_rules.csv`, `results/p3d_theory_fix.csv`)

Def 1, rates from 2019-21 citing papers (π ≈ 0), 10,973 academic refs / 297 papers, paper-bootstrap CI (B = 1000, seed 42). MC check: 5 seeds × 20,000 papers, max |MC − exact| / se = 1.16.

| Scenario | u_A [CI] | PPV* (π = 0.39 %) | PPV* (π = 0.5 %) | P(ff) n=50, k=2 | P(ff) n=150, k=2 |
|---|---|---|---|---|---|
| Crossref-only | 30.2 % [27.7, 32.6] | 1.3 % | 1.6 % | ≈ 1.000 | 1.000 |
| +DBLP | 4.03 % [3.38, 4.75] | 8.9 % | 11.1 % | 0.604 | 0.985 |
| +S2 (full) | 2.11 % [1.64, 2.58] | 15.7 % | 19.2 % | 0.285 | 0.827 |

PPV* is the pooled-π ceiling (1) on tier A; under F_A it is 17.3 % / 21.1 % (+S2). P(ff) is Bin(n, u_A) ≥ k, i.e. an all-academic bibliography of length n.

**Thresholds at n_A = 150, α = 0.05 / 0.01.** The tiered column is the definition of Lemma 4.0, at the corpus mix J 50, C 78, P 22. The point-estimate column is a threshold at the point estimate and is not α-safe.

| Scenario | Lemma 4.0: tiered u⁺_s | Pooled u⁺_A | Point estimate u_A (not α-safe) |
|---|---|---|---|
| Crossref-only | 60 / 63 | 59 / 63 | 56 / 60 |
| +DBLP | 13 / 15 | 13 / 15 | 11 / 13 |
| +S2 (full) | 9 / 11 | 8 / 10 | 7 / 9 |

Papers flagged on the 299 papers of 2019-21 (registered comparison; k = 1 and k = 2 count all tiers):

| Scenario | k = 1 (all tiers) | k = 2 (all tiers) | R1, α = 0.05 | R1, α = 0.01 |
|---|---|---|---|---|
| Crossref-only | 298 (99.7 %) | 286 (95.7 %) | 38 (12.7 %) | 21 (7.0 %) |
| +DBLP | 249 (83.3 %) | 199 (66.6 %) | 21 (7.0 %) | 12 (4.0 %) |
| +S2 (full) | 198 (66.2 %) | 142 (47.5 %) | 19 (6.4 %) | 12 (4.0 %) |

H5 (pre-registration §5, (3) LOO per paper, all tiers, k = 2): FAIL in all three scenarios (table in §7).

---

## 9. Measured numbers: rules (`results/p3d_theory_fix.csv`, `results/numbers.json`)

**Inputs.** 2019–21, def 1, 299 legitimate papers. u_s and its bounds come from the backend table. ρ_s and ρ⁺_s come from the exploratory beta-binomial fit (`results/p1_h5_betabinom.json`, B = 200).

| Tier | u_s full [u⁻_s, u⁺_s] | ρ_s full [ρ⁺_s] | u_s Crossref-only [u⁻_s, u⁺_s] | ρ_s Crossref-only [ρ⁺_s] |
|---|---|---|---|---|
| J | 3.73 % [2.80, 4.91] | 0.082 [0.163] | 18.45 % [16.04, 21.16] | 0.086 [0.117] |
| C | 1.35 % [0.94, 1.82] | 0.045 [0.076] | 27.67 % [25.33, 30.01] | 0.114 [0.149] |
| P | 1.01 % [0.30, 2.04] | 0.073 [0.222] | 66.92 % [62.46, 71.36] | 0.143 [0.181] |

Only the Crossref-only P tier has u > ½: v⁺_P = 0.2345 (at u⁻ = 62.46 %), against the earlier 0.2044 at u⁺.

**Dispersion (Proposition 2, part B).** Σ (N − λ)² is the observed squared deviation; V0 is the Poisson-binomial variance; V is the beta-binomial variance with the Cauchy–Schwarz cross-tier bound.

| Scenario | Σ (N − λ)² | Σ V0 | Σ V | ratio to V0 | ratio to V |
|---|---|---|---|---|---|
| Full | 741.6 | 224.4 | 1341.2 | 3.30 | 0.55 |
| Crossref-only | 11,355.9 | 2,046.1 | 17,188.5 | 5.55 | 0.66 |

**Legitimate papers rejected** (k / 299 [Wilson 95 %]; one-sided exact binomial p against α for R1; MC = beta-binomial model, 5 seeds × 20,000; all in-sample):

| Scenario | α | R1 (CI margin) | R2 (Beta quantile) | R3 (Cantelli) |
|---|---|---|---|---|
| Full | 0.05 | 19 (6.4 %) [4.1, 9.7]; p = 0.17; MC 5.2 % | 0 [0, 1.3]; MC 0 | 1 (0.3 %) [0.06, 1.9]; MC 0.03 % |
| Full | 0.01 | 12 (4.0 %) [2.3, 6.9]; p = 6 × 10⁻⁵; MC 2.5 % | 0 [0, 1.3] | 0 [0, 1.3] |
| +DBLP | 0.05 | 21 (7.0 %) [4.6, 10.5]; p = 0.076; MC 5.9 % | 0 [0, 1.3] | 0 [0, 1.3]; MC 0.01 % |
| +DBLP | 0.01 | 12 (4.0 %) [2.3, 6.9]; p = 6 × 10⁻⁵; MC 2.7 % | 0 [0, 1.3] | 0 [0, 1.3] |
| Crossref-only | 0.05 | 38 (12.7 %) [9.4, 17.0]; p < 10⁻⁶; MC 10.7 % | 0 [0, 1.3] | 0 [0, 1.3] |
| Crossref-only | 0.01 | 21 (7.0 %) [4.6, 10.5]; p < 10⁻⁶; MC 5.7 % | 0 [0, 1.3] | 0 [0, 1.3] |

**Thresholds k_i for 5 typical papers** (n_A at the 10/25/50/75/90 % quantiles of the 299 papers; α = 0.05, then α = 0.01; R1 / R2 / R3):

| n_A | Full | +DBLP | Crossref-only |
|---|---|---|---|
| 11 | 3 / 8 / 6 · 3 / 10 / 12 | 3 / 8 / 7 · 4 / 10 / 15 | 6 / 11 / 14 · 7 / 12 / 28 |
| 19 | 3 / 12 / 8 · 3 / 16 / 16 | 3 / 11 / 8 · 4 / 14 / 17 | 16 / 20 / 33 · 17 / 20 / 60 |
| 32 | 5 / 19 / 15 · 6 / 25 / 31 | 6 / 21 / 19 · 8 / 26 / 39 | 12 / 27 / 32 · 14 / 30 / 63 |
| 47 | 4 / 18 / 13 · 5 / 25 / 27 | 5 / 17 / 15 · 7 / 22 / 32 | 21 / 42 / 57 · 23 / 46 / 110 |
| 66 | 5 / 27 / 20 · 6 / 37 / 44 | 7 / 27 / 25 · 9 / 35 / 51 | 28 / 57 / 77 · 31 / 63 / 147 |

- k is not monotone in n_A across these five papers, because each threshold depends on the paper's own J/C/P mix.
- A threshold larger than n_A means the paper can never be rejected.

**Identifier scenarios (§4.P (c)).** Same five papers, and the full-cascade ρ⁺_s for every tier (an assumption). P(N ≥ 2) is the Poisson-binomial value at the rate, with the value at the upper bound in brackets.

*Union screen* (identifier route, then title cascade): u = 0.043 % (1/2,323), u⁺ = 0.185 %. No guarantee on recall.

| n_A | α = 0.05: R1 / R2 / R3 | α = 0.01: R1 / R2 / R3 | P(N ≥ 2) [at u⁺] | Cantelli bound, k = 2 |
|---|---|---|---|---|
| 11 | 1 / 4 / 2 | 2 / 7 / 3 | 0.001 % [0.019 %] | 0.016 |
| 19 | 1 / 5 / 3 | 2 / 10 / 5 | 0.003 % [0.057 %] | 0.051 |
| 32 | 2 / 6 / 3 | 2 / 14 / 7 | 0.009 % [0.164 %] | 0.093 |
| 47 | 2 / 7 / 4 | 2 / 15 / 8 | 0.020 % [0.350 %] | 0.131 |
| 66 | 2 / 9 / 5 | 2 / 21 / 12 | 0.039 % [0.679 %] | 0.254 |

*Identifier-only pair* (the one with TPR ≥ 1 − ε, Proposition 3 claim 1): u = 3.2 % (74/2,325), u⁺ = 5.77 %.

| n_A | α = 0.05: R1 / R2 / R3 | α = 0.01: R1 / R2 / R3 | P(N ≥ 2) [at u⁺] |
|---|---|---|---|
| 11 | 3 / 9 / 7 | 4 / 11 / 15 | 4.6 % [13.0 %] |
| 19 | 4 / 15 / 12 | 5 / 18 / 26 | 12.1 % [30.1 %] |
| 32 | 5 / 20 / 17 | 6 / 26 / 36 | 27.1 % [55.8 %] |
| 47 | 7 / 23 / 21 | 8 / 30 / 43 | 44.4 % [76.3 %] |
| 66 | 8 / 34 / 30 | 10 / 43 / 63 | 62.5 % [90.0 %] |

---

## 10. Superseded (do not cite; kept for the audit trail)

The earlier identifier table used u_id = 0.26 % (6/2,316) and u⁺_id = 0.60 %, the IEEEtran strip cell, which has no printed identifier. It was corrected on 24-10-2026. Its values (n_A = 11, 19, 32, 47, 66): α = 0.05, 2/5/3, 2/8/4, 2/11/6, 2/12/7, 3/16/9; α = 0.01, 2/8/5, 2/14/9, 3/18/12, 3/20/14, 3/28/21; P(N ≥ 2) = 0.04, 0.11, 0.32, 0.67, 1.3 %.
