import json
import os
from sentence_transformers import SentenceTransformer, CrossEncoder
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
HF_TOKEN = os.environ.get("HF_TOKEN")



# DATENABRUF (Data Retrieval)

# Zunächst erstellen wir die Dateien, um die Vector-Datenbank zu füttern.
# Um einen Gut-strukturierte Datenbank für einen Rechtsassistenten zu erstellen, brauchen wir drei quellen:
# Gesetzte, offizielle Urteile von Gerichtsverfahren und Ratgeber aus vertrauenswürdigen Quellen.

is_gesetze_file_ready = True
is_dsgvo_file_ready = True
is_urteil_file_ready = True
is_ratgeber_file_ready = True


# 1) Gesetze-Retrival
# hier, nutzen wir xml daten die ich aus gesetze-im-internet heruntergeladen habe:
# Für dieses Projekt werden wir die 34 am häufigsten angewandten Gesetzbücher heranziehen.

if not is_gesetze_file_ready:
    from retriever_gesetze import Gesetze_Retriever
    import glob
    DATA_DIR = "gesetze/"
    OUTPUT_JSON = "metadata/gesetze_database.json"
    alle_gesetze = []

    # Erstellt den Ordner, wenn es nicht bereits da ist:
    os.makedirs(DATA_DIR, exist_ok=True)

    # Sucht automatisch alle .xml Dateien im data-Ordner
    xml_dateien = glob.glob(f"{DATA_DIR}*.xml")

    # Lesen alle Gesetze ab:
    for xml_file in xml_dateien:
        gesetze_aus_datei = Gesetze_Retriever.parse_gesetz_xml(xml_file)
        alle_gesetze.extend(gesetze_aus_datei)  # Wir verwenden ".extend" für Iterationen.

    # Alles in eine große JSON speichern:
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(alle_gesetze, f, ensure_ascii=False, indent=4)
        print(f"Insgesamt {len(alle_gesetze)} Paragrafen/Artikel aus {len(xml_dateien)} Gesetzbüchern gespeichert.")


# 2) DSGVO-Retrival
# die Datenschutz-Grundverordnung (DSGVO) gehört der Europäischen Union, deswegen es is nicht in gesetze-im-internet.
# Für diesen Zweck werden wir website-scraping verwenden und die DAten aus dsgvo-gesetz.de abrufen.
if not is_dsgvo_file_ready:
    from retriever_dsgvo import DSGVO_Retriever
    OUTPUT_JSON_DSGVO = "data/dsgvo_parsed.json"
    OUTPUT_JSON_METADATA = "metadata/gesetze_database.json"

    # Die DSGVO-JSON-Daten abrufen:
    dsgvo_file = DSGVO_Retriever.scrape_dsgvo(OUTPUT_JSON_DSGVO)

    # Speichern DSGVO-JSON-Datei ab:
    os.makedirs(os.path.dirname(OUTPUT_JSON_DSGVO), exist_ok=True)
    with open(OUTPUT_JSON_DSGVO, "w", encoding="utf-8") as f:
        json.dump(dsgvo_file, f, ensure_ascii=False, indent=4)

    # Rufen die allgemeine Gesetze-Datei ab:
    with open(OUTPUT_JSON_METADATA, "r", encoding="utf-8") as f:
        master = json.load(f)

    # Erweitern die Gesetze-Datei um DSGVO:
    master.extend(dsgvo_file)

    # Speichern letztendliche Gesetze-Datei ab:
    with open(OUTPUT_JSON_METADATA, "w", encoding="utf-8") as f:
        json.dump(master, f, indent=4, ensure_ascii=False)


# 3) Gericht-Urteile-Retrival
# Wir werden Gerichtsurteile aus Openjur extrahieren, um unsere Datenbank zu erweitern.
# OpenJur ist eine gemeinnützige, freie juristische Datenbank.
# Sie bietet freien und unabhängigen Zugang zu mehr als 625.000 deutschen Gerichtsentscheidungen im Volltext.
# Ich habe 5 Api-Schlüssel aus Open-legal-gate geholt.

if not is_urteil_file_ready:
    from retriever_urteile import Urteile_Retriever
    # Es wird mehrere api keys dafür geben:
    my_api_keys = []

    for i in range(1, 5):
        API_KEY = os.getenv(f"OPEN_LEGAL_GATE_{i}")
        my_api_keys.append(API_KEY)

    url = "https://de.openlegaldata.io/api/cases/search/"

    Urteile_Retriever = Urteile_Retriever(my_api_keys, url)

    THEMEN_JSON = "json_files/themen_nach_gesetze.json"

    # Rufen die allgemeine themen-gesetze-datei ab:
    # Wir haben hier suchbegriffe spezifiziert für Gesetze und wir viele Urteile möchten wir dafür extrahieren.
    # z.b. : { "BGB": {"Mietrecht": 15, "Mietminderung": 5, ...}, ... }
    with open(THEMEN_JSON, "r", encoding="utf-8") as f:
        themen_nach_gesetze = json.load(f)

    # Abrufen alle Urteile:
    urteile_data = Urteile_Retriever.fetch_judgments(themen_nach_gesetze)

    # Zielpfad zum Speichern
    output_path = "metadata/urteile_database.json"

    # Speichern der bereinigten und deduplizierten Datenbasis
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(urteile_data, f, ensure_ascii=False, indent=4)


# 4) Offizielle Ratgeber-Retrival
# Wir werden Ratgeber, Mitteilungen, Warnungen oder ähnliches aus vertrauenswürdigen Quellen extrahieren.
# Dadurch werden die chatbot mehr über das Thema wissen.
# Wir diesen Zweck werden wir DuckDuckGo und trafilatura nutzen.

# DuckDuckGo: eine Bibliothek, mit der man Suchanfragen an die Suchmaschine sendet und Suchergebnisse (z. B. Webseiten, Bilder oder Nachrichten) programmgesteuert abruft.
# Trafilatura: eine Bibliothek, die den Hauptinhalt von Webseiten (z. B. Fließtext, Titel und Metadaten) automatisch extrahiert und dabei Werbung, Navigation und andere störende Elemente entfernt.

if not is_ratgeber_file_ready:
    from retriever_ratgeber import Ratgeber_Retriever
    INPUT_MASTER_JSON = "json_files/themen_nach_gesetze.json"
    OUTPUT_RATGEBER_JSON = "metadata/master_ratgeber_database.json"

    # Hier, definieren wir ca 4 webseite für jeden Suchbegriff.
    RECHTSGEBIET_QUELLEN = "json_files/rechtsgebiete_quellen.json"

    # Initialisieren den Retriever:
    Ratgeber_Retriever = Ratgeber_Retriever(RECHTSGEBIET_QUELLEN)

    # Durchsuchen, Filtern, Extrahieren und Speichern
    Ratgeber_Retriever.build_ratgeber_pipeline(INPUT_MASTER_JSON, OUTPUT_RATGEBER_JSON)


# jetzt, haben wir drei gut strukturierte Metadatendateien, die wir in die Vektordatenbank eingeben können.
# Gesetze, Urteile und Ratgeber



# Chunking:

is_chunking_ready = True
are_chunks_embedded = True

if not is_chunking_ready:
    from chunking_pipeline import Chunking_Langchain

    # Da 1 Token im Deutschen oft 3-4 Zeichen entspricht, nehmen wir 1200 Zeichen.
    # Der Overlap sorgt dafür, dass juristische Kontexte an den Schnittstellen nicht zerreißen.
    CHUNK_SIZE = 1200
    CHUNK_OVERLAP = 200

    # Chunking-Class initialisieren
    Chunking_Langchain = Chunking_Langchain(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    # Metadata:
    input_files = [
        "metadata/gesetze_database.json",
        "metadata/urteile_database.json",
        "metadata/ratgeber_database.json"
    ]

    # Alle Dokumente in Chunks unterteilen und ein Beispiel ausdrucken:
    final_chunks = Chunking_Langchain.run_chunking_pipeline(input_files)


INDEX_NAME = "german-legal-assistant-e5"

if not are_chunks_embedded:
    from chunks_embedding_pipeline import Chunks_Embedder

    EMBEDDING_DIMENSION = 768
    BATCH_SIZE = 100

    Chunks_Embedder = Chunks_Embedder(pinecone_api_key=PINECONE_API_KEY, hf_token=HF_TOKEN, index_name=INDEX_NAME,
                                      embedding_dimension=EMBEDDING_DIMENSION,batch_size=BATCH_SIZE)

    if not final_chunks:
        print("Keine Chunks generiert. Abbruch...")
    else:
        # Erstelle pinecone Datenbank:
        pinecone_index = Chunks_Embedder.setup_pinecone()
        # Lade alle generierten Chunks in Vector-Datenbank
        Chunks_Embedder.embed_and_upload(final_chunks, pinecone_index)




# Pinecone Retrival Pipeline
from pinecone_retrieval_pipeline import RetrievalPipeline

# Zentraler Cache für die Modelle im Backend
@st.cache_resource(show_spinner="⏳ Lade juristische Datenbank-Modelle ins Backend...")
def get_retrieval_models():
    """Lädt die Modelle genau einmal und hält sie für Streamlit im RAM."""
    e_model = SentenceTransformer("intfloat/multilingual-e5-base")
    r_model = CrossEncoder("cross-encoder/msmarco-MiniLM-L6-en-de-v1")
    return e_model, r_model

# Modelle global für diese Datei abrufen
embedder, reranker = get_retrieval_models()

RetrievalPipeline = RetrievalPipeline(PINECONE_API_KEY, HF_TOKEN, INDEX_NAME, embedder, reranker)




# LLM pipeline:
from llm_pipeline import LLMManager
from llm_query_expansion import Query_Expander

openai_api_key = os.getenv(f"OPENAI_API_KEY")
ai_model = "gpt-5.4-mini"
ai_model_query_expansion = "gpt-5.4-nano"

# Echter LLM manager:
LLMManager = LLMManager(api_key=openai_api_key, ai_model=ai_model)

# # LLM Manager für Anfrage-Erweiterung (Wir verwenden das, um genauer matches aus Vector-Datenbank zu erhalten)
# Query_Expander = Query_Expander(api_key=openai_api_key, ai_model=ai_model_query_expansion)



# App pipeline:
# hier, für die Geschwindigkeit der anwendung nutzen wir inheritance mit "app.py" nicht.
# Stattdessen stellen wir die manager classes zur app bereit
# Auf diese Weise können wir Funktionalität und Übersichtlichkeit gewährleisten, ohne dabei an Geschwindigkeit zu verlieren.

# Wir werden diese beiden funktionen in app.py implementieren.
def get_pinecone_manager():
    return RetrievalPipeline

def get_llm_manager():
    return LLMManager


# Jetzt, zur durchführung der App, reicht es im terminal zu schreiben:
# streamlit run app.py







