# pyright: reportMissingImports=false
# pylint: disable=import-error

"""
FastAPI backend for TableRAG.

Uses the google-genai SDK directly (not langchain-google-genai) to preserve
thought_signatures in multi-turn tool calls. The raw Content objects returned
by the SDK include thought_signatures natively — appending them verbatim to
the conversation history solves the 400 error without any patching.

Run from project root:
    uvicorn src.api:app --reload --port 5000
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Optional, Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- PATH SETUP ---
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
os.environ["TQDM_DISABLE"] = "1"

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

import logging
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

# --- GOOGLE GENAI SDK (direct — preserves thought_signature) ---
from google import genai
from google.genai import types

# --- VECTOR STORE (langchain for FAISS only) ---
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.utilities import SQLDatabase

# --- CONFIGURATION ---
DB_PATH      = PROJECT_ROOT / "dataset" / "articles.db"
INDEX_DIR    = PROJECT_ROOT / "vector_store"
MODEL_NAME   = "all-MiniLM-L6-v2"
GEMINI_MODEL = "gemini-3.5-flash-lite"
MAX_RESULTS  = 20

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("Error: GOOGLE_API_KEY not set.")
    sys.exit(1)

client = genai.Client(api_key=api_key)

# --- RESOURCES ---
db = SQLDatabase.from_uri(f"sqlite:///{DB_PATH}")
embeddings = HuggingFaceEmbeddings(model_name=MODEL_NAME)
try:
    vectorstore = FAISS.load_local(str(INDEX_DIR), embeddings, allow_dangerous_deserialization=True)
except Exception as e:
    print(f"Warning: Could not load vector store: {e}")
    vectorstore = None


# --- TOOL IMPLEMENTATIONS ---
def _search_database(query: str = None, **kwargs) -> str:
    # Accept 'queries' (plural) in case the LLM uses the wrong key name
    q = query or kwargs.get("queries") or kwargs.get("sql")
    if not q:
        return "Error: 'query' argument is required and must be a valid SQL string."
    
    # HARD GUARD: Prevent LLM from bypassing vector search with SQL LIKE on content
    q_lower = q.lower()
    if "full_content" in q_lower and "like" in q_lower:
        return (
            "ERROR: You are strictly forbidden from using SQL LIKE on full_content. "
            "Stop using search_database for this query. If you already used search_articles "
            "and got results, use those results to answer. Do not try to search for more."
        )

    try:
        return db.run(q)
    except Exception as e:
        return f"Error executing SQL: {e}"


def _search_articles(
    query: str,
    filter_category: Optional[str] = None,
    filter_titles: Optional[List[str]] = None,
    filter_source: Optional[str] = None,
    filter_word_count: Optional[int] = None,
    filter_authors: Optional[str] = None,
    limit: int = 3,
) -> str:
    if not vectorstore:
        return "Vector store not initialized."
    if not query or not query.strip():
        return "Error: query is required for semantic search."
    try:
        effective_limit = min(limit, MAX_RESULTS)
        criteria = {}
        if filter_category:   criteria["article_category"] = filter_category
        if filter_source:     criteria["source"]           = filter_source
        if filter_word_count: criteria["word_count"]       = filter_word_count
        if filter_authors:    criteria["authors"]          = filter_authors

        requested_titles = set(filter_titles) if filter_titles else None

        def faiss_filter(metadata):
            if requested_titles and metadata.get("title") not in requested_titles:
                return False
            for key, val in criteria.items():
                doc_val = metadata.get(key)
                if not doc_val and doc_val != 0:
                    return False
                if str(val).lower() not in str(doc_val).lower():
                    return False
            return True

        found_docs = vectorstore.similarity_search(query, k=100, filter=faiss_filter)
        found_docs = found_docs[:effective_limit]

        if not found_docs:
            return "No documents found matching the criteria."

        lines = []
        for i, doc in enumerate(found_docs, 1):
            lines.append(f"--- Document {i} ---")
            lines.append(f"Source: {doc.metadata.get('source', 'N/A')}")
            lines.append(f"Title: {doc.metadata.get('title', 'N/A')}")
            lines.append(f"Category: {doc.metadata.get('article_category', 'N/A')}")
            lines.append(f"Date: {doc.metadata.get('published_date', 'N/A')}")
            preview = doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content
            lines.append(f"Content: {preview}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error during search: {e}"


TOOL_MAP = {
    "search_database": _search_database,
    "search_articles": _search_articles,
}

# --- TOOL DECLARATIONS FOR GENAI SDK ---
TOOLS = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="search_database",
        description=(
            "Useful for counting articles, finding min/max, or aggregating data by category or date. "
            "Input should be a valid SQL query for SQLite. "
            "DO NOT use this tool for text search. NEVER use LIKE on full_content. "
            "article_category values are LOWERCASE."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(type=types.Type.STRING, description="Valid SQLite SQL query"),
            },
            required=["query"],
        ),
    ),
    types.FunctionDeclaration(
        name="search_articles",
        description=(
            "Performs SEMANTIC SEARCH on article content. query parameter is REQUIRED. "
            "For metadata-only filtering use search_database. "
            "DO NOT use filter_date — use SQL for date filtering."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query":             types.Schema(type=types.Type.STRING,  description="REQUIRED semantic search query"),
                "filter_category":   types.Schema(type=types.Type.STRING,  description="Filter by article category"),
                "filter_titles":     types.Schema(type=types.Type.ARRAY,   items=types.Schema(type=types.Type.STRING), description="Titles to search within"),
                "filter_source":     types.Schema(type=types.Type.STRING,  description="Filter by source URL"),
                "filter_authors":    types.Schema(type=types.Type.STRING,  description="Filter by author name"),
                "filter_word_count": types.Schema(type=types.Type.INTEGER, description="Filter by exact word count"),
                "limit":             types.Schema(type=types.Type.INTEGER, description="Max results (default 3, max 20)"),
            },
            required=["query"],
        ),
    ),
])

# --- SYSTEM PROMPT (built from schema.json) ---
def build_system_prompt() -> str:
    schema_path = PROJECT_ROOT / "dataset" / "schema.json"
    try:
        with open(schema_path) as f:
            schema_raw = json.dumps(json.load(f), indent=2)
    except Exception:
        schema_raw = '{"articles": {"columns": ["url","title","authors","published_date","article_category","content_word_count","full_content"]}}'

    return f"""You are a helpful assistant. You have access to two tools:
  - `search_database`: runs SQL queries against a SQLite database of articles
  - `search_articles`: performs semantic search against a FAISS vector store of article content

The database schema is:
```json
{schema_raw}
```

### HOW TO CHOOSE A TOOL

**RULE 1 — Topic + optional category → always `search_articles` only.**
  `search_articles` has a `filter_category` parameter. Use it. Never use SQL just because a category is mentioned.
  - "science articles about black holes"   → `search_articles(query="black holes", filter_category="science")` ✅ NO SQL
  - "finance articles about inflation"     → `search_articles(query="inflation", filter_category="finance")` ✅ NO SQL
  - "cooking articles about pasta"         → `search_articles(query="pasta recipes", filter_category="cooking")` ✅ NO SQL
  - Calling `search_database` to retrieve titles for a category before doing vector search is FORBIDDEN.

**RULE 2 — Pure aggregation/listing (no topic) → `search_database` SQL only.**
  - "count the number of articles grouped by author"  → SQL ✅
  - "show me the publication dates for all articles"  → SQL ✅
  - "list all articles in category X"  → SQL ✅  (listing, no topical search)
  - "show me articles by author Y"     → SQL ✅  (author is a schema field, no topic)

**RULE 3 — Hybrid ONLY when the filter cannot be expressed in `search_articles` parameters.**
  The ONLY valid hybrid cases are:
  - **Date range** ("between Jan and June 2023") → SQL for matching titles → `search_articles(query=..., filter_titles=[...])`
  - **Author + topic** ("articles by author Y about topic Z") → SQL for author titles → vector search
  - **Word count range** ("short articles about topic Z") → SQL for titles within word count range → vector search
  A category is NEVER a reason for hybrid — use `filter_category` instead.

### STRICT RULES
- NEVER use SQL `LIKE` on the `full_content` column. It is strictly forbidden.
- NEVER call `search_database` to get titles for a category — always use `filter_category` in `search_articles`.
- ONE TOOL CALL IS ENOUGH: After any tool returns a result, generate the final response immediately. Do NOT make a second tool call to "enrich" or "supplement" the first result.
- Once `search_articles` returns results, stop. Do NOT call `search_database` again.
- Once `search_database` returns results, stop. Do NOT call any tool again.
- SQL `article_category` values must be lowercase.
"""


SYSTEM_PROMPT = build_system_prompt()


# --- PRESET QUERIES ---
PRESET_QUERIES = [
    {"id": 1,  "label": "Count by category",         "query": "How many articles are in each category?",                                       "strategy": "aggregation"},
    {"id": 2,  "label": "By year & category",         "query": "What are the articles by year and category?",                                   "strategy": "aggregation"},
    {"id": 3,  "label": "List sports articles",       "query": "List all sports articles.",                                                     "strategy": "sql"},
    {"id": 4,  "label": "Articles by Reuters",        "query": "Show me articles by Reuters.",                                                  "strategy": "sql"},
    {"id": 5,  "label": "Electric vehicles",          "query": "What do articles say about electric vehicles?",                                 "strategy": "semantic"},
    {"id": 6,  "label": "Articles about children",    "query": "What articles about children do you have?",                                     "strategy": "semantic"},
    {"id": 7,  "label": "Fashion trends",             "query": "What are the trends in fashion?",                                              "strategy": "semantic"},
    {"id": 8,  "label": "Stocks & inflation",          "query": "In business articles between 500 and 700 words, which ones discuss stocks or inflation?",      "strategy": "hybrid"},
    {"id": 9,  "label": "Cancer & Chemotherapy",      "query": "What do health articles say about cancer and chemotherapy?",                  "strategy": "semantic"},
    {"id": 10, "label": "Tech crypto 2023",           "query": "Tell me technology articles about crypto in 2023.",                            "strategy": "hybrid"},
]


# --- CORE QUERY FUNCTION ---
def run_query_structured(q: str) -> Dict[str, Any]:
    """
    Runs a ReAct-style tool-calling loop using the raw google-genai SDK.
    The full Content objects (including thought_signatures) are appended
    verbatim to the conversation — the SDK handles signature preservation.
    """
    contents: List[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=q)])
    ]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[TOOLS],
    )

    steps = []
    tools_used: set = set()
    final_text = ""

    for _ in range(10):  # safety cap on turns
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )

        model_content = response.candidates[0].content

        # Append full raw Content — thought_signatures preserved automatically
        contents.append(model_content)

        function_calls = [p for p in model_content.parts if p.function_call]

        if not function_calls:
            # Final text response
            final_text = "".join(
                p.text for p in model_content.parts
                if hasattr(p, "text") and p.text
            )
            break

        # Execute each tool call and collect results
        tool_result_parts = []
        for part in function_calls:
            fc = part.function_call
            tool_name = fc.name
            tool_args = dict(fc.args) if fc.args else {}
            tools_used.add(tool_name)

            steps.append({"type": "tool_call", "tool": tool_name, "args": tool_args})

            tool_fn = TOOL_MAP.get(tool_name)
            if tool_fn:
                try:
                    result = tool_fn(**tool_args)
                except TypeError as e:
                    result = f"Error calling tool: {e}"
            else:
                result = f"Unknown tool: {tool_name}"

            steps.append({
                "type":   "tool_result",
                "tool":   tool_name,
                "output": result[:500] + "..." if len(result) > 500 else result,
            })

            tool_result_parts.append(types.Part(
                function_response=types.FunctionResponse(
                    id=fc.id,
                    name=tool_name,
                    response={"result": result},
                )
            ))

        contents.append(types.Content(role="user", parts=tool_result_parts))

    has_sql    = "search_database" in tools_used
    has_vector = "search_articles" in tools_used
    if has_sql and has_vector:
        tool_path = "hybrid"
        classification = "Hybrid (SQL + Semantic Search)"
    elif has_sql:
        tool_path = "sql"
        classification = "Database / SQL Query"
    elif has_vector:
        tool_path = "vector"
        classification = "Semantic Search"
    else:
        tool_path = "none"
        classification = "No tools used"

    # Prepend classification as the first trace entry
    steps.insert(0, {"type": "classification", "label": f"Query classified as: {classification}"})

    return {"response": final_text, "tool_path": tool_path, "steps": steps}


# --- FASTAPI APP ---
app = FastAPI(title="TableRAG API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str

@app.get("/api/queries")
def get_preset_queries():
    return {"queries": PRESET_QUERIES}

@app.post("/api/query")
def query_endpoint(req: QueryRequest):
    q = req.query.strip()
    if not q:
        return {"error": "Query cannot be empty."}
    try:
        return run_query_structured(q)
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=5000, reload=True,
                app_dir=str(Path(__file__).parent))
