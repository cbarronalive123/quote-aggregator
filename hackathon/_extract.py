import fitz

files = {
    "Ontario All Quote Agent Hackathon Brief - August 8 Update.pdf": "hackathon_brief.txt",
    "Ontario_All-Quote_Agent_Challenge_Deck.pdf": "challenge_deck.txt",
}

for src, dst in files.items():
    doc = fitz.open(src)
    text = "\n\n".join(page.get_text() for page in doc)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(text)
    print(dst, "pages:", doc.page_count, "chars:", len(text))
