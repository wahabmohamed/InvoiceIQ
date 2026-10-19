import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    CHROMA_HOST: str = os.getenv("CHROMA_HOST", "localhost")
    CHROMA_PORT: int = int(os.getenv("CHROMA_PORT", "8001"))
    # Collection versionnee : changer de modele d'embedding ou de metrique impose
    # une nouvelle collection (les anciens vecteurs ne sont pas comparables).
    CHROMA_COLLECTION: str = os.getenv("CHROMA_COLLECTION", "invoices_e5_cosine")

    # Modele multilingue (les factures et les questions sont en francais).
    # all-MiniLM-L6-v2 est entraine quasi uniquement sur de l'anglais.
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")

    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "database/invoiceiq.db")

    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "data/uploads")

    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))

    # RAG
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))
    # Similarite cosinus minimale pour qu'un chunk soit envoye au LLM / affiche comme source
    RAG_MIN_SCORE: float = float(os.getenv("RAG_MIN_SCORE", "0.75"))
    # Nombre max de lignes du tableau structure injecte dans le prompt du chat
    RAG_MAX_TABLE_ROWS: int = int(os.getenv("RAG_MAX_TABLE_ROWS", "200"))

    # Extraction : budget de caracteres envoyes au LLM (debut + fin du document)
    EXTRACTION_MAX_CHARS: int = int(os.getenv("EXTRACTION_MAX_CHARS", "12000"))
    # Tolerance (en unite monetaire) pour le controle HT + TVA = TTC
    AMOUNT_TOLERANCE: float = float(os.getenv("AMOUNT_TOLERANCE", "0.02"))

    ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


settings = Settings()
