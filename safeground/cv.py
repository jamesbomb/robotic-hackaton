from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from safeground.models import (
    CVClassification,
    ClassificationLabel,
    ClassificationResult,
    FrameRef,
    RecommendedAction,
    SafeGroundConfig,
)


SCENARIO_TO_FIXTURE = {
    "MINE": "mine.json",
    "NOT_MINE": "not_mine.json",
    "UNCERTAIN": "uncertain.json",
    "INVALID": "invalid.json",
    "LOW_CONFIDENCE": "low_confidence.json",
    "MISSING_BBOX": "missing_bbox.json",
}


def safe_uncertain(raw_response: Any, errors: list[str]) -> CVClassification:
    return CVClassification(
        raw_response=raw_response,
        result=ClassificationResult(
            label=ClassificationLabel.UNCERTAIN,
            confidence=0.0,
            bbox=None,
            evidence=["CV response was not safe to use; human review required."],
            recommended_action=RecommendedAction.HUMAN_REVIEW,
        ),
        valid=False,
        validation_errors=errors,
    )


class MockCVClient:
    """Fixture-backed CV contract stub. The real CV implementation plugs in here."""

    def __init__(self, config: SafeGroundConfig) -> None:
        self.fixture_dir = config.cv_fixture_dir
        self.low_confidence_threshold = config.low_confidence_threshold

    async def classify(self, frame: FrameRef, scenario: str) -> CVClassification:
        fixture_path = self._fixture_path(scenario)
        raw_text = fixture_path.read_text(encoding="utf-8")
        try:
            raw_response = json.loads(raw_text)
        except JSONDecodeError as exc:
            return safe_uncertain(raw_text, [f"invalid JSON: {exc.msg}"])

        try:
            result = ClassificationResult.model_validate(raw_response)
        except ValidationError as exc:
            return safe_uncertain(raw_response, [error["msg"] for error in exc.errors()])

        if result.confidence < self.low_confidence_threshold:
            return CVClassification(
                raw_response=raw_response,
                result=ClassificationResult(
                    label=ClassificationLabel.UNCERTAIN,
                    confidence=result.confidence,
                    bbox=result.bbox,
                    evidence=[
                        *result.evidence,
                        f"Confidence below P0 threshold {self.low_confidence_threshold}.",
                    ],
                    recommended_action=RecommendedAction.HUMAN_REVIEW,
                ),
                valid=True,
                validation_errors=[],
            )

        return CVClassification(raw_response=raw_response, result=result, valid=True)

    def _fixture_path(self, scenario: str) -> Path:
        key = scenario.upper()
        if key not in SCENARIO_TO_FIXTURE:
            allowed = ", ".join(sorted(SCENARIO_TO_FIXTURE))
            raise ValueError(f"unknown CV scenario {scenario!r}; choose one of: {allowed}")
        return self.fixture_dir / SCENARIO_TO_FIXTURE[key]
