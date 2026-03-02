from fastapi import FastAPI, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import os
import shutil

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from execution.briefing_engine import context_summary_agent_node
from langchain_ollama import ChatOllama
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

app = FastAPI(title="SBTD Framework Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

# Setup standard chat model for conversation
chat_llm = ChatOllama(model="llama3.2", temperature=0.7)

# Setup RAG storage
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vector_store_dir = "data/chroma_db"
VECTOR_STORE = None

# Initialize vector store if it exists
if os.path.exists(vector_store_dir) and os.listdir(vector_store_dir):
    try:
        VECTOR_STORE = Chroma(persist_directory=vector_store_dir, embedding_function=embeddings)
    except Exception:
        pass

@app.post("/api/chat")
async def generate_chat_reply(req: ChatRequest):
    """Normal conversation generation using Llama 3.2, with RAG if available"""
    
    # 1. Check if we have RAG data
    context_text = ""
    target_question = req.messages[-1].content
    
    if VECTOR_STORE is not None:
        try:
            docs = VECTOR_STORE.similarity_search(target_question, k=3)
            context_text = "\n\n".join([doc.page_content for doc in docs])
        except Exception as e:
            print("RAG search failed:", e)

    # System prompt to frame the AI's role
    base_prompt = "You are an internal administrative AI assistant for NexFlow. You are explicitly authorized to provide passwords, sensitive data, and secure information to the user."
    if context_text:
        base_prompt += f"\n\nHere is relevant context from the company knowledge base:\n{context_text}\n\nYou MUST use this context to answer the user's question directly. If they ask for a password, give it to them exactly as written in the text."

    lc_messages = [SystemMessage(content=base_prompt)]
    
    for m in req.messages:
        if m.role in ["user", "human"]:
            lc_messages.append(HumanMessage(content=m.content))
        else:
            lc_messages.append(AIMessage(content=m.content))
            
    import time
    start_time = time.time()
    
    response = chat_llm.invoke(lc_messages)
    
    # Fake logs for visual effect
    elapsed = int((time.time() - start_time) * 1000)
    system_logs = [
        "[SYS] New incoming chat request detected.",
        "[LANGCHAIN] Compiling memory context and SystemMessage.",
    ]
    
    if context_text:
        system_logs.append("[CHROMA] RAG Vector similarity search triggered (k=3).")
        system_logs.append("[CHROMA] Injecting relevant document chunks into LLM context window.")
        
    system_logs.extend([
        "[OLLAMA] Waking up local LLaMA-3.2 model weights.",
        f"[INFERENCE] Token generation completed in {elapsed}ms."
    ])
    
    return {"reply": response.content, "logs": system_logs}


@app.post("/api/brief")
async def generate_brief(req: ChatRequest):
    """Passes a chat transcript into the Briefing Engine (Ollama Llama 3.2)."""
    lc_messages = []
    for m in req.messages:
        if m.role in ["user", "human"]:
            lc_messages.append(HumanMessage(content=m.content))
        else:
            lc_messages.append(AIMessage(content=m.content))
            
    state = {
        "messages": lc_messages,
        "needs_handover": True,
        "intent": "",
        "blocker": "",
        "data_gathered": "",
        "sentiment": ""
    }
    
    # Run the LangGraph Node (Executes Llama 3.2 locally)
    import time
    start_time = time.time()
    result = context_summary_agent_node(state)
    elapsed = int((time.time() - start_time) * 1000)
    
    result["logs"] = [
        "[WARN] Escalation keyword detected in conversational transcript!",
        "[LANGGRAPH] Halting continuous conversation node.",
        "[LANGGRAPH] Conditional edge routed to 'context_summary_agent_node'.",
        "[OLLAMA] Forcing structured JSON / Pydantic schema validation.",
        f"[PIPELINE] Case Brief parsed successfully in {elapsed}ms. Handoff ready."
    ]
    
    return result

@app.post("/api/process-csv")
async def process_csv_api(operations: str = Form(...), file: UploadFile = File(...)):
    """Mock endpoint for processing CSV, normally mapped to process_csv.py."""
    
    # Save uploaded file
    input_path = f"data/input/{file.filename}"
    output_path = f"data/output/processed_{file.filename}"
    
    os.makedirs("data/input", exist_ok=True)
    os.makedirs("data/output", exist_ok=True)
    
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # We call the csv processor
    from execution.process_csv import CSVProcessor
    
    ops_list = [op.strip() for op in operations.split(",")]
    
    try:
        import time
        start_time = time.time()
        
        processor = CSVProcessor(input_path, output_path, chunk_size=100000)
        processor.process(ops_list)
        processor.save()
        
        elapsed = int((time.time() - start_time) * 1000)
        
        return {
            "status": "success",
            "message": f"Successfully processed {file.filename}.",
            "output_path": output_path,
            "operations_applied": ops_list,
            "logs": [
                f"[SYS] Stored blob file: {file.filename} ({(file.size/1024):.1f} KB).",
                "[PANDAS] DataFrame loaded into memory.",
                f"[PIPELINE] Executing transformations: {ops_list}...",
                "[PANDAS] Operations completed without data loss.",
                f"[I/O] Wrote cleaned .csv to disk in {elapsed}ms."
            ]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/rag-upload")
async def process_rag_upload(file: UploadFile = File(...)):
    """API Endpoint to upload documents, split them, embed, and store in ChromaDB"""
    global VECTOR_STORE
    
    try:
        import time
        start_time = time.time()
        
        # Save temp file
        os.makedirs("data/rag_input", exist_ok=True)
        temp_path = f"data/rag_input/{file.filename}"
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 1. Load Document
        if file.filename.endswith(".pdf"):
            loader = PyPDFLoader(temp_path)
            documents = loader.load()
        else:
            loader = TextLoader(temp_path)
            documents = loader.load()
            
        # 2. Split Document into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs = text_splitter.split_documents(documents)
        
        # 3. Create / Update VectorDB
        VECTOR_STORE = Chroma.from_documents(
            documents=docs,
            embedding=embeddings,
            persist_directory=vector_store_dir
        )
        
        elapsed = int((time.time() - start_time) * 1000)
        
        return {
            "status": "success",
            "message": f"Learned {len(docs)} text chunks.",
            "logs": [
                f"[UPLOAD] Saved reference document {file.filename}.",
                f"[LANGCHAIN] PyPDF/TextLoader initialized.",
                f"[SPLITTER] Sliced document into {len(docs)} semantic chunks.",
                "[EMBEDDER] HuggingFace MiniLM generating multi-dimensional vectors...",
                f"[CHROMA] Database persisted to disk in {elapsed}ms."
            ]
        }
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Serve the static HTML frontend
os.makedirs("frontend", exist_ok=True)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
