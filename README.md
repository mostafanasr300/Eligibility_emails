# AI Course Recommendation System (Hybrid RAG)

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
* **How it Ranks:** It uses LLM embeddings to calculate the cosine similarity (Vector Score) between the job description and the course description.

**Neo4j (Knowledge Graph)**
* **The Problem it Solves:** "Hard Requirements." If a job strictly requires "Vue.js", semantic search might accidentally recommend a "React" course because they are similar. Neo4j acts as a hard filter. It traverses relationships (`COURSE` -> `TEACHES` -> `SKILL`) to find exact matches.
* **How it Ranks:** It calculates a Graph Score based on how many explicit skills from the job description are structurally linked to the course in the database.

**The Solution:** The Hybrid Score blends these together. A course only gets a top rank if it semantically matches the job *and* explicitly teaches the required skills.

## External Data & CI/CD Architecture

The application relies on `Data&relation.txt` as its source of truth. When the application starts, it reads this file, structures it, and hydrates both Neo4j and ChromaDB.

**The CI/CD Flow (GitHub Actions + Render):**
1. **Validation:** On every push, GitHub Actions runs Pytest (Unit/Integration tests), Flake8 (Linting), and Bandit (Security Scanning) utilizing external keys via GitHub Secrets.
2. **Containerization:** The code is packaged into a Docker Image and pushed to the GitHub Container Registry (GHCR).
3. **Deployment:** GitHub Actions pings a Render Deploy Webhook. Render pulls the latest image and spins up the container.
4. **Persistence:** The production container mounts a Persistent Disk to `./chroma_db`. The Smart Cache and ChromaDB data live here, surviving all deployments and saving massive amounts of compute time.

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

4. **Run the Container (with Persistent Volume):**
   ```bash
   docker run -p 8502:8502 --env-file .env -v ${PWD}/chroma_db:/app/chroma_db hybrid-rag-app
   ```
   *Note: The `-v` flag maps the database and cache to your local hard drive so your data survives container restarts!*

5. **Access the App:** Open your browser and navigate to `http://localhost:8502`.

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
