from openai import OpenAI
from openai import APIError
import os
from pydantic_model import BotResponse
from pydantic import ValidationError


def load_text_file(filename: str):
    filepath = os.path.join(os.path.dirname(__file__), filename)
    try:
        with open(filepath, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        print(f"⚠️ Error: {filename} was not found.")
        return ""


# The class for our AI logic
class LLMManager:
    def __init__(self, api_key: str, ai_model=str):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key)
        self.model = ai_model
        # For the prompt Engineering:
        self.few_shot_examples = load_text_file("prompts/few_shot_examples.txt")
        self.system_prompt = load_text_file("prompts/system_prompt.txt")
        self.instructions = load_text_file("prompts/instructions.txt")


    def generate_response(self, user_question: str, context_text: str, is_first_message:True) -> BotResponse:
        # Diese Funktion übernimmt die Frage des Benutzers und den Kontext aus Pinecone,
        # leitet diese anschließend an OpenAI weiter und gibt ein validiertes Pydantic-Objekt zurück.

        if is_first_message:
            greeting_rule = (
                "STRUKTURVORGABE: Beginne die Antwort zwingend mit einer kurzen, freundlichen Begrüßung "
                "(z.B. 'Guten Tag!') und 2-3 einleitenden Sätzen zum Thema. Erst danach folgt '### TEIL 1: ...'."
            )
        else:
            greeting_rule = (
                "STRUKTURVORGABE: Dies ist eine laufende Konversation. Verzichte auf Grußformeln "
                "(kein 'Hallo', kein 'Guten Tag'). Starte direkt mit 2-3 fließenden Übergangssätzen zum neuen Thema, "
                "bevor du mit '### TEIL 1: ...' beginnst."
            )

        # STATISCHER SYSTEM-PROMPT (Perfekt für OpenAI Caching)
        system_prompt = f"""
            {self.system_prompt}

            INSTRUCTIONS:
            {self.instructions}

            FEW SHOT EXAMPLES:
            {self.few_shot_examples}

            {greeting_rule}
            """

        # DYNAMISCHER USER-PROMPT
        user_prompt = f"""
            CONTEXT FROM THE METADATA:
            {context_text}

            USER QUESTION:
            {user_question}
            """


        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=BotResponse,  # Enforces strict adherence to your Pydantic model
                temperature=0.2  # A low temperature is highly recommended for strict legal facts
            )

            # OpenAI automatically validates the JSON and returns the populated Pydantic object
            validated_bot_response = response.choices[0].message.parsed

            return validated_bot_response

        except Exception as e:
            print(f"❌ OpenAI API Error: {e}")
            # Gib ein Fallback-Objekt zurück, damit die Streamlit-App nicht komplett abstürzt
            return BotResponse(
                explanation="Entschuldigung, es gab einen Fehler bei der Verbindung zum Sprachmodell.",
                cited_laws=[],
                is_information_missing=True
            )


        except APIError as e:
            if e.code in [429, 500, 502, 503, 504]:
                print(f"⚠️ Openai Server ausgelastet (Code {e.code}).")
            else:
                print(f"❌ Fataler API Fehler: {e}")


        except ValidationError as e:
                # Das LLM hat kein sauberes JSON geliefert. Sofort abbrechen!
                print(f"❌ Pydantic Parsing Fehler: {e}")


        except Exception as e:
                print(f"❌ Unerwarteter Python Fehler: {e}")


    def ask_question(self, question, pinecone_manager, is_first_message):
        # Den Input säubern für die Prüfung
        clean_input = question.strip().lower()

        # Smalltalk-Filter: (Der Türsteher)
        # Liste mit typischen kurzen Begrüßungen und Verabschiedungen
        greetings = ["hallo", "hi", "hey", "heyy", "heyy", "servus", "moin", "moin moin", "guten tag", "guten morgen", "guten mittag", "guten abend", "grüß gott", "grüss gott", "grüezi", "nabend", "tach", "hallöchen", "huhu", "jo", "yo", "hola"]
        verabschiebungen = ["tschüss", "tschau", "ciao", "bye", "bye bye", "bis dann", "bis später", "bis bald", "auf wiedersehen", "mach's gut", "machs gut", "schönen tag", "schönen abend", "gute nacht", "wir sehen uns", "bis zum nächsten mal"]
        danken = ["danke", "danke dir", "danke schön", "dankeschön", "vielen dank", "besten dank", "tausend dank", "lieben dank", "herzlichen dank", "merci", "thx", "thanks",]

        # Wenn das Wort in der Liste ist ODER die Frage extrem kurz ist (z.B. unter 15 Zeichen)
        if clean_input in greetings or len(clean_input) < 15:

            # Wir bauen eine direkte, freundliche Antwort ohne KI-Kosten
            if clean_input in greetings:
                antwort_text = "Guten Tag! Ich bin Ihr juristischer KI-Assistent. Wie kann ich Ihnen heute bei einer rechtlichen Frage weiterhelfen?"
            elif clean_input in danken:
                antwort_text = "Sehr gerne! Wenn Sie weitere juristische Fragen haben, bin ich jederzeit für Sie da."
            elif clean_input in verabschiebungen:
                antwort_text = "Bitte Schön!\nWenn Sie noch weitere Fragen haben, zögern Sie bitte nicht, mich anzusprechen.\nIch wünsche Ihnen einen schönen Tag. 💞"
            else:
                antwort_text = "Entschuldigung, ich habe die Frage nicht verstanden.\n Ich bin Ihr juristischer KI-Assistent und Sie können mir jede Frage zum deutschen Rechtssystem stellen."

            # Wir geben ein simuliertes BotResponse-Objekt zurück, damit app.py nicht abstürzt!
            return BotResponse(
                explanation=antwort_text,
                cited_laws=[],  # Keine Gesetze zitiert
                is_information_missing=False
            )

        # Durchführung einer echten Vektorsuche in Pinecone:
        pinecone_output = pinecone_manager.retrieve_matches(question)

        # Erhalten den fertiggestellten context text von Pinecone:
        finaler_prompt = pinecone_manager.build_llm_prompt(pinecone_output)

        # Passing the context and question to Openai
        try:
            response = self.generate_response(user_question=question, context_text=finaler_prompt, is_first_message=is_first_message)
            return response

        except Exception as e:
            if response is None:
                print(
                    "Entschuldigung, die KI-Server sind derzeit überlastet. Bitte versuchen Sie es später noch einmal.")
            else:
                print(response.explanation)




