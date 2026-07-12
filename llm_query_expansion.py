import os
import json
from pydantic import BaseModel, Field
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()


#  PYDANTIC SCHEMA DEFINIEREN
class QueryExpansionResult(BaseModel):
    expanded_keywords: list = Field(
        description="Eine liste von 3 juristische Fachbegriffe, Synonyme und abstrakte Konzepte zur Nutzerfrage."
    )


class Query_Expander:
    def __init__(self):
        self.api_key = os.getenv(f"OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-5.4-nano"

    # DIE EXPANSION FUNKTION
    def expand_query(self, user_query: str) -> QueryExpansionResult:

        system_prompt = """
        Du bist ein brillanter deutscher Fachanwalt. 
        Deine Aufgabe ist es, die umgangssprachliche Frage eines Nutzers in präzise juristische Fachbegriffe zu übersetzen.
        Antworte sehr schnell.
    
        KONTEXT ZUR AUFGABE:
        Wir nutzen deine Ausgabe, um eine semantische Vektordatenbank (Embeddings) zu durchsuchen. 
        Daher ist "Semantic Anchoring" überlebenswichtig: Wenn du nur allgemeine Begriffe wie "Mangel" oder "Minderung" nennst, findet die Datenbank womöglich Dokumente aus dem Kaufrecht, obwohl der Nutzer ein Problem mit Schimmel in der Wohnung (Mietrecht) hat. 
    
        GEHE WIE FOLGT VOR:
        1. Der ALLERERSTE Begriff in deiner Liste MUSS zwingend das übergeordnete Rechtsgebiet sein (z.B. "Mietrecht", "Arbeitsrecht", "Urheberrecht").
        2. Überlege dann, wie die Konzepte der Frage in formellen deutschen Gesetzen und Urteilen genannt werden (Beispiel: "Homeoffice" wird im Gesetz "mobile Arbeit" genannt. "Kaution" wird "Mietsicherheit" genannt).
        3. Beschränke dich auf exakt 5 hochrelevante Begriffe. Zu viele Begriffe verwässern den Vektor und führen zu falschen Treffern.
    
        WICHTIG: Du musst AUSSCHLIESSLICH ein valides JSON-Objekt zurückgeben. 
        Verwende zwingend exakt diese Struktur:
        Eine json objekt die nur eine liste "expanded_keywords" enthält. Und diese liste "expanded_keywords" enthält 5 Relevante juristische Fachbegriffe.
        {
            "expanded_keywords": [
                "Übergeordnetes Rechtsgebiet (z.B. Mietrecht)",
                "Fachbegriff 1",
                "Fachbegriff 2",
                "Fachbegriff 3",
                "Fachbegriff 4"
            ]
        }
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Nutzerfrage: {user_query}"}
                ],
                response_format={"type": "json_object"},  # Zwingt das LLM zu JSON
                temperature=0.1  # Sehr niedrig, damit es präzise bleibt
            )

            # Antwort auslesen und in das Pydantic-Modell pressen
            raw_json = response.choices[0].message.content
            data_dict = json.loads(raw_json)

            result = QueryExpansionResult(**data_dict)

            return result

        except Exception as e:
            print(f"LLM Expansion fehlgeschlagen: {e}.")
            return QueryExpansionResult(
                expanded_keywords=["","","","",""],
            )