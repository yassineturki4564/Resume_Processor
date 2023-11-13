#importing libraries:
import shutil
import base64
import os
import pdfplumber
import cProfile
import fitz  # PyMuPDF library for PDF text extraction
import pandas as pd
import re
import openpyxl
import uuid
import PyPDF2
import json
import tempfile
from datetime import datetime
import subprocess
from googletrans import Translator
import glob
from unicodedata import normalize
from docx2pdf import convert
import docx
from nltk import sent_tokenize
import nltk
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from tqdm import tqdm
import streamlit as st
nltk.download('punkt')
#creating an NLP object:
education_keywords = [
        "iset rades/bts","faculty","extracurricular activity","windows xp – 2000 - 2003","isg tunis","génie logiciel","diplôme de baccalauréat en sciences informatiques avec mention bien","summer internship","vie sociale","Projet de fin d’études","essths","permis","projets académiques","projet académique","stage d'été","stagiaire","académique","Stage","intern","internship",
        "bachelor","licence","master","phd","doctorate","doctorat","education","master’s", "master's", "baccalaureate", 
        "degree", "preparatory institute", "university", "school","membre bénévole","athlétisme","engineering", "cursus","institute", "national school", 
        "éducation", "baccalauréat", "université", "école","iset rades","ingénierie","institut","elydata was founded in 2012","graduate","institut préparatoire",
        "graduation","etudiant","étudiant","student","diploma","rganisation nationale de l'enfant ariana ,tunisie ,","diplôme","iset rades/bts en informatique de gestion","lycée","high school","ecole","stage","certificate","SQL Server 2008",
        "accréditation","mahdia, tunisie septembre 2012 - juin 2016","certification","study","studies","studied","étude","esprit","faculté","visual studio 2005","windows server (2008, 2012, 2016)","windows 2008"
    ]
months = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", 
          "août", "septembre", "octobre", "novembre", "décembre"]
def extract_text_from_pdf(file_path):
    text = ""
    pdf_document = fitz.open(file_path)
    num_pages = pdf_document.page_count
    for page_num in range(num_pages):
        page = pdf_document[page_num]
        text += page.get_text("text")
    pdf_document.close()
    return text
def normalize_spacing(text):
    # Remove any multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Try to combine spaced characters
    text = re.sub(r'(?<=\w) (?=\w)', '', text)
    
    return text

def sanitize_string(input_value):
    if isinstance(input_value, str):
        return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', input_value)
    else:
        return input_value
def extract_and_clean_text(file_path):
    
    experience_pattern = re.compile(
        r"(?i)"
        r"\b\d{2}/\d{4}\s*-\s*actuel\b|"
        r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december|janv.|févr.|avr.|juil.|sept.|oct.|nov.|déc.)\s+(\d{4})\s*to\s*(?:january|february|march|april|may|june|july|august|september|october|november|december|janv.|févr.|avr.|juil.|sept.|oct.|nov.|déc.)\s+(\d{4})\b|"
        r"\b\d{4}/\d{4}\b|"
        r"\b\d{1,2}/\d{4}\s*-\s*\d{1,2}/\d{4}\b|"
        r"\b(.*?)\s*(\d{4})\s*(?:[-–]|to|through|à)\s*(.*?)\s*(\d{4}|.*?Current.*?|.*?Present.*?|.*?Now.*?|.*?Ongoing.*?|.*?présent.*?)\b|"
        r"(?<!\d)(\d{4})\s*(?:[-–]|to|through|à)\s*(?<!\d)(\d{4}|.*?Current.*?|.*?Present.*?|.*?Now.*?|.*?Ongoing.*?|.*?présent.*?)(?!\d)|"
        r"De\s+(.*?)\s+(\d{4})\s+à\s+(.*?)\s+(\d{4}|.*?Current.*?|.*?Present.*?|.*?Now.*?|.*?Ongoing.*?|.*?présent.*?)|"
        r"(.*?)\s*(\d{4})\s*maintenant.*?|"
        r"((?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|janv.|févr.|avr.|juil.|sept.|oct.|nov.|déc.)[\s\S]{0,10}\d{4})|"
        r"^(\d{4})\s*$|"
        r"(\d{4})\s*maintenant.*?|"
        r"(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|janv.|févr.|avr.|juil.|sept.|oct.|nov.|déc.|january|february|march|april|may|june|july|august|september|october|november|december|sep.|mar.|aug.)\s*(\d{4})\s*[-–]\s*(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|janv.|févr.|avr.|juil.|sept.|oct.|nov.|déc.|january|february|march|april|may|june|july|august|september|october|november|december|sep.|mar.|aug.)?\s*(\d{4}|présent|current|now|ongoing|à ce jour|maintenant|actuel)?|"
        r"du\s*(\d{1,2}/\d{4})\s*au\s*(\d{1,2}/\d{4}|présent|current|now|ongoing|à ce jour|maintenant|actuel)|"
        r"since\s*(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|janv.|févr.|avr.|juil.|sept.|oct.|nov.|déc.|january|february|march|april|may|june|july|august|september|october|november|december|sep.|mar.|aug.)\s*(\d{4})|"
        r"(\d{1,2}/\d{4})\s*[-–]\s*(\d{1,2}/\d{4}|présent|current|now|ongoing|à ce jour|maintenant|actuel)|"
        r"(\d{4})\s*[-–]\s*(\d{4}|présent|current|now|ongoing|à ce jour|maintenant|actuel)"
    )

    # Extract text from the PDF
    doc = fitz.open(file_path)
    text = " ".join([page.get_text("text") for page in doc])
    lines = text.splitlines()

    # Handle experience adjustments first
    for i in range(len(lines) - 1):
        current_line = lines[i].strip()
        next_line = lines[i + 1].strip()

        is_current_line_match = (re.fullmatch(experience_pattern.pattern, current_line) or 
                                re.fullmatch(experience_pattern.pattern + r'\s*', current_line))
        is_next_line_match = re.search(experience_pattern, next_line)

        if is_current_line_match and not is_next_line_match:
            lines[i] = lines[i] + ' ' + next_line
            lines[i + 1] = ''
        elif is_current_line_match and is_next_line_match:
            lines[i] = ''

    text = '\n'.join(lines)
    text = text.lower()
    # Education keywords combined into a regex pattern
    education_keywords = [
        "iset rades/bts","faculty","extracurricular activity","windows xp – 2000 - 2003","isg tunis","génie logiciel","diplôme de baccalauréat en sciences informatiques avec mention bien","summer internship","vie sociale","Projet de fin d’études","essths","permis","projets académiques","projet académique","stage d'été","stagiaire","académique","Stage","intern","internship",
        "bachelor","licence","master","phd","doctorate","doctorat","education","master’s", "master's", "baccalaureate", 
        "degree", "preparatory institute", "university", "school","membre bénévole","athlétisme","engineering", "cursus","institute", "national school", 
        "éducation", "baccalauréat", "université", "école","iset rades","ingénierie","institut","elydata was founded in 2012","graduate","institut préparatoire",
        "graduation","etudiant","étudiant","student","diploma","rganisation nationale de l'enfant ariana ,tunisie ,","diplôme","iset rades/bts en informatique de gestion","lycée","high school","ecole","stage","certificate","SQL Server 2008",
        "accréditation","mahdia, tunisie septembre 2012 - juin 2016","certification","study","studies","studied","étude","esprit","faculté","visual studio 2005","windows server (2008, 2012, 2016)","windows 2008"
    ]

    # Sort the keywords by length, with longer phrases first
    education_keywords = sorted(education_keywords, key=len, reverse=True)
    pattern = r'\b(?:' + '|'.join(map(re.escape, education_keywords)) + r')\b'
    positions_to_delete = []

    # Detect and delete the keywords and surrounding words
    for match in re.finditer(pattern, text, re.IGNORECASE):
        start_pos = match.start()
        end_pos = match.end()

        # Extract 5 tokens before the matched keyword
        pre_tokens = re.findall(r'\S+', text[max(0, start_pos - 100):start_pos])[-8:]
        pre_words = ' '.join(pre_tokens)
        
        # Extract 5 tokens after the matched keyword
        post_tokens = re.findall(r'\S+', text[end_pos:end_pos + 100])[:8]
        post_words = ' '.join(post_tokens)
        
        # Find the next date ranges
        date_matches = list(re.finditer(experience_pattern, text[end_pos:end_pos + 100]))
        
        if date_matches:  # If date range is found
            first_date_match = date_matches[0]
            delete_end_pos = first_date_match.end() + end_pos + len(post_words)
            positions_to_delete.append((start_pos - len(pre_words), delete_end_pos))
        else:
            # If no date found, delete the educational information and 5 tokens before & after
            delete_start_pos = start_pos - len(pre_words)
            delete_end_pos = end_pos + len(post_words)
            positions_to_delete.append((delete_start_pos, delete_end_pos))

    positions_to_delete.sort(key=lambda x: x[0])
    merged_positions = []
    for start, end in positions_to_delete:
        if merged_positions and start <= merged_positions[-1][1]:
            merged_positions[-1] = (merged_positions[-1][0], max(merged_positions[-1][1], end))
        else:
            merged_positions.append((start, end))

    offset = 0
    for start, end in merged_positions:
        text = text[:start-offset] + text[end-offset:]
        offset += (end - start)
    education_end_years = [int(year) for match in re.finditer(experience_pattern, text) for year in match.groups() if year and year.isdigit()]

    return text
def is_potential_job_title(word):
    # A set of common job titles or terms that usually follow a person's role rather than their name.
    job_titles = {'engineer', 'developer', 'manager', 'executive', 'attendant', 'professor', 'analyst'}
    return word.lower() in job_titles
def derive_name_from_email(email):
    # Splitting the email into local and domain parts
    if '@' not in email:
        return ""  # or some default value to indicate no name derived

    # Splitting the email into local and domain parts
    local_part, _ = email.split('@', 1)

    # Splitting the local part using common separators to get name components
    name_components = re.split('[._-]', local_part)
    
    # Capitalizing the first letter of each component
    derived_name = ' '.join([component.capitalize() for component in name_components if component])
    
    return derived_name
def process_match(match):
    for i in range(0, len(match), 4): 
        if len(match[i:i+4]) == 4:
            start, start_year, end, end_year = match[i:i+4]
            if start_year and (end_year or end):
                return f"{start} {start_year} to {end} {end_year}"
    return ''
def extract_name_and_email_and_experience_levels(cleaned_text):
    # Extracting emails
    email_pattern = re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b|[A-Za-z0-9._%+-]+@[A-Za-z0.9.-]+\.[A-Z|a-z]{2,})")
    email_matches = re.findall(email_pattern, cleaned_text.lower())
    email = email_matches[0] if email_matches else ""

    # Extracting names from the compiled text
    name = derive_name_from_email(email)

    # Prioritized experience patterns
    experience_patterns = [
        r"\d{1,2}\s*years of experience",
        r"\d{1,2}\s*years of professional experience",
        r"\d{1,2}\s*ans d'(?:expérience|expérience)s?",
        r"\d{1,2}\s*années d'(?:expérience|expérience)s?",
        r"\d{1,2}\s*ans d’éxpé riéncé",
        r"\d{1,2}\s*ans d’experience"  # Added pattern
    ]

    combined_pattern = "|".join(experience_patterns)

    # Extracting other experience data
    
    experience_pattern = re.compile(
        r"(?i)"
        r"\b\d{2}/\d{4}\s*-\s*actuel\b|"
        r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december|janv.|févr.|avr.|juil.|sept.|oct.|nov.|déc.)\s+(\d{4})\s*to\s*(?:january|february|march|april|may|june|july|august|september|october|november|december|janv.|févr.|avr.|juil.|sept.|oct.|nov.|déc.)\s+(\d{4})\b|"
        r"\b\d{4}/\d{4}\b|"
        r"\b\d{1,2}/\d{4}\s*-\s*\d{1,2}/\d{4}\b|"
        r"\b(.*?)\s*(\d{4})\s*(?:[-–]|to|through|à)\s*(.*?)\s*(\d{4}|.*?Current.*?|.*?Present.*?|.*?Now.*?|.*?Ongoing.*?|.*?présent.*?)\b|"
        r"(?<!\d)(\d{4})\s*(?:[-–]|to|through|à)\s*(?<!\d)(\d{4}|.*?Current.*?|.*?Present.*?|.*?Now.*?|.*?Ongoing.*?|.*?présent.*?)(?!\d)|"
        r"De\s+(.*?)\s+(\d{4})\s+à\s+(.*?)\s+(\d{4}|.*?Current.*?|.*?Present.*?|.*?Now.*?|.*?Ongoing.*?|.*?présent.*?)|"
        r"(.*?)\s*(\d{4})\s*maintenant.*?|"
        r"((?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|janv.|févr.|avr.|juil.|sept.|oct.|nov.|déc.)[\s\S]{0,10}\d{4})|"
        r"^(\d{4})\s*$|"
        r"(\d{4})\s*maintenant.*?|"
        r"(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|janv.|févr.|avr.|juil.|sept.|oct.|nov.|déc.|january|february|march|april|may|june|july|august|september|october|november|december|sep.|mar.|aug.)\s*(\d{4})\s*[-–]\s*(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|janv.|févr.|avr.|juil.|sept.|oct.|nov.|déc.|january|february|march|april|may|june|july|august|september|october|november|december|sep.|mar.|aug.)?\s*(\d{4}|présent|current|now|ongoing|à ce jour|maintenant|actuel)?|"
        r"du\s*(\d{1,2}/\d{4})\s*au\s*(\d{1,2}/\d{4}|présent|current|now|ongoing|à ce jour|maintenant|actuel)|"
        r"since\s*(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|janv.|févr.|avr.|juil.|sept.|oct.|nov.|déc.|january|february|march|april|may|june|july|august|september|october|november|december|sep.|mar.|aug.)\s*(\d{4})|"
        r"(\d{1,2}/\d{4})\s*[-–]\s*(\d{1,2}/\d{4}|présent|current|now|ongoing|à ce jour|maintenant|actuel)|"
        r"(\d{4})\s*[-–]\s*(\d{4}|présent|current|now|ongoing|à ce jour|maintenant|actuel)"
    )


    experience_matches = re.findall(experience_pattern, cleaned_text.lower())
    experience_levels = [' '.join([x for x in match if x]).strip() for match in experience_matches]

    current_year = datetime.now().year
    filtered_experience_levels = []
    
    for level in experience_levels:
        years = re.findall(r"\d{4}", level)
        if not years: 
            continue
        start_year = int(years[0])
        if any(keyword in level for keyword in ["present", "current", "now", "ongoing", "présent", "maintenant"]):
            end_year = current_year
        else:
            end_year = int(years[-1])
        if 1993 <= start_year <= current_year and 1993 <= end_year <= current_year:
            filtered_experience_levels.append(level)

    return name, email, filtered_experience_levels
#def compute_education_years(cleaned_text, education_keywords):
    # Get text after removing educational blocks
 #   text_without_education = remove_education_paragraphs_and_intervals(cleaned_text, education_keywords)
  #  years = [int(year) for year in re.findall(r"\b\d{4}\b", text_without_education)]

   # if not years:
    #    return 0

#    education_years = max(years) - min(years) + 1  # +1 to include both starting and ending years
 #   return education_years
def compute_experience_from_oldest_year(experience_levels, prioritized_experience=None):
    # Extracting all the years from the experience levels
    years = [int(year) for level in experience_levels for year in re.findall(r"\d{4}", level)]
    
    # Add the prioritized experience value if it exists
    if prioritized_experience:
        num = re.search(r'\d+', prioritized_experience[0])  # Extract numbers from the first matched string
        if num:
            return int(num.group())
    
    # If there are no years found, return 0
    if not years:
        return 0
    
    # Compute experience from the oldest year found
    oldest_year = min(years)
    return datetime.now().year - oldest_year

def extract_years_of_experience(experience_levels):
    years_of_experience = []
    unique_years = set()
    current_year = datetime.now().year  # Getting the current year
    
    specific_years_pattern = r"(\d{1,2})\s*(?:years? of (?:professional )?experience|ans d'(?:expérience|expérience)s?|années d'(?:expérience|expérience)s?|ans d’éxpé riéncé)"

    for level in experience_levels:
        if isinstance(level, tuple):
            level = level[0]

        # Check for specific years pattern
        specific_years_matches = re.findall(specific_years_pattern, level, re.IGNORECASE)
        if specific_years_matches:
            for year_match in specific_years_matches:
                years_of_experience.append(int(year_match))
            continue  # No need to process further for this level

        years = re.findall(r"\d{4}", level)
        if len(years) >= 1:
            start_year = int(years[0])
            # Check if "Present" is in the level and assign the end year as the current year
            if "Present" in level or "Current" in level:
                end_year = current_year
            else:
                end_year = int(years[-1])

            if (start_year, end_year) not in unique_years:
                years_of_experience.append(end_year - start_year)
                unique_years.add((start_year, end_year))

    return years_of_experience
def remove_years_before_education(cleaned_text, education_keywords):
    years = [int(year) for year in re.findall(r"\b\d{4}\b", cleaned_text)]

    if not years:
        return cleaned_text

    # Identify education years.
    education_years = [int(year) for match in re.finditer("|".join(map(re.escape, education_keywords)), cleaned_text, re.IGNORECASE) for year in re.findall(r"\b\d{4}\b", match.group(0))]

    # If no education years are found, just return the cleaned text as is.
    if not education_years:
        return cleaned_text

    earliest_education_year = min(education_years)

    # Removing any year that precedes the earliest education year.
    for year in years:
        if year < earliest_education_year:
            cleaned_text = cleaned_text.replace(str(year), '')

    return cleaned_text
def rank_experience_lines(cleaned_text, education_keywords):
    scores = {}
    
    for line in cleaned_text.split('\n'):
        score = 0
        
        # Deduct for educational keywords.
        for keyword in education_keywords:
            if keyword.lower() in line.lower():
                score -= 1

        scores[line] = score

    return scores
def remove_irrelevant_years(text, education_keywords):
    # Extract the last year mentioned in the education section
    years_in_education = [int(match) for match in re.findall(r'\b(\d{4})\b', text.split("SKILLS")[0])]
    if not years_in_education:
        return text
    last_year_of_education = max(years_in_education)

    # Split the text into sections based on headers
    sections = re.split(r'\b(EDUCATION|SKILLS|ACADEMIC PROJECTS|EXTRACURRICULAR ACTIVITY)\b', text)
    if len(sections) < 3:
        return text

    education_section = sections[2]
    academic_projects_section = sections[6] if "ACADEMIC PROJECTS" in sections else ""

    # Remove years that are not associated with education keywords in the academic projects section
    for year in range(2014, last_year_of_education+1):  
        if str(year) in academic_projects_section:
            pattern = r'\b' + str(year) + r'\b(?!(' + '|'.join(education_keywords) + r'))'
            academic_projects_section = re.sub(pattern, '', academic_projects_section)

    # Combine sections back
    cleaned_text = sections[0] + "EDUCATION" + education_section + "SKILLS" + sections[4] + "ACADEMIC PROJECTS" + academic_projects_section + "".join(sections[7:])

    return cleaned_text
def filter_experience(cleaned_text, scores):
    # Only keep lines with score >= 0.
    return '\n'.join(line for line, score in scores.items() if score >= 0)
def remove_duplicate_dates(text):
    # Regular expression pattern to identify month-year combinations
    date_pattern = r'\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}\b'
    matches = list(re.finditer(date_pattern, text, re.IGNORECASE))
    
    seen_dates = set()
    positions_to_delete = []
    
    for match in matches:
        date_str = match.group().lower()
        if date_str in seen_dates:
            positions_to_delete.append((match.start(), match.end()))
        else:
            seen_dates.add(date_str)

    # Remove the duplicate dates from the text
    offset = 0
    for start, end in positions_to_delete:
        text = text[:start-offset] + text[end-offset:]
        offset += (end - start)
    
    return text
def all_the_process(directory, max_attempts, education_keywords, keywords, chunksize=10):
    experience_patterns = [
        r"\d{1,2}\s*years of experience",
        r"\d{1,2}\s*years of professional experience",
        r"\d{1,2}\s*ans d'(?:expérience|expérience)s?",
        r"\d{1,2}\s*années d'(?:expérience|expérience)s?",
        r"\d{1,2}\s*ans d’éxpé riéncé",
        r"\d{1,2}\s*ans d’experience"  # Added pattern
    ]

    combined_pattern = "|".join(experience_patterns)
    pdf_files = glob.glob(os.path.join(directory, "*.pdf"))
    if not pdf_files:
        print("No valid PDF files found in the directory.")
        return None

    resume_data = []

    with ThreadPoolExecutor() as executor:
        def process_file(file_path):
            with fitz.open(file_path) as doc:
                raw_text = "".join(page.get_text("text") for page in doc)
            cleaned_text = extract_and_clean_text(file_path)
            cleaned_text = remove_years_before_education(cleaned_text, education_keywords)
            scores = rank_experience_lines(cleaned_text, education_keywords)
            cleaned_text = filter_experience(cleaned_text, scores)
            cleaned_text = remove_irrelevant_years(cleaned_text, education_keywords)
            cleaned_text = remove_duplicate_dates(cleaned_text)
            name, email, _ = extract_name_and_email_and_experience_levels(raw_text)

            # Extract experience levels from cleaned text
            _, _, experience_levels = extract_name_and_email_and_experience_levels(cleaned_text)
            prioritized_matches = re.findall(combined_pattern, cleaned_text.lower())
            
            # If prioritized_matches found, extract the experience directly
            if prioritized_matches:
                num = re.search(r'\d+', prioritized_matches[0])  # Extract numbers from the first matched string
                if num:
                    experience_sum = int(num.group())
                else:
                    experience_sum = None
            else:
                experience_sum = compute_experience_from_oldest_year(experience_levels)

            name_attempts = 1
            while name is None and name_attempts <= max_attempts:
                name, email, experience_levels = extract_name_and_email_and_experience_levels(cleaned_text)
                name_attempts += 1
            if name is not None:
                years_of_experience = extract_years_of_experience(experience_levels)
                return {
                    "Raw_Text": raw_text,
                    "Cleaned_Text": cleaned_text,
                    "Name": name,
                    "Email": email,
                    "Experience_Levels": experience_levels,
                    "Years of Experience": years_of_experience,
                    "Experience Sum": experience_sum,  # Add this line
                    "PDF File": os.path.basename(file_path),
                }
            return None

        futures = [executor.submit(process_file, file_path) for file_path in pdf_files]

        for future in tqdm(futures, desc="Processing PDFs"):
            result = future.result()
            if result is not None:
                resume_data.append(result)

    new_words = list(set(keywords.split(";")))
    Dict = {i + 1: word for i, word in enumerate(new_words)}

    df = pd.DataFrame(resume_data)

    df["Cleaned_Text"] = df["Cleaned_Text"].str.lower()
    df["Raw_Text"] = df["Raw_Text"].str.lower()
    education_keywords_lower = [item.lower() for item in education_keywords]

    # Convert the dictionary values to lowercase
    Dict_lower = {k: v.lower() for k, v in Dict.items()}
    

    # Convert the keywords to lowercase
    keywords_lower = [kw.lower() for kw in keywords]


# Using the raw text for Match Count
    df["Match Count"] = df.apply(lambda row: sum(1 for word in Dict.values() if word.lower() in row["Raw_Text"].lower()), axis=1)
    df["Keywords"] = df.apply(lambda row: [word for word in Dict_lower.values() if word in row["Raw_Text"].lower() and word not in education_keywords_lower], axis=1)
    df.sort_values(by=["Match Count", "Experience Sum"], ascending=False, inplace=True)
    display_df = df.drop(columns=['Raw_Text', 'Cleaned_Text','Experience_Levels','Years of Experience'])
    return display_df
def get_download_link(filename, text):
    with open(filename, 'rb') as f:
        bytes = f.read()
        b64 = base64.b64encode(bytes).decode()
        href = f'<a href="data:file/xlsx;base64,{b64}" download="{filename}">{text}</a>'
    return href
def main():
    st.title('Resume Processor')
    BASE_DIRECTORY = st.text_input("Enter the directory path where the files are located:")

    uploaded_files = st.file_uploader("Upload Resumes", type=["pdf", "docx"], accept_multiple_files=True)

    if uploaded_files:
        # Creating a temporary directory for uploaded files
        uploaded_temp_dir = tempfile.mkdtemp()
        for uploaded_file in uploaded_files:
            with open(os.path.join(uploaded_temp_dir, uploaded_file.name), "wb") as f:
                f.write(uploaded_file.getvalue())

        max_attempts = 30
        education_keywords = [
            "iset rades/bts","faculty","extracurricular activity","windows xp – 2000 - 2003","isg tunis","génie logiciel","diplôme de baccalauréat en sciences informatiques avec mention bien","summer internship","vie sociale","Projet de fin d’études","essths","permis","projets académiques","projet académique","stage d'été","stagiaire","académique","Stage","intern","internship",
            "bachelor","licence","master","phd","doctorate","doctorat","education","master’s", "master's", "baccalaureate", 
            "degree", "preparatory institute", "university", "school","membre bénévole","athlétisme","engineering", "cursus","institute", "national school", 
            "éducation", "baccalauréat", "université", "école","iset rades","ingénierie","institut","elydata was founded in 2012","graduate","institut préparatoire",
            "graduation","etudiant","étudiant","student","diploma","rganisation nationale de l'enfant ariana ,tunisie ,","diplôme","iset rades/bts en informatique de gestion","lycée","high school","ecole","stage","certificate","SQL Server 2008",
            "accréditation","mahdia, tunisie septembre 2012 - juin 2016","certification","study","studies","studied","étude","esprit","faculté","visual studio 2005","windows server (2008, 2012, 2016)","windows 2008"
        ]  # Your previous list of education keywords here
        keywords = st.text_input("Enter keywords (separated by ;): ")
        if st.button("Process"):
            df_simple = all_the_process(uploaded_temp_dir, max_attempts, education_keywords, keywords)
            df_simple["PDF File"] = df_simple["PDF File"].apply(lambda x: os.path.join(BASE_DIRECTORY, os.path.basename(x)))
            df_simple["Resume Link"] = df_simple.apply(lambda row: f'=HYPERLINK("{row["PDF File"]}", "Open Resume")', axis=1)
            
            # Define the name of the output Excel file
            current_time_now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            sanitized_keywords = "_".join(keywords.split(";")).replace(" ", "_")
            output_file_name = f"{current_time_now}_{sanitized_keywords}_{str(uuid.uuid4())}.xlsx"
            
            # Create a temporary directory to save the Excel file
            excel_temp_dir = tempfile.mkdtemp()
            output_file_path = os.path.join(excel_temp_dir, output_file_name)
            df_simple.drop(columns=['PDF File']).to_excel(output_file_path, index=False, engine="openpyxl")            
            # Provide a link for downloading the file
            st.markdown(get_download_link(output_file_path, "Click here to download the processed file"), unsafe_allow_html=True)
            st.write("Data extraction and processing completed.")
            
            # Cleanup: Remove the temporary directories
            shutil.rmtree(uploaded_temp_dir)
            shutil.rmtree(excel_temp_dir)

        else:
            st.write("The uploaded data is being processed...")

    st.write("Thank you for using the Resume Processor.")

if __name__ == "__main__":
    main()
