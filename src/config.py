import os

# Storage Directory Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHROMA_DB_DIR = os.path.join(BASE_DIR, "chroma_db")
DATA_DIR = os.path.join(BASE_DIR, "data")
TRANSCRIPTS_DIR = os.path.join(DATA_DIR, "transcripts")
PROJECT_STATES_DIR = os.path.join(DATA_DIR, "project_states")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")

# Ensure required directories exist
for path in [CHROMA_DB_DIR, DATA_DIR, TRANSCRIPTS_DIR, PROJECT_STATES_DIR, UPLOADS_DIR]:
    os.makedirs(path, exist_ok=True)

# Default Model Configurations
LLM_MODEL_NAME = "gemini-2.5-flash"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = 0.65
COLLECTION_NAME = "snow_wiki_knowledge"
