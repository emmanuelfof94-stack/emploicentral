# Project Context

## Project Overview
JobMatch AI - An intelligent job platform that centralizes job offers from multiple sources, analyzes user CVs using AI, calculates compatibility scores between profiles and jobs, and sends real-time alerts for relevant opportunities.

## Key Decisions
| Date | Decision | By | Rationale |
|------|----------|-----|-----------|
| 2026-06-03 | Use Atoms Cloud backend | Alex | Built-in auth, DB, storage, AI capabilities |
| 2026-06-03 | AI PDF analysis for CV extraction | Alex | Leverage analyzepdf for structured data extraction |
| 2026-06-03 | deepseek-v4-pro for scoring | Alex | Cost-effective for structured JSON output |
| 2026-06-03 | Private bucket for CVs | Alex | CVs contain sensitive personal data |

## Constraints
- Color Palette: Blue (#2563EB primary), Purple (#7C3AED accent), Slate grays for text
- Typography: Inter for body, bold headings
- Layout: Clean dashboard style with card-based components
- Max 8 code files
- Images to Generate: 4 (hero banner, CV analysis, compatibility score, alerts) - DONE