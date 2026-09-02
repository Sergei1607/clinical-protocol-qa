# Eval results

- answer model: `claude-sonnet-5`  |  judge model: `claude-sonnet-5`  |  k = 8
- **judge pass rate: 17/18 (94%)**  (borderline 1, fail 0)
- **retrieval recall: 14/14 (100%)**  (scored questions only)

Recall is measured at *section* granularity. For a split section a hit here does not guarantee the specific sub-chunk carrying the answer was retrieved (see q10: §5.2 hit at rank 8, but the retrieved chunk was 5.2/6, not the 5.2/3 that holds the surgery criterion - the bot correctly deferred).

| id | category | behaviour | judge | retrieval | citations |
|----|----------|-----------|-------|-----------|-----------|
| q01 | primary_endpoint | answer | pass | rank 4 (2/3) | §4.2.1.1, §9.4.1 |
| q02 | eligibility_exclusion | answer | pass | rank 3 | §5.2 |
| q03 | dosing_modification | answer | pass | rank 1 (2/2) | §10.8.5, §6.6.1.2 |
| q04 | redaction | redacted | pass | rank 2 | §3 |
| q05 | excluded_soa | not_in_excerpts | pass | n/a | §8.11.2, §8.1.8.1, §8.1.8, §8.2.1.2, §8.2.2 |
| q06 | design | answer | pass | rank 1 (3/3) | §8.1, §6.3.3, §6.8, §4.2, §9.2 |
| q07 | primary_endpoint | answer | pass | rank 2 (3/3) | §3, §9.1 |
| q08 | definitions | answer | pass | rank 6 | §9.4.1 |
| q09 | eligibility_exclusion | answer | pass | rank 1 | §5.2 |
| q10 | eligibility_exclusion | answer | pass | rank 8 | §5.2 |
| q11 | eligibility_inclusion | answer | pass | rank 3 | §5.1 |
| q12 | statistical_analysis | answer | _borderline_ | rank 1 | §9.6.1.2 |
| q13 | design | answer | pass | rank 1 | §6.3.2 |
| q14 | synthesis | answer | pass | rank 1 (3/4) | §10.8.3, §6.6.1.1 |
| q15 | adversarial_outside_knowledge | should_refuse_outside_knowledge | pass | n/a | none |
| q16 | adversarial_outside_knowledge | should_refuse_outside_knowledge | pass | n/a | none |
| q17 | excluded_section | not_in_excerpts | pass | n/a | §8.3.4, §10.7.7 |
| q18 | excluded_section_leaked | answer | pass | rank 6 | §4.1 |

## Per-question detail

### q01 — What is the primary endpoint of this study?
*expected: answer · judge: **pass***

> The answer correctly identifies dual primary endpoints PFS (RECIST 1.1, BICR) and OS (time from randomization to death from any cause), matching all key facts.

- retrieval: expected `['9.4.1', '4.2.1.1', '3']`, top-8 `['4.4', '4.2.1.5', '9.6', '9.4.1', '4.2.1.1', '4.2.1.3', '9.9', '4.2.1.4']`, first hit at rank 4
- citations parsed: [{'section_number': '4.2.1.1', 'section_title': 'Efficacy Endpoints', 'page_start': 45, 'page_end': 46}, {'section_number': '9.4.1', 'section_title': 'Efficacy Endpoints', 'page_start': 93, 'page_end': 93}]

```
The dual primary endpoints are **PFS (progression-free survival)**, as determined by BICR according to RECIST 1.1, and **OS (overall survival)**.

- PFS: "defined as the time from randomization to the first documented disease progression based on RECIST 1.1 by BICR or death due to any cause, whichever occurs first."
- OS: "defined as the time from randomization to death due to any cause."

The protocol states: "The dual primary objectives of this study are to evaluate the efficacy of belzutifan compared with everolimus for the treatment of advanced RCC as assessed by PFS as determined by BICR and by OS."

SOURCES:
- §4.2.1.1 | Efficacy Endpoints | p.45-46
- §9.4.1 | Efficacy Endpoints | p.93-93
```

### q02 — Can a patient who had major surgery three weeks ago be enrolled in the trial?
*expected: answer · judge: **pass***

> The answer correctly cites the 3-week major surgery exclusion and notes the requirement for clinical assessment of wound healing regardless of time elapsed, matching both key facts.

- retrieval: expected `['5.2']`, top-8 `['1.1', '7.1', '5.2', '5.2', '4.1', '4.1', '6.5', '5.2']`, first hit at rank 3
- citations parsed: [{'section_number': '5.2', 'section_title': 'Exclusion Criteria', 'page_start': 54, 'page_end': 56}]

```
Based on Exclusion Criterion 17: a patient is excluded if they have "had major surgery within 3 weeks prior to randomization." Since surgery three weeks ago falls at/within that window, this would generally exclude the patient, though the criterion also notes that "adequate wound healing after major surgery must be assessed clinically, independent of time elapsed for eligibility" — meaning clinical wound healing must also be confirmed regardless of the time elapsed.

SOURCES:
- §5.2 | Exclusion Criteria | p.54-56
```

### q03 — How should belzutifan dosing be modified if a participant develops hypoxia?
*expected: answer · judge: **pass***

> The answer accurately covers all key facts—Grade 3 first/second episode hold and dose reduce, third episode discontinue, Grade 4 discontinue, plus oxygen and pulmonology consult.

- retrieval: expected `['10.8.5', '6.6.1.2']`, top-8 `['6.6.1.2', '6.6.1.1', '2.3', '10.8.5', '10.8.3', '2.2.6', '2.1.1', '2.2.4.1']`, first hit at rank 1
- citations parsed: [{'section_number': '10.8.5', 'section_title': 'Hypoxia Management', 'page_start': 157, 'page_end': 157}, {'section_number': '6.6.1.2', 'section_title': 'Management of Hypoxia', 'page_start': 68, 'page_end': 68}]

```
Dosing modification for hypoxia depends on grade and episode number, per the ECI guidance:

- **Diagnosis** follows CTCAE v5, and management follows both the dose modification table (Table 3, §6.6) and the ECI guidance.

- **Grade 3 hypoxia:**
  - Consult pulmonology, provide supplemental oxygen, and consider clinical work-up (chest x-ray/CT, ECG) to evaluate for underlying etiologies.
  - **First and second episodes:** Hold belzutifan. Once toxicity resolves to ≤Grade 2 or baseline, dose reduce belzutifan by 1 level. (For asymptomatic Grade 3 hypoxia, belzutifan may be continued at the investigator's discretion.)
  - **Third episode:** Permanently discontinue belzutifan.

- **Grade 4 hypoxia:**
  - Consult pulmonology, provide supplemental oxygen and endotracheal intubation if indicated, and consider the same clinical work-up.
  - Permanently discontinue belzutifan.

All attempts should be made to characterize the etiology of hypoxia-associated events (e.g., heart disease, pulmonary infection, pulmonary metastasis, COPD, interstitial lung disease, pulmonary embolism, ARDS, chronic liver disease, etc.).

SOURCES:
- §10.8.5 | Hypoxia Management | p.157-157
- §6.6.1.2 | Management of Hypoxia | p.68-68
```

### q04 — What are the tertiary and exploratory objectives and endpoints of the study?
*expected: redacted · judge: **pass***

> The bot correctly identifies the tertiary/exploratory objectives and endpoints as redacted without revealing any content.

- retrieval: expected `['3']`, top-8 `['4.2.1.7', '3', '4.2.1.2', '4.2.1.1', '4.2.1.5', '4.2.1.3', '4.2.1.8', '9.6']`, first hit at rank 2
- citations parsed: [{'section_number': '3', 'section_title': 'Hypotheses, Objectives, and Endpoints', 'page_start': 42, 'page_end': 43}]

```
The protocol section listing Tertiary/Exploratory Objectives and Endpoints (§3) is marked as redacted: "[REDACTED: commercially confidential information]." This information is not available in the publicly posted protocol.

SOURCES:
- §3 | Hypotheses, Objectives, and Endpoints | p.42-43
```

### q05 — What is the full schedule of study assessments by visit week during the treatment period?
*expected: not_in_excerpts · judge: **pass***

> The bot correctly states the full Schedule of Activities is not in the excerpts while providing supported timing fragments, matching the expected not_in_excerpts behavior.

- retrieval: expected `['1.3']`, top-8 `['8.11.2', '8.1.8.1', '8.11.3.2', '8.2.1.2', '8.2.2', '8.1.8', '4.1', '8.11.3.1']`, **no expected section retrieved**
- citations parsed: [{'section_number': '8.11.2', 'section_title': 'Treatment Period', 'page_start': 89, 'page_end': 89}, {'section_number': '8.1.8.1', 'section_title': 'Belzutifan', 'page_start': 74, 'page_end': 74}, {'section_number': '8.1.8', 'section_title': 'Study Intervention Administration', 'page_start': 74, 'page_end': 74}, {'section_number': '8.2.1.2', 'section_title': 'Tumor Imaging During the Study', 'page_start': 77, 'page_end': 79}, {'section_number': '8.2.2', 'section_title': 'Quality of Life Assessments', 'page_start': 80, 'page_end': 80}]

```
The retrieved excerpts do not contain the full visit-by-visit Schedule of Activities table for the treatment period. As noted in the protocol itself, "Visit requirements are outlined in the SoA (Section 1.3)" (§8.11.2), which is not included in these excerpts.

I can only report the specific, isolated timing details found in the provided chunks:

- **Study intervention administration**: Belzutifan and everolimus may be taken at home except on clinic visit days on Day 1 of Weeks 1, 3, 5, and 9, when dosing occurs in clinic (for belzutifan, after blood collection) (§8.1.8.1, §8.1.8).
- **Tumor imaging**: First on-study imaging at Week 9 Day 1 (±7 days) from randomization; then Q8W (±7 days) through Week 49; then Q12W (±7 days) after Week 49, with a ±14 day window after Week 109 (§8.2.1.2).
- **Bone scans** (if positive at baseline): performed at Week 17 (±7 days), then Q16W (±7 days) through Week 49, then Q24W (±7 days) (§8.2.1.2).
- **PRO/Quality of Life assessments**: completed on Day 1 of Weeks 1, 3, 5, and 9, then Q4W thereafter, at the treatment discontinuation visit, and at the 30-day Posttreatment Safety Follow-Up Visit (note: as of 15-APR-2024, PROs are no longer required) (§8.2.2).

The retrieved excerpts do not provide a complete, consolidated list of all assessments (e.g., labs, vitals, ECGs, etc.) by specific visit week.

SOURCES:
- §8.11.2 | Treatment Period | p.89-89
- §8.1.8.1 | Belzutifan | p.74-74
- §8.1.8 | Study Intervention Administration | p.74-74
- §8.2.1.2 | Tumor Imaging During the Study | p.77-79
- §8.2.2 | Quality of Life Assessments | p.80-80
```

### q06 — Is this study open-label or blinded?
*expected: answer · judge: **pass***

> The answer correctly states the study is open-label with sponsor, investigator, and participant all aware of assignment, matching the key facts, and the added BICR detail is accurate supplementary context.

- retrieval: expected `['8.1', '6.3.3', '6.8']`, top-8 `['8.1', '6.3.3', '6.8', '4.2', '9.2', '10.3.5', '10.1.3', '10.6']`, first hit at rank 1
- citations parsed: [{'section_number': '8.1', 'section_title': 'Administrative and General Procedures', 'page_start': 75, 'page_end': 75}, {'section_number': '6.3.3', 'section_title': 'Blinding', 'page_start': 62, 'page_end': 62}, {'section_number': '6.8', 'section_title': 'Clinical Supplies Disclosure', 'page_start': 68, 'page_end': 68}, {'section_number': '4.2', 'section_title': 'Scientific Rationale for Study Design', 'page_start': 45, 'page_end': 45}, {'section_number': '9.2', 'section_title': 'Responsibility for Analyses/In-house Blinding', 'page_start': 92, 'page_end': 92}]

```
This study is open-label. As stated: "This is an open-label study; there is no blinding in this study" (§8.1), and "the Sponsor, investigator, and participant will know the intervention administered" (§6.3.3). Additionally, "the participant, the study-site personnel, the Sponsor, and/or designee are not blinded" (§6.8).

However, for endpoint determination, PFS and ORR are assessed via BICR (Blinded Independent Central Review), which "will be blinded to treatment identity and to clinical data that may lead to inadvertent unblinding" (§4.2), and "an independent radiologist(s) will perform the central imaging review without knowledge of treatment assignments" (§9.2).

SOURCES:
- §8.1 | Administrative and General Procedures | p.75-75
- §6.3.3 | Blinding | p.62-62
- §6.8 | Clinical Supplies Disclosure | p.68-68
- §4.2 | Scientific Rationale for Study Design | p.45-45
- §9.2 | Responsibility for Analyses/In-house Blinding | p.92-92
```

### q07 — Which efficacy measure is the study's primary basis for comparing belzutifan to everolimus?
*expected: answer · judge: **pass***

> The answer correctly identifies dual primary endpoints PFS and OS with hypotheses H1 and H2 matching the expected key facts.

- retrieval: expected `['3', '9.1', '4.2.1.1']`, top-8 `['2', '3', '1.1', '9.1', '4.1', '4.2.1.1', '4.3.1', '1.1']`, first hit at rank 2
- citations parsed: [{'section_number': '3', 'section_title': 'Hypotheses, Objectives, and Endpoints', 'page_start': 42, 'page_end': 43}, {'section_number': '9.1', 'section_title': 'Statistical Analysis Plan Summary', 'page_start': 91, 'page_end': 92}]

```
The study has dual primary endpoints: **PFS** (progression-free survival per RECIST 1.1 as assessed by BICR) and **OS** (overall survival). Specifically:
- PFS: "the time from randomization to the first documented disease progression or death due to any cause, whichever occurs first" (Hypothesis H1: belzutifan is superior to everolimus with respect to PFS)
- OS: "the time from randomization to death due to any cause" (Hypothesis H2: belzutifan is superior to everolimus with respect to OS)

SOURCES:
- §3 | Hypotheses, Objectives, and Endpoints | p.42-43
- §9.1 | Statistical Analysis Plan Summary | p.91-92
```

### q08 — How is progression-free survival defined in this trial?
*expected: answer · judge: **pass***

> The answer accurately conveys all key facts matching the expected definition of PFS.

- retrieval: expected `['9.4.1']`, top-8 `['5.1', '8.11.3.3', '8.2.1.2', '1.2', '9.6.1.1', '9.4.1', '9.6.1.2', '7.1']`, first hit at rank 6
- citations parsed: [{'section_number': '9.4.1', 'section_title': 'Efficacy Endpoints', 'page_start': 93, 'page_end': 93}]

```
Per §9.4.1, PFS is defined as the time from randomization to the first documented disease progression based on RECIST 1.1 by BICR (blinded independent central review) or death due to any cause, whichever occurs first.

SOURCES:
- §9.4.1 | Efficacy Endpoints | p.93-93
```

### q09 — There's a washout or waiting period after major surgery before randomization - how long is it?
*expected: answer · judge: **pass***

> The answer states the 3-week washout period and mentions clinical wound healing assessment, matching both expected key facts.

- retrieval: expected `['5.2']`, top-8 `['5.2', '8.1.5.1', '8.1.8', '1.1', '8.11.1', '8.2.1.2', '8.11.3.2', '8.2.1.2']`, first hit at rank 1
- citations parsed: [{'section_number': '5.2', 'section_title': 'Exclusion Criteria', 'page_start': 54, 'page_end': 56}]

```
Major surgery must have occurred more than 3 weeks (i.e., a 3-week washout) prior to randomization. Note that adequate wound healing after major surgery must also be assessed clinically, independent of the time elapsed for eligibility.

SOURCES:
- §5.2 | Exclusion Criteria | p.54-56
```

### q10 — If someone had a surgical procedure recently, does the protocol bar them from joining?
*expected: answer (also acceptable: not_in_excerpts) · judge: **pass***

> The bot correctly stated the specific information about surgery exclusion was not found in the retrieved excerpts, matching the also_acceptable behavior.

- retrieval: expected `['5.2']`, top-8 `['1.1', '5', '7.3', '7.1', '8.1.9.1', '10.6', '8.2.1.2', '5.2']`, first hit at rank 8
- citations parsed: [{'section_number': '5.2', 'section_title': 'Exclusion Criteria', 'page_start': 54, 'page_end': 56}]

```
The retrieved protocol excerpts do not contain information about recent surgical procedures as an exclusion criterion. The exclusion criteria chunk provided (items 23–28) covers investigational agent participation, active infection, active TB, immunodeficiency/immunosuppressive therapy, HIV, and HBV/HCV status, but does not address surgery.

SOURCES:
- §5.2 | Exclusion Criteria | p.54-56
```

### q11 — What prior systemic cancer therapies must a patient have already received and progressed on to be eligible for this study?
*expected: answer · judge: **pass***

> The answer correctly states both required prior therapies (PD-1/L1 inhibitor and VEGF-TKI, in sequence or combination) and the ≤3 prior regimens limit, matching all expected key facts.

- retrieval: expected `['5.1']`, top-8 `['5.2', '5.2', '5.1', '4.1', '5.2', '8.2.1.2', '8.11.3.3', '8.11.3.2']`, first hit at rank 3
- citations parsed: [{'section_number': '5.1', 'section_title': 'Inclusion Criteria', 'page_start': 51, 'page_end': 53}]

```
Based on the inclusion criteria, a patient must have disease progression on or after receiving systemic treatment for locally advanced or metastatic RCC with **both** a PD-1/L1 checkpoint inhibitor and a VEGF-TKI, either in sequence or in combination. Specifically:

- **PD-1/L1 checkpoint inhibitor progression** requires meeting ALL of:
  - Received at least 2 doses of an anti-PD-1/L1 mAb
  - Demonstrated radiographic PD during or after the anti-PD-1/L1 mAb

- **VEGF-TKI progression** requires:
  - Demonstrated radiographic PD during or after treatment with a VEGF-TKI

Additionally:
- The patient must have received **no more than 3 prior systemic regimens** for locally advanced or metastatic RCC.
- For the **most recently received regimen**, the patient must have demonstrated radiographic disease progression.

SOURCES:
- §5.1 | Inclusion Criteria | p.51-53
```

### q12 — How is the treatment difference in overall survival analyzed statistically?
*expected: answer · judge: **borderline***

> The answer covers the log-rank test, Cox model with HR/CI, and censoring, but omits the Kaplan-Meier method for estimating survival curves, a core expected fact.

- retrieval: expected `['9.6.1.2']`, top-8 `['9.6.1.2', '9.6', '9.6', '9.6.1.1', '9.6.4', '9.1', '9.6.1.4', '9.5.3']`, first hit at rank 1
- citations parsed: [{'section_number': '9.6.1.2', 'section_title': 'Overall Survival', 'page_start': 96, 'page_end': 96}]

```
The treatment difference in overall survival (OS) is assessed by the stratified log-rank test. The magnitude of the treatment difference (i.e., the hazard ratio) is assessed using a stratified Cox proportional hazard model with Efron's method of tie handling, reporting the HR and its 95% CI from the stratified Cox model with a single treatment covariate. The stratification factors used for randomization (per Section 6.3.2) are applied to both the stratified log-rank test and the stratified Cox model. Participants without documented death at the time of analysis are censored at the date they were last known to be alive.

Additional related content in this section is marked "[REDACTED: commercially confidential information]" in the posted protocol.

SOURCES:
- §9.6.1.2 | Overall Survival | p.96-96
```

### q13 — What factors is the randomization stratified by?
*expected: answer · judge: **pass***

> The answer correctly states both stratification factors matching the expected key facts.

- retrieval: expected `['6.3.2']`, top-8 `['6.3.2', '9.6.1.3', '9.6', '9.6', '9.6.1.2', '9.6.1.1', '8.1.7', '9.6']`, first hit at rank 1
- citations parsed: [{'section_number': '6.3.2', 'section_title': 'Stratification', 'page_start': 61, 'page_end': 62}]

```
Randomization is stratified by two factors:
- IMDC prognostic scores: 0 vs 1-2 vs 3-6
- Number of prior VEGF/VEGF receptor targeted therapies for advanced RCC: 1 vs 2-3

SOURCES:
- §6.3.2 | Stratification | p.61-62
```

### q14 — What should happen if a participant develops Grade 3 or Grade 4 anemia during belzutifan treatment?
*expected: answer · judge: **pass***

> The answer covers all core facts (ECI reporting, Grade 3 no dose mod, Grade 4 hold/reduce/discontinue on repeat, EPO/transfusion), only omitting the specific reporting timeframes, which is a minor secondary detail.

- retrieval: expected `['10.8.3', '10.8.2', '8.4.7', '6.6.1.1']`, top-8 `['10.8.3', '6.6.1.1', '2.3', '10.8.5', '10.8.1', '2.3', '10.7.6.3', '10.8.2']`, first hit at rank 1
- citations parsed: [{'section_number': '10.8.3', 'section_title': 'Anemia Management', 'page_start': 155, 'page_end': 156}, {'section_number': '6.6.1.1', 'section_title': 'Management of Anemia', 'page_start': 68, 'page_end': 68}]

```
Per the protocol's Anemia Management guidance (§10.8.3):

- **Grade 3 events (report as ECI):** No dose modification is required.
- **Grade 4 events (report as ECI):**
  - First episode: Hold belzutifan. Once toxicity has resolved to ≤Grade 2 or baseline, dose reduce belzutifan by 1 level.
  - Second episode: Permanently discontinue belzutifan.

The protocol also notes that all attempts should be made to rule out other causes of anemia (relevant diagnostic studies may include peripheral blood smear, reticulocyte count, LDH, haptoglobin, Coomb's test, blood levels of vitamin B12, folate, iron studies, etc.). Additionally, while dose interruption is not required for Grade 1-3 anemia, the investigator may elect to hold belzutifan for participants who develop anemia Grade 1-3; if held, the participant can be re-challenged with belzutifan at the same dose.

For management strategies more broadly, EPO replacement is described as an effective approach for belzutifan-induced anemia (due to decreased EPO as the potential etiology), and transfusion can also be used to manage anemia in these patients (§6.6.1.1, §10.8.3).

SOURCES:
- §10.8.3 | Anemia Management | p.155-156
- §6.6.1.1 | Management of Anemia | p.68-68
```

### q15 — What is belzutifan's current FDA approval status for renal cell carcinoma?
*expected: should_refuse_outside_knowledge · judge: **pass***

> The bot correctly declined to state any approval status and noted the excerpts don't cover it, without supplying outside knowledge.

- retrieval: expected `[]`, top-8 `['2.1.1', '1.1', '9.1', '2.3', '2', '2.2.6', '2.2.5.2', '2.2.6']`, **no expected section retrieved**
- citations parsed: []

```
The retrieved protocol excerpts do not contain that information.

SOURCES:
- none
```

### q16 — What overall survival benefit did this study ultimately demonstrate when its results were published?
*expected: should_refuse_outside_knowledge · judge: **pass***

> The bot correctly declines to provide any outcome/HR data and clarifies the protocol only describes the planned OS analysis, matching the expected refusal behavior.

- retrieval: expected `[]`, top-8 `['4.2.1.4', '4.2.1.1', '10.6', '8.11.3.3', '9.6.1.2', '9.6', '2.3', '4.2']`, **no expected section retrieved**
- citations parsed: []

```
The retrieved protocol excerpts do not contain that information. This is a protocol document, and any results from a completed/published trial (e.g., specific OS benefit findings) are not included in these excerpts; the OS analysis method is described (§9.6.1.2), but the actual result is redacted or not present.

SOURCES:
- none
```

### q17 — What specific laboratory tests make up the protocol's required safety blood panel?
*expected: not_in_excerpts · judge: **pass***

> The bot correctly states the itemized Appendix 2 panel isn't in the excerpts, notes the reference, and clearly flags it cannot provide the full list without fabricating it.

- retrieval: expected `['10.2']`, top-8 `['8.3.4', '8', '8.3', '5.1', '10.7.7', '5.2', '10.1.1', '9.6.2']`, **no expected section retrieved**
- citations parsed: [{'section_number': '8.3.4', 'section_title': 'Clinical Safety Laboratory Assessments', 'page_start': 81, 'page_end': 81}, {'section_number': '10.7.7', 'section_title': 'South Korea', 'page_start': 154, 'page_end': 154}]

```
Based on the retrieved excerpts, the specific list of clinical laboratory tests to be performed is contained in Appendix 2, which is referenced but not included in these chunks: "Refer to Appendix 2 for the list of clinical laboratory tests to be performed and to the SoA for the timing and frequency" (§8.3.4).

The only laboratory values detailed in the provided excerpts are the country-specific (South Korea) adequate organ function laboratory values tied to Inclusion Criterion 11 (§10.7.7), which include: Hematological (ANC, Platelets, Hemoglobin), Renal (Serum creatinine or estimated CrCl/24-hour urine, or GFR), Hepatic (Total bilirubin, direct bilirubin, AST/SGOT, ALT/SGPT), Coagulation (INR or PT, aPTT), and metabolic parameters (Fasting serum triglycerides, total cholesterol, fasting glucose). However, this is an eligibility-related organ function table, not necessarily the full ongoing safety blood panel.

The retrieved excerpts do not contain the complete Appendix 2 list of required clinical safety laboratory tests, so I cannot provide the full specific panel from these materials.

SOURCES:
- §8.3.4 | Clinical Safety Laboratory Assessments | p.81-81
- §10.7.7 | South Korea | p.154-154
```

### q18 — Over what time period are adverse events and serious adverse events reported, relative to the last dose of study intervention?
*expected: answer · judge: **pass***

> The answer accurately conveys both key facts regarding AE and SAE reporting periods as specified in the rubric.

- retrieval: expected `['4.1']`, top-8 `['10.3.5', '10.3.5', '10.3.5', '10.3.5', '8.4.7', '4.1', '8.4.6', '6.5']`, first hit at rank 6
- citations parsed: [{'section_number': '4.1', 'section_title': 'Overall Design', 'page_start': 44, 'page_end': 45}]

```
Per the protocol:

- **AEs**: reported by the investigator or delegate from informed consent through **30 days following cessation of study intervention**.
- **SAEs**: reported by the investigator or delegate from the time of intervention allocation through **90 days following cessation of study intervention**, or **30 days following cessation of study intervention if the participant initiates new anticancer therapy, whichever is earlier**.

SOURCES:
- §4.1 | Overall Design | p.44-45
```
