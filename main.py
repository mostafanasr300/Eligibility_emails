# Note: `chromadb` is optional and used by other modules; avoid importing at module import time
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import os
import json
from langchain_community.document_loaders import WebBaseLoader
from langchain_core.output_parsers import JsonOutputParser
from graph_db import get_graph_provider

# Cache for course URL lookup to fill missing URLs in results
_COURSE_URL_MAP = None

def _load_course_url_map(*data_paths):
    global _COURSE_URL_MAP
    if _COURSE_URL_MAP is not None:
        return _COURSE_URL_MAP
    mapping = {}
    paths = list(data_paths) if data_paths else ["Data&relation.txt", "course_skill_graph_50_samples.json", "course_skill_graph_samples.json"]
    for data_path in paths:
        try:
            if os.path.exists(data_path):
                with open(data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    cid = item.get("course_id")
                    url = item.get("url") or item.get("links") or ""
                    if cid:
                        mapping[cid] = url
        except Exception:
            pass
    _COURSE_URL_MAP = mapping
    return _COURSE_URL_MAP

def web_loader(jop_link):
    """Load content from a given URL."""
    loader = WebBaseLoader(
        jop_link,
        header_template={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }
    )
    page_data = loader.load()
    return page_data

def prepare_model():
    load_dotenv()
    llama_key = os.getenv("llama-70b-key")
    if not llama_key:
        raise ValueError("Llama API key not found in environment. Please check your .env file.")
    try:
        from langchain_groq import ChatGroq
    except Exception as e:
        raise ModuleNotFoundError(
            "The 'langchain_groq' package is required for the LLM backend but is not installed. "
            "Install it with `pip install langchain-groq` or configure an alternative LLM. "
            f"(Original error: {e})"
        )

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=1.0,
        api_key=llama_key
    )
    return llm

# ─── Direct Prompt Methods (No Agent/Tools - avoids Groq tool-calling failures) ─────

def _extract_skills_from_description(llm, description):
    """Helper function to extract skills specifically from job description text."""
    if not description or not description.strip():
        return []
    
    prompt = PromptTemplate.from_template("""
            ### JOB DESCRIPTION:
            {description}
            ### INSTRUCTION:
            Extract ONLY the technical and professional skills required for this job.
            Return as a JSON array of skill strings (e.g., ["Python", "React", "AWS", "Docker"]).
            Be comprehensive and include programming languages, frameworks, tools, and methodologies.
            Only return the valid JSON array. No explanations or preamble.
            ### JSON ARRAY (NO PREAMBLE):    
            """
    )
    chain = prompt | llm
    try:
        res = chain.invoke(input={"description": description})
        content = res.content.strip()
        
        # Parse JSON array
        if content.startswith("```"):
            first_newline = content.find("\n")
            if first_newline != -1:
                content = content[first_newline:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        
        json_parser = JsonOutputParser()
        skills = json_parser.parse(content)
        return skills if isinstance(skills, list) else []
    except Exception as e:
        print(f"Error extracting skills from description: {e}")
        return []


def _jop_prompt_direct(llm, page_data):
    """
    Direct LLM prompt method (no agent/tools).
    Extracts job details from scraped page data into JSON format.
    """
    if isinstance(page_data, list):
        content_str = max((getattr(p, 'page_content', str(p)) for p in page_data), key=lambda s: len(s))
    else:
        content_str = str(page_data)
    
    prompt = PromptTemplate.from_template("""
            ### SCRAPED TEXT FROM WEBSITE:
            {page_data}
            ### INSTRUCTION:
            The scraped text is from a job offers website.
            Your job is to extract the job postings and return them in JSON format containing the 
            following keys: `role`, `experience`, `skills` and `description`.
            
            - `role`: Extract the specific job title/position keyword explicitly
            - `experience`: Extract the specific required years of experience or level keyword explicitly (e.g., 'Senior', '3+ years', 'Entry-level')
            - `skills`: A comprehensive JSON array of explicit technical and professional skill keywords required
            - `description`: A precise detail of the job posting, qualifications, summary, highlighting key responsibilities and requirements
                              
            Only return the valid JSON. Return one complete JSON. Do your best to extract the skills and role from the description if they are not explicitly listed.
            Do not return any empty or null values, if a field is missing or cannot be extracted directly, simply extract it from description. 
            Do not include any other text, explanations, or markdown code fences (do not wrap in ```json ... ```).
            The output should be a single JSON object with the specified keys not other types .
            
            IMPORTANT: Do NOT call any tools or functions. Just return the JSON directly.
            
            ### VALID JSON (NO PREAMBLE):    
            """
    )
    chain = prompt | llm
    res = chain.invoke(input={"page_data": content_str})
    
    # Robustly parse JSON (stripping code block wrappers if generated)
    content = res.content.strip()
    if content.startswith("```"):
        first_newline = content.find("\n")
        if first_newline != -1:
            content = content[first_newline:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    json_parser = JsonOutputParser()
    json_data = json_parser.parse(content)
    
    # If skills are empty or sparse, extract them specifically from the description
    extracted_skills = json_data.get("skills", [])
    if extracted_skills and isinstance(extracted_skills, list):
        json_data["skills"] = [str(s) for s in extracted_skills if s is not None]

    description = json_data.get("description", "")
    if description:
        description_skills = _extract_skills_from_description(llm, description)
        if description_skills:
            json_data["skills"] = [str(s) for s in description_skills]
    
    return json_data


def _email_prompt_direct(llm, json_data, recommended_courses, min_vector_score=0.4):
    """
    Direct LLM prompt method (no agent/tools).
    """
    def format_course_line(course):
        match_info = ""
        if course.get("matched_skills"):
            match_info = f" — matches: {', '.join(course['matched_skills'])}"

        title = course.get("title", "Untitled Course")
        platform = course.get("platform", "Unknown Platform")
        url = course.get("url", "").strip()

        if url:
            return f"{title} on {platform} ({url}){match_info}"
        return f"{title} on {platform}{match_info}"

    highlighted_courses = [
        course for course in recommended_courses
        if (course.get("vector_score", course.get("v_score", 0.0)) or 0.0) > min_vector_score
    ]
    llm_courses = highlighted_courses if highlighted_courses else recommended_courses[:5]
    course_list_str = "; ".join(format_course_line(course) for course in llm_courses)

    skills_field = json_data.get('skills') or []
    if isinstance(skills_field, str):
        skills_field = [skills_field]
    skills_field = [str(s) for s in skills_field]

    job_desc_text = (
        f"Role: {json_data.get('role','N/A')}\n"
        f"Experience: {json_data.get('experience','N/A')}\n"
        f"Skills: {', '.join(skills_field)}\n"
        f"Description: {json_data.get('description','')}"
    )

    e_prompt = PromptTemplate.from_template(
        """
        ### JOB DESCRIPTION:
        {job_description}

        ### INSTRUCTION:
        You are a big expert in the tech field. You work as an AI & Software Consultant helping candidates prepare for tech jobs and become fully eligible.
        Your task is to write a highly professional, encouraging, and actionable guidance email/message addressed directly to the CANDIDATE who is about to apply for this job.
        
        IMPORTANT: Do NOT call any tools or functions. Just write the email directly.
        
        In the email body:
        1. Address the candidate directly (e.g., "Dear Candidate" or "Hello there").
        2. Summarize the key requirements of the role.
        3. Recommend the following tailored courses from our collection that match the required job skills and bridge their gaps.
        4. Mention every course listed below naturally inside the email body:
        {course_list}
        5. Explain briefly how each course will help them build the specific skills needed to make them extremely eligible for the role.
        6. Provide tips on how to prepare for the interview.
        
        Remember:
        - Sign off as "Mostafa, AI & Software Consulting Expert".
        - Do not include a subject line because it will be added separately.
        - Do not provide a preamble or postamble. Output only the email body.
        ### EMAIL BODY TO CANDIDATE (NO PREAMBLE):
        """
    )
    email_chain = e_prompt | llm
    email_body = email_chain.invoke({"job_description": job_desc_text, "course_list": course_list_str}).content.strip()

    # Post-process: ensure each recommended course URL is mentioned
    for course in llm_courses:
        title = course.get('title', '')
        url = course.get('url', '') or course.get('links', '') or ''
        if url and url not in email_body:
            email_body += f"\n\nAlso recommended: {title} — you can find it here: {url}."

    subject_role = json_data.get("role", "Target Role").strip() or "Target Role"
    subject_line = f"Subject: Preparation Plan for the {subject_role} Role"

    return f"{subject_line}\n\n{email_body}"


# ─── Public Wrappers (Direct Only - No Agent/Tools) ────────────────────────

def jop_prompt(llm, page_data):
    """Extract job details from scraped page data using direct prompt only."""
    return _jop_prompt_direct(llm, page_data)

def email_prompt(llm, json_data, recommended_courses, min_vector_score=0.365):
    """Generate email using direct prompt only."""
    return _email_prompt_direct(llm, json_data, recommended_courses, min_vector_score)


# ─── Query Functions ───────────────────────────────────────────────

def _build_content_str(page_data):
    """Extract the longest content string from page_data."""
    if isinstance(page_data, list):
        return max((getattr(p, 'page_content', str(p)) for p in page_data), key=lambda s: len(s))
    return str(page_data)


def apply_query(json_data, collection, w_vector=0.5, w_graph=0.5, top_k=10):
    # Extract criteria for search
    criteria = json_data.get("skills", [])
    if not criteria:
        criteria = [json_data.get("role", "")]
    
    # Filter out None values and convert to strings
    criteria = [str(item) for item in criteria if item is not None]
    if not criteria:
        criteria = ["general"]
    
    # 1. Vector Search using Chroma DB
    description = json_data.get("description", "") or ""
    query_text = " ".join(criteria) + " " + description
    vector_results = collection.query(query_texts=[query_text], n_results=top_k)
    
    # Process vector results
    vector_dict = {}
    if vector_results and "ids" in vector_results and vector_results["ids"]:
        ids = vector_results["ids"][0]
        distances = vector_results["distances"][0] if "distances" in vector_results else [1.0] * len(ids)
        metadatas = vector_results["metadatas"][0] if "metadatas" in vector_results else [{}] * len(ids)
        
        for i_idx, c_id in enumerate(ids):
            # Compute vector similarity score bounded in [0, 1]
            dist = distances[i_idx]
            v_score = 1.0 / (1.0 + dist)
            meta = metadatas[i_idx]
            
            # Try multiple URL keys to ensure we find the URL
            url = meta.get("url", "") or meta.get("links", "") or meta.get("links_url", "")
            vector_dict[c_id] = {
                "course_id": c_id,
                "title": meta.get("title", f"Course {c_id}"),
                "url": url,
                "platform": meta.get("platform", ""),
                "v_score": v_score,
                "dist": dist
            }

    # 2. Graph Search using Neo4j or Fallback
    graph_provider, provider_name = get_graph_provider()
    graph_results = graph_provider.query_graph(criteria)
    
    # Process graph results
    graph_dict = {}
    max_graph_score = max([g["score"] for g in graph_results]) if graph_results else 0
    
    for g in graph_results:
        c_id = g["course_id"]
        # Normalize graph score to [0, 1]
        g_score = g["score"] / max_graph_score if max_graph_score > 0 else 0.0
        graph_dict[c_id] = {
            "course_id": c_id,
            "title": g["title"],
            "url": g["url"],
            "platform": g["platform"],
            "g_score": g_score,
            "raw_g_score": g["score"],
            "matched_skills": g.get("matched_skills", [])
        }

    # 3. Hybrid Combination (Weighted Fusion)
    all_course_ids = set(vector_dict.keys()).union(set(graph_dict.keys()))
    hybrid_results = []
    
    for c_id in all_course_ids:
        v_info = vector_dict.get(c_id, {})
        g_info = graph_dict.get(c_id, {})
        
        title = v_info.get("title") or g_info.get("title") or f"Course {c_id}"
        # Ensure we have a URL for every course by falling back to the source data mapping.
        url = v_info.get("url") or g_info.get("url") or ""
        if not url:
            url_map = _load_course_url_map()
            url = url_map.get(c_id, "")
        platform = v_info.get("platform") or g_info.get("platform") or ""
        
        v_score = v_info.get("v_score", 0.0)
        g_score = g_info.get("g_score", 0.0)
        
        # Weighted hybrid score
        combined_score = (w_vector * v_score) + (w_graph * g_score)
        
        hybrid_results.append({
            "course_id": c_id,
            "title": title,
            "url": url,
            "platform": platform,
            "combined_score": combined_score,
            "vector_score": v_score,
            "graph_score": g_score,
            "raw_graph_score": g_info.get("raw_g_score", 0.0),
            "matched_skills": g_info.get("matched_skills", [])
        })

    # Sort hybrid results descending by combined score
    hybrid_results.sort(key=lambda x: x["combined_score"], reverse=True)
    
    return {
        "hybrid": hybrid_results,
        "vector": list(vector_dict.values()),
        "graph": list(graph_dict.values()),
        "provider": provider_name
    }