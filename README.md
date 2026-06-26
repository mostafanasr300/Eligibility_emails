# AI Course Recommendation System (Hybrid RAG)

> 🎯 **Scope:** This system is exclusively focused on **Software Engineering & Technology courses**. It is purpose-built to match SWE job descriptions with the most relevant tech courses across domains including Backend Development, Cloud Engineering, Data Engineering, Machine Learning, AI Engineering, Cybersecurity, Mobile Development, and more. Non-tech courses are out of scope by design.

A powerful, Hybrid Retrieval-Augmented Generation (RAG) system designed to analyze job descriptions and recommend the most relevant educational courses. By blending semantic vector search with strict knowledge graph relationships, the application provides unparalleled accuracy in bridging the gap between required job skills and available educational content.

## Value Proposition

Traditional search engines often fail to understand the nuance of job requirements, either relying too heavily on keyword matching or missing hard requirements. This application solves that by combining two state-of-the-art technologies:
1. **Understanding Meaning:** Finding courses that match the overall *theme* and *semantic context* of a job description.
2. **Understanding Relationships:** Verifying that a course *explicitly* teaches the exact skills (e.g., Python, React) required by the role.

This ensures learners do not waste time on irrelevant courses, and hiring managers can accurately assess educational pathways for their teams.

## Core Features and What They Deliver

### 1. Hybrid RAG (Retrieval-Augmented Generation)
* **What it delivers:** Combines the flexibility of vector embeddings with the precision of a graph database to rank and recommend courses. It calculates a "Combined Score" to ensure the best of both worlds.

### 2. Streamlit User Interface
* **What it delivers:** A clean, interactive web frontend. Users can paste a job description directly into the UI, adjust the weighting between the Graph and Vector databases, and instantly see visual course recommendations and skill trees.

### 3. Smart Caching System
* **What it delivers:** Eliminates long startup times. By hashing the source data files, the application caches both the Vector and Graph states. If the container restarts, it loads instantly. It only rebuilds the database if the underlying data files change.

### 4. Automated CI/CD Pipeline
* **What it delivers:** Enterprise-grade automation. Every push to the main branch is automatically linted, security scanned, tested, built into a Docker container, and deployed seamlessly to production.

## How ChromaDB and Neo4j Solve Different Problems

The ranking system is the core of this application. It works by querying two completely different types of databases and merging their results:

**ChromaDB (Vector Database)**
* **The Problem it Solves:** "Semantic Search." If a job asks for a "Frontend Web Developer," ChromaDB understands that a course on "HTML/CSS and UI Design" is highly relevant, even if the exact keywords don't match. It understands the *meaning* of the text.
* **The Advantage of ChromaDB:** Unlike cloud-hosted enterprise vector databases (Pinecone, Weaviate) which require expensive API calls and constant internet connectivity, ChromaDB is lightweight, runs fully local, and operates in-memory/on-disk via SQLite. It is lightning fast, zero-configuration, completely free, and bakes perfectly into our Docker container for a standalone deployment.
* **How it Ranks:** It uses LLM embeddings to calculate the cosine similarity (Vector Score) between the job description and the course description. The score scales based on absolute vector proximity.

**Neo4j (Knowledge Graph)**
* **The Problem it Solves:** "Hard Requirements." If a job strictly requires "Vue.js", semantic search might accidentally recommend a "React" course because they are similar. Neo4j acts as a hard filter. It traverses relationships (`COURSE` -> `TEACHES` -> `SKILL`) to find exact matches.
* **How it Ranks:** It calculates a Graph Score based on how many explicit skills from the job description are structurally linked to the course in the database.

**The Solution: The Hybrid Score**
The Hybrid Score elegantly blends these approaches. 
* **Course Score Calculation:** The final recommendation isn't just a list—it's mathematically weighted. By adjusting the slider in the UI, you control how much the Vector Score (Semantic) and Graph Score (Exact Match) contribute.
* **Formula:** `Final Score = (Vector Score * Vector Weight) + (Graph Score * Graph Weight)`. This ensures a course only gets a top rank if it semantically aligns with the job *and* explicitly teaches the required tools.

### The Role of the AI (LLM) and Tool Usage
Our system doesn't just pass strings to a database. It utilizes a Large Language Model (like Llama 3 via Groq) acting as a smart orchestrator:
1. **Information Extraction (Scraping & Parsing):** The LLM takes a raw HTML job posting url and structurally dissects it. It navigates anti-bot protections, extracts the true intent of the posting, and isolates explicit constraints (e.g. Years of Experience, Role Title).
2. **Entity Recognition:** It actively distills paragraphs of text into exact "Skill" nodes (e.g. converting "experience with modern js frameworks" into specific entities like `React`, `Vue`, `Angular`).
3. **Query Orchestration:** The LLM builds the actual search parameters used against both ChromaDB and Neo4j, taking unstructured human text and turning it into machine-readable query criteria to fetch the ultimate recommendations.

### Visualizing the Knowledge Graph
To help you understand exactly *why* a course was recommended, the application features a built-in interactive visualizer. 

[Explore the Interactive Knowledge Graph](file:///c:/Users/mosta/Python_Projects/langchin_emails/graph_vis.html)

This interactive map allows you to explore the Neo4j database directly from the web app. You can see how specific courses (purple nodes) branch out and connect to the underlying skills, frameworks, and languages (green nodes) they teach. This provides full transparency into the AI's decision-making process.

### Important: Hugging Face Secrets
When deploying to Hugging Face Spaces, the environment variables (`GROQ_API_KEY`, `NEO4J_URI`, etc.) from your local `.env` file are not copied automatically. You **must** add these to your Hugging Face Space manually:
1. Go to your Space on Hugging Face.
2. Click **Settings** > **Variables and secrets**.
3. Add your `GROQ_API_KEY`, `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD` as New Secrets.

## External Data & CI/CD Architecture

The application relies on `Data&relation.txt` as its source of truth. When the application starts, it reads this file, structures it, and hydrates both Neo4j and ChromaDB.

**The CI/CD Flow (GitHub Actions + Hugging Face Spaces):**
1. **Validation:** On every push, GitHub Actions runs Pytest (Unit/Integration tests), Flake8 (Linting), and Bandit (Security Scanning) utilizing external keys via GitHub Secrets.
2. **Containerization:** The code is packaged into a Docker Image and pushed to the GitHub Container Registry (GHCR).
3. **Deployment (Git-based Sync):** Instead of using the HF REST API, GitHub Actions clones your HF Space repository using your `HF_TOKEN`, makes an empty commit, and pushes it. This triggers the Hugging Face build pipeline to pull the latest image from GHCR and deploy it — making the sync 100% reliable and immune to API permission errors.
4. **Data Persistence:** The local `chroma_db` is committed to the repository and baked directly into the Docker image. Because Hugging Face Spaces provides free ephemeral hosting, any new data added at runtime is reset upon restart, but the baked-in database is always preserved!

> **Required GitHub Secrets:** `GROQ_API_KEY`, `HF_TOKEN` (HF write-access token), `HF_SPACE` (format: `username/space-name`), `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`.

---

## How to Install and Run

### Option 1: Running with Docker (Recommended)

Running with Docker ensures you have the exact same environment as production.

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd <your-repo-name>
   ```

2. **Configure Environment Variables:**
   Create a `.env` file in the root directory and add your API keys:
   ```env
   GROQ_API_KEY=your_groq_key
   NEO4J_URI=bolt://localhost:7687  # Or your Neo4j Aura URI
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   ```

3. **Build the Docker Image:**
   ```bash
   docker build -t hybrid-rag-app .
   ```

4. **Run the Container Locally:**
   The `Dockerfile` exposes port `7860` because that is strictly required by Hugging Face Spaces. To access it locally on `8502`, map the ports like this:
   ```bash
   docker run -p 8502:7860 --env-file .env -v ${PWD}/chroma_db:/app/chroma_db hybrid-rag-app
   ```
   *Note: The `-v` flag maps the database and cache to your local hard drive so your data survives container restarts!*

5. **Access the App:** Open your browser and navigate to `http://localhost:8502`.

### Deploying to Hugging Face Spaces
Hugging Face Spaces natively routes traffic to Docker containers on port `7860`. When you deploy your GHCR image to Hugging Face, it will automatically detect the exposed `7860` port and serve your application to the public for free!

### Option 2: Running Locally (Python VENV)

1. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Streamlit application:**
   ```bash
   streamlit run app.py
   ```
