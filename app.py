import streamlit as st
import os
import importlib
import traceback
import json
from CHromdb import creat_db
from graph_db import get_graph_provider, get_graph_visualization_data
from cache_manager import get_cache_stats, get_cached_query, set_cached_query
from streamlit.components.v1 import html as st_html

# Suppress LangChain USER_AGENT warning
os.environ.setdefault("USER_AGENT", "EligibilityEmailsApp/1.0")

import logging
logging.getLogger("neo4j").setLevel(logging.ERROR)

# Custom CSS for high-end UI design
CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main-title {
        font-size: 3rem !important;
        font-weight: 700;
        background: linear-gradient(135deg, #FF3366 0%, #7000FF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    
    .subtitle {
        font-size: 1.2rem;
        color: #888899;
        text-align: center;
        margin-bottom: 2rem;
    }

    .course-card {
        border-radius: 12px;
        padding: 1.5rem;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 1rem;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    }

    .course-card:hover {
        transform: translateY(-4px);
        background: rgba(255, 255, 255, 0.08);
        border-color: rgba(112, 0, 255, 0.4);
        box-shadow: 0 8px 30px rgba(112, 0, 255, 0.1);
    }

    .badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        background: rgba(112, 0, 255, 0.2);
        color: #b080ff;
        border: 1px solid rgba(112, 0, 255, 0.3);
        border-radius: 20px;
        font-size: 0.8rem;
        margin-right: 0.4rem;
        margin-bottom: 0.4rem;
    }

    .badge-primary {
        background: rgba(255, 51, 102, 0.2);
        color: #ff80a0;
        border: 1px solid rgba(255, 51, 102, 0.3);
    }

    .badge-success {
        background: rgba(0, 204, 153, 0.2);
        color: #80ffd8;
        border: 1px solid rgba(0, 204, 153, 0.3);
    }

    .score-box {
        display: inline-block;
        font-weight: 600;
        padding: 0.2rem 0.5rem;
        border-radius: 6px;
        font-size: 0.85rem;
        background: rgba(255, 255, 255, 0.1);
        margin-right: 0.5rem;
    }

    .graph-container {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1rem;
    }

    .stat-card {
        background: rgba(112, 0, 255, 0.1);
        border: 1px solid rgba(112, 0, 255, 0.2);
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }

    .stat-number {
        font-size: 2rem;
        font-weight: 700;
        color: #b080ff;
    }

    .stat-label {
        font-size: 0.85rem;
        color: #888899;
    }
    
    .suggestion-chip {
        display: inline-block;
        padding: 0.35rem 0.8rem;
        margin: 0.15rem 0.3rem;
        background: rgba(112, 0, 255, 0.15);
        border: 1px solid rgba(112, 0, 255, 0.3);
        border-radius: 20px;
        font-size: 0.8rem;
        color: #b080ff;
        cursor: pointer;
        transition: all 0.2s;
    }
    .suggestion-chip:hover {
        background: rgba(112, 0, 255, 0.3);
        border-color: rgba(112, 0, 255, 0.6);
    }
    
    .cache-flag {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 0.75rem;
        padding: 2px 8px;
        border-radius: 10px;
        margin-right: 6px;
    }
    .cache-flag.active {
        background: rgba(0, 204, 153, 0.3);
        color: #00ffcc;
        border: 1px solid rgba(0, 204, 153, 0.6);
        font-weight: 700;
    }
    .cache-flag.inactive {
        background: rgba(255, 51, 102, 0.2);
        color: #ff80a0;
        border: 1px solid rgba(255, 51, 102, 0.4);
        font-weight: 700;
    }
</style>
"""

default_job_link = "https://wuzzuf.net/jobs/p/zCgEzB5TJkp0-Front-End-Developer-Numo-Cairo-Egypt?o=1&l=bp&t=bj&bpv=np&a=Front-End-Developer-Jobs-in-Egypt"


def render_pyvis(html_content):
    """Render PyVis HTML inline using st.components.v1.html."""
    if not html_content or "NoConnection" in html_content:
        st.info("Graph visualization not available. Connect to Neo4j for full graph rendering.")
        return
    
    try:
        col_g1, col_g2 = st.columns([3, 1])
        with col_g2:
            st.download_button(
                label="⬇️ Download Graph HTML",
                data=html_content,
                file_name="knowledge_graph.html",
                mime="text/html",
                use_container_width=True
            )

        st.info("💡 **Performance Mode:** The graph visualization is large (2000+ nodes) and has been detached from the main UI to keep this app running fast. Click the download button above, then open the HTML file in your browser to explore the interactive graph.")
    except Exception as e:
        st.error(f"Could not render graph visualization: {e}")


def display_graph_tab(provider, provider_name):
    """Display Neo4j graph visualization tab content."""
    st.markdown("### 🕸️ Knowledge Graph Overview")
    
    if provider_name != "Neo4j":
        st.info("Graph visualization requires Neo4j connection. Currently using in-memory fallback.")
        return
    
    try:
        # Get graph stats and mermaid data
        stats, mermaid = get_graph_visualization_data()
        
        if not stats:
            st.warning("Could not retrieve graph statistics.")
            return
        
        # Display statistics cards
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                f'<div class="stat-card"><div class="stat-number">{stats["course_count"]}</div>'
                f'<div class="stat-label">📚 Courses</div></div>',
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                f'<div class="stat-card"><div class="stat-number">{stats["skill_count"]}</div>'
                f'<div class="stat-label">⚡ Skills</div></div>',
                unsafe_allow_html=True
            )
        with col3:
            st.markdown(
                f'<div class="stat-card"><div class="stat-number">{stats["relationship_count"]}</div>'
                f'<div class="stat-label">🔗 Relationships</div></div>',
                unsafe_allow_html=True
            )
        
        # Top Skills by Connections
        st.markdown("### 🏆 Top Skills by Connections")
        if stats.get("top_skills"):
            skills_data = []
            for s in stats["top_skills"][:10]:
                skills_data.append({"Skill": s["skill"], "Courses Connected": s["connections"]})
            st.dataframe(skills_data, width='stretch', hide_index=True)
        
        # Top Courses by Connections
        st.markdown("### 🏆 Top Courses by Connections")
        if stats.get("top_courses"):
            courses_data = []
            for c in stats["top_courses"][:5]:
                courses_data.append({"Course": c["title"], "Skills Covered": c["connections"]})
            st.dataframe(courses_data, width='stretch', hide_index=True)
        
        # Relationship Type Distribution
        st.markdown("### 🔗 Relationship Distribution")
        if stats.get("relationship_types"):
            rel_data = []
            for r in stats["relationship_types"]:
                rel_data.append({"Relationship Type": r["rel_type"], "Count": r["count"]})
            st.dataframe(rel_data, width='stretch', hide_index=True)
        
        # PyVis Graph
        st.markdown("### 📊 Graph Visualization (PyVis)")
        if mermaid:
            render_pyvis(mermaid)
            st.caption("Note: Graph shows a subset of nodes/relationships. Full graph is larger. Use scroll wheel to zoom and drag to pan.")
        
    except Exception as e:
        st.error(f"Error displaying graph: {e}")
        st.exception(e)


def display_cache_status():
    """Display caching status in the sidebar as minimal flags."""
    stats = get_cache_stats()
    
    # Minimal cache flags
    flags_html = '<div style="display:flex; flex-wrap:wrap; gap:4px; margin-bottom:6px;">'
    if stats["neo4j"]:
        flags_html += '<span class="cache-flag active">✅ Neo4j</span>'
    else:
        flags_html += '<span class="cache-flag inactive">⬜ Neo4j</span>'
    if stats["chroma"]:
        flags_html += '<span class="cache-flag active">✅ Chroma</span>'
    else:
        flags_html += '<span class="cache-flag inactive">⬜ Chroma</span>'
    flags_html += '</div>'
    
    st.sidebar.markdown("### 💾 Cache")
    st.sidebar.markdown(flags_html, unsafe_allow_html=True)
    
    # Show cached query suggestions if available
    cached_entries = stats.get("query_cache_entries", 0)
    if cached_entries > 0:
        st.sidebar.markdown(f'<span style="font-size:0.75rem;color:#888899;">📋 {cached_entries} cached queries</span>', unsafe_allow_html=True)


def display_cached_query_suggestions():
    """Show previous query suggestions as clickable chips."""
    from cache_manager import QUERY_CACHE_FILE
    if os.path.exists(QUERY_CACHE_FILE):
        try:
            with open(QUERY_CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            # Extract role names from cached queries for suggestions
            suggestions = set()
            for key, entry in cache_data.items():
                result = entry.get("result", {})
                if isinstance(result, dict):
                    role = result.get("role", "")
                    if role and isinstance(role, str) and role.strip():
                        suggestions.add(role.strip())
            if suggestions:
                st.markdown("#### 🔍 Previous Searches")
                chips_html = '<div>'
                for suggestion in list(suggestions)[:5]:
                    safe_suggestion = suggestion.replace("'", "'")
                    chips_html += f'<span class="suggestion-chip">{safe_suggestion}</span>'
                chips_html += '</div>'
                st.markdown(chips_html, unsafe_allow_html=True)
        except Exception:
            pass


def create_streamlit_app():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown('<div class="main-title"> Hybrid RAG Job Eligibility System</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Match candidates to job descriptions using combined Vector & Knowledge Graph Search</div>', unsafe_allow_html=True)

    if st.session_state.get("cache_used", False):
        st.success("⚡ **Loaded results instantly from Query Cache!** (Identical input and weights detected)")
        st.session_state["cache_used"] = False

    st.sidebar.markdown("### 🛠️ Configuration & Status")

    # Cache ChromaDB collection in session_state to prevent re-initialization
    if "chroma_collection" not in st.session_state:
        try:
            st.session_state["chroma_collection"] = creat_db()
        except Exception as e:
            st.session_state["chroma_collection"] = None
            st.sidebar.error(f"Chroma DB init error: {e}")

    if "graph_provider" not in st.session_state:
        try:
            st.session_state["graph_provider"] = get_graph_provider()
        except Exception as e:
            st.session_state["graph_provider"] = (None, "Error")

    # Database status with visible bar styling
    try:
        _, provider_name = st.session_state["graph_provider"]
        st.sidebar.markdown("### 🗄️ DB Status")
        db_emoji = "🍃" if provider_name == "Neo4j" else "💾"
        st.sidebar.markdown(f"{db_emoji} **{provider_name}**")
        collection = st.session_state["chroma_collection"]
        if collection is not None:
            st.sidebar.markdown(f"📚 **{collection.count()} courses**")
    except:
        pass
    
    display_cache_status()

    st.sidebar.markdown("### ⚖️ Retrieval Tuning")
    w_vector = st.sidebar.slider("Vector Search Weight (Chroma)", 0.0, 1.0, 0.5, 0.05)
    w_graph = st.sidebar.slider("Graph Search Weight (Neo4j)", 0.0, 1.0, 0.5, 0.05)
    top_k = st.sidebar.slider("Max Courses from Vector DB", 1, 50, 10, 1)

    if "job_json" in st.session_state:
        job_json = st.session_state["job_json"]
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📊 Extracted Job Profile")
        st.sidebar.write(f"**Role:** {job_json.get('role', 'N/A')}")
        st.sidebar.write(f"**Experience:** {job_json.get('experience', 'N/A')}")
        st.sidebar.write("**Extracted Required Skills:**")
        skills = job_json.get("skills", [])
        if isinstance(skills, list):
            for s in skills:
                st.sidebar.markdown(f'<span class="badge badge-primary">{s}</span>', unsafe_allow_html=True)
        else:
            st.sidebar.markdown(f'<span class="badge badge-primary">{skills}</span>', unsafe_allow_html=True)

    st.subheader("🔗 Input Job Description")
    url_input = st.text_input("Enter Job URL:", value=default_job_link)
    col1, col2 = st.columns([1, 1])
    with col1:
        custom_jd_input = st.text_area("Or Paste Raw Job Description text (optional BUT recommended for accurate results):", height=120)
    submit_button = st.button("🚀 Run Hybrid Matcher", width='stretch')

    if submit_button:
        with st.spinner("Analyzing job posting, running queries, and building hybrid recommendations..."):
            try:
                try:
                    main = importlib.import_module("main")
                except Exception:
                    err = traceback.format_exc()
                    st.error("Failed to import core module 'main'. Check dependencies and logs.")
                    st.code(err)
                    raise

                llm = main.prepare_model()
                page_content = ""

                # Cache key generation based on input AND weights
                import hashlib
                query_key = ""
                if custom_jd_input.strip():
                    query_key = "text_" + hashlib.md5(f"{custom_jd_input.strip()}_{w_vector}_{w_graph}_{top_k}".encode()).hexdigest()
                    page_content = custom_jd_input
                else:
                    query_key = "url_" + hashlib.md5(f"{url_input.strip()}_{w_vector}_{w_graph}_{top_k}".encode()).hexdigest()

                # Check Query Cache
                cached_data = get_cached_query(query_key)
                if cached_data:
                    st.session_state["cache_used"] = True
                    job_json = cached_data.get("job_json", {})
                    results = cached_data.get("results", {})
                    email_content = cached_data.get("email_content", "")
                    page_content = cached_data.get("page_content_raw", "")
                else:
                    if custom_jd_input.strip():
                        # User pasted raw job description - use directly
                        st.info("📝 Using pasted job description text.")
                    else:
                        # URL provided - use enhanced loading with job-specific filtering
                        st.info("🌐 Loading and analyzing job posting from URL...")
                        
                        # Step 1: Load the raw page
                        raw_page_data = main.web_loader(url_input)
                        raw_content_str = main._build_content_str(raw_page_data)
                        st.info(f"📄 Page loaded ({len(raw_content_str):,} chars) — filtering job content...")
                        
                        # Detect block/captcha
                        is_blocked = False
                        if len(raw_content_str) < 500 or any(x in raw_content_str for x in ["Cloudflare", "Enable JavaScript", "Attention Required!", "Access Denied"]):
                            is_blocked = True
                            st.warning("⚠️ **Anti-Bot Protection Detected:** The website appears to have blocked our automatic scraper (very common for Indeed/LinkedIn). Please try running it again, or **copy and paste the raw job description text** into the text area for immediate results.")
                        
                        # Step 2: Use LLM to rephrase & organize the job content
                        # Extract keywords AND keep all info organized
                        rephrase_prompt = f"""
You are a job description rephrasing specialist. Below is the raw HTML/text scraped from a job posting website.

Your task: EXTRACT and ORGANIZE the job information into a clean structured description.

You MUST clearly identify and extract KEYWORDS for the following fields, ensuring you capture them fully:
- **Role/Job Title**: [extract the job role keyword explicitly]
- **Required Experience**: [extract the exact years of experience or seniority level keyword explicitly]
- **Required Skills**: [extract an exhaustive list of all technical, domain, and soft skill keywords]
- **Responsibilities**: [key duties]
- **Qualifications**: [education, certifications]
- **Job Description**: [full rephrased description incorporating all above keywords]

Rules:
1. Keep ALL job-relevant information - do not remove any helpful content.
2. EXPLICITLY EXTRACT AND LIST the KEYWORDS: role title, experience required, and skill set. Do not skip this step.
3. Format with clear labeled sections for easy parsing.
4. Remove only obvious navigation text like "Click here", "Subscribe", "Cookie settings".
5. Return ONLY the organized job description with ALL fields explicitly present.

RAW PAGE CONTENT:
{raw_content_str[:15000]}
"""
                        try:
                            rephrase_response = llm.invoke(rephrase_prompt)
                            if hasattr(rephrase_response, "content"):
                                rephrased_content = rephrase_response.content
                            else:
                                rephrased_content = str(rephrase_response)
                            if rephrased_content.strip() and len(rephrased_content.strip()) > 100:
                                page_content = rephrased_content
                                st.info(f"✅ Job content rephrased and organized ({len(rephrased_content):,} chars)")
                            else:
                                page_content = raw_content_str
                                st.info("⚠️ Using raw page content (rephrasing produced minimal output)")
                        except Exception:
                            page_content = raw_content_str
                            st.info("⚠️ Using raw page content (rephrasing step failed)")

                    job_json = main.jop_prompt(llm, page_content)

                    # Validate extracted job JSON
                    extracted_skills = job_json.get('skills') if isinstance(job_json, dict) else None
                    if extracted_skills is None:
                        extracted_skills = []
                    if isinstance(extracted_skills, str):
                        extracted_skills = [extracted_skills]

                    role_val = (job_json.get('role') or '').strip() if isinstance(job_json, dict) else ''
                    description_val = (job_json.get('description') or '').strip() if isinstance(job_json, dict) else ''

                    if not role_val and not description_val and not any(s.strip() for s in extracted_skills):
                        st.warning('The provided URL/text did not extract a valid job posting. Please provide a different job link or paste the job description text.')
                        st.session_state['job_json'] = job_json
                        st.session_state['page_content_raw'] = page_content
                        st.rerun()
                        return

                    # Use cached collection
                    collection = st.session_state.get("chroma_collection")
                    if collection is None:
                        collection = creat_db()
                        st.session_state["chroma_collection"] = collection
                    
                    results = main.apply_query(job_json, collection, w_vector, w_graph, top_k=top_k)
                    email_content = main.email_prompt(llm, job_json, results["hybrid"])

                    # Save to Query Cache
                    set_cached_query(query_key, {
                        "job_json": job_json,
                        "results": results,
                        "email_content": email_content,
                        "page_content_raw": page_content,
                        "role": role_val
                    })

                st.session_state["job_json"] = job_json
                st.session_state["results"] = results
                st.session_state["email_content"] = email_content
                st.session_state["page_content_raw"] = page_content

                st.rerun()
            except Exception as e:
                st.error(f"An error occurred during execution: {e}")
                st.exception(e)

    if "results" in st.session_state:
        results = st.session_state["results"]
        job_json = st.session_state["job_json"]
        email_content = st.session_state["email_content"]

        st.markdown("---")
        st.subheader("🎓 Course Recommendations")
        tab1, tab2, tab3, tab4 = st.tabs(["🏆 Hybrid Recommendations", "🔍 Vector Search (Chroma DB)", "🕸️ Graph Search (Neo4j)", "📊 Graph Visualization"])

        with tab1:
            st.markdown("### Combined Best Match Courses")
            hybrid_list = results["hybrid"]
            if not hybrid_list:
                st.warning("No recommendations found.")
            else:
                for course in hybrid_list[:8]:
                    st.markdown(
                        f"""
                        <div class="course-card">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                <h4 style="margin: 0; color: #fff;">{course['title']}</h4>
                                <span class="score-box" style="background: rgba(112, 0, 255, 0.2); color: #c4a1ff;">Hybrid Score: {course['combined_score']:.3f}</span>
                            </div>
                            <p style="margin: 0.2rem 0; font-size: 0.9rem;">Platform: <b>{course['platform']}</b> | Link: <a href="{course['url']}" target="_blank">{course['url']}</a></p>
                            <div style="margin-top: 0.5rem;">
                                <span class="score-box" style="font-size: 0.75rem;">Vector component: {course['vector_score']:.3f}</span>
                                <span class="score-box" style="font-size: 0.75rem;">Graph component: {course['graph_score']:.3f}</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    if course.get("matched_skills"):
                        st.markdown("Matched Skills:")
                        for skill in course["matched_skills"]:
                            st.markdown(f'<span class="badge badge-success">{skill}</span>', unsafe_allow_html=True)

        with tab2:
            st.markdown("### Raw Vector Search Matches")
            vector_list = results["vector"]
            if not vector_list:
                st.warning("No vector search matches.")
            else:
                for c in vector_list:
                    st.markdown(
                        f"""
                        <div class="course-card">
                            <h5 style="margin: 0; color: #eee;">{c['title']}</h5>
                            <p style="margin: 0.2rem 0; font-size: 0.85rem;">Platform: {c['platform']} | Link: <a href="{c['url']}" target="_blank">{c['url']}</a></p>
                            <span class="score-box" style="font-size: 0.75rem;">Vector Similarity: {c['v_score']:.3f} (Distance: {c['dist']:.3f})</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

        with tab3:
            st.markdown(f"### Raw Graph Search Matches ({results['provider']})")
            graph_list = results["graph"]
            if not graph_list:
                st.warning("No graph search matches. Add skills or set up Neo4j relationship graph.")
            else:
                for c in graph_list:
                    st.markdown(
                        f"""
                        <div class="course-card">
                            <h5 style="margin: 0; color: #eee;">{c['title']}</h5>
                            <p style="margin: 0.2rem 0; font-size: 0.85rem;">Platform: {c['platform']} | Link: <a href="{c['url']}" target="_blank">{c['url']}</a></p>
                            <span class="score-box" style="font-size: 0.75rem;">Normalized Graph Score: {c['g_score']:.3f} (Matches: {c['raw_g_score']})</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    if c.get("matched_skills"):
                        for skill in c["matched_skills"]:
                            st.markdown(f'<span class="badge badge-success">{skill}</span>', unsafe_allow_html=True)

        # Graph Visualization Tab with Mermaid.js
        with tab4:
            provider, provider_name = st.session_state["graph_provider"]
            display_graph_tab(provider, provider_name)

        st.markdown("---")
        st.subheader("✉️ Recommended Candidate Guidance Email")
        # Render email as markdown so links are clickable and formatted
        st.markdown(email_content)
        st.success("Candidate guidance email generated successfully based on hybrid recommendations!")
    
    # Display cached query suggestions below the main input
    if "results" not in st.session_state:
        display_cached_query_suggestions()

if __name__ == "__main__":
    create_streamlit_app()