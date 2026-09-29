<!-- Source: AIR10 exam-pack PYQ pattern analysis (gate-ee); reproduced as our own analysis. -->

# GATE Electrical Engineering (EE) — 5-Year Previous Year Question (PYQ) Pattern Analysis

**Exam:** Graduate Aptitude Test in Engineering (GATE), **Electrical Engineering paper — code `EE`**
**Conducting body:** GATE is conducted jointly by **IISc Bengaluru and all IITs** on behalf of the **National Coordination Board (NCB), Department of Higher Education, Ministry of Education, Government of India**, with a **rotating Organizing Institute** each year.
**Purpose:** gateway to M.Tech / MS / Direct-PhD / PhD admissions (IITs, IISc, NITs, IIITs), PSU recruitment, and several other organisations.
**Window covered:** the five most recent completed cycles **GATE 2022 → GATE 2026** (papers held Feb 2022 → Feb 2026; GATE 2026 results declared 19 March 2026), with **GATE 2021 shown as a baseline** in the trend tables.
**Compiled:** 2026-09-29.
**Basis:** official GATE portals (gate2025.iitr.ac.in, gate2026.iitg.ac.in, gate2027.iitm.ac.in) — question-paper pattern page, EE syllabus PDF, important-dates page, and the conducting institutes' Statistical & Performance Reports as compiled by ProSyllabus — plus publicly reported analyses (ProSyllabus, Physics Wallah, MADE EASY, AspirantMitraa, Careers360).
**Integrity rule:** no URL is invented; any figure that could not be verified is written as `UNSURE`, not guessed.

---

## 0. Critical caveats (read first)

1. **The paper format is official and rock-stable; the section-wise weightage is NOT published.** GATE releases the **official question papers and answer keys** and the **Statistical & Performance Reports** every year, but it publishes **no chapter/section-wise weightage for EE** — the **only** fixed section figure is **Engineering Mathematics: 13 marks** (stated in the brochure / pattern page). Every topic-weightage table in §6 is therefore **somebody's count of past papers**, not an official blueprint.
2. **Counts differ by source by ±1–2 marks.** Assigning a question to a section is judgemental: e.g. a harmonic power-factor question belongs to both Electric Circuits and Power Electronics. ProSyllabus counted all 165 subject questions across 2024–2026 and found **16 of 165 could fit two sections**. Treat differences of a mark or two as noise, and trust the **multi-year average** over any single year.
3. **The qualifying cut-off is formula-driven, not a fixed pass mark.** It is `max(25, min(40, μ + σ))` — the mean plus one standard deviation of the paper's marks, floored at 25 and capped at 40. So it moves with paper difficulty (25 → 25.7 → 25 → 27.7 across 2023–2026). Reported figures for **2021 and 2022 conflict across sources**, so they are marked `UNSURE`.
4. **EE was a single-session paper in 2024–2026** — no cross-session normalisation applies to those cycles. (Normalisation only matters for papers split across multiple sessions.)
5. **"PYQ" here = the official papers.** Unlike some exams, GATE genuinely publishes its question papers and final keys, so the counts in §6 are based on real papers, not memory reconstructions.
6. **Marks ≠ score ≠ rank.** The same raw mark is worth very different scores in different years because the **topper average (M̄t)** rises (see §8). Always compare on score/rank, never on raw marks across years.

---

## 1. Exam at a glance (representative of the whole window)

| Item | Detail |
| :--- | :--- |
| Conducting body | Rotating Organizing Institute IIT/IISc, on behalf of NCB-GATE, MoE |
| Mode | **Computer-Based Test (CBT)**; English medium |
| Duration | **3 hours (180 minutes)** — PwD candidates with >40% benchmark disability get **+1 hour** compensatory time |
| Total questions | **65** |
| Total marks | **100** |
| Sections | **General Aptitude (GA) + the EE paper** (which itself carries Engineering Mathematics + the core EE sections) |
| Question types | **MCQ** (single correct), **MSQ** (multiple select), **NAT** (numerical answer type) |
| Marking | Each question is **1 mark or 2 marks** |
| Negative marking | **MCQ:** −1/3 (1-mark) · −2/3 (2-mark). **MSQ/NAT:** **no negative marking**. **MSQ has no partial marking** |
| Papers per candidate | A candidate may appear in **one or two** test papers (only approved two-paper combinations) |
| Score validity | **3 years** from the date of result announcement |
| Number of test papers (all branches) | **30** (GATE 2025 and GATE 2026) |
| Age limit / attempt limit | None |

---

## 2. Section-wise structure & marks (official)

The official GATE 2025 question-paper-pattern page states the mark distribution for **all papers except AR, CY, DA, EY, GG, MA, PH, ST, XH and XL** (this group includes **EE**):

| Component | Marks | Share of 100 |
| :--- | ---: | ---: |
| **General Aptitude (GA)** | **15** | 15% |
| **Engineering Mathematics** | **13** | 13% |
| **Subject questions (core EE, incl. the Maths marked above)** | **72** | 72% |
| **Total** | **100** | 100% |

- **EE is in the "GA 15 + Engg Maths 13 + Subject 72" group** (the page's own EE row lists "GA 15 · Subject 85 · Total 100", i.e. the 85 non-GA marks are the paper, of which Engineering Mathematics is 13).
- **65 questions = GA 10 questions (5 × 1-mark + 5 × 2-mark = 15 marks) + 55 subject questions (85 marks).**
- **Time pressure:** 180 min ÷ 65 Q ≈ **166 seconds per question** on average, but 2-mark NATs (mostly in Power Systems, Machines, Power Electronics) take far longer — the real constraint is the heavy numerical sections, not the average.
- **Official EE syllabus = 10 sections** (see §6 for the exact list): Engineering Mathematics · Electric Circuits · Electromagnetic Fields · Signals and Systems · Electrical Machines · Power Systems · Control Systems · Electrical & Electronic Measurements · Analog and Digital Electronics · Power Electronics.

---

## 3. Marking scheme (official, identical across the window)

- Every question is worth **1 mark or 2 marks**; **no partial marking** in MSQ.
- **MCQ:** **+full** correct · **−1/3** (1-mark) or **−2/3** (2-mark) wrong · **0** unattempted.
- **MSQ:** **+full** correct · **0** wrong (no negative; must select *all* correct options for full credit; no partial credit).
- **NAT:** **+full** correct · **0** wrong (no negative; enter a number within a stated range/decimals).
- **Strategic consequence:** the **MSQ + NAT ("no-negative") share** is real but shrinking relative to MCQs. ProSyllabus counted the MCQ share of subject marks rising from **32 of 85 (2024) → 55 of 85 (2026)** — i.e. the paper is getting **more negative-marking-heavy**, so blind guessing costs more now than in 2024.

---

## 4. Format-change history — why the 5-year window is uniform

| Era | Duration | Questions | Marks | Structure |
| :--- | ---: | ---: | ---: | :--- |
| **GATE 2021 → GATE 2026** | 3 h | **65** | **100** | GA 15 + Engg Maths 13 + Subject 72 · MCQ/MSQ/NAT · +1/+2 · −1/3 & −2/3 |
| Earlier years (e.g. pre-2021) | 3 h | 65 | 100 | Same 65-Q / 100-mark / GA-15 skeleton; syllabus and section emphasis have been reorganised over time |

- The **65-question / 100-mark / 3-hour / GA-15** skeleton has been **unchanged for the entire window**, so a 5-year PYQ read is genuinely comparable year-on-year.
- The **EE syllabus was reorganised into the current 10-section form** before this window; the section headings used in §6 are the **current (2025) syllabus headings**. Older papers (pre-2021) remain usable for concept coverage, but check each topic against the current syllabus.

---

## 5. Cycles, organisers & schedule (2021 → 2027)

**Organizing-institute rotation (IISc + IITs rotate annually):**

| Cycle | Organizing institute | Exam dates (as held/scheduled) | Results |
| :--- | :--- | :--- | :--- |
| **GATE 2021** | IIT Bombay | Feb 2021 (multi-session) | 2021 |
| **GATE 2022** | IIT Kharagpur | Feb 2022 (multi-session) | 2022 |
| **GATE 2023** | IIT Kanpur | Feb 2023 | 2023 |
| **GATE 2024** | IISc Bengaluru | Feb 2024 | 2024 |
| **GATE 2025** | IIT Roorkee | Feb 2025 | 2025 |
| **GATE 2026** | **IIT Guwahati** | **7, 8, 14, 15 February 2026** (official) | **19 March 2026** (official) |
| **GATE 2027** *(upcoming)* | **IIT Madras** (official site live) | reported as **Feb 2027** — exact dates `UNSURE` here | ~19 March 2027 (reported) |

- **GATE 2026 (official, IIT Guwahati):** registration opened **28 Aug 2025**; regular registration closed **7 Oct 2025**; extended (late-fee) closed **13 Oct 2025**; admit cards **13 Jan 2026**; exams **7/8/14/15 Feb 2026**; **results 19 Mar 2026**; scorecard released. **New for 2026:** a sectional paper **Energy Science (XE-I)** was added to the Engineering Sciences (XE) paper; **30 test papers** total; a candidate may take **one or two** papers.
- **GATE 2027:** official site (`gate2027.iitm.ac.in`) is live with **IIT Madras** as the organizing institute; a **new EE + Robotics & Automation two-paper combination** is reported. The 2027 score **formula is unchanged** (per the 2027 brochure as compiled by ProSyllabus).
- **EE score users (GATE 2026, official notices):** **Engineers India Ltd (EIL)**, **GAIL**, **OPTCL** and **NPCIL** announced they will use GATE 2026 **EE** results for recruitment (with other PSUs using other papers).

---

## 6. Section-wise recurring topics & indicative weightage

> **Source class for §6:** third-party counts of the **official papers** — ProSyllabus (counted all 55 subject questions in each of the 2024, 2025 and 2026 official papers + final keys), Physics Wallah, and MADE EASY. **Not an official weightage.** Sections can swing by up to **8 marks** between years, so read these as **recurring bands and multi-year averages**, not a fixed blueprint.

### 6.1 Section-wise marks by year (2021 → 2026)

Marks are out of **100** (includes GA 15 and Engineering Mathematics). Each cell is a source count of that year's paper; totals each year = 100.

| Section (official heading) | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | 3-yr mean 24–26 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **General Aptitude** | 15 | 15 | 15 | 15 | 15 | 15 | 15.0 |
| **Engineering Mathematics** | 12 | 13 | 13 | 13 | 13 | **18** | **14.7** |
| **Electric Circuits** | 11 | 7 | 10 | 7 | **4** | **12** | 7.7 |
| **Electromagnetic Fields** | 6 | 7 | 4 | 4 | 7 | 6 | 5.7 |
| **Signals and Systems** | 8 | 8 | 11 | 11 | 9 | **4** | 8.0 |
| **Electrical Machines** | 8 | 12 | 10 | 8 | 9 | 9 | 8.7 |
| **Power Systems** | 12 | 8 | 6 | 10 | 9 | 12 | **10.3** |
| **Control Systems** | 8 | 8 | 9 | 9 | 9 | 6 | 8.0 |
| **Electrical & Electronic Measurements** | 2 | 2 | 2 | 3 | 5 | 2 | 3.3 |
| **Analog and Digital Electronics** | 9 | 9 | 12 | 9 | 10 | 7 | 8.7 |
| **Power Electronics** | 9 | 11 | 8 | 11 | 10 | 9 | **10.0** |
| **Total** | **100** | **100** | **100** | **100** | **100** | **100** | 100 |

**How to read the table / source notes:**
- **2021 & 2022** rows are computed from Physics Wallah's per-subject **1-mark / 2-mark question counts** for those papers (marks = 1×count + 2×count).
- **2023** row is the MADE EASY count; **2024–2026** rows are the ProSyllabus count (they counted the actual papers + final keys, and report the sections that sum to 100).
- **Sources disagree by ±1–2 marks** for the same year (e.g. 2024 Electrical Machines: ProSyllabus 8 vs MADE EASY 6; 2024 Engg Maths: ProSyllabus 13 vs MADE EASY 14; 2023: MADE EASY vs PW differ on Machines/PS/PE). This is section-boundary judgement, not error.
- **The three-year mean column (2024–2026, ProSyllabus)** is the steadiest guide to ROI: **Engg Maths 14.7 → Power Systems 10.3 → Power Electronics 10.0 → Machines 8.7 ≈ Analog+Digital 8.7 → Signals 8.0 ≈ Control 8.0 → Circuits 7.7 → EM Fields 5.7 → Measurements 3.3.**

### 6.2 Section by section — recurring themes and what repeats

**Engineering Mathematics (largest single block; 13 by rule, often more).** Linear Algebra (matrix algebra, systems of equations, eigenvalues/vectors); Calculus (mean-value theorems, definite/improper integrals, partial derivatives, maxima–minima, multiple integrals, Fourier series, vector identities, the integral theorems — Stokes/Gauss/divergence/Green); Differential Equations (first-order, higher-order linear with constant coefficients, variation of parameters, Cauchy/Euler equations, PDEs by separation of variables); Complex Variables (analytic functions, Cauchy integral theorem/formula, Taylor & Laurent series, residue theorem); Probability & Statistics (sampling, conditional probability, mean/median/mode/SD, discrete & continuous distributions — Poisson/Normal/Binomial, correlation, regression). **ProSyllabus found ~18 marks of essentially-mathematical questions in 2026** (divergence theorem, classifying an ODE, a skew-symmetric quadratic form, orthogonal matrices, a contour integral, probability, a definite integral) — above the 13 fixed, because some are filed under subject sections.

**Electric Circuits / Network Theory (highly volatile: 4 → 12 marks in one year).** Ideal/dependent sources; KCL/KVL; node & mesh analysis; network theorems (Thevenin, Norton, superposition, max power transfer); transient response of DC & AC networks; sinusoidal steady state; resonance; two-port networks; balanced three-phase circuits; star–delta; complex power and power factor.

**Electromagnetic Fields (small but steady; 4–7).** Coulomb's law, field intensity, flux density, Gauss's law, divergence; fields/potential of point, line, plane, spherical distributions; dielectrics, capacitance of simple configurations; Biot–Savart, Ampère's law, curl, Faraday's law, Lorentz force; inductance, MMF, reluctance, magnetic circuits, self/mutual inductance.

**Signals and Systems (swings hard: 11 in 2024 → 4 in 2026).** Continuous/discrete signal representation; shifting & scaling; LTI and causal systems; Fourier series of periodic signals; sampling theorem; Fourier transform (CT & DT); **Laplace and Z transforms**; RMS/average for general periodic waveforms.

**Electrical Machines (steadily 8–12; low variance, reliable marks).** Single-phase transformer (equivalent circuit, phasor diagram, OC/SC tests, regulation, efficiency); three-phase transformers (connections, vector groups, parallel operation); auto-transformer; electromechanical energy conversion; DC machines (separately excited, series, shunt; motoring/generating, characteristics, speed control); three-phase induction machines (performance, torque–speed, no-load & blocked-rotor tests, equivalent circuit, starting & speed control); single-phase induction motors; synchronous machines (cylindrical & salient pole, regulation, parallel operation, starting); losses & efficiency.

**Power Systems (highest subject average, 10.3; steadiest high-mark subject alongside Power Electronics).** Generation concepts; AC/DC transmission; transmission-line & cable models; **Economic Load Dispatch (with/without losses)**; series & shunt compensation; insulator field distribution; distribution systems; per-unit; bus admittance matrix; **Gauss–Seidel and Newton–Raphson load flow**; voltage & frequency control; power-factor correction; symmetrical components; symmetrical & unsymmetrical fault analysis; protection principles (over-current, differential, directional, distance); circuit breakers; system stability & equal-area criterion.

**Control Systems (steady ~8–9).** Modelling & representation; feedback; transfer function; block diagrams & signal-flow graphs; transient & steady-state analysis of LTI systems; stability via **Routh–Hurwitz** and **Nyquist**; **Bode plots**; **root loci**; lag/lead/lead-lag compensators; P, PI, PID controllers; **state-space model and solution of state equations of LTI systems** (state space appeared in all three of 2024/2025/2026).

**Electrical & Electronic Measurements (smallest section, 2–5).** Bridges & potentiometers; measurement of voltage, current, power, energy, power factor; instrument transformers; digital voltmeters & multimeters; phase/time/frequency measurement; oscilloscopes; error analysis. **Wheatstone-bridge-type questions recur (2025, 2026).**

**Analog and Digital Electronics (8–12).** Simple diode circuits (clipping, clamping, rectifiers); amplifiers (biasing, equivalent circuit, frequency response); oscillators & feedback amplifiers; op-amps (characteristics & applications); active filters (Sallen-Key, Butterworth); VCOs & timers; **combinational and sequential logic circuits**; multiplexers/demultiplexers; Schmitt triggers; sample-and-hold; A/D and D/A converters.

**Power Electronics (10.0 average; steadiest high-mark subject with Power Systems).** Static V-I characteristics & firing/gating circuits for **Thyristor, MOSFET, IGBT**; DC–DC conversion — **Buck, Boost and Buck-Boost converters** (recurring every year 2024–2026); single- and three-phase uncontrolled rectifiers; voltage- and current-commutated thyristor converters; bidirectional AC–DC voltage-source converters; line-current harmonics (magnitude & phase); power factor & distortion factor of AC–DC converters; single- and three-phase VSI/CSI; sinusoidal PWM.

### 6.3 Topics that repeated in every recent paper (ProSyllabus)

| Topic | Section | Papers |
| :--- | :--- | :--- |
| Economic Load Dispatch | Power Systems | 2024, 2025, 2026 |
| Boost & Buck converters | Power Electronics | 2024, 2025, 2026 |
| State-space analysis | Control Systems | 2024, 2025, 2026 |
| Load flow: Newton–Raphson & bus types | Power Systems | 2025, 2026 (2 of 3) |
| Wheatstone-bridge-type measurement | Measurements | 2025, 2026 (2 of 3) |

---

## 7. Difficulty & question-style trend (2021 → 2026)

> **Source class:** the conducting institutes' official statistics (μ, σ, topper mean) as compiled by ProSyllabus, plus reported paper analyses (PW, MADE EASY, AspirantMitraa). Difficulty labels are subjective; the numerical column is official-report-derived.

| Year | Qualifying mark (GEN) | Paper μ / σ | Topper mean M̄t | Highest mark | Reported difficulty |
| :--- | ---: | :--- | ---: | ---: | :--- |
| 2021 | `UNSURE` (one source reports 30.3) | `UNSURE` | `UNSURE` | `UNSURE` | Moderate |
| 2022 | `UNSURE` (sources conflict: 30.7 vs 25.0) | `UNSURE` | `UNSURE` | `UNSURE` | Moderate |
| **2023** | **25.0** | 10.90 / 9.09 | 57.24 | 66 | **Harder** (lowest topper mean) |
| **2024** | **25.7** | 16.18 / 9.55 | 67.48 | 77 | Moderate |
| **2025** | **25.0** | 14.30 / 10.69 | 71.55 | 81.67 | Moderate |
| **2026** | **27.7** | 16.62 / 11.16 | 75.45 | **92** | Moderate (but highest topper scores) |

**Stable markers across the window:**
- **The format is frozen** — 65 Q / 100 marks / 3 h / GA 15 / Engg Maths 13 / Subject 72 / +1,+2 / −1/3, −2/3. The single most reliable fact in this file.
- **Power Systems and Power Electronics are the steadiest high-mark subjects** (multi-year averages ~10 each); **Electrical Machines is the most reliable** (8–9 every recent year, low variance); **Measurements is the smallest** (2–5).
- **Volatility lives in Circuits, Signals and Maths.** Electric Circuits jumped **4 (2025) → 12 (2026)**; Signals fell **11 (2024) → 4 (2026)**; Maths peaked at ~18 in 2026. **Do not drop any section — a single section can move 8 marks.**
- **The paper is getting "easier to top, harder to stand out":** the **topper mean M̄t rose from 57.24 (2023) to 75.45 (2026)** and the **highest mark rose 66 → 92**. Because the score formula uses M̄t, the **same raw marks convert to a lower GATE score each year**.
- **Negative marking burden is rising:** MCQ share of subject marks **32 (2024) → 55 (2026)** of 85 (ProSyllabus).

---

## 8. Qualifying cut-off & marks→score→rank trend

### 8.1 Official qualifying marks (GEN / OBC-NCL-EWS / SC-ST-PwD)

The qualifying mark follows `max(25, min(40, μ + σ))`; OBC-NCL & EWS need **0.9×** the GEN mark and SC/ST/PwD **two-thirds** of it.

| Year | GEN | OBC-NCL / EWS | SC / ST / PwD |
| :--- | ---: | ---: | ---: |
| 2021 | `UNSURE` | `UNSURE` | `UNSURE` |
| 2022 | `UNSURE` *(sources conflict — see §7)* | `UNSURE` | `UNSURE` |
| **2023** | 25.0 | 22.5 | 16.6 |
| **2024** | 25.7 | 23.1 | 17.1 |
| **2025** | 25.0 | 22.5 | 16.6 |
| **2026** | **27.7** | 24.9 | 18.4 |

- **The "25 marks every year" story is incomplete.** The floor of 25 applied in 2023 and 2025, but 2024 was 25.7 and 2026 was 27.7. (A widely reprinted claim that the cut-off was exactly "25 for 2022–2025" is contradicted by the official reports.)
- **Qualifying = a floor, not a target.** In 2026, only **13,726 of 65,801 (20.9%)** EE candidates qualified.

### 8.2 Official score formula (unchanged through 2027 brochure)

`Score = Sq + (St − Sq) × (M − Mq) / (M̄t − Mq)`, with **Sq = 350**, **St = 900**, `Mq` = GEN qualifying mark, `M̄t` = mean mark of the top 0.1% (or top 10, whichever is larger). Capped at 1000.

**Consequence:** the same raw marks are worth less every year as M̄t climbs. Illustrative (ProSyllabus arithmetic on official Mq/M̄t):

| Raw marks | Score on 2023 field | on 2024 field | on 2025 field | on 2026 field |
| ---: | ---: | ---: | ---: | ---: |
| 40 | 606 | 538 | 527 | 492 |
| 50 | 776 | 670 | 645 | 607 |
| 60 | 947 | 802 | 764 | 722 |
| 70 | 1000 | 933 | 882 | 837 |

So **50 marks = a top-~110 performance in 2023 but only top-~870 in 2026.**

### 8.3 How steep the field is (official marks distribution, 2026)

Appeared EE candidates by marks band (GATE 2026 Statistical & Performance Report, as compiled by ProSyllabus):

| Marks band | Candidates |
| :--- | ---: |
| Below 0 (net negative) | 1,763 |
| 0–10 | 16,464 |
| 10–20 | 27,282 |
| 20–30 | 12,743 |
| 30–40 | 4,789 |
| 40–50 | 1,890 |
| 50–60 | 643 |
| 60–70 | 168 |
| 70+ | 59 |

**Read:** in 2026, **40 marks ≈ top 2,760**, **50 ≈ top 870**, **60 ≈ top 230** of 65,801 — which is exactly what PSU shortlists and IIT cut-offs are asking for (a **good GATE EE target is 60+**, not the 25-mark floor).

### 8.4 Illustrative higher bars (reported, not the qualifying cut-off)

- **IIT Madras M.Tech 2026** made Power Systems / Power Electronics offers at **GATE score ≈ 730 (GEN)** (official cut-off PDF, as cited by ProSyllabus).
- **NPCIL Executive Trainee 2026** shortlisted UR EE candidates at **GATE score 630** (official notice of 19 May 2026, as cited by ProSyllabus).
- **POWERGRID (GATE 2025)** shortlisted UR EE candidates at **51 normalised marks** (official Notice 5 of 4 Nov 2025, as cited by ProSyllabus).

---

## 9. Applicant volume & competition (official-report-derived)

| Year (organiser) | Appeared (EE) | Qualified | Qualified share | Topper mean M̄t |
| :--- | ---: | ---: | ---: | ---: |
| 2021 (IIT Bombay) | `UNSURE` | `UNSURE` | `UNSURE` | `UNSURE` |
| 2022 (IIT Kharagpur) | `UNSURE` | `UNSURE` | `UNSURE` | `UNSURE` |
| 2023 (IIT Kanpur) | 55,292 | 6,213 | 11.2% | 57.24 |
| 2024 (IISc) | 59,599 | 12,596 | 21.1% | 67.48 |
| 2025 (IIT Roorkee) | 67,701 | 11,902 | 17.6% | 71.55 |
| 2026 (IIT Guwahati) | 65,801 | 13,726 | 20.9% | 75.45 |

**Category split (appeared, 2026, official-report-derived):** GEN 16,130 · GEN-EWS 5,334 · OBC-NCL 27,908 · SC 11,766 · ST 4,663 · Female (all categories) 20,447. (EE is a large, OBC-heavy field; roughly **1 in 5 qualifies** in recent years.)

---

## 10. Five-year synthesis — what actually repeats (prep-relevant)

1. **The format is frozen for the whole window.** 65 questions · 100 marks · 180 minutes · GA 15 · Engineering Mathematics 13 · Subject 72 · MCQ/MSQ/NAT · +1/+2 · −1/3 & −2/3 · no negative on MSQ/NAT. **This is the single most reliable planning fact.**
2. **Marks are section-fixed; weightage is not.** You always face 10 GA questions and 55 subject questions, but the *section mix swings by up to 8 marks*. **Cover every one of the 10 sections; weight the top five a little more.**
3. **The five biggest, steadiest blocks (2024–2026 averages):** Engineering Maths **14.7** → Power Systems **10.3** → Power Electronics **10.0** → Electrical Machines **8.7** ≈ Analog & Digital **8.7**. Then Signals **8.0** ≈ Control **8.0** → Circuits **7.7** → EM Fields **5.7** → Measurements **3.3**.
4. **Reliable-marks sections:** Electrical Machines (8–9 every recent year, low variance) and Power Electronics (every-year topics: **Buck/Boost/Buck-Boost converters**). **High-ROI recurring items:** **Economic Load Dispatch** and **load flow (Newton–Raphson, bus types)** in Power Systems, **state-space** in Control, **Wheatstone-bridge** measurements.
5. **The make-or-break variable is volatility, not any single topic.** Circuits 4→12, Signals 11→4, Maths →18 within one cycle. Depth in a "small" section is often where rank is won.
6. **Target 60+, not the 25-mark floor.** The qualifying mark is only ~25 (GEN) — clearing it is easy; **40 → top ~2,760, 50 → top ~870, 60 → top ~230 in 2026**. PSU/IIT bars are far above qualifying.
7. **Compare on score/rank, not raw marks.** The topper mean rose 57→75 across the window, so identical marks yield a **lower score every year**; the score formula (Sq 350, St 900) is unchanged.
8. **The paper rewards numerical accuracy.** With the MCQ share of subject marks rising (32→55 of 85) and negative marking on MCQs, and 2-mark NATs concentrated in Power Systems / Machines / Power Electronics, **"full numerical solutions to the last decimal" beats option-elimination** in the heavy sections.

---

## 11. Sources (real, retrieved 2026-09-29)

**Official (GATE organizing institutes / NCB-GATE):**
- GATE 2026 official portal (IIT Guwahati; 30 papers, two-paper rule, 3-year score validity, PSU users incl. EIL/GAIL/OPTCL/NPCIL for EE) — https://gate2026.iitg.ac.in/index.html
- GATE 2026 important dates (registration, exam 7/8/14/15 Feb 2026, results 19 Mar 2026) — https://gate2026.iitg.ac.in/important-dates.html
- GATE 2025 test papers & syllabus (30 papers; "each paper = 100 marks, GA 15, rest 85") — https://gate2025.iitr.ac.in/exam-papers-and-syllabus.html
- GATE 2025 question-paper pattern (mode, duration, MCQ/MSQ/NAT, mark distribution GA 15 / Engg Maths 13 / Subject 72, negative marking −1/3 & −2/3, no negative on MSQ/NAT) — https://gate2025.iitr.ac.in/question-paper-pattern.html
- GATE 2025 EE syllabus (the 10 official sections) — https://gate2025.iitr.ac.in/doc/2025/GATE%20_EE_2025_Syllabus.pdf
- GATE 2027 official portal (IIT Madras, organizing institute) — https://gate2027.iitm.ac.in/

**Official-report-derived and secondary analyses:**
- ProSyllabus — *GATE EE Previous Year Papers: Topic-Wise Counts 2024, 2025 and 2026* (section-wise mark counts of the official papers + keys; repeated topics; MCQ-share trend; 3-year means) — https://www.prosyllabus.com/hub/gate-ee-previous-year-papers-topic-wise-analysis
- ProSyllabus — *GATE EE Marks vs Score vs Rank: Four Years of Official Data* (score formula; qualifying marks; μ, σ, M̄t; appeared/qualified 2023–2026; official marks distribution; PSU/IIT bars) — https://www.prosyllabus.com/hub/gate-ee-marks-vs-score-vs-rank-calculator
- Physics Wallah — *GATE EE Cut Off* (stated 2026 GEN/OBC/SC qualifying marks; 2021–2025 reported trend) — https://www.pw.live/gate/exams/gate-ee-cut-off
- Physics Wallah — *GATE EE Subject Wise Weightage* (per-subject question counts for 2021 & 2022; 2017–2025 % table) — https://www.pw.live/gate/exams/gate-ee-subject-wise-weightage
- MADE EASY — *GATE 2027 EE Subject-Wise Weightage* (per-subject marks for 2023, 2024, 2025; each sums to 100; exam pattern) — https://www.madeeasy.in/blog/gate-ee-subject-wise-weightage
- AspirantMitraa — *GATE EE Previous Year Cutoff 2025, 2024, 2023, 2022* (an alternative, conflicting "flat 25" view — flagged in §7/§8) — https://www.aspirantmitraa.com/blog/gate-ee-previous-year-cutoff-2025-2024-2023-2022-electrical-engineering-cutoff-trends
- Careers360 — *GATE 2026 conducted by IIT Guwahati* (organizer + Feb 7/8/14/15 2026 dates) — https://engineering.careers360.com/articles/gate-2026-conducted-by-iit-guwahati

---

## 12. UNSURE register (do NOT treat as fact)

- **GATE EE qualifying marks for 2021 and 2022** — the official statistical reports for these years were not retrieved here and reported figures **conflict** (one source gives 30.3 / 30.7, another a flat 25.0). Marked `UNSURE`.
- **GATE EE appeared/qualified counts for 2021 and 2022** — not verified here.
- **GATE 2022 section-wise marks** — ProSyllabus could not retrieve the 2022 official report; the 2022 row in §6.1 is from Physics Wallah's question counts and should be treated as an estimate.
- **GATE 2027 exact exam dates and EE result date** — reported only; not confirmed on the official 2027 page here.
- **Any *official* section-wise weightage for EE** — none exists; the only fixed figure is Engineering Mathematics = 13 marks. Every weightage table here is a count of past papers and varies ±1–2 marks by source.
- **Per-topic (chapter-level) official mark counts** — not published by GATE; §6.2/§6.3 are derived from third-party tagging of the papers.
- **Application fee, number of seats, and category-wise *admission* (not qualifying) cut-offs** for the window — not verified here.

---

*Compiled by the AIR10 exam-pack worker. Structure, marks, marking scheme, syllabus sections, organisers and dates are taken from official GATE portals; qualifying marks, topper means, applicant counts and section-weightage counts are official-report-derived or third-party counts and are labelled as such. Figures that could not be verified are marked `UNSURE`; no URLs were fabricated.*
