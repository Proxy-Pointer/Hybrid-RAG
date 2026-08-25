# pyright: reportMissingImports=false
# pylint: disable=import-error

import pandas as pd
import os
from pathlib import Path
from sqlalchemy import create_engine, text
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

# --- PATH SETUP ---
PROJECT_ROOT = Path(__file__).parent.parent
INPUT_FILE   = PROJECT_ROOT / "dataset" / "articles_curated.xlsx"
DB_PATH      = PROJECT_ROOT / "dataset" / "articles.db"
INDEX_DIR    = PROJECT_ROOT / "vector_store"
MODEL_NAME   = "all-MiniLM-L6-v2"

def setup_resources():
    print("Step 1: Setting up SQLite Database...")
    try:
        df = pd.read_excel(INPUT_FILE)
        print(f"Loaded {len(df)} rows from Excel.")
        
        # Standardize published_date to ISO 8601 (YYYY-MM-DD HH:MM:SS)
        if 'published_date' in df.columns:
            df['published_date'] = pd.to_datetime(df['published_date']).dt.strftime('%Y-%m-%d %H:%M:%S')
            print("Standardized 'published_date' to ISO 8601.")
        
        engine = create_engine(f'sqlite:///{DB_PATH}')
        df.to_sql('articles', engine, if_exists='replace', index=False)
        print(f"Database created at {DB_PATH}. Table 'articles' populated.")
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT count(*) FROM articles"))
            count = result.fetchone()[0]
            print(f"Verified: SELECT count(*) -> {count}")
            
    except Exception as e:
        print(f"Error setting up database: {e}")
        return

    print("\nStep 2: Creating FAISS Index from Database...")
    try:
        engine = create_engine(f'sqlite:///{DB_PATH}')
        df_sql = pd.read_sql('SELECT * FROM articles', engine)
        print(f"Read {len(df_sql)} rows from SQL for indexing.")
        
        documents = []
        for idx, row in df_sql.iterrows():
            content = str(row['full_content']).strip()
            if not content:
                continue
                
            metadata = {
                "source": row.get('url', ''),
                "title": row.get('title', ''),
                "authors": str(row.get('authors', '')),
                "article_category": str(row.get('article_category', 'unknown')),
                "published_date": str(row.get('published_date', '')),
                "word_count": int(row.get('content_word_count', 0))
            }
            
            doc = Document(page_content=content, metadata=metadata)
            documents.append(doc)

        print(f"Prepared {len(documents)} documents for embedding.")
        
        print(f"Initializing embeddings ({MODEL_NAME})...")
        embeddings = HuggingFaceEmbeddings(model_name=MODEL_NAME)
        
        print("Building FAISS index...")
        vectorstore = FAISS.from_documents(documents, embeddings)
        
        INDEX_DIR.mkdir(exist_ok=True)
        print(f"Saving index to {INDEX_DIR}...")
        vectorstore.save_local(str(INDEX_DIR))
        print("Index saved successfully.")
        
    except Exception as e:
        print(f"Error creating index: {e}")

if __name__ == "__main__":
    setup_resources()
