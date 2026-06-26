"""
CV Analysis service layer.
Provides AI-powered CV extraction and job compatibility scoring.
"""

import json
import logging
import re
from typing import Any, Dict, List

from fastapi import HTTPException

from core.config import settings
from schemas.aihub import AnalyzePdfRequest, ChatMessage, GenTxtRequest
from services import cv_heuristic
from services.aihub import AIHubService, default_text_model

logger = logging.getLogger(__name__)


def extract_json_block(text: str) -> str:
    """Extract JSON block from AI response that may contain markdown fences."""
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\n(.*?)```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text


class CvAnalysisService:
    """Service for CV analysis and job compatibility scoring."""

    def __init__(self):
        self.ai_service = AIHubService()
        # External AI is optional. When unconfigured, we use the local heuristic engine.
        self.ai_available = bool(
            getattr(settings, "app_ai_base_url", "") and getattr(settings, "app_ai_key", "")
        )

    async def analyze_cv(self, pdf_base64: str) -> Dict[str, Any]:
        """Analyze a CV PDF. Uses external AI if configured, else a local heuristic.

        Falls back to the local heuristic if the AI call fails for any reason.
        """
        if self.ai_available:
            try:
                return await self._analyze_cv_ai(pdf_base64)
            except Exception as exc:  # noqa: BLE001 - graceful degradation
                logger.warning("AI CV analysis failed (%s); falling back to local heuristic", exc)
        return self._analyze_cv_local(pdf_base64)

    def _analyze_cv_local(self, pdf_base64: str) -> Dict[str, Any]:
        """Key-free CV extraction using PyMuPDF + keyword heuristics."""
        try:
            text = cv_heuristic.decode_pdf_text(pdf_base64)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Fichier PDF invalide.") from exc
        if not text.strip():
            raise HTTPException(
                status_code=422,
                detail="Impossible d'extraire du texte du PDF (CV scanné/image ?).",
            )
        return cv_heuristic.analyze_cv_text(text)

    async def _analyze_cv_ai(self, pdf_base64: str) -> Dict[str, Any]:
        """
        Analyze a CV PDF and extract structured profile data.

        Args:
            pdf_base64: Base64 data URI of the PDF file.

        Returns:
            Dict with keys: skills, experience_years, education, sector, job_title,
            full_name, email, phone, location, profile_summary
        """
        instruction = (
            "Extract the following information from this CV/resume as a JSON object:\n"
            "- full_name (string): the candidate's full name\n"
            "- email (string): email address\n"
            "- phone (string): phone number\n"
            "- skills (string): comma-separated list of technical and soft skills\n"
            "- experience_years (integer): total years of professional experience\n"
            "- education (string): highest education level and field\n"
            "- sector (string): primary industry/sector\n"
            "- job_title (string): current or most recent job title\n"
            "- location (string): city/country\n"
            "- profile_summary (string): a brief 2-3 sentence professional summary\n\n"
            "Return ONLY a valid JSON object with these exact keys. "
            "If a field cannot be determined, use null."
        )

        request = AnalyzePdfRequest(
            pdf=pdf_base64,
            instruction=instruction,
            mode="extract",
        )

        response = await self.ai_service.analyze_pdf(request)
        raw_content = response.result.strip()

        # Parse the structured output
        payload_text = extract_json_block(raw_content)

        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            # Retry with repair
            repair_request = GenTxtRequest(
                messages=[
                    ChatMessage(role="system", content="Fix this into valid JSON only. Return ONLY the JSON object."),
                    ChatMessage(role="user", content=payload_text),
                ],
                model=default_text_model(),
            )
            repaired = await self.ai_service.gentxt(repair_request)
            try:
                payload = json.loads(extract_json_block(repaired.content.strip()))
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to parse CV analysis results. Please try again."
                ) from exc

        # Validate required fields
        required_fields = ["skills", "experience_years", "education", "sector", "job_title"]
        missing = [field for field in required_fields if field not in payload]
        if missing:
            raise HTTPException(
                status_code=500,
                detail=f"CV analysis missing fields: {', '.join(missing)}. Please try again."
            )

        return payload

    async def calculate_compatibility(
        self, profile_data: Dict[str, Any], job_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compatibility score. Uses external AI if configured, else local heuristic.

        Falls back to the local heuristic if the AI call fails for any reason.
        """
        if self.ai_available:
            try:
                return await self._calculate_compatibility_ai(profile_data, job_data)
            except Exception as exc:  # noqa: BLE001 - graceful degradation
                logger.warning("AI scoring failed (%s); falling back to local heuristic", exc)
        return cv_heuristic.score_profile_job(profile_data, job_data)

    async def _calculate_compatibility_ai(
        self, profile_data: Dict[str, Any], job_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate compatibility score between a user profile and a job offer.

        Args:
            profile_data: Dict with user profile fields (skills, experience_years, etc.)
            job_data: Dict with job offer fields (title, requirements, sector, etc.)

        Returns:
            Dict with keys: score (0-100), strengths (list), gaps (list), summary (string)
        """
        prompt = (
            "You are a job matching expert. Analyze the compatibility between this candidate profile "
            "and job offer. Return ONLY a valid JSON object with these exact keys:\n"
            "- score (integer 0-100): overall compatibility percentage\n"
            "- strengths (array of strings): 2-4 key strengths that match the job\n"
            "- gaps (array of strings): 1-3 areas where the candidate falls short\n"
            "- summary (string): a brief 2-sentence explanation of the match\n\n"
            f"CANDIDATE PROFILE:\n"
            f"- Skills: {profile_data.get('skills', 'N/A')}\n"
            f"- Experience: {profile_data.get('experience_years', 'N/A')} years\n"
            f"- Education: {profile_data.get('education', 'N/A')}\n"
            f"- Sector: {profile_data.get('sector', 'N/A')}\n"
            f"- Job Title: {profile_data.get('job_title', 'N/A')}\n"
            f"- Location: {profile_data.get('location', 'N/A')}\n\n"
            f"JOB OFFER:\n"
            f"- Title: {job_data.get('title', 'N/A')}\n"
            f"- Company: {job_data.get('company', 'N/A')}\n"
            f"- Sector: {job_data.get('sector', 'N/A')}\n"
            f"- Requirements: {job_data.get('requirements', 'N/A')}\n"
            f"- Description: {job_data.get('description', 'N/A')}\n"
            f"- Location: {job_data.get('location', 'N/A')}\n"
            f"- Contract Type: {job_data.get('contract_type', 'N/A')}\n"
        )

        request = GenTxtRequest(
            messages=[
                ChatMessage(role="system", content="You are a job matching expert. Return ONLY valid JSON."),
                ChatMessage(role="user", content=prompt),
            ],
            model=default_text_model(),
        )

        response = await self.ai_service.gentxt(request)
        raw_content = response.content.strip()

        payload_text = extract_json_block(raw_content)

        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            # Retry with repair
            repair_request = GenTxtRequest(
                messages=[
                    ChatMessage(role="system", content="Fix this into valid JSON only. Return ONLY the JSON object."),
                    ChatMessage(role="user", content=payload_text),
                ],
                model=default_text_model(),
            )
            repaired = await self.ai_service.gentxt(repair_request)
            try:
                payload = json.loads(extract_json_block(repaired.content.strip()))
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to parse compatibility score. Please try again."
                ) from exc

        # Validate required fields
        required_fields = ["score", "strengths", "gaps", "summary"]
        missing = [field for field in required_fields if field not in payload]
        if missing:
            raise HTTPException(
                status_code=500,
                detail=f"Compatibility result missing fields: {', '.join(missing)}. Please try again."
            )

        # Ensure score is an integer between 0-100
        try:
            payload["score"] = max(0, min(100, int(payload["score"])))
        except (TypeError, ValueError):
            payload["score"] = 0

        return payload

    async def batch_calculate_scores(
        self, profile_data: Dict[str, Any], jobs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Calculate compatibility scores for a profile against multiple jobs.

        Args:
            profile_data: Dict with user profile fields.
            jobs: List of job offer dicts.

        Returns:
            List of dicts with job_id, job_title, company, score, strengths, gaps, summary,
            sorted by score descending.
        """
        results = []

        for job in jobs:
            try:
                score_data = await self.calculate_compatibility(profile_data, job)
                results.append({
                    "job_id": job.get("id"),
                    "job_title": job.get("title"),
                    "company": job.get("company"),
                    "location": job.get("location"),
                    "contract_type": job.get("contract_type"),
                    "score": score_data.get("score", 0),
                    "strengths": score_data.get("strengths", []),
                    "gaps": score_data.get("gaps", []),
                    "summary": score_data.get("summary", ""),
                })
            except HTTPException:
                # If scoring fails for one job, add it with score 0
                results.append({
                    "job_id": job.get("id"),
                    "job_title": job.get("title"),
                    "company": job.get("company"),
                    "location": job.get("location"),
                    "contract_type": job.get("contract_type"),
                    "score": 0,
                    "strengths": [],
                    "gaps": [],
                    "summary": "Unable to calculate compatibility score.",
                })
            except Exception as e:
                logger.error(f"Error scoring job {job.get('id')}: {e}")
                results.append({
                    "job_id": job.get("id"),
                    "job_title": job.get("title"),
                    "company": job.get("company"),
                    "location": job.get("location"),
                    "contract_type": job.get("contract_type"),
                    "score": 0,
                    "strengths": [],
                    "gaps": [],
                    "summary": "Unable to calculate compatibility score.",
                })

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results