import json
import re
import sqlite3
from flask import Flask, render_template, request
import pdfplumber
import docx
from fuzzywuzzy import process

app = Flask(__name__)

# Load skills with synonyms from JSON file
with open("skills.json", "r") as f:
    SKILLS_DICT = json.load(f)

# Flatten skill names for easier matching
SKILLS_LIST = list(SKILLS_DICT.keys()) + [syn for lst in SKILLS_DICT.values() for syn in lst]

# Database setup
conn = sqlite3.connect("resumes.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    phone TEXT,
    skills TEXT,
    score INTEGER
)
""")
conn.commit()

def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text.strip()

def extract_text_from_docx(docx_path):
    doc = docx.Document(docx_path)
    return "\n".join([p.text for p in doc.paragraphs]).strip()

def extract_resume_text(file_path):
    if file_path.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif file_path.endswith(".docx"):
        return extract_text_from_docx(file_path)
    return ""

def match_skills(resume_text):
    resume_words = set(re.findall(r'\b\w+\b', resume_text.lower()))
    found_skills = []

    for skill, synonyms in SKILLS_DICT.items():
        all_variants = [skill.lower()] + [s.lower() for s in synonyms]
        if any(word in resume_words for word in all_variants):
            found_skills.append(skill)
        else:
            match_score = process.extractOne(skill.lower(), resume_words)
            if match_score and match_score[1] >= 85:
                found_skills.append(skill)
    
    return list(set(found_skills))

def extract_details(text):
    name_match = re.search(r"Name[:\s]+([A-Za-z\s]+)", text)
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    phone_match = re.search(r"\b\d{10}\b", text)
    skills = match_skills(text)
    score = len(skills) * 10 if skills else 0  # Scoring based on skills found

    return {
        "Name": name_match.group(1) if name_match else "Not found",
        "Email": email_match.group(0) if email_match else "Not found",
        "Phone": phone_match.group(0) if phone_match else "Not found",
        "Skills": skills,
        "Score": min(score, 100)  # Max score = 100
    }

@app.route("/", methods=["GET", "POST"])
def index():
    data = None

    if request.method == "POST":
        file = request.files["resume"]
        if file:
            file_path = "uploaded_resume." + file.filename.split(".")[-1]
            file.save(file_path)
            
            resume_text = extract_resume_text(file_path)
            data = extract_details(resume_text)

            # Save to database
            cursor.execute("INSERT INTO resumes (name, email, phone, skills, score) VALUES (?, ?, ?, ?, ?)",
                           (data["Name"], data["Email"], data["Phone"], ", ".join(data["Skills"]), data["Score"]))
            conn.commit()

    return render_template("index.html", data=data)

if __name__ == "__main__":
    app.run(debug=True)
