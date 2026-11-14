# T09 privacy gate - audit checklist

- run: poc / track: t09 / seed: 42 / offline: True
- policy: g07-1.1.0 (as_of 2026-11-14), sha256 ef49790a9ef3c744
- policy file: configs\policy\privacy_policy_v1.yaml
- input: fixtures\t09_privacy_gate, cases: 12
- approver on file: Pham Huu Minh (data governance reviewer, G07)

Teaching artefact. The gate is a review aid; the DPO or counsel owns the final call.

| case | market | engine | final | reviewer | reason codes |
|---|---|---|---|---|---|
| CASE-01 | VN | HOLD | HOLD | - | NO_LAWFUL_BASIS |
| CASE-02 | EU | HOLD | HOLD | - | XBORDER_NO_MECHANISM |
| CASE-03 | VN | HOLD | HOLD | Pham Huu Minh | CONSENT_INVALID;RETENTION_UNBOUNDED;RAW_PII_IN_CLOUD |
| CASE-04 | EU | HOLD | HOLD | Pham Huu Minh | NO_LAWFUL_BASIS;LIA_MISSING;DPIA_MISSING |
| CASE-05 | US-CA | HOLD | HOLD | - | NOTICE_MISSING |
| CASE-06 | SG | GO | GO | Pham Huu Minh | NO_GAP_FOUND |
| CASE-07 | VN | HOLD | HOLD | - | XBORDER_NO_IMPACT_ASSESSMENT |
| CASE-08 | EU | HOLD | HOLD | Pham Huu Minh | NO_LAWFUL_BASIS;AMBIGUOUS_NEEDS_LEGAL |
| CASE-09 | IN | HOLD | HOLD | Pham Huu Minh | CONSENT_RECORD_MISSING;MINORS |
| CASE-10 | EU | GO | GO | Pham Huu Minh | NO_GAP_FOUND |
| CASE-11 | US-CA | HOLD | HOLD | Pham Huu Minh | SPI_LIMIT_REQUIRED;AMBIGUOUS_NEEDS_LEGAL |
| CASE-12 | VN | HOLD | HOLD | Pham Huu Minh | NO_LAWFUL_BASIS;RETENTION_EXCESSIVE;NO_ENCRYPTION |

## Per-case evidence

### CASE-01 - VN - HOLD
- R-VN-01 [HOLD] NO_LAWFUL_BASIS, needs legal review
  - source: Luat Bao ve du lieu ca nhan 91/2025/QH15 - Art. 9 (consent), Art. 19 (cases not requiring consent)
  - VN law has no legitimate-interest basis; processing without consent needs one of the listed exceptions.

### CASE-02 - EU - HOLD
- R-XB-01 [HOLD] XBORDER_NO_MECHANISM, needs legal review
  - source: GDPR (EUR-Lex) - Chapter V, Art. 44-49
  - Transfer out of the EEA with no Chapter V mechanism (adequacy, SCC plus TIA, BCR, derogation).

### CASE-03 - VN - HOLD
- R-CONS-02 [REWORK] CONSENT_INVALID, needs legal review
  - source: Luat 91/2025/QH15 and GDPR - Luat 91 Art. 9-10 (specific, voluntary, withdrawable); GDPR Art. 7(3)
  - Bundled or non-withdrawable consent is not valid consent; re-collect with a specific, withdrawable prompt.
- R-RET-01 [REWORK] RETENTION_UNBOUNDED
  - source: GDPR (EUR-Lex) - Art. 5(1)(e) storage limitation
  - No retention period set: storage limitation cannot be demonstrated.
- R-SEC-01 [HOLD] RAW_PII_IN_CLOUD
  - source: GDPR (EUR-Lex) - Art. 5(1)(c) minimisation, Art. 25 data protection by design
  - Identifiable raw footage uploaded with no redaction at the edge: the privacy control the design relies on is absent.
- reviewer Pham Huu Minh: approve - Raw faces in the cloud with no retention limit is the worst combination in this batch.

### CASE-04 - EU - HOLD
- R-EU-02 [HOLD] NO_LAWFUL_BASIS, needs legal review
  - source: EDPB Guidelines 01/2020 on connected vehicles - s. 2.3 legitimate interest, s. 3 in-vehicle processing
  - In-cabin or facial imagery under legitimate interest: EDPB treats in-vehicle monitoring of identifiable people as needing a stricter basis and a documented balancing test.
- R-EU-04 [HOLD] LIA_MISSING, needs legal review
  - source: GDPR (EUR-Lex) and EDPB Guidelines 01/2020 - Art. 6(1)(f) with Art. 5(2) accountability; EDPB s. 2.3
  - Legitimate interest without a documented balancing test on file: the basis cannot be relied on, and the controller cannot show the assessment if asked.
- R-EU-03 [HOLD] DPIA_MISSING
  - source: GDPR (EUR-Lex) - Art. 35(1), 35(3)(c)
  - Systematic monitoring of a publicly accessible area, or of people in the cabin, requires a DPIA before processing starts.
- reviewer Pham Huu Minh: approve - In-cabin footage under legitimate interest, no DPIA, and no balancing test on file either (LIA_MISSING, new in v1.1.0). All three must be fixed, not one.

### CASE-05 - US-CA - HOLD
- R-CA-01 [HOLD] NOTICE_MISSING, needs legal review
  - source: CCPA/CPRA (California Civil Code 1798.100) - 1798.100(a) notice at collection
  - CCPA/CPRA has no lawful-basis concept; a notice at or before collection is the gating duty.

### CASE-06 - SG - GO
- no rule fired: no gap found against policy g07-1.1.0 (an absent finding is not a legal clearance)
- field renamed before judging, per the policy aliases: li_assessment_done->lia_done
- reviewer Pham Huu Minh: approve - Correcting my round-1 escalation. I wrote that no legitimate-interests assessment was on file; CASE-06.json carries li_assessment_done: true, so that was wrong. The queue did not show the field because policy v1.0.0 had no SG rule reading it. Under v1.1.0, R-SG-02 reads it (aliased to lia_done) and the case passes on the evidence. Approving GO.

### CASE-07 - VN - HOLD
- R-VN-02 [HOLD] XBORDER_NO_IMPACT_ASSESSMENT, needs legal review
  - source: Luat 91/2025/QH15 and Nghi dinh 356/2025/ND-CP - Luat 91 Art. 21 (transfer impact assessment); ND 356 dossier rules
  - A cross-border transfer impact-assessment dossier must exist and be filed with the authority within 60 days.

### CASE-08 - EU - HOLD
- R-EU-01 [HOLD] NO_LAWFUL_BASIS, needs legal review
  - source: GDPR (EUR-Lex) - Art. 6(1)
  - No Art. 6(1) basis identified (an 'unknown' basis is not a basis).
- AMB-01 [HOLD] AMBIGUOUS_NEEDS_LEGAL, needs legal review
  - source: G07 protocol - ambiguity escalates, it never defaults to GO
  - case file is ambiguous, legal must resolve it: Vendor contract unclear whether vendor is processor or joint controller.
- reviewer Pham Huu Minh: approve - Processor vs joint controller is unresolved in the contract; counsel owns this one.

### CASE-09 - IN - HOLD
- R-CONS-03 [REWORK] CONSENT_RECORD_MISSING
  - source: GDPR (EUR-Lex) - Art. 7(1) demonstrate consent
  - The controller must be able to demonstrate consent; with no record the basis cannot be evidenced in an audit.
- R-MIN-01 [HOLD] MINORS, needs legal review
  - source: GDPR and DPDP Act 2023 (India) - GDPR Art. 8; DPDP s. 9 (verifiable parental consent)
  - Children may be in frame and no verifiable parental-consent or exclusion mechanism is evidenced in the case file.
- R-IN-01 [NOTE, not in force yet] DPDP_CORE_OBLIGATIONS, binds from 2027-05-13, needs legal review
  - source: DPDP Act 2023 and DPDP Rules 2025 (India) - Rules 2025 commencement schedule
  - DPDP core obligations (notice, consent manager, parental consent) bind from 13/05/2027 under the DPDP Rules 2025; plan the controls now, do not score it as a present-day breach.
- AMB-UPCOMING [NOTE, not in force yet] UPCOMING_OBLIGATION, needs legal review
  - source: docs/tracks/T09.md - section 8, effective_date handling
  - future-dated duty recorded, not scored as a present breach: DPDP Act 2023: core obligations apply from 13/05/2027 (DPDP Rules 2025); treat as upcoming law.
- reviewer Pham Huu Minh: approve - DPDP binds 13/05/2027, but the missing consent record and possible minors are gaps today.

### CASE-10 - EU - GO
- no rule fired: no gap found against policy g07-1.1.0 (an absent finding is not a legal clearance)
- reviewer Pham Huu Minh: approve - Adequacy mechanism, transfer impact assessment and DPIA are all on file; release approved.

### CASE-11 - US-CA - HOLD
- R-CA-02 [REWORK] SPI_LIMIT_REQUIRED, needs legal review
  - source: CPRA - 1798.121 right to limit use of sensitive personal information
  - Precise geolocation and biometrics are sensitive personal information: use must be limited and a limit/opt-out path offered.
- AMB-01 [HOLD] AMBIGUOUS_NEEDS_LEGAL, needs legal review
  - source: G07 protocol - ambiguity escalates, it never defaults to GO
  - case file is ambiguous, legal must resolve it: Unclear if company meets CCPA covered-business thresholds in 2026.
- reviewer Pham Huu Minh: approve - Precise location is SPI; covered-business threshold question goes to counsel.

### CASE-12 - VN - HOLD
- R-VN-01 [HOLD] NO_LAWFUL_BASIS, needs legal review
  - source: Luat Bao ve du lieu ca nhan 91/2025/QH15 - Art. 9 (consent), Art. 19 (cases not requiring consent)
  - VN law has no legitimate-interest basis; processing without consent needs one of the listed exceptions.
- R-RET-02 [REWORK] RETENTION_EXCESSIVE, needs legal review
  - source: GDPR (EUR-Lex) plus the retention ceiling set by this group - Art. 5(1)(e) and G07 ceiling
  - Retention beyond the frozen 365-day ceiling needs a written justification per purpose.
- R-SEC-02 [HOLD] NO_ENCRYPTION
  - source: GDPR (EUR-Lex) - Art. 32(1)(a) security of processing
  - Raw personal data retained without encryption at rest.
- reviewer Pham Huu Minh: approve - Three independent gaps; no release before legal signs the basis and the encryption fix.

## Sign-off

- [ ] Pham Huu Minh (data governance reviewer, G07) has read every HOLD above and agrees with the reason codes
- [ ] every rule marked needs_legal_review has been checked against the original instrument
- [ ] cases flagged UPCOMING_OBLIGATION are in the compliance roadmap, with their dates
