# Technical Guidelines — Methodology, Certifications & Team Requirements

> These guidelines define the minimum technical standards that vendors must demonstrate
> in their proposals. Technical evaluations are scored 0–100 using the rubric below.
> A minimum score of 60 is required to proceed to commercial evaluation.

---

## 1. Methodology Requirements

1.1 Vendors must clearly document their **project delivery methodology** in the technical
    proposal. Generic statements ("we follow best practices") are not acceptable.

1.2 Accepted methodologies and their documentation requirements:

| Methodology | Required Documentation |
|---|---|
| **Agile (Scrum/Kanban)** | Sprint cadence, ceremony schedule, backlog management approach, definition of done |
| **Waterfall** | Full WBS, phase gates, sign-off process per phase, escalation matrix |
| **Hybrid (Agile + Waterfall)** | Justification for hybrid, clear delineation of which phases use which method |

1.3 Vendors using Agile must specify:
   - Sprint length (2 weeks preferred; 3-week max)
   - Tooling (e.g., Jira, Azure DevOps, Linear)
   - How they handle scope change mid-sprint
   - Velocity tracking and reporting cadence

1.4 All methodologies must include a **RACI matrix** covering LiverX, vendor, and
    any named subcontractors.

---

## 2. Mandatory Certifications

The following certifications are **required** for all vendor organisations. Missing
certifications at bid submission will result in automatic technical disqualification.

| Certification | Level Required | Validity |
|---|---|---|
| **ISO 9001:2015** (Quality Management) | Organisation-wide | Must be current (not expired) |
| **ISO 27001:2022** (Information Security) | Organisation-wide | Must be current |

The following certification is **strongly preferred** and awards bonus scoring:

| Certification | Scoring Benefit | Notes |
|---|---|---|
| **SOC 2 Type II** | +5 bonus points | Must be within last 12 months; full report required |
| **ISO 22301** (Business Continuity) | +3 bonus points | Optional; relevant for managed services |
| **PCI-DSS** (if handling payment data) | Required if in scope | N/A for non-payment engagements |

2.1 Certificates must be issued by an **accredited certification body** (UKAS, DAkkS,
    or equivalent).

2.2 Vendors with certifications in progress may flag this; **interim** certifications
    do not satisfy the mandatory requirement.

---

## 3. Team Composition Requirements

3.1 All proposals must name the **core delivery team** and provide CVs for all named
    individuals. Anonymous team descriptions are not accepted.

3.2 Minimum named team composition for any engagement:

| Role | Minimum Requirement | Conditions |
|---|---|---|
| **Project Manager** | 1 dedicated PM | PMP or PRINCE2 certification preferred |
| **Technical Lead / Architect** | 1 dedicated tech lead | Must have 7+ years relevant experience |
| **Engineers / Analysts** | Minimum 2 | Seniority mix must align with rate card |
| **QA / Testing Lead** | 1 (or shared with Tech Lead for small engagements) | ISTQB certification preferred |

3.3 CVs must include:
   - Full name and current role
   - Years of experience in relevant domain
   - Top 3 comparable project references with client name, scope, and outcome
   - Certifications held (with expiry dates)
   - Availability commitment (% dedicated to this engagement)

3.4 Key personnel substitution requires **written approval** from the LiverX Project
    Sponsor and 2-week notice minimum.

---

## 4. Technical Scoring Rubric (0–100)

All technical proposals are scored by a panel of at least two LiverX technical evaluators.
Scores are averaged across evaluators. The minimum passing score is **60 out of 100**.

| Category | Max Points | Scoring Criteria |
|---|---|---|
| **Methodology Quality** | 30 pts | Clarity, relevance, adaptability, tooling maturity, RACI completeness |
| **Team Competence** | 30 pts | Experience depth, CV quality, seniority mix, key personnel availability |
| **Certifications** | 20 pts | ISO 9001 (10 pts), ISO 27001 (10 pts), SOC 2 bonus (+5), ISO 22301 bonus (+3) |
| **Relevant Past Projects** | 20 pts | Similarity of scope, recency (last 3 yrs), verifiable references, outcome quality |
| **TOTAL** | **100 pts** | Pass threshold: **60 / 100** |

4.1 Vendors scoring below **60** are disqualified from further evaluation.

4.2 Vendors scoring **75–84** are classified as "Qualified — Conditional" and may be
    invited for a technical clarification interview before final ranking.

4.3 Vendors scoring **85+** are classified as "Technically Preferred" and receive
    priority in final ranking if commercial terms are equivalent.

---

## 5. Security & Architecture Standards

5.1 Proposed solutions must comply with LiverX's **Information Security Policy baseline**:
   - Data encrypted at rest with **AES-256**
   - Data encrypted in transit with **TLS 1.2 or higher**
   - Multi-Factor Authentication (MFA) required for all privileged accounts
   - Critical security patches applied within **72 hours** of release

5.2 Any solution storing or processing LiverX data must undergo a **security architecture
    review** by LiverX's IT Security team before deployment.

5.3 Vendors must provide an annual **penetration test report** from an accredited third-
    party security firm (CREST-certified preferred).

---

## 6. Past Project References

6.1 Vendors must provide a minimum of **3 comparable project references** from the
    last 3 years, with:
   - Client organisation name and industry
   - Engagement scope and contract value (range acceptable)
   - Project duration and delivery outcome
   - Reference contact name and email (references may be contacted)

6.2 LiverX reserves the right to contact references directly. False or misleading
    references will result in immediate disqualification.

---

*Last updated: 2026-04-14 | Owner: LiverX Technology & Architecture*
