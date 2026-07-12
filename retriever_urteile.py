import requests
import time
import re
from bs4 import BeautifulSoup
import html
from collections import Counter



class Urteile_Retriever:
    def __init__(self, api_keys: list[str], url:str):
        self.api_keys = api_keys
        self.url = url
        self.current_key_index = 0
        self.current_api_key = self.api_keys[self.current_key_index]
        self.headers = {
            "Authorization": f"Token {self.current_api_key}",
            "Accept": "application/json"
        }

    def switch_to_next_key(self):
        self.current_key_index += 1

        if self.current_key_index >= len(self.api_keys):
            raise Exception("ALLE API-Schlüssel haben ihr Ratenlimit erreicht!")

        print("-" * 100)
        print("\nWeiter zum nächsten Schlüssel...")


    def fetch_judgments(self, gesetze_themen: dict):
        urteile_data = []
        id_law = {}

        for law, area in gesetze_themen.items():
            print(f"\nDas Gesetz: '{law}'...")
            law_count = 0

            for query, urteil_number in area.items():
                case_count = 0
                print(f"\nSuche für: '{query}'...")

                # Die Quote, die wir aus unserer JSON-Struktur auslesen werden
                # Urteil nummer is die Zahl wie viele Urteile pro Suchbegriffe möchten wir extrahieren.
                ziel_quote = urteil_number

                while True:
                    params = {
                        "text": query,
                        "order_by": "most_cited",   # Damit erhalten wir die Fälle von höchster Qualität.
                        "start_date": "2015-01-01", # kein veralteter Fall.
                        "page_size":60
                    }

                    # Schritt 1: Die Suchanfrage:
                    response = requests.get(self.url, headers=self.headers, params=params)

                    if response.status_code == 200:
                        results = response.json().get('results', [])

                        # Wir schneiden die Liste exakt auf unsere Wunsch-Quote ab!
                        erfolgreiche_urteile = 0

                        for case in results:
                            if erfolgreiche_urteile >= ziel_quote:
                                break
                            case_id = case.get('id')
                            if not case_id:
                                continue

                            doc_id = f"urteil_{str(case_id)}"

                            # Wir prüfen, ob das Urteil bereits aus einer früheren Suche in unserer Liste vorhanden ist.
                            existing_doc = next((d for d in urteile_data if d['id'] == doc_id), None)

                            if existing_doc:
                                # Wenn das Urteil bereits vorliegt, fügen wir den Suchbegriff zu den topic_tags hinzu.
                                if query not in existing_doc['topic_tags']:
                                    if law == id_law[doc_id]:
                                        existing_doc['topic_tags'].append(query)
                                    continue
                                continue

                            # Schritt 2: Der Detail-Abruf
                            detail_url = f"https://de.openlegaldata.io/api/cases/{case_id}/"
                            detail_response = requests.get(detail_url, headers=self.headers)

                            anzahl_error_429 = 0

                            if detail_response.status_code == 200:
                                detail_data = detail_response.json()

                                # Harte Kategorie auslesen: (Gerichtsbarkeit)
                                gerichtsbarkeit = detail_data.get('court_jurisdiction') or 'Ordentliche Gerichtsbarkeit'

                                # Gerichtsnamen speichern:
                                court_info = detail_data.get('court')
                                if isinstance(court_info, dict):
                                    gericht = court_info.get('name', 'Gericht')
                                else:
                                    slug = detail_data.get('slug', '')
                                    gericht = slug.split('-')[0].upper() if slug else "Gericht"

                                aktenzeichen = detail_data.get('file_number') or detail_data.get('slug', 'Kein Az.')
                                datum = detail_data.get('date', 'Kein Datum')
                                text = detail_data.get('content')

                                if text:
                                    # HTML-Entities decodieren (Macht aus &#228; wieder ein "ä")
                                    text_unescaped = html.unescape(text)

                                    # entfernen alle html-Tags: (separator sorgt dafür, dass Wörter nicht zusammenkleben)
                                    soup = BeautifulSoup(text_unescaped, 'html.parser')
                                    raw_clean_text = soup.get_text(separator=" ", strip=True)

                                    # Doppelte Leerzeichen und kaputte Umbrüche entfernen
                                    clean_text = " ".join(raw_clean_text.split())

                                    # Wir prüfen, ob JEDES Kernwort aus der Suche mindestens 2-mal vorkommt
                                    such_woerter = [w.lower() for w in query.split()]   # Manchmal enthalten Suchbegriffe mehr als ein wort.
                                    text_lower = clean_text.lower()
                                    is_relevant = True

                                    for wort in such_woerter:
                                        if text_lower.count(wort) < 3:
                                            is_relevant = False
                                            break

                                    # Wenn der Fall nicht relevant ist, bricht diesen Durchlauf ab und geht zum nächsten Urteil
                                    if not is_relevant:
                                        continue

                                    # Bereinigung von extrem langen Texten:
                                    if len(clean_text) > 3000:
                                        clean_text = clean_text[:3000] + "... [Text gekürzt für RAG]"

                                    # Betroffene Gesetze per Regex extrahieren:
                                    gesetze = (r'GG|BGB|StGB|ZPO|ArbZG|KSchG|BetrVG|AGG|DSGVO|BDSG|DDG|UrhG|BSIG|GeschGehG'
                                               r'|GewO|HGB|GmbHG|OWiG|AktG|AufenthG|AufenthV|WoGG|FreizügG/EU|AO|EStG'
                                               r'|StVO|BAföG|SGB\s+[IVX]+|SGB\s+\d+|SGB')

                                    gesetz_muster = r'(?:§|Art\.?)\s*\d+[a-z]*.*?(?:%s)' % gesetze
                                    gefundene_gesetze_raw = re.findall(gesetz_muster, raw_clean_text)

                                    saubere_gesetze = []

                                    for fund in gefundene_gesetze_raw:
                                        sauberer_fund = " ".join(fund.split())
                                        if len(sauberer_fund) < 30:
                                            saubere_gesetze.append(sauberer_fund)


                                    # Wir werden nur top 3 "betroffen gesetzte" pro Fall aufnehmen: (die echten Schwerpunkte des Urteils)

                                    # Zählt, wie oft jedes Gesetz im Urteil zitiert wird
                                    gesetz_counter = Counter(saubere_gesetze)

                                    # most_common(3) gibt eine Liste von Tupeln zurück: [('§ 626 BGB', 12), ('§ 535 BGB', 5), ...]
                                    affected_laws = [gesetz for gesetz, anzahl in gesetz_counter.most_common(3)]

                                    # Nur eine kleine Textkorrektur:
                                    clean_text= clean_text.replace('Tenor', 'Tenor:', 1).replace("Gründe","Gründe:",1)

                                    # Das finale, optimierte Dokumenten-Schema
                                    dokument = {
                                        "id": doc_id,
                                        "type": "urteil",
                                        "legal_area": law,
                                        "topic_tags": [query],  # Unsere Suchbegriffe die dem gleichen Urteil geführt haben.
                                        "related_laws": affected_laws,
                                        "source": gericht,
                                        "jurisdiction": gerichtsbarkeit,
                                        "title": f"Urteil: {gericht} - Az. {aktenzeichen} ({datum})",
                                        "reference": aktenzeichen,
                                        "text": clean_text
                                    }

                                    urteile_data.append(dokument)
                                    id_law[doc_id] = law
                                    case_count +=1
                                    law_count +=1
                                    erfolgreiche_urteile += 1

                                time.sleep(1)

                            elif detail_response.status_code == 429:
                                print(detail_response)
                                anzahl_error_429 +=1

                                if anzahl_error_429 >= 20:
                                    self.switch_to_next_key()

                                time.sleep(20)



                            elif detail_response.status_code >= 500:
                                print(detail_response)
                                time.sleep(20)

                            else:
                                print(detail_response)
                                time.sleep(20)
                        break


                    elif response.status_code == 429:
                        print(response)
                        self.switch_to_next_key()
                        print("\nWir sind zum nächsten Schlüssel gewechselt")
                        time.sleep(20)

                    elif response.status_code >= 500:
                        print(response)
                        time.sleep(20)

                    else:
                        print(f"⚠️ Fehler bei der API-Anfrage für '{query}': Status {response.status_code}")
                        print(response)
                        time.sleep(20)


                    print(f"{query}:{case_count} Urteile wurden gespeichert.")
                    time.sleep(3)


            print(f"\n{law}:{law_count} Urteile")
            print("-"*100)
            time.sleep(10)

        print("-" * 50)
        print(f"✅ API-Import beendet! Insgesamt {len(urteile_data)} Urteile wurden gespeichert.")

        return urteile_data