import json

with open("json_files/gesetze.json", "r", encoding="utf-8") as f:
    gesetze = json.load(f)      # {'GG': 'Grundgesetz für...', 'BGB': 'Bürgerliches Gesetzbuch'},

class Gesetze_Retriever:

    def parse_gesetz_xml(xml_file_path: str):
        import xml.etree.ElementTree as ET
        print(f"Lese XML-Datei: {xml_file_path}...")
        tree = ET.parse(xml_file_path)
        root = tree.getroot()

        gesetze_daten = []
        current_chapter = ""

        for norm in root.findall('.//norm'):
            # Lesen Kapitel-Überschrift ab:
            gliederung_bezeichnung = norm.find('.//gliederungsbez')  # e.g., "I." oder "Buch 1"
            gliederung_titel = norm.find('.//gliederungstitel')  # e.g., "Die Grundrechte"

            # Wir speichern das Kapitel ab:
            if gliederung_titel is not None:
                bezeichnung = gliederung_bezeichnung.text.strip() if gliederung_bezeichnung is not None and gliederung_bezeichnung.text else ""
                titel = gliederung_titel.text.strip() if gliederung_titel.text else ""
                current_chapter = f"{bezeichnung}: {titel}".strip().replace("\n"," ")

            # Paragrafen und Artikel lesen:
            Gesetzesname = norm.find('.//jurabk')
            Gesetzessatz = norm.find('.//enbez')
            Gesetzestitel = norm.find('.//titel')

            text_elems = norm.findall('.//text/Content/P')

            # Wenn es ein echter Artikel mit Text ist:
            if Gesetzesname is not None and Gesetzessatz is not None and text_elems:
                source = Gesetzesname.text.strip() if Gesetzesname.text else "Unbekannt"
                if source.startswith("SGB"):    # SGB haben Nummerierung.
                    source = " ".join(source.split()[:2])
                else:
                    source = source.split(" ")[0]

                paragraph = Gesetzessatz.text.strip() if Gesetzessatz.text else ""

                # wenn der Paragraf einen eigenen Titel hat (z.B. "Parlamentarisches Kontrollgremium"):
                eigener_titel = Gesetzestitel.text.strip() if Gesetzestitel is not None and Gesetzestitel.text else ""

                # Titel Konfiguration:
                if current_chapter and eigener_titel:
                    final_title = f"{current_chapter} - {eigener_titel}"
                elif current_chapter and not eigener_titel:   # Fallback für GG
                    final_title = current_chapter
                else:
                    final_title = eigener_titel


                # Rekursive Text-Extraktion (fixt Listen und Aufzählungen)
                volltext_parts = []

                for para in text_elems:
                    raw_text = " ".join(para.itertext())
                    clean_text = " ".join(raw_text.split())
                    if clean_text:
                        volltext_parts.append(clean_text)

                volltext = "\n".join(volltext_parts)

                # Nur Paragrafen, Artikel oder Vorwörter zulassen
                is_valid_paragraph = paragraph.startswith("§") or paragraph.startswith("Art") or "Präambel" in paragraph

                if volltext and is_valid_paragraph:
                    safe_para = paragraph.replace(' ', '_').replace('§_', '').replace('§', '')
                    doc_id = f"{source}_{safe_para}".lower().replace(" ","_")

                    dokument = {
                        "id": doc_id,
                        "type": "gesetz",
                        "legal_area": source,
                        "source": f"{source} ({gesetze[source]})",
                        "title": final_title,
                        "paragraph": paragraph,
                        "text": volltext
                    }
                    gesetze_daten.append(dokument)

        print(f"{len(gesetze_daten)} Einträge wurden für {source} extrahiert.")
        return gesetze_daten