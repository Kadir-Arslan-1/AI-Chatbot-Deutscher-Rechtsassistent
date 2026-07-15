import re
import time
from tqdm import tqdm
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI, RateLimitError


class Chunks_Embedder:
    def __init__(self, pinecone_api_key: str, openai_api_key: str, index_name: str, embedding_model):

        self.pinecone_api_key = pinecone_api_key
        self.openai_api_key = openai_api_key
        self.openai_client = OpenAI(api_key=self.openai_api_key)
        self.index_name = index_name
        self.model = embedding_model

        # text-embedding-3-large modell:
        self.embedding_dimension = 3072

        # Um openai limits einzuhalten werden wir 100 chunks pro anfrage abrufen:
        self.batch_size = 100

    def setup_pinecone(self):
        print("Connecting to Pinecone...")
        pc = Pinecone(api_key=self.pinecone_api_key)

        if self.index_name not in pc.list_indexes().names():
            print(f"Erstellen neue index '{self.index_name}'...")
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
            print(f"Index '{self.index_name}' already exists.")

        return pc.Index(self.index_name)

    def sanitize_id(self, raw_id):
        if not isinstance(raw_id, str):
            raw_id = str(raw_id)

        replacements = {
            'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'Ä': 'Ae',
            'Ö': 'Oe', 'Ü': 'Ue', 'ß': 'ss'
        }
        for search, replace in replacements.items():
            raw_id = raw_id.replace(search, replace)

        raw_id = re.sub(r'[^a-zA-Z0-9_-]', '', raw_id)
        return raw_id

    def embed_and_upload(self, chunked_documents, index):
        total_chunks = len(chunked_documents)
        print(f"Beginnen mit embedding und laden mit {total_chunks} chunks...\n")

        for i in tqdm(range(0, total_chunks, self.batch_size), desc="Batch Upload"):
            batch_docs = chunked_documents[i: i + self.batch_size]

            texts = [doc.page_content for doc in batch_docs]

            ids = [f"{self.sanitize_id(doc.metadata.get('id', 'doc'))}_chunk_{i + j}" for j, doc in
                   enumerate(batch_docs)]

            metadatas = []

            for doc in batch_docs:
                meta = doc.metadata.copy()
                meta["text"] = doc.page_content
                metadatas.append(meta)

            # Error Handling:
            max_retries = 5

            for attempt in range(max_retries):
                try:
                    response = self.openai_client.embeddings.create(
                        input=texts,
                        model= self.model
                    )

                    # Die 3072-dimensionalen Zahlenvektoren aus der API-Antwort extrahieren
                    embeddings = [data.embedding for data in response.data]

                    # Paket erstellen und direkt auf Pinecone hochladen
                    vectors_to_upsert = list(zip(ids, embeddings, metadatas))

                    index.upsert(vectors=vectors_to_upsert)
                    break

                except RateLimitError:
                    print(f"\nRatenlimit erreicht. Warten 60 Sekunden... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(60)
                except Exception as e:
                    print(f"\n[!] Unerwartete error: {e}")
                    time.sleep(5)