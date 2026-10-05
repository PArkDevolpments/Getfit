# Getfit UI/UX Evolution Programme Ledger

**Ledger authority:** committed repository state  
**Initial baseline:** Getfit 0.1.39  
**Baseline main SHA at programme creation:** `b7cb572cfcfe3a9068b4bb70269395a26e20687e`

Status values:

- PLANNED
- READY
- ACTIVE
- REVIEW
- MERGED
- RELEASED
- BLOCKED

GitHub issue numbers below are the governed backlog created for this programme.

## 0.1.40 — Quality foundation

| Workstream | Status | GitHub issue | Dependencies | Primary owner lane | Release gate |
|---|---|---:|---|---|---|
| GF-0140-01 Review-pack visibility correctness | ACTIVE | #74 | none | Visual QA + Frontend | pending |
| GF-0140-02 Review-pack privacy sanitisation | PLANNED | #75 | none | Security/Privacy + Frontend | pending |
| GF-0140-03 Mobile workout secondary controls | PLANNED | #76 | none | Frontend + Product/UX | pending |
| GF-0140-04 Today responsive contract alignment | PLANNED | #77 | none | Product/UX + Frontend | pending |
| GF-0140-05 Accessibility contrast closure | PLANNED | #78 | none | Accessibility + Frontend | pending |
| GF-0140-06 Tablet review-capture reliability | PLANNED | #79 | GF-0140-01 related | Visual QA + Frontend | pending |

## 0.2.0 — Core premium journey

| Workstream | Status | GitHub issue | Dependencies | Primary owner lane | Release gate |
|---|---|---:|---|---|---|
| GF-0200-01 Shared design system | PLANNED | #80 | 0.1.40 complete | Design System + Frontend | pending |
| GF-0200-02 Today coaching dashboard | PLANNED | #81 | GF-0200-01 | Product/UX + Frontend | pending |
| GF-0200-03 Live workout coaching context | PLANNED | #82 | GF-0200-01; governed recommendation evidence | Frontend + Domain | pending |
| GF-0200-04 Workout Complete | PLANNED | #83 | GF-0200-01; completion evidence | Frontend + Domain | pending |
| GF-0200-05 Progress information architecture | PLANNED | #84 | GF-0200-01 | Product/UX + Frontend | pending |
| GF-0200-06 Strength analytics presentation | PLANNED | #85 | GF-0200-05 | Data/Analytics + Frontend | pending |
| GF-0200-07 Muscle activity visualisation | PLANNED | #86 | GF-0200-05 | Data/Analytics + Frontend | pending |
| GF-0200-08 Training and consistency presentation | PLANNED | #87 | GF-0200-05 | Data/Analytics + Frontend | pending |
| GF-0200-09 Responsive premium pass | PLANNED | #88 | GF-0200-02..08 | Product/UX + Visual QA | pending |
| GF-0200-10 0.2.0 release validation | PLANNED | #89 | GF-0200-01..09 | Release + QA | pending |

## 0.2.1 — Programme and discovery

| Workstream | Status | GitHub issue | Dependencies | Primary owner lane | Release gate |
|---|---|---:|---|---|---|
| GF-0210-01 Plan journey | PLANNED | #90 | 0.2.0 released | Product/UX + Frontend | pending |
| GF-0210-02 Library density and discovery | PLANNED | #91 | 0.2.0 released | Product/UX + Frontend | pending |
| GF-0210-03 Exercise Detail | PLANNED | #92 | GF-0210-02 | Frontend + Data/Analytics | pending |
| GF-0210-04 More information architecture | PLANNED | #93 | 0.2.0 released | Product/UX + Frontend | pending |
| GF-0210-05 0.2.1 release validation | PLANNED | #94 | GF-0210-01..04 | Release + QA | pending |

## 0.2.2 — Polish and ambient experience

| Workstream | Status | GitHub issue | Dependencies | Primary owner lane | Release gate |
|---|---|---:|---|---|---|
| GF-0220-01 Workout dark mode | PLANNED | #95 | 0.2.1 released | Design System + Frontend | pending |
| GF-0220-02 Motion system | PLANNED | #96 | 0.2.1 released | Product/UX + Frontend + Accessibility | pending |
| GF-0220-03 Home Assistant ambient surfaces | PLANNED | #97 | 0.2.1 released | HA Integration + Frontend | pending |
| GF-0220-04 0.2.2 release validation | PLANNED | #98 | GF-0220-01..03 | Release + QA | pending |

## Future 0.3.x

Governed coaching/progression/adaptation remains future scope and has no implementation authority from this ledger yet.

## Ledger update rule

Every workstream transition must update:

- status;
- issue/PR reference;
- acceptance evidence;
- review evidence;
- release result or blocker.

Do not use chat as a substitute for this ledger.
