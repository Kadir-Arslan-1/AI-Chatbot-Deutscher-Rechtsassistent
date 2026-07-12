import json
import time
import os
from urllib.parse import urlparse
import trafilatura
from ddgs import DDGS
import re
from collections import Counter


# Hier, definieren wir ca 4 webseite für jeden Suchbegriff.
class Ratgeber_Retriever:
    def __init__(self, rechtsgebiet_quellen:str):
        self.rechtsgebiete = rechtsgebiet_quellen

        with open(self.rechtsgebiete, "r", encoding="utf-8") as f:
            self.Rechtsgebiet_Quellen = json.load(f)


    # Wir werden gleiche Suchbegriffe wie Urteil-Retriever verwenden aber wir werden die Anzahl der Anfrage nue einrichten.
    # Wir brauchen ein bisschen weniger ratgeber als Urteile.
    def beratung_mapping(self, x:int):
        if x >= 10:
            return 3
        elif x >= 5:
            return 2
        else:
            return 1

    # Qualität-Kontrolle des Textes:
    def ratgeber_quality_check(self, url, text):
        url_lower = url.lower()
        text_lower = text.lower()

        # Wir werden die Seite die diese wörter enthalten, nicht abrufen.

        bad_url_words = ["veranstaltung", "seminar", "termin", "termine" "publikation", "broschuere", "presse", "news", "meldung",
                         "kalender", "shop", "medienangebot", "kategorie", "forum.bfdi.bund.de", ".pdf"]

        bad_text_phrases = ["herzliche einladung", "anmeldung unter", "veranstaltungsort:", "termin:", "uhrzeit:", "stehempfang", "anmeldeschluss"]

        if any(bad_word in url_lower for bad_word in bad_url_words):
            return False

        if any(phrase in text_lower for phrase in bad_text_phrases):
            return False

        # Gewünschte text-länge:
        if len(text) < 3500 or len(text) > 32000:
            return False

        # Ein echter Text mit > 800 Zeichen hat mindestens 5-10 Sätze (Punkte).
        if text.count('.') < 5:
            return False

        # Der Listen-Check (Mega-Menü Erkennung) (Zählt, wie viele Zeilen mit einem Bindestrich (Trafilatura-Liste))
        lines = text.split('\n')
        list_items = sum(1 for line in lines if line.strip().startswith('-'))

        # Wenn mehr als 50% des Textes nur aus Listen/Stichpunkten besteht, wirf ihn weg
        if len(lines) > 0:
            ratio = list_items / len(lines)
            if ratio > 0.50:
                return False

        # Wenn die Seite alle tests besteht:
        return True


    # Extraktions-funktion:
    def fetch_ratgeber(self, gesetz, thema, seen_urls, urteil_num:int):

        trusted_list = self.Rechtsgebiet_Quellen.get(gesetz, self.Rechtsgebiet_Quellen["DEFAULT"])

        site_filter = " OR ".join([f"site:{domain}" for domain in trusted_list])

        such_zusatz = "Erklärung"

        search_query = f'{thema} {such_zusatz} ({site_filter})'

        while True:
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(search_query, region='wt-wt', safesearch='off', max_results=20))

                    ziel = self.beratung_mapping(urteil_num)

                    beratung_num = 0

                    if not results:
                        print(f"Keine Ergebnisse für '{thema}'.")
                        return False

                    for result in results:
                        url = result.get("href")
                        title = result.get("title")

                        if beratung_num == ziel:
                            break

                        # Duplikate überspringen:
                        # Wenn wir mit aktuellem Suchbegriff zu einem Duplikat führen, fügen wir diesen Begriff auch zur früheren Anfrage hinzu.
                        if url in seen_urls:
                            if thema not in seen_urls[url]["topic_tags"]:
                                seen_urls[url]["topic_tags"].append(thema)
                            continue

                        # Wenn URL neu ist, laden wir sie herunter
                        downloaded = trafilatura.fetch_url(url)

                        if downloaded:
                            extracted_text = trafilatura.extract(downloaded, include_links=False, include_images=False)

                            if extracted_text:
                                if self.ratgeber_quality_check(thema, url, extracted_text):

                                    gesetze = (r'GG|BGB|StGB|ZPO|ArbZG|KSchG|BetrVG|AGG|DSGVO|BDSG|DDG|UrhG|BSIG|GeschGehG'
                                               r'|GewO|HGB|GmbHG|OWiG|AktG|AufenthG|AufenthV|WoGG|FreizügG/EU|AO|EStG'
                                               r'|StVO|BAföG|SGB\s+[IVX]+|SGB\s+\d+|SGB')

                                    gesetz_muster = r'(?:§|Art\.?)\s*\d+[a-z]*.*?(?:%s)' % gesetze

                                    gefundene_gesetze_raw = re.findall(gesetz_muster, extracted_text)

                                    saubere_gesetze = []

                                    for fund in gefundene_gesetze_raw:
                                        sauberer_fund = " ".join(fund.split())
                                        if len(sauberer_fund) < 30:
                                            saubere_gesetze.append(sauberer_fund)

                                    # Zählt, wie oft jedes Gesetz im Urteil zitiert wird
                                    gesetz_counter = Counter(saubere_gesetze)

                                    # Extrahiert die Top 3 Gesetze (die echten Schwerpunkte des Urteils)
                                    affected_laws = [gesetz for gesetz, anzahl in gesetz_counter.most_common(3)]

                                    beratung_num += 1

                                    domain = urlparse(url).netloc

                                    dokument = {
                                        "id": f"ratgeber_{domain.replace('www.', '').replace('.', '_')}_{hash(thema) % 10000}",
                                        "type": "ratgeber",
                                        "legal_area": gesetz,
                                        "topic_tags": [thema],
                                        "related_laws": affected_laws,
                                        "source": domain,
                                        "url": url,
                                        "title": title,
                                        "text": "\n".join([line for line in extracted_text.split('\n') if line.strip() != ''])
                                    }

                                    # Im Dictionary abspeichern:
                                    seen_urls[url] = dokument


                    break

            except Exception as e:
                print(f"❌ Such-Fehler bei '{thema}': {e}")
                print("warten 5 sekunden...")
                time.sleep(5)


    # haupt-pipeline:
    def build_ratgeber_pipeline(self, master_json_path, output_path):

        if not os.path.exists(master_json_path):
            print(f"Fehler: '{master_json_path}' nicht gefunden.")
            return

        with open(master_json_path, "r", encoding="utf-8") as f:
            master_topics = json.load(f)

        # Das Dictionary, das alle bisher gefundenen URLs speichert
        seen_urls = {}

        for gesetz, themen_dict in master_topics.items():
            for thema, urteil_num in themen_dict.items():
                # Wir übergeben seen_urls an die Funktion
                self.fetch_ratgeber(gesetz, thema, seen_urls, urteil_num)
                time.sleep(2)

        # Am Ende wandeln wir die Werte des Dictionaries in eine saubere Liste um
        finale_daten = list(seen_urls.values())

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(finale_daten, f, ensure_ascii=False, indent=4)

        print(f"✅ Pipeline beendet! {len(finale_daten)} Ratgeber wurden in '{output_path}' gespeichert.")