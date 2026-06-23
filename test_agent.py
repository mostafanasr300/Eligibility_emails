"""Integration test for agent-based job extraction and email generation with fallback."""
import sys
sys.path.insert(0, '.')
import os
os.environ['USER_AGENT'] = 'test_agent/1.0'

from dotenv import load_dotenv
load_dotenv()

from main import (
    prepare_model, jop_prompt_agent, web_loader, email_prompt_agent,
    web_search, fetch_url, jop_prompt, email_prompt, apply_query,
    _jop_prompt_direct, _email_prompt_direct
)

print("=" * 60)
print("TEST 1: Tool Functions")
print("=" * 60)

ws = web_search.invoke("React developer job requirements 2025")
print(f"web_search: {len(ws)} chars returned")
assert len(ws) > 50, f"web_search returned too little: {ws[:100]}"

fu = fetch_url.invoke("https://example.com")
print(f"fetch_url: {len(fu)} chars returned")
assert "Example" in fu, "fetch_url should contain 'Example'"

print("✓ Tool functions work correctly\n")

print("=" * 60)
print("TEST 2: Backward-Compatible Wrappers")
print("=" * 60)

print("✓ jop_prompt() wrapper available")
print("✓ email_prompt() wrapper available")
print("✓ apply_query() available")
print("✓ _jop_prompt_direct() fallback available")
print("✓ _email_prompt_direct() fallback available")

print("\n=" * 60)
print("TEST 3: Direct (Fallback) Methods Work")
print("=" * 60)

llm = prepare_model()
print("✓ LLM model prepared (llama-3.3-70b-versatile)")

# Load a real job posting
job_url = "https://wuzzuf.net/jobs/p/zCgEzB5TJkp0-Front-End-Developer-Numo-Cairo-Egypt?o=1&l=bp&t=bj&bpv=np&a=Front-End-Developer-Jobs-in-Egypt"
page_data = web_loader(job_url)
print(f"✓ Page loaded: {len(page_data)} page(s)")

# Test direct fallback method
print("\nTesting direct (fallback) job extraction...")
job_json = _jop_prompt_direct(llm, page_data)
role = job_json.get("role", "?")
skills = job_json.get("skills", [])
print(f"✓ Direct method extracted:")
print(f"  Role: {role}")
print(f"  Skills ({len(skills)}): {skills[:5]}")
assert len(role) > 0, "Role should not be empty"
assert len(skills) > 0, "Skills should not be empty"

print("\n=" * 60)
print("TEST 4: Agent-Based Job Extraction (with fallback)")
print("=" * 60)

print("Running agent-based job extraction (may take 10-30 seconds)...")
job_json = jop_prompt_agent(llm, page_data)
role = job_json.get("role", "?")
skills = job_json.get("skills", [])
experience = job_json.get("experience", "?")
print(f"✓ Agent result:")
print(f"  Role: {role}")
print(f"  Experience: {experience}")
print(f"  Skills ({len(skills)}): {skills[:5]}")
assert len(role) > 0, "Role should not be empty"
assert len(skills) > 0, "Skills should not be empty"

print("\n=" * 60)
print("TEST 5: Agent-Based Email Generation (with fallback)")
print("=" * 60)

mock_courses = [
    {
        "course_id": "CRS-001",
        "title": "Complete React Developer Course",
        "url": "https://example.com/react-course",
        "platform": "Udemy",
        "combined_score": 0.85,
        "vector_score": 0.8,
        "graph_score": 0.7,
        "matched_skills": ["React", "JavaScript", "Frontend"]
    },
    {
        "course_id": "CRS-002",
        "title": "Advanced CSS and Sass",
        "url": "https://example.com/css-course",
        "platform": "Coursera",
        "combined_score": 0.72,
        "vector_score": 0.7,
        "graph_score": 0.6,
        "matched_skills": ["CSS", "Sass", "Responsive Design"]
    }
]

print("Running agent-based email generation...")
email = email_prompt_agent(llm, job_json, mock_courses)
print(f"✓ Email generated ({len(email)} chars)")
print(f"\n--- Email Preview (first 400 chars) ---")
print(email[:400])
print("...")

assert "Subject:" in email, "Email should contain subject line"
assert "Mostafa" in email, "Email should contain signature"

print("\n" + "=" * 60)
print("ALL TESTS PASSED SUCCESSFULLY")
print("=" * 60)
print("\nKey changes made to main.py:")
print("  1. Agent with web_search & fetch_url tools (create_react_agent)")
print("  2. Direct prompt methods kept as fallback (_jop_prompt_direct)")
print("  3. try/except + fallback logic - if agent fails, uses direct prompts")
print("  4. Agent told to NOT call tools unless text is critically incomplete")
print("  5. Backward-compatible wrappers maintained")