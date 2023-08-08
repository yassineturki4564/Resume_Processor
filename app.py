#importing libraries:
import shutil
import base64
import os
import spacy
import pdfplumber
import cProfile
import fitz  # PyMuPDF library for PDF text extraction
import pandas as pd
import re
import openpyxl
import uuid
import PyPDF2
from datetime import datetime
import subprocess
from googletrans import Translator
from flask import Flask, render_template, request
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
    "education", "baccalaureate", "degree", "preparatory institute", "university", "school","engineering", 
    "institute", "national school", "éducation", "baccalauréat", "université", "école","ingénierie","institut","institut préparatoire",
    "graduation","etudiant","étudiant","student","diploma","diplôme","lycée","high school"
]
@lru_cache(maxsize=None)
def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, "rb") as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
    return text
def determine_date_placement(text):
    # Check the beginning part of the text to determine date placement
    start_text = text[:200]  # adjust this based on your needs
    if re.search(r"\d{4}\s*[-–]", start_text):
        return "before"
    return "after"
def sanitize_string(input_value):
    if isinstance(input_value, str):
        return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', input_value)
    else:
        return input_value
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
def extract_name_and_email_and_experience_levels(file_path):
    text = ""
    email_annotations = []

    pdf = fitz.open(file_path)

    for page_num in range(len(pdf)):
        page = pdf[page_num]
        text += page.get_text()

        annotations = page.annots()
        for annot in annotations:
            if annot.type[0] == 6 and "mailto:" in annot.get_info()["URI"]:
                email_annotations.append(annot.get_info()["URI"].replace("mailto:", ""))

    pdf.close()

    email_pattern = re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b|[A-Za-z0-9._%+-]+@[A-Za-z0.9.-]+\.[A-Z|a-z]{2,})")
    email_matches = re.findall(email_pattern, text)
    email_matches += email_annotations
    email = email_matches[0] if email_matches else ""

    # Extracting names from the compiled text
    name = derive_name_from_email(email)
    date_placement = determine_date_placement(text)

    if date_placement == "before":
        experience_pattern = re.compile(
            r"(?i)\d{4}\s*[-–~]\s*\d{4}\s*(?:[A-Za-z][a-z]+)|"
            r"\d{4}\s*(?:to|through|-|~)\s*\d{4}\s*(?:[A-Za-z][a-z]+)|"
            r"(?:[A-Za-z]{3,}\s+\d{4}\s*(?:to|through|-|~)\s*[A-Za-z]{3,}\s+\d{4})|"
            r"\d{4}\s*[-–]\s*(?:Current|Present|Now|Ongoing)\s*(?:[A-Za-z][a-z]+)"
        )
    else:
        experience_pattern = re.compile(
            r"(?i)\b(?:[A-Za-z][a-z]+\s)?(?:[A-Za-z][a-z]+)?\s?(?:\d{1,2}/)?\d{4}\s*(?:to|through|-|~|à)\s*(?:[A-Za-z][a-z]+\s)?(?:[A-Za-z][a-z]+)?(?:\d{1,2}/)?\d{4}|"
            r"(?:\d{1,2}/)?\d{4}\s*(?:to|through|-|~|à)\s*(?:Current|Present|Now|Ongoing)|"
            r"De\s+(?:[A-Za-z][a-z]+)\s+\d{4}\s+à\s+(?:[A-Za-z][a-z]+)\s+\d{4}|"
            r"(?:[A-Za-z]{3,}\s+\d{4}\s*(?:to|through|-|~|à)\s*[A-Za-z]{3,}\s+\d{4})"
        )

    education_intervals = find_education_years(text)


    experience_matches = re.findall(experience_pattern, text)
    experience_levels = [match.replace("–", "-") for match in experience_matches]

    unique_intervals = set()
    filtered_levels = []

    for level in experience_levels:
        if not any(keyword.lower() in level.lower() for keyword in education_keywords):
            years = tuple(map(int, re.findall(r"\d{4}", level)))
            if years not in unique_intervals and not any(education_start <= year <= education_end for education_start, education_end in education_intervals for year in years):
                filtered_levels.append(level)
                unique_intervals.add(years)
    
    return name, email, filtered_levels
def find_education_years(text):
    education_years = set()
    for keyword in education_keywords:
        matches = re.finditer(keyword, text, re.IGNORECASE)
        for match in matches:
            subsequent_text = text[match.end():]
            years = re.findall(r"\d{4}", subsequent_text)
            if len(years) >= 2:
                education_years.add((int(years[0]), int(years[-1])))
    return education_years

def extract_years_of_experience(experience_levels):
    years_of_experience = []
    unique_years = set()
    current_year = datetime.now().year  # Getting the current year

    for level in experience_levels:
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
def all_the_process(directory, max_attempts, education_keywords, keywords, chunksize=10):
    pdf_files = glob.glob(os.path.join(directory, "*.pdf"))
    if not pdf_files:
        print("No valid PDF files found in the directory.")
        return None

    resume_data = []

    with ThreadPoolExecutor() as executor:
        def process_file(file_path):
            name, email, experience_levels = extract_name_and_email_and_experience_levels(file_path)
            name_attempts = 1
            while name is None and name_attempts <= max_attempts:
                name, email, experience_levels = extract_name_and_email_and_experience_levels(file_path)
                name_attempts += 1
            if name is not None:
                text = extract_text_from_pdf(file_path)
                cleaned_text = sanitize_string(text)
                sentences = sent_tokenize(text)
                cleaned_text = " ".join(sentences)
                years_of_experience = extract_years_of_experience(experience_levels)
                return {
                    "Cleaned_Text": cleaned_text,
                    "Name": name,
                    "Email": email,
                    "Experience_Levels": experience_levels,
                    "Years of Experience": years_of_experience,
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
    df["Cleaned_Text"] = df["Cleaned_Text"].apply(sanitize_string)
    df["Cleaned_Text"] = df["Cleaned_Text"].str.lower()
    education_keywords_lower = [item.lower() for item in education_keywords]

    # Convert the dictionary values to lowercase
    Dict_lower = {k: v.lower() for k, v in Dict.items()}

    # Convert the keywords to lowercase
    keywords_lower = [kw.lower() for kw in keywords]
    df['Experience Sum'] = df['Years of Experience'].apply(lambda x: sum(x))
    df["Match Count"] = df.apply(lambda row: sum(1 for word in Dict.values() if word.lower() in row["Cleaned_Text"].lower()), axis=1)
    df["Keywords"] = df.apply(lambda row: [word for word in Dict_lower.values() if word in row["Cleaned_Text"] and word not in education_keywords_lower], axis=1)    

    df.sort_values(by=["Match Count", "Experience Sum"], ascending=False, inplace=True)

    return df
def get_download_link(filename, text):
    with open(filename, 'rb') as f:
        bytes = f.read()
        b64 = base64.b64encode(bytes).decode()
        href = f'<a href="data:file/xlsx;base64,{b64}" download="{filename}">{text}</a>'
    return href
def main():
    st.title('Resume Processor')
    
    # Ask the user to manually input the directory path
    BASE_DIRECTORY = st.text_input("Enter the directory path where the files are located:")

    uploaded_files = st.file_uploader("Upload Resumes", type=["pdf", "docx"], accept_multiple_files=True)

    if uploaded_files:
        temp_dir = "tempDir"
        os.makedirs(temp_dir, exist_ok=True)
        for uploaded_file in uploaded_files:
            with open(os.path.join(temp_dir, uploaded_file.name), "wb") as f:
                f.write(uploaded_file.getvalue())

        max_attempts = 3
        education_keywords = [
            "education", "baccalaureate", "degree", "preparatory institute", "university", "school","engineering", 
            "institute", "national school", "éducation", "baccalauréat", "université", "école","ingénierie","institut","institut préparatoire",
            "graduation","etudiant","étudiant","student","diploma","diplôme","lycée","high school"
        ]
        keywords = st.text_input("Enter keywords (separated by ;): ")

        if st.button("Process"):
            df_simple = all_the_process(temp_dir, max_attempts, education_keywords, keywords)
            # Map file names back to their original paths in the base directory
            df_simple["PDF File"] = df_simple["PDF File"].apply(lambda x: os.path.join(BASE_DIRECTORY, os.path.basename(x)))
            df_simple["Resume Link"] = df_simple.apply(lambda row: f'=HYPERLINK("{row["PDF File"]}","Open Resume")', axis=1)
            if df_simple is not None and not df_simple.empty:
                output_file = str(uuid.uuid4()) + ".xlsx"
                df_simple.to_excel(output_file, index=False, engine="openpyxl")

                st.markdown(get_download_link(output_file, "Click here to download the processed file"), unsafe_allow_html=True)
                st.write("Data extraction and processing completed.")
            else:
                st.warning("No valid PDF files found or data extraction failed.")
            
            # Remove the temporary directory
            shutil.rmtree(temp_dir)
        st.write("Data extraction and processing completed.")


    st.write("Data extraction and processing completed.")
if __name__ == "__main__":
    main()