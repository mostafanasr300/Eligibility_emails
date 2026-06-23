import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import (  # noqa: E402
    prepare_model,
    jop_prompt,
    email_prompt,
    _jop_prompt_direct,
    _email_prompt_direct,
    apply_query,
    web_loader,
)


def test_prepare_model_returns_llm():
    """Verify prepare_model() returns a usable LLM object when API key is set."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        pytest.skip("GROQ_API_KEY not set in environment — skipping live LLM test.")
    llm = prepare_model()
    assert llm is not None


def test_jop_prompt_direct_structure():
    """Verify _jop_prompt_direct returns expected keys when called with live LLM."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        pytest.skip("GROQ_API_KEY not set in environment — skipping live LLM test.")
    llm = prepare_model()
    result = _jop_prompt_direct(llm, "Looking for a Frontend developer with 2 years of React experience.")
    assert isinstance(result, dict)
    assert result.get("role") is not None
    assert isinstance(result.get("skills"), list)


def test_email_prompt_direct_structure():
    """Verify _email_prompt_direct returns a string email when called with live LLM."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        pytest.skip("GROQ_API_KEY not set in environment — skipping live LLM test.")
    llm = prepare_model()
    job_json = {"role": "Frontend Developer", "skills": ["React"]}
    mock_courses = [
        {"course_id": "CRS-001", "title": "React Basics", "combined_score": 0.9}
    ]
    email = _email_prompt_direct(llm, job_json, mock_courses)
    assert isinstance(email, str)
    assert len(email) > 0
