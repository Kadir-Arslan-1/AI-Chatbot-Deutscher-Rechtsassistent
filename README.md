# ⚖️ KI-gestützter Deutscher Rechtsassistent

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Streamlit](https://img.shields.io/badge/Streamlit-%23FE4B4B.svg?style=for-the-badge&logo=streamlit&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-%23412991.svg?style=for-the-badge&logo=openai&logoColor=white)
![Pinecone](https://img.shields.io/badge/Pinecone-000000.svg?style=for-the-badge&logo=pinecone&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C.svg?style=for-the-badge&logo=langchain&logoColor=white)

Willkommen in meinem Repository!  

Dieses Projekt ist ein intelligenter Chatbot, der auf Basis von RAG (Retrieval-Augmented Generation) komplexe juristische Fragen zum deutschen Recht beantworten kann. 

## Der Chatbot:
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://kadir-arslan-deutsches-recht.streamlit.app/)


## Über mich
Hi, ich bin **Kadir Arslan**, Informatik-Student an der TU Dortmund.  

Mich faszinieren Software Engineering, Data Science und der Bau von praktischen KI-Lösungen.  
Es macht mir großen Spaß, konkrete Lösungen für Probleme zu entwickeln, die den Menschen helfen können.

## Das Ziel des Projekts
Dieses Projekt wurde entwickelt, um zu zeigen, wie man unstrukturierte juristische Texte (Gesetze, Urteile und Ratgeber) so verarbeitet, dass ein Large Language Model (LLM) damit verlässliche und präzise Antworten generieren kann.  

Das Ziel war es, einen Chatbot zu bauen, der nicht einfach nur rät, sondern sich streng an echte deutsche Gesetzestexte hält und nicht ins Straucheln gerät, wenn er nach konkreten Paragrafen gefragt wird.

## Kernfunktionen und Systemarchitektur

Die Architektur des Projekts besteht aus mehreren wichtigen Schritten, die ich hier kurz erkläre:

### 1. Datenbeschaffung (Web-Scraping & APIs)
Ein LLM ist nur so gut wie seine Daten. Deshalb habe ich eine dreischichtige Datenbank aufgebaut:
* **Gesetze (`gesetze_database.json`):** Ich habe die XML-Dateien von 34 wichtigen Gesetzbüchern (wie BGB, GG) direkt von *Gesetze im Internet* heruntergeladen und einen eigenen XML-Scraper dafür geschrieben. Da die DSGVO dort nicht als XML verfügbar war, habe ich diese per Web-Scraping ergänzt.
* **Gerichtsurteile (`urteile_database.json`):** Über die API von *Open Legal Data* habe ich rund 3.000 relevante Urteile aus openJUR abgerufen. Diese wurden gezielt nach Rechtsgebieten und speziellen Suchbegriffen (Topic Tags) gefiltert.
* **Ratgeber (`ratgeber_database.json`):** Für verständliche Erklärungen habe ich DuckDuckGo-Suchen automatisiert, um etwa vier vertrauenswürdige juristische Webseiten pro Rechtsgebiet zu durchsuchen. Mit `trafilatura` habe ich dann saubere Texte ohne Werbung extrahiert und Duplikate sauber herausgefiltert.

Alle Daten wurden ordentlich strukturiert (ID, Typ, Rechtsgebiet, Quelle, Paragraph, Text).

### 2. Chunking & Embeddings
Damit die KI die Texte durchsuchen kann, mussten sie in kleine Stücke (Chunks) zerteilt werden:
* **Chunking (`chunking_pipeline.py`):** Hier kam **LangChain** ins Spiel. Mit dem `RecursiveCharacterTextSplitter` habe ich die Texte in Blöcke von 1200 Zeichen mit einem Overlap von 200 Zeichen aufgeteilt, damit keine wichtigen Sätze zerrissen werden.
* **Embeddings (`chunks_embedding_pipeline.py`):** Diese Chunks wurden dann mit dem Modell `text-embedding-3-large` von OpenAI in mathematische Vektoren umgewandelt und in die Vektordatenbank **Pinecone** hochgeladen.

### 3. Retrieval Pipeline (Die Suchmaschine)
Wenn ein Nutzer eine Frage stellt, passiert im Hintergrund (`pinecone_retrieval_pipeline.py`) folgendes:
* **Query Expansion:** Ein kleines, schnelles LLM (`gpt-5.4-mini`) formuliert die Frage des Nutzers blitzschnell in 5 juristische Suchbegriffe um.
* **Vektorsuche:** Pinecone sucht nach den besten Chunks. Dabei nutze ich Metadaten-Filter (z.B. um gezielt nach Gesetzen oder Urteilen zu filtern).
* **Reranking:** Da die Vektorsuche nicht immer perfekt ist, schicke ich die gefundenen Treffer durch einen Cross-Encoder (`msmarco-MiniLM-L6-en-de-v1`). Dieses Modell vergleicht die Chunks noch einmal sehr genau mit der Frage und sortiert sie nach Relevanz.

### 4. LLM Pipeline & Frontend
* **Generierung (`llm_pipeline.py`):** Die besten Text-Chunks werden zusammen mit der Frage an die OpenAI API (`gpt-5.4`) gesendet. Wichtig ist hier: Durch strenge System-Prompts verbiete ich dem Modell, sich für schlechte Suchtreffer zu rechtfertigen.
* **Pydantic:** Damit das System nicht abstürzt und die Antworten gut strukturiert sind, zwinge ich die KI mit `Pydantic` dazu, immer ein fest definiertes Format (`BotResponse`) zurückzugeben.
* **Das Interface (`app.py` & `main.py`):** Das Frontend ist mit **Streamlit** gebaut. Die Reranker- und Embedder-Modelle werden direkt beim Start gecached (`@st.cache_resource`), damit die App performant und flüssig bleibt.

## 💻 Tech Stack
* **Sprache:** Python
* **Frontend:** Streamlit
* **AI & NLP:** OpenAI API, LangChain, Text-Embedding, SentenceTransformers, Cross-Encoder, 
* **Datenbank:** Pinecone (Vector DB)
* **Scraping & Daten:** XML-Parsing, Trafilatura, DuckDuckGo-Search, Pydantic

## Live Demo
Try the bot live here:  
**[KI-gestützter Deutscher Rechtsassistent](https://kadir-arslan-deutsches-recht.streamlit.app/)**