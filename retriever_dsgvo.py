class DSGVO_Retriever:
    def get_dsgvo_hierarchy(article_num: int) -> str:
        # Kapitel und Abschnitt für allen DSGVO-Artikel:
        structure = [
            (1, 4, "Kapitel I: Allgemeine Bestimmungen"),
            (5, 11, "Kapitel II: Grundsätze"),
            (12, 12, "Kapitel III: Rechte der betroffenen Person - Abschnitt 1: Transparenz und Modalitäten"),
            (13, 15, "Kapitel III: Rechte der betroffenen Person - Abschnitt 2: Informationspflicht und Recht auf Auskunft zu personenbezogenen Daten"),
            (16, 20, "Kapitel III: Rechte der betroffenen Person - Abschnitt 3: Berichtigung und Löschung"),
            (21, 22, "Kapitel III: Rechte der betroffenen Person - Abschnitt 4: Widerspruchsrecht und automatisierte Entscheidungsfindung"),
            (23, 23, "Kapitel III: Rechte der betroffenen Person - Abschnitt 5: Beschränkungen"),
            (24, 31, "Kapitel IV: Verantwortlicher und Auftragsverarbeiter - Abschnitt 1: Allgemeine Pflichten"),
            (32, 34, "Kapitel IV: Verantwortlicher und Auftragsverarbeiter - Abschnitt 2: Sicherheit personenbezogener Daten"),
            (35, 36, "Kapitel IV: Verantwortlicher und Auftragsverarbeiter - Abschnitt 3: Datenschutz-Folgenabschätzung und vorherige Konsultation"),
            (37, 39, "Kapitel IV: Verantwortlicher und Auftragsverarbeiter - Abschnitt 4: Datenschutzbeauftragter"),
            (40, 43, "Kapitel IV: Verantwortlicher und Auftragsverarbeiter - Abschnitt 5: Verhaltensregeln und Zertifizierung"),
            (44, 50, "Kapitel V: Datenübermittlung an Drittländer"),
            (51, 59, "Kapitel VI: Unabhängige Aufsichtsbehörden"),
            (60, 76, "Kapitel VII: Zusammenarbeit und Kohärenz"),
            (77, 84, "Kapitel VIII: Rechtsbehelfe, Haftung und Sanktionen"),
            (85, 91, "Kapitel IX: Vorschriften für besondere Verarbeitungssituationen"),
            (92, 99, "Kapitel X & XI: Schlussbestimmungen")
        ]

        for start, end, hierarchy_name in structure:
            if start <= article_num <= end:
                return hierarchy_name

        return "DSGVO"  # Fallback


    def scrape_dsgvo(output_path: str):
        import requests
        from bs4 import BeautifulSoup
        import time
        base_url = "https://dsgvo-gesetz.de/art-{}-dsgvo/"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"}

        dsgvo_data = []

        # Wir haben 100 Artikel:
        for i in range(1, 100):
            url = base_url.format(i)
            print(f"Lese Artikel {i}...")

            try:
                response = requests.get(url, headers=headers)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    title_tag = soup.find('h1', class_='entry-title')
                    raw_title = title_tag.text.strip() if title_tag else ""
                    clean_title = raw_title.replace(f"Art. {i} DSGVO", "").strip()

                    content_div = soup.find('div', class_='entry-content')

                    if content_div:
                        # Wir suchen gezielt nach den störenden Elementen und löschen sie aus dem HTML-Baum:
                        for unwanted in content_div.find_all(['sup', 'nav', 'aside']):
                            unwanted.decompose()

                        # Löscht alle eingebetteten <div> Container:
                        for verschachteltes_div in content_div.find_all('div'):
                            verschachteltes_div.decompose()

                        # Die HTML-Struktur verankern:
                        for top_list in content_div.find_all(['ol', 'ul'], recursive=False):
                            for j, li in enumerate(top_list.find_all('li', recursive=False), 1):
                                if top_list.name == 'ol':
                                    li.insert(0, f"\n({j}) ")
                                else:
                                    li.insert(0, f"\n- ")

                        for nested_list in content_div.find_all(['ol', 'ul']):
                            if nested_list.parent == content_div:
                                continue
                            for li in nested_list.find_all('li', recursive=False):
                                li.insert(0, f"\n  - ")

                        # text-extraction:
                        text_parts = []
                        for tag in content_div.find_all(['p', 'ol', 'ul'], recursive=False):
                            text = tag.get_text(separator=" ", strip=True)
                            if text:
                                text_parts.append(text)

                        raw_text = "\n".join(text_parts)
                        volltext = raw_text.replace(" \n ", "\n").replace("\n ", "\n").replace(" \n", "\n").strip()

                        if volltext:
                            hierarchy = DSGVO_Retriever.get_dsgvo_hierarchy(i)  # Holen ihren Namen.
                            final_title = f"{hierarchy} - {clean_title}"

                            dokument = {
                                "id": f"dsgvo_art_{i}",
                                "type": "gesetz",
                                "legal_area": "DSGVO",
                                "source": "DSGVO (Datenschutz-Grundverordnung)",
                                "title": final_title,
                                "paragraph": f"Art {i}",
                                "text": volltext
                            }
                            dsgvo_data.append(dokument)

                time.sleep(0.2)

            except Exception as e:
                print(f"Fehler bei Artikel {i}: {e}")

        print(f"Scraping beendet! {len(dsgvo_data)} DSGVO-Artikel gespeichert.")

        return dsgvo_data