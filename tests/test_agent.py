import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import jop_prompt_agent, email_prompt_agent, _jop_prompt_direct, llm

def test_tool_functions():
    from main import web_search, fetch_url
    ws = web_search.invoke("React developer job requirements")
    fu = fetch_url.invoke("https://example.com")
    
    assert len(ws) > 0
    assert "Example" in fu

def test_fallback_job_extraction():
    # Use real LLM for extraction
    result = _jop_prompt_direct(llm, "Looking for a Frontend developer with 2 years of React experience.")
    
    assert result.get("role") is not None
    assert isinstance(result.get("skills"), list)

def test_agent_email_generation():
    job_json = {"role": "Frontend", "skills": ["React"]}
    mock_courses = [
        {"course_id": "CRS-001", "title": "React Basics", "combined_score": 0.9}
    ]
    
    email = email_prompt_agent(llm, job_json, mock_courses)
    
    assert "Subject:" in email
