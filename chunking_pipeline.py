import json
import os
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

class Chunking_Langchain:
    def __init__(self, chunk_size:int, chunk_overlap:int):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap


    # Json laden und konvertierung funktionen:
    def load_and_convert_to_documents(self, filepath):
        if not os.path.exists(filepath):
            print(f"⚠️ Datei nicht gefunden: {filepath}")
            return []

        with open(filepath, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        documents = []

        for item in raw_data:
            # Wir extrahieren den Text für den page_content
            text = item.get("text", "")
            if not text:
                continue

            # Alles andere wird zu Metadaten, Wir erstellen eine Kopie des Dictionaries und löschen den Text heraus.
            metadata = item.copy()
            del metadata["text"]

            # LangChain Document erstellen
            doc = Document(page_content=text, metadata=metadata)
            documents.append(doc)

        print(f"✅ {len(documents)} Dokumente aus {os.path.basename(filepath)} geladen.")
        return documents


    # DIE HAUPT-PIPELINE
    def run_chunking_pipeline(self, metadaten:list):
        input_files = metadaten
        all_raw_documents = []

        # Alle JSON-Dateien einlesen und in LangChain-Dokumente umwandeln
        for file in input_files:
            docs = self.load_and_convert_to_documents(file)
            all_raw_documents.extend(docs)

        print(f"Insgesamt {len(all_raw_documents)} Roh-Dokumente im Speicher.")

        # RecursiveCharacterTextSplitter initialisieren:
        # Er versucht zuerst an doppelten Absätzen (\n\n) zu trennen, dann an (\n), dann an Punkten (.)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ".", " ", ""]
        )

        # Das eigentliche Chunking:
        chunked_documents = text_splitter.split_documents(all_raw_documents)

        print(f"Fertig! Aus {len(all_raw_documents)} Dokumenten wurden {len(chunked_documents)} Vektor-Chunks erstellt.")

        # den allerersten Chunk als Test ausdrucken, um die Struktur zu prüfen
        if chunked_documents:
            test_chunk = chunked_documents[0]
            print("\n🔍 TEST-ANSICHT DES ERSTEN CHUNKS:")
            print(f"Metadaten: {json.dumps(test_chunk.metadata, indent=2, ensure_ascii=False)}")
            print(f"Text-Ausschnitt: {test_chunk.page_content[:200]}...")

        return chunked_documents