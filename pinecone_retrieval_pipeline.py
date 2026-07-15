from pinecone import Pinecone
from llm_query_expansion import Query_Expander
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime


class RetrievalPipeline:
    def __init__(self, pinecone_api_key, openai_api_key, hf_token, index_name, embedding_model, reranker):
        self.pinecone_api_key = pinecone_api_key
        self.pc = Pinecone(api_key=self.pinecone_api_key)
        self.hf_token = hf_token
        self.index_name = index_name
        self.index = self.pc.Index(self.index_name)
        self.openai_api_key = openai_api_key
        self.openai_client = OpenAI(api_key=self.openai_api_key)
        self.model = embedding_model
        self.reranker = reranker
        self.query_expander = Query_Expander()

    # die Retrival funktion
    def retrieve_matches(self, user_query, top_k_per_type=7, final_k_per_type=4):

        # Die Anfrage durch ki schlau erweitern damit bessere matches gefunden werden:
        llm_analysis = self.query_expander.expand_query(user_query)

        word_list = []

        try:
            for i in llm_analysis.expanded_keywords:
                word_list.append(i)

            explanation = f"Der Hauptpunkt diser Situation ist {word_list[0]}. Außerdem handelt es sich hier um {word_list[1]}, {word_list[2]}, {word_list[3]} und {word_list[4]}."

            # Wir kombinieren die rohe Nutzerfrage mit den Keywords des LLMs
            combined_search_text = f"{user_query} {explanation}"

            formatted_query = f"query: {combined_search_text}"

        except:
            formatted_query = f"query: {user_query}"

        # Den Vektor über die OpenAI API generieren
        response = self.openai_client.embeddings.create(
            input=formatted_query,
            model=self.model
        )

        # Den Vektor aus der Antwort extrahieren
        query_vector = response.data[0].embedding

        document_types = ["gesetz", "urteil", "ratgeber"]

        all_retrieved_docs = []

        for doc_type in document_types:
            # Basis-Filter für den Dokumententyp
            pinecone_filter = {"type": doc_type}

            # DYNAMISCHER TÜRSTEHER: Wir fügen die Rechtsgebiete hinzu, falls das LLM welche gefunden hat.
            raw_results = self.index.query(
                vector=query_vector,
                top_k=top_k_per_type,
                include_metadata=True,
                filter=pinecone_filter
            )

            for match in raw_results.matches:
                meta = match.metadata
                all_retrieved_docs.append({
                    "id": match.id,
                    "type": meta.get("type", doc_type),
                    "text": meta.get("text", ""),
                    "source": meta.get("source", "Unbekannt"),
                    "paragraph": meta.get("paragraph", ""),
                    "legal_area": meta.get("legal_area", "Allgemein"),
                    "related_laws": meta.get("related_laws", [""]),
                    "title": meta.get("title", ""),
                    "url": meta.get("url", ""),
                    "pinecone_score": match.score
                })

        if not all_retrieved_docs:
            return []


        # RERANKING:
        pairs = [[formatted_query, doc["text"]] for doc in all_retrieved_docs]

        rerank_scores = self.reranker.predict(pairs, batch_size=7, show_progress_bar=False)

        for i, doc in enumerate(all_retrieved_docs):
            doc["rerank_score"] = rerank_scores[i]

        # Alle Dokumente absteigend nach semantischer Relevanz sortieren:
        reranked_docs = sorted(all_retrieved_docs, key=lambda x: x["rerank_score"], reverse=True)

        # die besten ergebnisse auswählen:
        final_docs = []
        counts = {"gesetz": 0, "urteil": 0, "ratgeber": 0}

        # Kategoriespezifische Filtern:
        THRESHOLDS = {
            "ratgeber": -3.0,
            "urteil": -9.0,
            "gesetz": -8.0
        }

        for doc in reranked_docs:
            dt = doc["type"]

            # Wir prüfen das Dokument gegen den spezifischen Threshold seiner Kategorie
            if doc["rerank_score"] < THRESHOLDS[dt]:
                continue  # Dokument ist zu schlecht, überspringen

            if len(doc["text"]) < 150:
                continue # chunk ist zu kurz

            if counts[dt] < final_k_per_type:
                final_docs.append(doc)
                counts[dt] += 1

        # Wir sortieren die finalen 9 Dokumente logisch für das LLM:
        sort_order = {"gesetz": 1, "urteil": 2, "ratgeber": 3}
        final_docs_grouped = sorted(final_docs, key=lambda x: sort_order.get(x["type"], 4))

        return final_docs_grouped


    def build_llm_prompt(self, final_docs):
        count_list = []
        context_text = ""
        for i, doc in enumerate(final_docs):
            # Wir heben den Typen (GESETZ, URTEIL, RATGEBER) im Prompt optisch hervor
            if doc['type'].upper() == "GESETZ":
                if "GESETZ" not in count_list:
                    context_text +="Gesetze:\n"
                    count_list.append("GESETZ")
                # context_text += f"-> Pinecone Score: {doc['rerank_score']:>5.2f}\n"
                context_text += f"{doc['legal_area']:<5} | Source: {doc['source']} | Title: {doc['title']} | Paragraph: {doc['paragraph']}\n"
                context_text += f"Text: {doc['text']}\n\n"

            if doc['type'].upper() == "URTEIL":
                if "URTEIL" not in count_list:
                    context_text +="Urteile:\n"
                    count_list.append("URTEIL")
                # context_text += f"-> Pinecone Score: {doc['rerank_score']:>5.2f}\n"
                context_text += f"{doc['legal_area']:<5} | Source: {doc['source']} | Title: {doc['title']} | Related Laws: {doc['related_laws']}\n"
                context_text += f"Text:{doc['text']}\n\n"

            if doc['type'].upper() == "RATGEBER":
                if "RATGEBER" not in count_list:
                    context_text +="Ratgeber:\n"
                    count_list.append("RATGEBER")
                # context_text += f"-> Pinecone Score: {doc['rerank_score']:>5.2f}\n"
                context_text += f"{doc['legal_area']:<5} | Related Laws: {doc['related_laws']} | URL: {doc['url']}\n"
                context_text += f"Text:{doc['text']}\n\n"

        return context_text