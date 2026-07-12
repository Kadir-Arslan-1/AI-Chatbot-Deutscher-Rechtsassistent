from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import re


class Chunks_Embedder:
    def __init__(self, pinecone_api_key: str, hf_token: str, index_name: str, embedding_dimension: int, batch_size: int):
        self.pinecone_api_key = pinecone_api_key
        self.hf_token = hf_token
        self.index_name = index_name
        self.embedding_dimension = embedding_dimension
        self.batch_size = batch_size

    def setup_pinecone(self):
        print("Verbinde mit Pinecone...")
        pc = Pinecone(api_key=self.pinecone_api_key)

        if self.INDEX_NAME not in pc.list_indexes().names():
            print(f"Erstelle neuen Index '{self.index_name}' (Dimensionen: {self.embedding_dimension})...")
            pc.create_index(
                name=self.index_name,
                dimension=self.embedding_dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
        else:
            print(f"Index '{self.index_name}' existiert bereits.")

        return pc.Index(self.index_name)


    def sanitize_id(self, raw_id):
        # Macht aus deutschen Strings ASCII-IDs
        if not isinstance(raw_id, str):
            raw_id = str(raw_id)

        replacements = {
            'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'Ä': 'Ae',
            'Ö': 'Oe', 'Ü': 'Ue', 'ß': 'ss'
        }
        for search, replace in replacements.items():
            raw_id = raw_id.replace(search, replace)

        # Entfernt alles, was kein Buchstabe, Zahl, Unterstrich oder Bindestrich ist
        raw_id = re.sub(r'[^a-zA-Z0-9_-]', '', raw_id)
        return raw_id



    # Embedding - laden funktion
    def embed_and_upload(self, chunked_documents, index):

        model = SentenceTransformer("intfloat/multilingual-e5-base")

        total_chunks = len(chunked_documents)

        print(f"Starte Embedding und Upload für {total_chunks} Chunks...\n")

        for i in tqdm(range(0, total_chunks, self.batch_size), desc="Batch Upload"):
            batch_docs = chunked_documents[i: i + self.batch_size]

            # Wir müssen dieses "Passage" Präfix hinzufügen, damit das Modell erkennt, dass es einen Datenbankeintrag speichert.
            formatted_texts_for_ai = [f"passage: {doc.page_content}" for doc in batch_docs]

            ids = [f"{self.sanitize_id(doc.metadata.get('id', 'doc'))}_chunk_{i+j}" for j, doc in enumerate(batch_docs)]

            metadatas = []

            for doc in batch_docs:
                meta = doc.metadata.copy()
                # Wir speichern den ORIGINAL-Text (ohne „passage:“ ) in den Metadaten, damit LLM reines deutsches Recht liest.
                meta["text"] = doc.page_content
                metadatas.append(meta)

            # Erzeuge die embeddings anhand der mit prefixed texts
            embeddings = model.encode(formatted_texts_for_ai, convert_to_numpy=True).tolist()

            vectors_to_upsert = list(zip(ids, embeddings, metadatas))

            index.upsert(vectors=vectors_to_upsert)