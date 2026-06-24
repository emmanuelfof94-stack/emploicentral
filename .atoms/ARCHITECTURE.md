# Architecture Design

## System Overview
Full-stack job matching platform with React frontend and Atoms Cloud backend. AI-powered CV analysis extracts user skills/experience, then compatibility scoring matches profiles against job offers.

## Tech Stack
- Frontend: React + TypeScript + Tailwind CSS + shadcn/ui
- Backend: Atoms Cloud (FastAPI, PostgreSQL, Object Storage, AI Hub)
- AI: analyzepdf for CV extraction, deepseek-v4-pro for compatibility scoring

## Module Design
| Module | Responsibility | Key Files |
|--------|---------------|-----------|
| Landing | Marketing page with features | src/pages/Landing.tsx |
| Auth | Login/Register flow | src/pages/Auth.tsx |
| Dashboard | User overview with scores | src/pages/Dashboard.tsx |
| Jobs | Job listing with filters | src/pages/Jobs.tsx |
| Profile | CV upload and profile management | src/pages/Profile.tsx |
| Alerts | Alert preferences configuration | src/pages/Alerts.tsx |
| Backend API | CV analysis and scoring | backend/routers/cv_analysis.py |

## Tech Decisions
| Decision | Choice | Rationale |
|----------|--------|-----------|
| CV Analysis | analyzepdf endpoint | Native PDF parsing with AI extraction |
| Scoring | deepseek-v4-pro gentxt | Cost-effective structured JSON output |
| Storage | Private bucket | CV data is sensitive |
| Frontend AI calls | client.apiCall.invoke | Chained AI needs backend orchestration |

## File Tree Plan
```
app/frontend/src/
├── App.tsx (routing)
├── pages/
│   ├── Landing.tsx
│   ├── Auth.tsx
│   ├── Dashboard.tsx
│   ├── Jobs.tsx
│   ├── Profile.tsx
│   └── Alerts.tsx
├── components/
│   └── Navbar.tsx
└── lib/
    └── client.ts (web-sdk)

app/backend/routers/
└── cv_analysis.py (custom AI endpoints)
app/backend/services/
└── cv_analysis.py (business logic)
```

## Implementation Guide
1. Backend: Create cv_analysis router with analyze-cv, compatibility-score, and batch-scores endpoints
2. Frontend: Build pages with web-sdk integration for auth, CRUD, storage, and AI
3. Use client.apiCall.invoke for custom backend endpoints (CV analysis, scoring)
4. Use client.entities for standard CRUD (job_offers, user_profiles, alert_preferences)