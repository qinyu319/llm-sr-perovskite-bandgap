# Reproducible Physics-Constrained LLM-Assisted Symbolic Regression for Interpretable Band-Gap Modeling in Hybrid Perovskites

> Build note: the final revised DOCX files in `paper/` are authoritative. This Markdown file is retained only as a review-copy build source.

## Abstract

Compositionally tunable hybrid organic-inorganic perovskites require models that are accurate enough for screening yet simple enough to expose actionable design rules. Black-box machine learning can predict band gaps accurately, while conventional symbolic regression can return analytical expressions, but both approaches present practical limitations: black-box explanations are usually post hoc, and unconstrained symbolic searches may produce unstable or unnecessarily complex formulas. Here we present a reproducible physics-constrained large-language-model-assisted symbolic regression (LLM-SR) workflow in which the LLM proposes candidate structures only. Numerical coefficients are fitted by ordinary least squares, candidate structures are ranked by five-fold cross-validation on the training set, and the final model is frozen using parsimony, variance-inflation factors, coefficient confidence intervals, and bootstrap sign stability before the held-out test set is evaluated. The resulting final frozen 8-term M4 model is

[[EQUATION:M4]]

where the variables are composition fractions. M4 achieves a fixed five-fold training-CV RMSE of 0.057532 eV and a held-out test RMSE of 0.060613 eV with R² = 0.976545. All retained slopes have bootstrap sign stability of at least 0.999, whereas the discarded Cl2 term has a confidence interval crossing zero and sign stability of 0.603 when added to M4. Comparisons with exhaustive polynomial search, PySR, a compact genetic-programming baseline, Gaussian-process regression, gradient boosting, random forests, and XGBoost show that black-box models can be more accurate, but M4 provides a compact analytical surrogate. SHAP analysis independently identifies Br, Sn, and Cl as the dominant variables and reveals nonlinear interaction regions not fully represented by M4. Group-aware tests define the applicability boundary: composition-family splits show moderate robustness, while leaving out Cl-containing compositions causes a large error increase. The workflow therefore supports transparent interpolation and composition screening within the dominant data manifold; it is not presented as a universal extrapolation law for the full ABX3 space.

**Keywords:** hybrid perovskites; band gap; symbolic regression; large language models; interpretable machine learning; SHAP; applicability domain

# 1. Introduction

Hybrid organic-inorganic perovskites (HOIPs) have become a central semiconductor platform for photovoltaics, light-emitting diodes, photodetectors, and tandem devices because their electronic structure can be tuned over a wide energy range by composition [1-4]. In three-dimensional ABX3 perovskites, replacement of Pb by Sn at the B site generally narrows the band gap, whereas substitution of I by Br or Cl at the X site produces a blue shift. Nonlinear bowing is common in mixed-metal and mixed-halide systems, and the A-site cation can indirectly affect the band gap through lattice dimensions, octahedral tilting, phase stability, and local structural disorder [5-8]. These coupled effects make the band gap an ideal test case for composition-property modeling: it is technologically important, experimentally abundant, and sufficiently nonlinear that a purely linear rule is inadequate.

Data-driven models can capture these trends, but the representation of knowledge matters. Ensemble trees and Gaussian processes often provide strong prediction accuracy, yet their design guidance is mediated through post hoc tools or numerical queries rather than a reusable closed-form rule [10]. Classical symbolic regression addresses this interpretability problem by searching directly over equations [11-13]. However, unconstrained searches can expand into large operator spaces, produce algebraically different expressions across random seeds, and exploit correlations created by compositional closure. These risks are amplified in materials datasets that are small, heterogeneous, and concentrated in a limited composition manifold. Recent work has explored large language models as scientific equation generators or program-guided hypothesis proposers [14], but a scientifically defensible workflow must separate stochastic structure generation from numerical fitting and model selection.

We therefore use the LLM only as a constrained symbolic-structure proposer. The prompt fixes the admissible variables, limits expressions to main effects, squared terms, and a small number of pairwise interactions, forbids coefficients and non-polynomial operators, and expands the search in stages from M0 to M4. Every coefficient is subsequently determined by ordinary least squares (OLS). Five-fold cross-validation (CV) on the training partition governs screening, and the held-out test set is unavailable during generation, fitting, pruning, and freezing. This separation is essential: the LLM supplies hypotheses, whereas deterministic statistical procedures decide whether those hypotheses survive.

The contribution is consequently not a claim that an LLM discovered the universally best band-gap equation. It is a constrained and auditable symbolic-modeling workflow that combines structure generation, CV-qualified parsimony, coefficient diagnostics, conventional symbolic and statistical baselines, repeated LLM runs, black-box prediction benchmarks, SHAP interpretation, and group-aware sensitivity analysis. These tests yield a diagnostically frozen 8-term Cs-Cl-containing M4 formula. We evaluate LLM-SR not only by held-out accuracy, but also by structural reproducibility, comparison with conventional symbolic regression, coefficient behavior under compositional collinearity, agreement and tension with SHAP, and sensitivity to composition-family exclusion. The result is a design-ready first-pass surrogate with an explicitly defined applicability domain.

[[FIGURE:figure1_workflow.png|Figure 1. Physics-constrained LLM-SR workflow. The LLM is confined to candidate-structure generation. OLS fitting, training-set cross-validation, complexity-aware selection, coefficient diagnostics, benchmarking, applicability-domain tests, and final model freezing are deterministic.]]

# 2. Materials and Methods

## 2.1. Dataset curation and composition representation

The source data were derived from the open Perovskite Database Project described by Jacobsson et al. [9]. The analysis used a frozen local workbook snapshot dated January 28, 2026. The retained scope was restricted to three-dimensional ABX3 HOIP compositions represented by A-site fractions FA, MA, and Cs; B-site fractions Pb and Sn; X-site fractions I, Br, and Cl; and a reported optical band gap. No journal impact factor, Journal Citation Reports category, or publication-prestige criterion was used, because such filters do not directly assess measurement quality and would introduce a bibliometric selection bias. The band-gap distribution was not artificially balanced, truncated, oversampled, or reshaped.

The fixed modeling files contain 610 rows: 518 training records and 92 held-out test records. Fractions are represented on a 0-1 scale. Because each crystallographic site is compositionally closed, FA + MA + Cs = 1, Pb + Sn = 1, and I + Br + Cl = 1 in an ideal record. Pb, I, and FA were therefore treated as implicit baselines when Sn, Br, Cl, Cs, and MA were used as model variables. This avoids exact linear dependence within a site. For the final formula, the active raw variables are Sn, Br, Cl, and Cs.

The project archive includes repeated measurements at identical or nearly identical compositions. These observations were not averaged in the primary 610-row analysis because reported band gaps can differ with processing, phase state, and measurement conditions, metadata that are not fully represented in the compact composition model. A duplicate audit found nine exact duplicate training rows after removing the row identifier and no exact duplicate test rows. At the four-variable M4 representation level, 29 unique Sn-Br-Cl-Cs combinations were shared between training and test, corresponding to 43 test rows; 49 test rows had unseen four-variable combinations. Thus the fixed random split is primarily an interpolation test rather than a strict new-composition test. This limitation motivated the group-aware experiments.

A separate strict closure audit was applied for group-aware sensitivity analysis with tolerance 10^-6. Eleven training rows and two test rows exceeded this tolerance. Values were not silently renormalized. The group-aware workflow excluded the 11 affected training rows and used 507 valid training records; the two test issues were documented for reference because the original test set was never used to select a group-aware model. The primary frozen M4 remains the model fitted to the predeclared 518-row training file, preserving the original analysis path, while the strict-QC group workflow tests whether the scientific conclusions persist under a more conservative data policy.

## 2.2. Fixed train/test split and representativeness

The supplied split was fixed at 85/15, with 518 records assigned to training and 92 to test. The split files were treated as immutable analysis inputs. The training partition alone was used for candidate screening, OLS coefficient estimation during CV, pruning, repeated-CV comparison, bootstrap analysis, and final model freezing. The test workbook was loaded only after the final 8-term structure had been frozen.

The target distribution is concentrated in the technologically common 1.5-1.7 eV interval. This range contains 268 training records (51.7%) and 43 test records (46.7%). The training mean and standard deviation are 1.651 and 0.310 eV, compared with 1.695 and 0.398 eV for the test set. The test set is therefore somewhat broader and contains a larger fraction of high-gap observations: 10.9% of test records have Eg >= 2.2 eV, compared with 6.9% of training records. Cl-containing compositions are sparse, with 27 training and eight test records having Cl > 0. The distributional similarity in the main 1.5-1.7 eV region supports a random-split interpolation assessment, while the sparse Cl-rich and high-Eg tails require separate applicability-domain analysis.

Five-fold CV used `KFold(n_splits=5, shuffle=True, random_state=42)` for the fixed model comparisons. A repeated-CV audit used 100 independently shuffled five-fold partitions with seeds 0-99. All metrics were computed in electronvolts. RMSE was the primary predictive metric; MAE and R² were reported as supporting metrics.

## 2.3. Physics-constrained prompt design

The prompt design encoded physical knowledge through the admissible term space and the order in which the space was expanded, rather than by prescribing coefficient signs. At every stage the model output had to be a single symbolic structure without numerical coefficients or explanatory text. The LLM could not access the test data or test metrics.

M0 allowed only a constant and the linear Sn, Br, and Cl terms. M1 added the univariate curvature terms Sn2, Br2, and Cl2 but prohibited interactions. M2 allowed a small number of pairwise interactions among Sn, Br, and Cl to represent metal-halide and mixed-halide coupling. M3 introduced Cs and permitted selected Cs-Sn, Cs-Br, and Cs-Cl interactions, with Cs2 optional. M4 requested simplification of a late-stage quadratic model to 8-11 non-constant terms. Across all stages, logarithms, exponentials, ratios, cubic and higher powers, and newly invented variables were forbidden. The LLM was not allowed to fit coefficients.

These constraints serve two purposes. First, they enforce a dimensional and compositional interpretation: every term is either a site fraction, a bowing-like quadratic correction, or a pairwise composition coupling. Second, they reduce the chance that the LLM exploits a numerically convenient but scientifically opaque operator. The complete prompts, output-validation rules, and raw candidate logs are designated for Supporting Information.

## 2.4. OLS fitting, model selection, pruning, and final freezing

For any candidate structure, a design matrix was constructed from the included terms and an intercept. Coefficients were fitted by OLS on the current training data. During five-fold CV, coefficients were refitted within each training fold and evaluated on the corresponding validation fold. The held-out test set played no role in this process.

Selection used a constrained-parsimony rule. Within a stage, candidates with mean CV RMSE within 5% of the best stage value were considered accuracy-equivalent. The candidate with the fewest non-constant terms was selected; ties were broken by lower CV RMSE. Across stages, structures with CV RMSE below 0.06 eV entered the late-stage candidate pool. The final freeze decision additionally considered: (i) term count, (ii) maximum and median variance-inflation factor (VIF), (iii) OLS 95% confidence intervals, (iv) 1000-row-resampling bootstrap confidence intervals, (v) bootstrap sign stability, and (vi) subgroup errors. Bootstrap sampling used seed 2026. Sign stability was the fraction of bootstrap fits in which a coefficient retained the sign of its full-training estimate.

The final M4 structure was selected from the late-stage M4-family candidate pool, not obtained by deleting only one interaction from the historical 13-term model. Terms with weak confidence support, unstable bootstrap signs, or severe collinearity were removed even if they marginally improved training fit. The final formula was frozen before test evaluation.

## 2.5. Robustness and benchmark experiments

Several complementary experiments were used to test necessity, reproducibility, and interpretability.

**Conventional symbolic and polynomial search.** An exhaustive OLS search evaluated all 511 non-empty subsets of the nine-term anion polynomial dictionary {Sn, Br, Cl, Sn2, Br2, Cl2, SnBr, SnCl, BrCl}. PySR was run with five random seeds under polynomial and richer operator settings. A compact GPLearn baseline used composition variables, the operators add/subtract/multiply, a parsimony grid selected by training five-fold CV, and five independent full-training refits. Because the computational budget of this compact GPLearn run was deliberately limited, its result is interpreted as a stability/control experiment rather than a definitive tuning study.

**Classical statistical selection.** LASSO, ridge, elastic net, and stepwise or exhaustive AIC/BIC analyses were applied to the anion polynomial dictionary [20-23]. These methods were used as pruning diagnostics, not as direct selectors of the final A-site-containing M4.

**Repeated LLM workflows.** Thirty isolated M0-M4 runs were executed with identical prompts, data, candidate counts, and CV rules. Coefficient fitting remained deterministic; only structure generation was stochastic. Additional Qwen and DeepSeek runs at multiple temperature settings provided a cross-model sensitivity check. Exact regeneration was not required. The target question was whether compact M4-family backbones repeatedly reappeared.

**Black-box benchmarks and SHAP.** Gaussian-process regression (GP), gradient-boosted regression trees (GBRT), random forests (RF), and XGBoost were optimized on the training split [15-18]. SHAP values were calculated for the tree models to compare global feature importance and interaction patterns with the symbolic coefficients [19].

**Group-aware sensitivity.** Using the strict-QC training set, the entire candidate-screening and fitting procedure was rerun under 20 composition-family group-shuffle splits, halide leave-one-group-out (LOGO), and A-site LOGO. Screening occurred inside each outer training partition, and the held-out group was evaluated only after a structure had been selected and refitted. No external-test information entered group construction or model selection.

# 3. Results and Discussion

## 3.1. Dataset structure, split fairness, and composition bias

Table 1 and Figure 2 summarize the modeling population. Training and test means are similar for Sn and Br, while the test set has slightly more Cl and MA and slightly less Cs. The principal difference is tail coverage: the test target distribution is broader and more enriched in high-gap records. This is useful for challenging the model, but the small number of Cl-containing records means that aggregate metrics are dominated by I/Br-rich compositions.

[[TABLE:dataset]]

The marginal correlations support the staged physical design. In the training set, Br and Cl correlate positively with Eg (r = 0.630 and 0.687), Sn correlates negatively (r = -0.385), and the A-site fractions are substantially weaker (r = 0.159 for Cs and 0.078 for MA). These values should not be interpreted as causal coefficients because site closure and nonlinear response distort marginal relationships. They nevertheless explain why M0-M2 focused on Sn and the halides, while A-site terms were introduced only after the dominant B/X-site structure was established.

The train/test split resembles the overall target distribution in the central region, but it is not a strict composition holdout. Forty-three test rows share one of 29 Sn-Br-Cl-Cs combinations with training, while 49 rows are unseen in the four-variable M4 representation. Final M4 has RMSE 0.0528 eV on the shared-combination subset and 0.0667 eV on the unseen-combination subset. The latter is still useful performance, but the gap confirms that random-split accuracy partly reflects interpolation around previously observed composition coordinates. The group-aware section therefore carries more weight for claims about transfer to new composition families.

[[FIGURE:figure2_dataset_structure.png|Figure 2. Dataset structure and representativeness. (a) Training and test band-gap distributions, with the dense 1.5-1.7 eV interval highlighted. (b) Mean fractions of the active composition variables. (c) Training-set marginal correlations with the band gap. (d) Sparse Cl-containing observations occupy much of the high-gap tail.]]

## 3.2. Stage-wise evolution from M0 to the final M4 family

The stage sequence demonstrates that increasing nominal expressiveness does not guarantee monotonic validation improvement. The M0 linear model, containing only Sn, Br, and Cl, has CV RMSE 0.08773 eV. Adding univariate curvature in M1 reduces the CV RMSE to 0.06394 eV, confirming the importance of bowing-like behavior, especially for Sn and Br. The full anion interaction model used as M2 has CV RMSE 0.06655 eV, worse than M1 despite having more terms. Its fitted Cl, Cl2, and BrCl coefficients become large and mutually compensating, a symptom of sparse Cl coverage and collinearity rather than a robust physical correction.

Introducing constrained Cs interactions in M3-full lowers the CV RMSE to 0.05833 eV. This improvement is important because a nine-term anion-only core gives 0.06655 eV and the best six-term anion exhaustive subset gives 0.06285 eV. A-site information therefore contributes, but not as a large independent main effect. Its value appears mainly through interaction terms that condition the Sn and halide response.

The final 8-term M4 is a diagnostically pruned and frozen compact model selected from this late-stage family. Its fixed CV RMSE is 0.05753 eV, lower than the 14-term M3-full reference, while its term count is reduced from 14 to eight. Repeated five-fold CV gives 0.05806 eV for final M4 and 0.06006 eV for M3-full. The paired difference is -0.00200 eV, with a 95% interval from -0.00263 to -0.00147 eV. The result shows that the additional full-model terms were not merely unnecessary for interpretability; on repeated splits they were also detrimental to validation performance.

## 3.3. Final frozen M4 and coefficient diagnostics

The final formula is:

[[EQUATION:M4]]

The intercept corresponds to the implicit FA-Pb-I baseline of the chosen encoding, not a universal band gap for every pure material state. The negative linear Sn coefficient is consistent with Pb-to-Sn gap narrowing. The positive Sn2 term introduces curvature, allowing the magnitude of the Sn effect to vary across the substitution range. Br and Cl have positive main effects, consistent with I-to-Br-to-Cl blue shifting, while Br2 captures nonlinear mixed-halide behavior. The small positive Cs main effect and negative CsSn and CsCl interactions represent a minimal A-site correction. They do not imply that A-site chemistry dominates the electronic structure.

[[TABLE:coefficients]]

All eight slopes are statistically and numerically stable. No OLS or bootstrap confidence interval crosses zero. Bootstrap sign stability is 1.000 for seven slopes and 0.999 for CsCl. The largest VIF is 15.79 for Sn2, followed by 15.17 for Sn; Br and Br2 have VIFs near nine. These values reflect the expected correlation between a raw fraction and its square. They are higher than conservative textbook thresholds, but remain far below the pathological values in the unpruned model, where the maximum VIF is 3250 because Cl, Cl2, and BrCl are almost linearly dependent over the sparse Cl-containing subset [25].

The Cl2 diagnostic is decisive. When Cl2 is added to final M4, its OLS and bootstrap intervals cross zero, bootstrap sign stability is 0.603, and the nested F-test gives p = 0.2332. Adding it also worsens fixed CV RMSE from 0.05753 to 0.05826 eV and increases maximum VIF. Cl2 was therefore not retained. Similar logic removed Cs2, SnBr, SnCl, BrCl, and CsBr from the frozen model. Their exclusion does not mean that the underlying physical couplings never occur. It means that these terms could not be represented as stable independent coefficients in this dataset and encoding.

[[FIGURE:figure3_diagnostics.png|Figure 3. Diagnostics for the final frozen M4. (a) OLS coefficients and 95% confidence intervals. (b) Variance-inflation factors; the dashed line marks VIF = 10. (c) Bootstrap sign stability from 1000 training-row resamples.]]

## 3.4. Comparison with conventional symbolic regression and polynomial search

The conventional baselines clarify what the LLM contributes and what it does not. Exhaustive search over all 511 anion-only polynomial subsets is deterministic and highly interpretable. Its best structure contains Sn, Br, Cl, Sn2, Br2, and SnBr, with CV RMSE 0.06285 eV and post hoc test RMSE 0.06671 eV. This is a strong compact baseline, but it lacks the A-site interactions needed to reach the final M4 validation level. The result also weakens the case for Cl2: the global optimum excludes it.

Sparse regularization provides similar diagnostic evidence. Minimum-CV LASSO and elastic net keep all nine anion terms, whereas the one-standard-error solutions set Cl2 and BrCl to zero but retain SnBr and SnCl. Stepwise AIC and BIC select seven terms: Sn, Br, Cl, Sn2, Br2, SnBr, and SnCl. Exhaustive AIC/BIC prefer the full nine-term anion model because their likelihood penalties do not directly account for coefficient sign stability or the interpretability cost of collinearity. None of these methods exactly reproduces final M4, but together they show that prediction-optimal term retention and diagnostically stable term retention are different objectives.

PySR reaches test errors close to M4 in some runs but exhibits structural variability. Across five polynomial-operator seeds, the best-equation test RMSE has mean 0.0683 eV, standard deviation 0.0096 eV, and minimum 0.0610 eV; all five selected structures are different. The richer operator setting gives mean 0.0637 eV and minimum 0.0611 eV, again with five unique selected expressions. Complexity-matched PySR expressions can reach lower post hoc errors, but they are algebraically less transparent than the eight named polynomial terms.

The compact GPLearn experiment performs substantially worse, with CV RMSE 0.1453 eV and mean test RMSE 0.1773 +/- 0.0228 eV across five independent refits. The evolved programs are also seed-dependent. This result should not be interpreted as a universal ranking of genetic programming: the run used a deliberately constrained operator set and limited computational budget. It demonstrates that merely enabling evolutionary symbolic search does not guarantee a stable, accurate, and compact equation under a practical search budget.

[[TABLE:benchmarks]]

Taken together, the baselines do not establish that LLM-SR is an unconstrained accuracy optimizer. Rather, the LLM is useful for proposing physically organized candidate families that include a small A-site correction without exhaustively enumerating every cross-site polynomial. Deterministic diagnostics still decide which proposal is acceptable.

## 3.5. LLM stochasticity and repeated-run stability

Structure generation is stochastic even though coefficient fitting is deterministic. In a direct set of 30 independent M4-only proposals, all outputs satisfied the 8-11-term constraint, but seven normalized structures appeared. Sn, Br, Cl, Cs, Sn2, SnBr, and SnCl were proposed in every run; Br2 appeared in 93.3% and CsBr in 96.7%, while CsCl appeared in 30.0% and CsSn in 10.0%. These frequencies demonstrate that individual terminal interactions are not deterministic outputs of the language model.

A second experiment repeated the complete M0-M4 workflow 30 times with 16 candidates at each stage and deterministic CV selection. M0 and M1 converged to the same stage structures in all runs, M2 retained the M1 structure in 29 of 30 runs, and M3 consistently added Cs and CsSn. The selected M4 structure was identical across these workflow repetitions but ended with CsBr rather than the CsCl term in the final frozen model. Its CV RMSE was 0.05813 eV and test RMSE 0.06176 eV.

This apparent difference is informative rather than contradictory. Repeated runs consistently recover a compact M4-family backbone containing Sn, Br, Cl, Cs, Sn2, Br2, and CsSn, while the terminal A-site-halide interaction varies between CsBr and CsCl depending on the proposal pool. The final CsCl-containing formula was not chosen by majority vote. It was frozen after fixed and repeated CV, VIF, confidence-interval, bootstrap, and subgroup diagnostics favored it. External Qwen and DeepSeek runs likewise produced multiple structures but median test errors near 0.0618 eV for most temperature settings. Reproducibility therefore resides in the constrained workflow and the recurring model family, not in word-for-word regeneration of a single LLM response.

## 3.6. Black-box benchmark and SHAP interpretability cross-check

Black-box models establish the achievable accuracy level with the same compact composition inputs. The best GP model uses Sn, Br, Cl, Cs, and MA with a Matérn-1.5 kernel. It achieves CV RMSE 0.05132 eV and test RMSE 0.04860 eV. GBRT gives CV/test RMSE of 0.05325/0.05202 eV, RF gives 0.05968/0.05586 eV, and XGBoost gives 0.05127/0.06056 eV. Final M4 is therefore competitive but not uniformly superior. Its test RMSE is close to XGBoost and about 0.012 eV higher than GP.

This accuracy difference is the cost of restricting the model to eight explicit terms. The symbolic model can be evaluated manually, differentiated analytically, converted directly into a composition map, and audited coefficient by coefficient. GP and tree ensembles are better choices when predictive refinement is the primary objective, particularly near nonlinear boundaries. M4 is intended as a first-pass design surrogate and explanatory model.

SHAP provides an independent cross-check. For GBRT, mean absolute SHAP importance is 0.1078 eV for Br, 0.0966 eV for Sn, 0.0813 eV for Cl, 0.0128 eV for Cs, and 0.0121 eV for MA. RF and XGBoost give the same qualitative ranking. This agrees with M4's dominant B/X-site structure and weak A-site correction. The direction of SHAP dependence is also consistent: increasing Sn generally lowers the prediction, while increasing Br and Cl raises it.

[[FIGURE:figure4_benchmark_shap.png|Figure 4. Predictive and interpretability benchmarks. (a) Training-CV and held-out test RMSE for black-box and compact analytical models. PySR-P is shown by its across-seed mean post hoc test RMSE; a directly comparable CV value was not available in the project output. (b) GBRT global SHAP importance.]]

SHAP also reveals a limitation of the compact formula. The largest interaction in GBRT, RF, and XGBoost is Br-Cl, with mean absolute interaction SHAP of 0.00725, 0.00841, and 0.01651 eV, respectively. Final M4 contains no explicit BrCl term because that term is unstable in OLS and strongly coupled to Cl and Cl2 under sparse Cl sampling. These findings are not mutually exclusive. The black-box models can represent localized Br-Cl interaction regions without assigning one global coefficient, whereas the compact analytical model requires a single stable coefficient over the full training manifold. SHAP therefore supports the main composition hierarchy while identifying nonlinear regions that M4 compresses or omits.

## 3.7. MA encoding sensitivity and A-site interpretation

MA was not excluded because it is physically irrelevant. Under the A-site closure FA + MA + Cs = 1, all three fractions cannot be included with an intercept without exact dependence. FA was used as the implicit baseline. The question was therefore whether MA or Cs provided the more useful minimal correction in the available data.

The nine-term Sn-Br-Cl core has CV RMSE 0.06655 eV. Adding only a Cs main effect leaves the error essentially unchanged at 0.06657 eV. Adding only MA improves it slightly to 0.06559 eV, and adding both Cs and MA main effects gives 0.06441 eV. In contrast, the Cs interaction model reaches 0.05833 eV. Thus the useful A-site signal is not a strong isolated linear effect; it is a composition-dependent correction associated with Cs interactions.

The frozen model retains Cs, CsSn, and CsCl as the minimum A-site encoding supported by CV and coefficient diagnostics. MA-rich post hoc RMSE is 0.06010 eV, compared with 0.05796 eV for the 14-term full model, a difference of 0.00214 eV. This small aggregate difference does not guarantee reliability for pure-MA or unusual MA-dominated systems. Those compositions should be checked against local training density and, when possible, evaluated with a nonlinear benchmark.

## 3.8. Group-aware splitting and applicability domain

Random splitting estimates interpolation within a data manifold that contains repeated and nearby compositions. Group-aware splitting asks a harder question: can the workflow select a useful model when entire composition families are absent from training? The 20 composition-family group-shuffle splits produce mean RMSE 0.08844 eV, median 0.07496 eV, and worst-case 0.16223 eV. Mean Jaccard similarity between selected terms and frozen M4 is 0.779. Sn, Br, Cl, and Sn2 are selected in every split; Br2 appears in 70%, Cs in 75%, CsSn in 60%, and CsCl in 55%. Cl2 and BrCl are never selected. These frequencies reinforce the stable backbone and the weaker identifiability of specific A-site interactions.

Halide LOGO exposes the clearest boundary. Holding out mixed-halide, I-rich, or Br-rich groups gives RMSE of 0.05564, 0.06620, and 0.07259 eV, respectively. Holding out all Cl-containing compositions gives RMSE 0.88940 eV. This extreme result occurs because the model has almost no information from which to learn the steep Cl effect when the entire Cl region is removed. It is consistent with the sparse high-gap Cl distribution in Figure 2 and with the instability of global Cl-related interaction coefficients in larger polynomials.

A-site LOGO is less severe but still heterogeneous. Held-out mixed-A and FA-rich groups have RMSE 0.02612 and 0.05691 eV; MA-rich gives 0.08501 eV; Cs-rich gives 0.17382 eV. The Cs-rich error supports treating the Cs terms as local corrections rather than a guarantee of extrapolation to isolated Cs-rich families.

[[FIGURE:figure5_group_aware.png|Figure 5. Group-aware sensitivity and applicability domain. (a) Errors for specific held-out halide and A-site groups. (b) Mean and standard deviation across composition-family, halide-LOGO, and A-site-LOGO strategies. The dashed line is the fixed random-split M4 test RMSE.]]

The group-aware analysis does not invalidate M4; it defines where the formula should and should not be used. M4 is reliable mainly for interpolation in the dominant I/Br-rich composition manifold represented by the training data. Predictions for Cl-containing, strongly Cs-rich, or otherwise isolated families require a local-density check and should be confirmed with additional data or a nonlinear model. The random split and group-aware tests answer different questions, and both are required for an honest assessment.

## 3.9. Held-out evaluation and external-validation limits

After freezing, final M4 was fitted once to the full 518-row training set and evaluated on the 92-row test set. Training RMSE, MAE, and R² are 0.05411 eV, 0.03926 eV, and 0.96938. Test RMSE, MAE, median absolute error, maximum absolute error, and R² are 0.06061 eV, 0.04676 eV, 0.03665 eV, 0.18355 eV, and 0.97655. Cl-containing test RMSE is 0.11180 eV, nearly twice the aggregate value, again locating the main error concentration.

The held-out test set is drawn from the same curated database source and is therefore not a fully independent literature validation. The project archive does not contain a verified 30-composition external literature set with harmonized measurement conditions. We consequently do not claim that external validation proves broad transferability. A submission-ready extension should assemble composition-resolved literature measurements with documented temperature, phase, measurement method, and uncertainty, report RMSE, MAE, median and maximum absolute error, and preserve the external set as a non-selection check. Until that experiment is completed, the strongest defensible evidence is the held-out split plus the group-aware sensitivity analysis.

## 3.10. Composition-guided design demonstration

The practical advantage of an analytical surrogate is that it can be evaluated over dense composition grids without retraining or repeated model calls. Figure 6 illustrates two slices of the final M4 response. The first varies Sn and Br at Cs = 0.10 and Cl = 0; the second varies Br and Cl at Cs = 0.10 and Sn = 0. In both cases the remaining site fractions are defined by closure.

To avoid presenting unconstrained extrapolation as design guidance, grid points are displayed only when their Euclidean distance in the Sn-Br-Cl-Cs feature space is no greater than 0.25 from at least one training composition. The hatched region marks an illustrative 1.60-1.80 eV screening window. In the Cl-free slice, increasing Sn lowers the gap while Br raises it, and the quadratic terms create curved iso-gap contours. In the halide slice, relatively small Cl additions produce a steep blue shift, but the admissible colored region narrows where the training data become sparse.

[[FIGURE:figure6_design_map.png|Figure 6. Composition-guided design maps generated directly from final M4. Colored regions satisfy a local training-density criterion; white areas are outside that illustrative applicability mask. Hatching marks predicted Eg between 1.60 and 1.80 eV.]]

Such maps can support rapid screening for a target gap, lower-Sn candidates, or composition trajectories that preserve an optical objective. They cannot replace phase-stability calculations, defect analysis, synthesis feasibility, or experimental validation. The most appropriate workflow is sequential: use M4 to generate transparent first-pass candidates within the represented domain, use black-box or physics-based models for local refinement, and confirm final candidates experimentally.

# 4. Conclusions

This work presents a reproducible physics-constrained LLM-assisted symbolic regression workflow for HOIP band-gap modeling. The LLM proposes structures in a restricted polynomial term space; it does not fit coefficients or inspect test performance. OLS, training-set five-fold CV, constrained parsimony, VIF, confidence intervals, bootstrap sign stability, and subgroup diagnostics determine the final model.

The diagnostically frozen 8-term M4 achieves CV RMSE 0.057532 eV and held-out test RMSE 0.060613 eV with R² = 0.976545. Its coefficient directions are physically readable and bootstrap-stable. Cl2 and several interaction terms are excluded because they are unstable or collinearity-heavy, not because the associated physical phenomena are impossible. Conventional symbolic and statistical baselines support the need for curvature and selective interaction terms but do not reproduce the same parsimony-diagnostic balance. Black-box models, especially Gaussian-process regression and GBRT, achieve lower errors and should be preferred when maximum predictive accuracy is required.

Repeated LLM experiments support recovery of a compact M4-family backbone, while the terminal A-site-halide interaction remains stochastic. SHAP corroborates the dominant roles of Br, Sn, and Cl and exposes localized Br-Cl interactions that the compact global formula omits. Group-aware splits establish the central limitation: M4 is a strong interpolative surrogate in the dominant composition manifold, but Cl-containing and Cs-rich families define applicability boundaries. The scientific contribution is therefore a transparent and auditable modeling workflow, not a claim of universal LLM superiority or unrestricted ABX3 extrapolation.

# Data and Code Availability

The frozen local dataset snapshot, fixed train/test workbooks, model-comparison tables, prompts, repeated-run logs, benchmark outputs, SHAP summaries, group-aware split manifests, and analysis scripts are contained in the accompanying project archive. The SHA-256 checksums are: `data/dataset_610_snapshot.xlsx`, 2F4A5A0CA845137EC39798F8E06FF4F110B93458FD12B91EFF1D52A16B2B037A; `data/train_518.xlsx`, A329CA43106A835BEBC16516731871C9681D5704DBAB7C539E8C8DF07E3FF873; `data/test_92.xlsx`, 00BECF24ED7FE8866F5D3C966F2B2C2F0397C973EE372885EB145F8B94FC5352. A public GitHub release and immutable Zenodo archive should be created before journal submission; no unverified public URL is asserted here.

# Supporting Information

Recommended Supporting Information includes the complete M0-M4 candidate and stage tables; full prompt templates; raw outputs from 30 repeated workflows and external-model runs; GPLearn and PySR settings and expressions; all 511 exhaustive polynomial models; LASSO, ridge, elastic-net, AIC, and BIC outputs; full VIF, confidence-interval, and bootstrap tables; SHAP beeswarm, dependence, and interaction figures; all group-aware split manifests and selected formulas; closure-QC exclusions; and a reproducible execution guide.

# References

1. Kojima, A.; Teshima, K.; Shirai, Y.; Miyasaka, T. Organometal Halide Perovskites as Visible-Light Sensitizers for Photovoltaic Cells. *J. Am. Chem. Soc.* **2009**, *131*, 6050-6051. https://doi.org/10.1021/ja809598r.

2. Lee, M. M.; Teuscher, J.; Miyasaka, T.; Murakami, T. N.; Snaith, H. J. Efficient Hybrid Solar Cells Based on Meso-Superstructured Organometal Halide Perovskites. *Science* **2012**, *338*, 643-647. https://doi.org/10.1126/science.1228604.

3. Green, M. A.; Ho-Baillie, A.; Snaith, H. J. The Emergence of Perovskite Solar Cells. *Nat. Photonics* **2014**, *8*, 506-514. https://doi.org/10.1038/nphoton.2014.134.

4. Stranks, S. D.; Eperon, G. E.; Grancini, G.; et al. Electron-Hole Diffusion Lengths Exceeding 1 Micrometer in an Organometal Trihalide Perovskite Absorber. *Science* **2013**, *342*, 341-344. https://doi.org/10.1126/science.1243982.

5. Filip, M. R.; Eperon, G. E.; Snaith, H. J.; Giustino, F. Steric Engineering of Metal-Halide Perovskites with Tunable Optical Band Gaps. *Nat. Commun.* **2014**, *5*, 5757. https://doi.org/10.1038/ncomms6757.

6. Jacobsson, T. J.; Pazoki, M.; Hagfeldt, A.; Edvinsson, T. Goldschmidt's Rules and Strontium Replacement in Lead Halogen Perovskite Solar Cells: Theory and Preliminary Experiments on CH3NH3SrI3. *J. Phys. Chem. C* **2015**, *119*, 25673-25683. https://doi.org/10.1021/acs.jpcc.5b06436.

7. Ogomi, Y.; Morita, A.; Tsukamoto, S.; et al. CH3NH3SnxPb(1-x)I3 Perovskite Solar Cells Covering up to 1060 nm. *J. Phys. Chem. Lett.* **2014**, *5*, 1004-1011. https://doi.org/10.1021/jz5002117.

8. Noh, J. H.; Im, S. H.; Heo, J. H.; Mandal, T. N.; Seok, S. I. Chemical Management for Colorful, Efficient, and Stable Inorganic-Organic Hybrid Nanostructured Solar Cells. *Nano Lett.* **2013**, *13*, 1764-1769. https://doi.org/10.1021/nl400349b.

9. Jacobsson, T. J.; Hultqvist, A.; García-Fernández, A.; et al. An Open-Access Database and Analysis Tool for Perovskite Solar Cells Based on the FAIR Data Principles. *Nat. Energy* **2022**, *7*, 107-115. https://doi.org/10.1038/s41560-021-00941-3.

10. Butler, K. T.; Davies, D. W.; Cartwright, H.; Isayev, O.; Walsh, A. Machine Learning for Molecular and Materials Science. *Nature* **2018**, *559*, 547-555. https://doi.org/10.1038/s41586-018-0337-2.

11. Schmidt, M.; Lipson, H. Distilling Free-Form Natural Laws from Experimental Data. *Science* **2009**, *324*, 81-85. https://doi.org/10.1126/science.1165893.

12. Udrescu, S.-M.; Tegmark, M. AI Feynman: A Physics-Inspired Method for Symbolic Regression. *Sci. Adv.* **2020**, *6*, eaay2631. https://doi.org/10.1126/sciadv.aay2631.

13. Cranmer, M. Interpretable Machine Learning for Science with PySR and SymbolicRegression.jl. *arXiv* **2023**, arXiv:2305.01582. https://doi.org/10.48550/arXiv.2305.01582.

14. Shojaee, P.; Meidani, K.; Gupta, S.; Farimani, A. B.; Reddy, C. K. LLM-SR: Scientific Equation Discovery via Programming with Large Language Models. *arXiv* **2024**, arXiv:2404.18400. https://doi.org/10.48550/arXiv.2404.18400.

15. Breiman, L. Random Forests. *Mach. Learn.* **2001**, *45*, 5-32. https://doi.org/10.1023/A:1010933404324.

16. Friedman, J. H. Greedy Function Approximation: A Gradient Boosting Machine. *Ann. Stat.* **2001**, *29*, 1189-1232. https://doi.org/10.1214/aos/1013203451.

17. Chen, T.; Guestrin, C. XGBoost: A Scalable Tree Boosting System. In *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining*; ACM: New York, 2016; pp 785-794. https://doi.org/10.1145/2939672.2939785.

18. Rasmussen, C. E.; Williams, C. K. I. *Gaussian Processes for Machine Learning*; MIT Press: Cambridge, MA, 2006.

19. Lundberg, S. M.; Lee, S.-I. A Unified Approach to Interpreting Model Predictions. In *Advances in Neural Information Processing Systems 30*; 2017; pp 4765-4774.

20. Tibshirani, R. Regression Shrinkage and Selection via the Lasso. *J. R. Stat. Soc. B* **1996**, *58*, 267-288. https://doi.org/10.1111/j.2517-6161.1996.tb02080.x.

21. Zou, H.; Hastie, T. Regularization and Variable Selection via the Elastic Net. *J. R. Stat. Soc. B* **2005**, *67*, 301-320. https://doi.org/10.1111/j.1467-9868.2005.00503.x.

22. Akaike, H. A New Look at the Statistical Model Identification. *IEEE Trans. Autom. Control* **1974**, *19*, 716-723. https://doi.org/10.1109/TAC.1974.1100705.

23. Schwarz, G. Estimating the Dimension of a Model. *Ann. Stat.* **1978**, *6*, 461-464. https://doi.org/10.1214/aos/1176344136.

24. Efron, B.; Tibshirani, R. J. *An Introduction to the Bootstrap*; Chapman & Hall/CRC: New York, 1993.

25. Belsley, D. A.; Kuh, E.; Welsch, R. E. *Regression Diagnostics: Identifying Influential Data and Sources of Collinearity*; Wiley: New York, 1980.

26. Pedregosa, F.; Varoquaux, G.; Gramfort, A.; et al. Scikit-learn: Machine Learning in Python. *J. Mach. Learn. Res.* **2011**, *12*, 2825-2830.

27. Wilkinson, M. D.; Dumontier, M.; Aalbersberg, I. J.; et al. The FAIR Guiding Principles for Scientific Data Management and Stewardship. *Sci. Data* **2016**, *3*, 160018. https://doi.org/10.1038/sdata.2016.18.
