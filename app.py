import streamlit as st
import fitz
import pandas as pd
import json
import re
from io import BytesIO
from google import genai
from supabase import create_client

# =========================================================
# PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="ScholarPilot",
    page_icon="🎓",
    layout="wide",
)

# =========================================================
# SUPABASE AUTHENTICATION SETUP
# =========================================================
def get_supabase_client():
    """Create one Supabase client per Streamlit browser session."""
    if "scholarpilot_supabase" in st.session_state:
        return st.session_state["scholarpilot_supabase"]

    try:
        config = st.secrets.get("supabase", {})
        supabase_url = config.get("url", st.secrets.get("SUPABASE_URL", ""))
        supabase_key = config.get("key", st.secrets.get("SUPABASE_KEY", ""))
        if not supabase_url or not supabase_key:
            return None
        client = create_client(supabase_url, supabase_key)
        st.session_state["scholarpilot_supabase"] = client
        return client
    except Exception as error:
        st.session_state["scholarpilot_auth_setup_error"] = str(error)
        return None


def get_response_user(response):
    """Get a user object from Supabase auth response versions."""
    user = getattr(response, "user", None)
    if user is not None:
        return user
    session = getattr(response, "session", None)
    return getattr(session, "user", None) if session is not None else None


def user_details(user):
    if user is None:
        return None
    return {
        "id": getattr(user, "id", ""),
        "email": getattr(user, "email", "") or "",
    }


supabase = get_supabase_client()

# Supabase sends users back to this app with a short-lived PKCE auth code.
# The same client is kept in Streamlit session state so it can exchange the code.
if supabase is not None:
    try:
        oauth_code = st.query_params.get("code")
        if oauth_code:
            auth_response = supabase.auth.exchange_code_for_session({"auth_code": oauth_code})
            oauth_user = get_response_user(auth_response)
            if oauth_user is None:
                current_session = supabase.auth.get_session()
                oauth_user = getattr(current_session, "user", None) if current_session else None
            if oauth_user is not None:
                st.session_state["scholarpilot_user"] = user_details(oauth_user)
                st.session_state["show_workspace"] = True
            st.query_params.clear()
    except Exception as error:
        st.session_state["scholarpilot_oauth_error"] = (
            "Google sign-in could not be completed. Please try signing in again. "
            f"Details: {error}"
        )
        try:
            st.query_params.clear()
        except Exception:
            pass


# =========================================================
# PREMIUM LANDING PAGE
# =========================================================
if "show_workspace" not in st.session_state:
    st.session_state.show_workspace = False

if not st.session_state.show_workspace:
    st.markdown(
        """
        <style>
        .sp-hero {
            position: relative;
            overflow: hidden;
            text-align: center;
            padding: 76px 20px 42px;
            border-radius: 24px;
            background: radial-gradient(ellipse at 50% 12%, #302451 0%, #15182D 46%, #0B1020 100%);
            border: 1px solid #353052;
            margin: 6px 0 20px;
        }
        .sp-watermark {
            position: absolute;
            top: 12px;
            left: 0;
            width: 100%;
            font-size: clamp(42px, 11vw, 112px);
            line-height: 1.1;
            font-weight: 900;
            letter-spacing: 3px;
            color: #A78BFA;
            opacity: 0.12;
            text-shadow: 2px 2px 0 #302454, 5px 5px 0 #211A3C, 0 0 28px #8B5CF6;
            pointer-events: none;
            white-space: nowrap;
        }
        .sp-content { position: relative; z-index: 1; }
        .sp-badge {
            display: inline-block;
            padding: 7px 14px;
            border: 1px solid #6552A8;
            border-radius: 30px;
            color: #D8CCFF;
            background: rgba(33, 26, 60, 0.85);
            font-size: 13px;
            margin: 12px 0 22px;
        }
        .sp-title {
            font-size: clamp(30px, 5vw, 54px);
            font-weight: 800;
            line-height: 1.15;
            color: #F8FAFC;
            margin-bottom: 18px;
        }
        .sp-title span { color: #B7A0FF; }
        .sp-description {
            max-width: 680px;
            margin: 0 auto;
            color: #CBD5E1;
            font-size: 17px;
            line-height: 1.8;
        }
        .sp-features {
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 30px;
        }
        .sp-feature {
            background: rgba(23, 29, 49, 0.9);
            border: 1px solid #303A55;
            border-radius: 12px;
            padding: 13px 16px;
            color: #E2E8F0;
            font-size: 14px;
        }
        .sp-signature {
            margin-top: 32px;
            color: #B7A0FF;
            font-size: 12px;
            letter-spacing: 2px;
        }
        [data-testid="stButton"] button {
            border-radius: 12px;
            min-height: 50px;
            font-weight: 700;
        }
        </style>

        <div class="sp-hero">
            <div class="sp-watermark">KAgger☕</div>
            <div class="sp-content">
                <div class="sp-badge">✦ YOUR AI RESEARCH COMPANION</div>
                <div class="sp-title">
                    Turn Research Papers<br>
                    Into <span>Meaningful Insights.</span>
                </div>
                <div class="sp-description">
                    Analyze academic papers, discover key findings,
                    identify research gaps, and organize your literature
                    review in one intelligent workspace.
                </div>
                <div class="sp-features">
                    <div class="sp-feature">📄 AI Paper Analysis</div>
                    <div class="sp-feature">🔎 Evidence &amp; Page References</div>
                    <div class="sp-feature">📚 Literature Review Matrix</div>
                </div>
                <div class="sp-signature">DESIGNED WITH PURPOSE · SCHOLARPILOT</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    if st.button(
        "🚀 Start Researching",
        type="primary",
        use_container_width=True,
        key="start_researching",
    ):
        st.session_state.show_workspace = True
        st.rerun()

    st.caption(
        "AI-assisted research analysis. Always verify important findings "
        "against original papers."
    )
    st.stop()

# =========================================================
# AUTHENTICATION GATE FOR THE RESEARCH WORKSPACE
# =========================================================
if supabase is None:
    st.error(
        "ScholarPilot sign-in is not configured yet. Please check the Supabase "
        "URL and publishable key in Streamlit Secrets."
    )
    setup_error = st.session_state.get("scholarpilot_auth_setup_error")
    if setup_error:
        st.caption(f"Setup detail: {setup_error}")
    st.stop()

# Recover a session already held by this browser's Supabase client.
if not st.session_state.get("scholarpilot_user"):
    try:
        current_session = supabase.auth.get_session()
        current_user = getattr(current_session, "user", None) if current_session else None
        if current_user is not None:
            st.session_state["scholarpilot_user"] = user_details(current_user)
    except Exception:
        pass

signed_in_user = st.session_state.get("scholarpilot_user")
if not signed_in_user:
    st.title("🔐 Sign in to ScholarPilot")
    st.write("Create an account or sign in to open your research workspace.")

    oauth_error = st.session_state.pop("scholarpilot_oauth_error", None)
    if oauth_error:
        st.error(oauth_error)

    login_tab, signup_tab = st.tabs(["Sign in", "Create account"])
    with login_tab:
        with st.form("scholarpilot_login_form"):
            login_email = st.text_input("Email address", key="sp_login_email")
            login_password = st.text_input(
                "Password", type="password", key="sp_login_password"
            )
            login_submitted = st.form_submit_button(
                "Sign in with email", type="primary", use_container_width=True
            )
        if login_submitted:
            try:
                response = supabase.auth.sign_in_with_password(
                    {"email": login_email.strip(), "password": login_password}
                )
                user = get_response_user(response)
                if user is None:
                    session = getattr(response, "session", None)
                    user = getattr(session, "user", None) if session else None
                if user is None:
                    st.error("Sign-in did not return a user. Please try again.")
                else:
                    st.session_state["scholarpilot_user"] = user_details(user)
                    st.session_state["show_workspace"] = True
                    st.session_state.pop("scholarpilot_results", None)
                    st.session_state.pop("scholarpilot_comparison", None)
                    st.rerun()
            except Exception as error:
                st.error(f"Sign-in failed. Check your email and password. ({error})")

    with signup_tab:
        with st.form("scholarpilot_signup_form"):
            signup_email = st.text_input("Email address", key="sp_signup_email")
            signup_password = st.text_input(
                "Create password (at least 8 characters)",
                type="password",
                key="sp_signup_password",
            )
            signup_confirm = st.text_input(
                "Confirm password", type="password", key="sp_signup_confirm"
            )
            signup_submitted = st.form_submit_button(
                "Create account", type="primary", use_container_width=True
            )
        if signup_submitted:
            if not signup_email.strip():
                st.warning("Enter your email address.")
            elif len(signup_password) < 8:
                st.warning("Your password must be at least 8 characters long.")
            elif signup_password != signup_confirm:
                st.warning("The passwords do not match.")
            else:
                try:
                    response = supabase.auth.sign_up(
                        {"email": signup_email.strip(), "password": signup_password}
                    )
                    user = get_response_user(response)
                    session = getattr(response, "session", None)
                    if user is not None and session is not None:
                        st.session_state["scholarpilot_user"] = user_details(user)
                        st.session_state["show_workspace"] = True
                        st.rerun()
                    else:
                        st.success(
                            "Account request received. Check your email for a "
                            "confirmation link, then return here to sign in."
                        )
                except Exception as error:
                    st.error(f"Could not create your account: {error}")

    st.divider()
    st.markdown("**Or sign in with Google**")
    if st.button("Continue with Google", use_container_width=True):
        try:
            app_url = "https://scholarpilot-8nz8pgthwr6ngbd3z5wgda.streamlit.app/"
            oauth_response = supabase.auth.sign_in_with_oauth(
                {
                    "provider": "google",
                    "options": {"redirect_to": app_url},
                }
            )
            oauth_url = getattr(oauth_response, "url", None)
            if oauth_url is None and isinstance(oauth_response, dict):
                oauth_data = oauth_response.get("data", oauth_response)
                oauth_url = oauth_data.get("url") if isinstance(oauth_data, dict) else None
            if oauth_url:
                st.session_state["scholarpilot_google_oauth_url"] = oauth_url
            else:
                st.error("Supabase did not return a Google sign-in link. Please try again.")
        except Exception as error:
            st.error(f"Could not start Google sign-in: {error}")

    oauth_url = st.session_state.get("scholarpilot_google_oauth_url")

if oauth_url:
    st.markdown(
        f"""
        <a href="{oauth_url}" target="_self"
           style="
               display: block;
               text-align: center;
               padding: 14px;
               background-color: #6D4AFF;
               color: white;
               text-decoration: none;
               border-radius: 10px;
               font-weight: bold;
               margin-top: 10px;
           ">
           Continue to Google
        </a>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "After Google confirms your account, "
        "you will return to ScholarPilot."
    )

st.stop()

# Clear any in-memory research results if the signed-in account changes.
current_user_id = signed_in_user.get("id")
previous_user_id = st.session_state.get("scholarpilot_active_user_id")
if previous_user_id and current_user_id != previous_user_id:
    st.session_state.pop("scholarpilot_results", None)
    st.session_state.pop("scholarpilot_comparison", None)
st.session_state["scholarpilot_active_user_id"] = current_user_id

# =========================================================
# WORKSPACE HEADER / RETURN HOME
# =========================================================
top_left, top_right = st.columns([4, 1])
with top_left:
    st.title("🎓 ScholarPilot")
    st.subheader("Your AI-Powered Research Paper Assistant")
    st.markdown(
        "Analyze research papers, organize findings, identify research gaps, "
        "and compare studies using AI."
    )
    st.caption(f"Signed in as: {signed_in_user.get('email', 'ScholarPilot user')}")
with top_right:
    if st.button("🚪 Sign out", use_container_width=True):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        for key in (
            "scholarpilot_user", "scholarpilot_active_user_id",
            "scholarpilot_results", "scholarpilot_comparison",
            "scholarpilot_google_oauth_url",
        ):
            st.session_state.pop(key, None)
        st.session_state.show_workspace = False
        st.rerun()
    if st.button("🏠 Home", use_container_width=True):
        st.session_state.show_workspace = False
        st.rerun()

# =========================================================
# GEMINI CLIENT
# =========================================================
def get_gemini_client():
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            st.error(
                "Gemini API key not found. Please check your Streamlit app Secrets."
            )
            return None
        return genai.Client(api_key=api_key)
    except Exception as error:
        st.error(f"Could not connect to Gemini: {error}")
        return None

# =========================================================
# PDF EXTRACTION
# =========================================================
def extract_pdf(uploaded_file):
    """Extract text from every PDF page."""
    try:
        pdf_bytes = uploaded_file.getvalue()
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page_index, page in enumerate(document):
            pages.append({
                "page": page_index + 1,
                "text": page.get_text("text").strip(),
            })
        document.close()
        return pages
    except Exception as error:
        st.error(f"Could not read {uploaded_file.name}: {error}")
        return []

def prepare_paper_text(pages, max_chars=45000):
    """Prepare PDF text while retaining PDF page numbers."""
    sections = []
    remaining = max_chars
    for page in pages:
        page_text = page.get("text", "")
        if not page_text:
            continue
        section = f"\n[PDF PAGE {page['page']}]\n{page_text}\n"
        if len(section) > remaining:
            if remaining > 100:
                sections.append(section[:remaining])
            break
        sections.append(section)
        remaining -= len(section)
        if remaining <= 0:
            break
    return "\n".join(sections)

# =========================================================
# GEMINI RESPONSE HELPERS
# =========================================================
def clean_json_response(response_text):
    """Remove Markdown code fences from JSON if present."""
    text = response_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

def generate_content(client, prompt, json_mode=False):
    """Generate content using Gemini."""
    config = {"temperature": 0.1}
    if json_mode:
        config["response_mime_type"] = "application/json"
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=config,
    )
    if not response.text:
        raise ValueError("Gemini returned an empty response.")
    return response.text

# =========================================================
# ANALYZE INDIVIDUAL RESEARCH PAPER
# =========================================================
def analyze_paper(client, filename, pages):
    paper_text = prepare_paper_text(pages)
    if not paper_text.strip():
        raise ValueError(
            "No readable text was extracted from this PDF. "
            "The document may be scanned and require OCR."
        )

    prompt = f"""
You are ScholarPilot, an academic research assistant.
Analyze the supplied research paper.

Return ONLY valid JSON. Do not use Markdown code fences.
Use exactly these keys:
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

INSTRUCTIONS:
1. Use information supported by the supplied paper.
2. Do not invent authors, dates, statistics, or results.
3. If information is unavailable, write "Not reported".
4. Summarize findings clearly and accurately.
5. Distinguish author-reported limitations from your own interpretation.
6. Distinguish author-reported research gaps from potential gaps inferred from the paper.
7. For evidence fields, provide short, exact quotations from the supplied paper text when possible.
8. Include the corresponding PDF page number for each quote.
9. Format quotations like this: "Exact quotation from the paper" (PDF p. 4)
10. Only use page numbers shown in the supplied text.
11. Never invent quotations or page references.
12. If suitable evidence is unavailable, explain that.
13. PDF page numbers refer to actual PDF page order and may differ from printed page numbers.

SOURCE FILE: {filename}

PAPER TEXT:
{paper_text}
"""
    response_text = generate_content(client, prompt, json_mode=True)
    cleaned_text = clean_json_response(response_text)
    try:
        result = json.loads(cleaned_text)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Gemini returned a response that could not be read as JSON: {error}"
        )

    expected_fields = [
        "Paper Title", "Authors", "Publication Year", "Research Objective",
        "Methodology", "Study Design", "Sample Size", "Key Findings",
        "Limitations", "Research Gaps", "Evidence for Key Findings",
        "Evidence for Limitations", "Evidence for Research Gaps",
    ]
    for field in expected_fields:
        result.setdefault(field, "Not reported")
    result["Source File"] = filename
    return result

# =========================================================
# LITERATURE REVIEW MATRIX
# =========================================================
def build_literature_matrix(papers):
    fields = [
        "Source File", "Paper Title", "Authors", "Publication Year",
        "Research Objective", "Methodology", "Study Design", "Sample Size",
        "Key Findings", "Limitations", "Research Gaps",
        "Evidence for Key Findings", "Evidence for Limitations",
        "Evidence for Research Gaps",
    ]
    rows = []
    for paper in papers:
        rows.append({field: paper.get(field, "Not reported") for field in fields})
    return pd.DataFrame(rows, columns=fields)

# =========================================================
# EXCEL EXPORT
# =========================================================
def create_excel_file(dataframe):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Literature Matrix")
    output.seek(0)
    return output.getvalue()

# =========================================================
# COMPARE RESEARCH PAPERS
# =========================================================
def compare_papers(client, papers):
    summary_fields = [
        "Source File", "Paper Title", "Authors", "Publication Year",
        "Research Objective", "Methodology", "Study Design", "Sample Size",
        "Key Findings", "Limitations", "Research Gaps",
        "Evidence for Key Findings", "Evidence for Limitations",
        "Evidence for Research Gaps",
    ]
    summaries = [
        {field: paper.get(field, "") for field in summary_fields}
        for paper in papers
    ]
    prompt = f"""
You are an academic literature review assistant.
Compare the following research paper summaries:
{json.dumps(summaries, ensure_ascii=False, indent=2)}

Write a Markdown report with these sections:
## Common Themes
Identify themes supported by the supplied papers.
## Agreements
Describe findings that appear consistent, citing paper titles and available evidence.
## Differences
Compare findings, methods, study designs, and populations.
## Unresolved Inquiries
Identify questions the papers do not adequately answer.
## Research Gaps
Distinguish gaps reported by authors from potential gaps inferred by comparing papers.
## Overall Synthesis
Write a balanced preliminary literature synthesis.
## Evidence and Verification Notes
Identify claims that should be checked against original PDFs. Include available quotations and PDF page references.

RULES:
- Do not invent citations, quotations, statistics, or page numbers.
- Use only the supplied summaries.
- Distinguish evidence from interpretation.
- Similar topics do not automatically mean studies agree.
- State when information is insufficient.
- Do not claim that a research gap is definitive without evidence.
- This synthesis does not replace reading the original papers.
"""
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config={"temperature": 0.2},
    )
    if not response.text:
        raise ValueError("Gemini did not return a comparison report.")
    return response.text

# =========================================================
# MAIN APPLICATION: UPLOAD PAPERS
# =========================================================
st.divider()
st.header("📄 Upload Research Papers")
uploaded_files = st.file_uploader(
    "Choose one or more research paper PDFs",
    type=["pdf"],
    accept_multiple_files=True,
    help="For best results, use PDFs containing selectable text. Scanned PDFs may require OCR.",
)

if uploaded_files:
    st.info(f"{len(uploaded_files)} PDF file(s) selected.")
    analyze_button = st.button(
        "🚀 Analyze Research Papers",
        type="primary",
        use_container_width=True,
    )
    if analyze_button:
        client = get_gemini_client()
        if client:
            results = []
            progress = st.progress(0)
            status = st.empty()
            total_files = len(uploaded_files)

            for index, uploaded_file in enumerate(uploaded_files):
                status.write(
                    f"Analyzing {index + 1} of {total_files}: {uploaded_file.name}"
                )
                pages = extract_pdf(uploaded_file)
                if not pages:
                    st.warning(
                        f"Skipping {uploaded_file.name}: no pages could be extracted."
                    )
                    progress.progress((index + 1) / total_files)
                    continue
                try:
                    with st.spinner(f"Analyzing {uploaded_file.name}..."):
                        paper_result = analyze_paper(
                            client, uploaded_file.name, pages
                        )
                    results.append(paper_result)
                    st.success(f"Successfully analyzed {uploaded_file.name}")
                except Exception as error:
                    st.error(f"Could not analyze {uploaded_file.name}: {error}")
                progress.progress((index + 1) / total_files)

            status.empty()
            st.session_state["scholarpilot_results"] = results
            st.session_state.pop("scholarpilot_comparison", None)
            if results:
                st.success(
                    f"Analysis complete! {len(results)} paper(s) processed."
                )
            else:
                st.warning("No papers were analyzed successfully.")

# =========================================================
# DISPLAY RESULTS AND DASHBOARD
# =========================================================
papers = st.session_state.get("scholarpilot_results", [])

if papers:
    st.divider()
    st.header("📊 Research Dashboard")
    st.write("An overview of your analyzed research collection.")

    def has_reported_information(value):
        if value is None:
            return False
        normalized = str(value).strip().lower()
        return normalized not in (
            "", "not reported", "none", "n/a", "not available"
        )

    total_papers = len(papers)
    findings_count = sum(
        1 for paper in papers
        if has_reported_information(paper.get("Key Findings", ""))
    )
    limitations_count = sum(
        1 for paper in papers
        if has_reported_information(paper.get("Limitations", ""))
    )
    gaps_count = sum(
        1 for paper in papers
        if has_reported_information(paper.get("Research Gaps", ""))
    )

    col1, col2 = st.columns(2)
    with col1:
        st.metric("📄 Papers Analyzed", total_papers)
    with col2:
        st.metric("🔍 Papers With Key Findings", findings_count)
    col3, col4 = st.columns(2)
    with col3:
        st.metric("⚠️ Papers With Limitations", limitations_count)
    with col4:
        st.metric("🎯 Papers With Research Gaps", gaps_count)

    st.caption(
        "Counts reflect information extracted by AI. Verify important claims "
        "against the original papers."
    )

    st.divider()
    st.header("📚 Literature Review Matrix")
    matrix = build_literature_matrix(papers)
    st.dataframe(matrix, use_container_width=True, hide_index=True)
    excel_data = create_excel_file(matrix)
    st.download_button(
        label="📥 Download Literature Matrix (Excel)",
        data=excel_data,
        file_name="scholarpilot_literature_matrix.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.divider()
    st.header("🔍 Review Individual Papers")
    for index, paper in enumerate(papers):
        title = paper.get("Paper Title", "Untitled paper")
        filename = paper.get("Source File", f"Paper {index + 1}")
        with st.expander(f"📄 {title} — {filename}", expanded=False):
            st.markdown(f"**Source file:** {filename}")
            st.markdown("### Paper Information")
            display_fields = [
                "Authors", "Publication Year", "Research Objective",
                "Methodology", "Study Design", "Sample Size",
                "Key Findings", "Limitations", "Research Gaps",
            ]
            for field in display_fields:
                st.markdown(f"**{field}**")
                st.write(paper.get(field, "Not reported"))
            st.markdown("### Evidence and Page References")
            evidence_fields = [
                "Evidence for Key Findings", "Evidence for Limitations",
                "Evidence for Research Gaps",
            ]
            for field in evidence_fields:
                st.markdown(f"**{field}**")
                st.write(paper.get(field, "Not reported"))

    st.divider()
    st.header("⚖️ Compare Research Papers")
    if len(papers) >= 2:
        st.write(
            "Compare papers to explore shared themes, agreements, differences, "
            "and research gaps."
        )
        if st.button(
            "Generate Research Comparison",
            type="primary",
            use_container_width=True,
        ):
            client = get_gemini_client()
            if client:
                try:
                    with st.spinner("Comparing your research papers..."):
                        comparison = compare_papers(client, papers)
                    st.session_state["scholarpilot_comparison"] = comparison
                except Exception as error:
                    st.error(f"Could not compare the papers: {error}")

        comparison = st.session_state.get("scholarpilot_comparison", "")
        if comparison:
            st.markdown(comparison)
            st.download_button(
                label="📥 Download Comparison Report",
                data=comparison,
                file_name="scholarpilot_comparison.md",
                mime="text/markdown",
                use_container_width=True,
            )
    else:
        st.info(
            "Analyze at least two papers to use the research comparison feature."
        )

    st.divider()
    if st.button("🗑️ Clear Results"):
        st.session_state.pop("scholarpilot_results", None)
        st.session_state.pop("scholarpilot_comparison", None)
        st.rerun()

# =========================================================
# FOOTER
# =========================================================
st.divider()
st.caption(
    "ScholarPilot | AI-assisted academic research analysis. Always verify "
    "quotations, page numbers, and interpretations against the original papers."
)
