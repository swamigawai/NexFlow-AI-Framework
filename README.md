## Architecture & Design

NexFlow is structured as a decoupled, multi-service system rather than a monolithic
script or a thin API wrapper over an LLM. The goal was to demonstrate how
individual components can evolve, be tested, and be replaced independently.

---

### System Overview

The system is composed of four loosely coupled layers:

| Layer | Responsibility |
|---|---|
| Frontend UI | Stateless presentation; renders responses and streams live backend logs |
| FastAPI Backend | Async routing, input validation, workflow triggering, log streaming |
| RAG Pipeline | Document ingestion, chunking, embedding, ChromaDB retrieval |
| Data Processing | Deterministic CSV transformations via Python + Pandas (no LLM dependency) |

Keeping the data processing layer completely isolated from the AI components
means structured transformations stay reproducible and independently testable —
a deliberate design choice, not an afterthought.

---

### 2. Agent Orchestration

NexFlow uses LangGraph for workflow orchestration rather than running a single
flat conversational loop.

**Separation of Concerns**
- One node handles conversational RAG Q&A
- A separate, isolated node handles deterministic structured parsing

**Context-Based Routing**
The workflow evaluates user intent and routes execution between nodes based on
explicitly defined conditions — not arbitrary branching.

**Structured Outputs**
Pydantic schemas enforce a fixed JSON structure on LLM outputs, enabling reliable
integration with external systems such as Jira or Salesforce. Validation guarantees
structure — not semantic perfection — and that distinction is intentional.

---

### 3. Deployment Model

The system is fully containerized to simulate production-style service isolation.

**Dockerized Backend**
FastAPI runs on a minimal `python:3.11-slim` base image to keep the container
footprint small.

**Multi-Container Setup**
The FastAPI backend and the Ollama model server run in separate containers,
fully independent of each other, managed via `docker-compose`.

**Environment Configuration**
Model endpoints, vector store paths, and network ports are all injected via
environment variables — no hardcoded values anywhere in the codebase.

> This setup demonstrates deployment awareness. It does not yet include
> production-grade monitoring, autoscaling policies, or authentication layers —
> those are the clear and honest next steps.

---

### 4. Cost & Data Considerations

**Local Inference**
By running Ollama and local embeddings (`all-MiniLM-L6-v2`), the framework
avoids all per-token API fees associated with external LLM providers.
Operational cost is limited to local compute — CPU/GPU, RAM, and electricity.

**Data Locality**
All documents and user interactions remain entirely within the local environment.

> Regulatory compliance (GDPR, HIPAA, etc.) depends on organizational policies,
> infrastructure security, access controls, and audit processes. This project does
> not independently guarantee regulatory compliance.

---

### 5. Scaling Pathways

The current build is optimized for local demonstration. The architecture is
designed with clear, low-friction pathways for future expansion.

**Vector Storage Migration**
The local ChromaDB instance can be swapped for a distributed vector database
(e.g., Pinecone, AWS OpenSearch) by updating the `VECTOR_STORE_DIR` in the
docker-compose environment config.

**Model Scaling**
Local inference speed is bound to host hardware. Supporting high-concurrency
environments would require:
- Multiple Ollama model server replicas
- A reverse proxy / load balancer in front of them
- Dedicated GPU infrastructure

**Data Processing Evolution**
The current Pandas pipeline runs in memory and handles moderate dataset sizes well.
For very large datasets (50 GB+), the data-worker node would need either
chunked processing or migration to a distributed framework such as Apache Spark.
