import streamlit as st
import fitz
import pandas as pd
import re
import json
from io import BytesIO
from google import genai

st.set_page_config(
    page_title="ScholarPilot",
    page_icon="📚",
    layout="wide"
)

# -----------------------------
# APP DESIGN
# -----------------------------

st.title("📚 ScholarPilot")
st.subheader("Your AI Research Assistant")

st.write(
    "Analyze research papers, verify findings against original "
    "PDF pages, and build literature review matrices."
)

st.info(
    "AI-generated information can contain errors. "
    "Always verify quotations, page numbers, and conclusions "
    "against the original paper."
)

# -----------------------------
# GEMINI CONNECTION
# -----------------------------

def get_gemini_client():
    api_key = st.secrets.get("GEMINI_API_KEY")

    if not api_key:
        st.error(
            "Gemini API key not found. Check your Streamlit Secrets."
        )
        st.stop()

    return genai.Client(api_key=api_key)


# -----------------------------
# PDF TEXT EXTRACTION
# -----------------------------

def extract_pdf(uploaded_file):
    pages = []

    with fitz.open(
        stream=uploaded_file.getvalue(),
        filetype="pdf"
    ) as document:

        for page_number, page in enumerate(document, start=1):
            page_text = page.get_text()

            pages.append({
                "page": page_number,
                "text": page_text
            })

    return pages


def prepare_paper_text(pages, max_chars=45000):
    """
    Preserve PDF page labels so the AI can identify
    the page containing supporting evidence.
    """
    sections = []
    total_chars = 0

    for page in pages:
        section = (
            f"\n[PDF PAGE {page['page']}]\n"
            f"{page['text']}\n"
        )

        remaining = max_chars - total_chars

        if remaining <= 0:
            break

        sections.append(section[:remaining])
        total_chars += min(len(section), remaining)

    return "\n".join(sections)


# -----------------------------
# AI PAPER ANALYSIS
# -----------------------------

def analyze_paper(client, filename, pages):

    paper_text = prepare_paper_text(pages)

    prompt = f"""
You are a careful academic research assistant.

Analyze the research paper below.

Return a valid JSON object with these exact keys:

{{
  "Paper Title": "",
  "Authors": "",
  "Publication Year": "",
  "Research Objective": "",
  "Methodology": "",
  "Study Design": "",
  "Sample Size": "",
  "Key Findings": "",
  "Limitations": "",
  "Research Gaps": "",
  "Evidence for Key Findings": "",
  "Evidence for Limitations": "",
  "Evidence for Research Gaps": ""
}}

RULES:

1. Use only information supported by the supplied paper text.
2. Never invent authors, dates, statistics, quotations, or findings.
3. If information is missing, write "Not clearly reported".
4. Keep answers concise and academically appropriate.
5. Distinguish author-reported information from your own inferences.
6. For evidence fields, provide a short verbatim quotation from
   the paper followed by its PDF page number.
7. Use page labels such as "PDF page 6" from the supplied text.
8. PDF page numbers refer to the numbered pages of the uploaded
   file, starting at page 1. They may differ from printed journal
   page numbers.
9. Copy evidence quotations exactly as they appear in the
   extracted text. Do not invent or reconstruct missing wording.
10. If the evidence cannot be located confidently, say
    "Evidence not located; manual verification required."
11. For research gaps, distinguish:
    - gaps explicitly identified by the paper's authors
    - potential gaps inferred from the paper
12. Do not present an inferred research gap as a fact.
13. If the text does not contain enough information, explain this.
14. Return valid JSON only, without Markdown fences.

SOURCE FILE: {filename}

PAPER TEXT:
{paper_text}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    )

    result = json.loads(response.text)

    expected_fields = [
        "Paper Title",
        "Authors",
        "Publication Year",
        "Research Objective",
        "Methodology",
        "Study Design",
        "Sample Size",
        "Key Findings",
        "Limitations",
        "Research Gaps",
        "Evidence for Key Findings",
        "Evidence for Limitations",
        "Evidence for Research Gaps",
    ]

    for field in expected_fields:
        result.setdefault(field, "Not clearly reported")

    result["Source File"] = filename

    return result


# -----------------------------
# MULTI-PAPER COMPARISON
# -----------------------------

def compare_papers(client, papers):

    summaries = []

    for paper in papers:
        summaries.append({
            "title": paper.get("Paper Title", ""),
            "authors": paper.get("Authors", ""),
            "objective": paper.get("Research Objective", ""),
            "methodology": paper.get("Methodology", ""),
            "design": paper.get("Study Design", ""),
            "findings": paper.get("Key Findings", ""),
            "limitations": paper.get("Limitations", ""),
            "gaps": paper.get("Research Gaps", ""),
            "finding_evidence": paper.get(
                "Evidence for Key Findings", ""
            ),
            "gap_evidence": paper.get(
                "Evidence for Research Gaps", ""
            ),
            "source_file": paper.get("Source File", ""),
        })

    prompt = f"""
You are an academic literature review assistant.

Compare the following extracted research paper information:

{json.dumps(summaries, ensure_ascii=False)}

Write a Markdown report with these headings:

## Common Themes
Identify themes supported by the supplied papers.

## Agreements
Identify findings that appear consistent, citing the paper
titles and relevant evidence where available.

## Differences
Compare findings, methods, study designs, and populations.

## Unresolved Inquiries
Describe questions the supplied papers do not adequately answer.

## Research Gaps
Distinguish gaps explicitly reported by authors from potential
gaps inferred by comparing the papers.

## Overall Synthesis
Write a concise, balanced preliminary literature synthesis.

## Evidence and Verification Notes
Identify important claims that require checking against the
original PDFs. Include available source filenames, quotations,
and PDF page references.

IMPORTANT:
- Do not invent citations, quotations, statistics, or page numbers.
- Use only evidence included in the supplied summaries.
- Distinguish evidence from interpretation.
- Similar topics
