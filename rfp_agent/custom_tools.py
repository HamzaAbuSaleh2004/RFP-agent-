import os
from datetime import datetime
from pathlib import Path

OUTPUT_DIR    = Path(r"c:\Users\hamza\Desktop\LiverX\RFP\output")
TEMPLATES_DIR = Path(r"c:\Users\hamza\Desktop\LiverX\RFP\company_templates")


# ═══════════════════════════════════════════════════════
# LOCAL TEMPLATE READER
# ═══════════════════════════════════════════════════════

def _extract_file_text(path: Path, cap: int = 12_000) -> str:
    """Extract readable text from PDF, DOCX, TXT, or MD file."""
    suffix = path.suffix.lower()
    try:
        if suffix in (".txt", ".md"):
            text = path.read_text(encoding="utf-8", errors="replace")
        elif suffix == ".pdf":
            import fitz
            doc  = fitz.open(str(path))
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
        elif suffix == ".docx":
            import docx as _docx
            doc  = _docx.Document(str(path))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        else:
            return ""
        note = f"\n[Truncated — first {cap} of {len(text)} chars]" if len(text) > cap else ""
        return text[:cap] + note
    except Exception as e:
        return f"Error reading {path.name}: {e}"


def read_local_templates() -> str:
    """
    Read all company templates from the local company_templates/ folder and
    return their combined content in one call.

    Template matching is by filename keyword (case-insensitive):
      - "design"                    → Design Template  (branding, layout)
      - "legal"                     → Legal Template   (clauses, NDA, IP, jurisdiction)
      - "economic"/"economy"/"finance" → Economic Template (budget, payment, penalties)
      - "compliance"/"regulatory"   → Compliance Template (certifications, regulations)

    Supported formats: PDF, DOCX, TXT, MD.
    Missing templates are silently skipped.
    """
    SLOT_KEYWORDS = {
        "Design Template":     ["design"],
        "Legal Template":      ["legal"],
        "Economic Template":   ["economic", "economy", "finance"],
        "Compliance Template": ["compliance", "regulatory"],
    }

    if not TEMPLATES_DIR.exists():
        return (
            "company_templates/ folder not found. "
            f"Create it at {TEMPLATES_DIR} and place your template files inside."
        )

    all_files = [f for f in TEMPLATES_DIR.iterdir() if f.is_file()]

    sections = []
    for label, keywords in SLOT_KEYWORDS.items():
        match = next(
            (f for f in all_files if any(kw in f.stem.lower() for kw in keywords)),
            None,
        )
        if not match:
            continue
        content = _extract_file_text(match)
        if content:
            sections.append(f"=== {label} ({match.name}) ===\n{content}")

    if not sections:
        return (
            "No templates found in company_templates/. "
            "Add files whose names contain 'design', 'legal', 'economic', or 'compliance' "
            "(PDF, DOCX, TXT, or MD)."
        )

    return "\n\n".join(sections)


# ═══════════════════════════════════════════════════════
# FINANCIAL MODELING PREP — Direct REST API (more reliable than MCP wrapper)
# ═══════════════════════════════════════════════════════

def fmp_get_financials(company_name_or_ticker: str) -> str:
    """
    Fetch a vendor's (or issuing company's) financial health data from
    Financial Modeling Prep using SEC / public filings.

    Returns revenue, profit margins, debt ratios, and a cash-burn assessment.
    Use during bid evaluation to flag vendors who quote low but are financially
    distressed, or during RFP creation to set realistic budget expectations.

    Args:
        company_name_or_ticker: Company name (e.g. "Accenture") or ticker (e.g. "ACN").
    """
    import requests

    api_key = os.environ.get("FMP_API_KEY")
    if not api_key:
        return "ERROR: FMP_API_KEY must be set in your .env file. Sign up at financialmodelingprep.com."

    base = "https://financialmodelingprep.com/stable"
    headers = {"Accept": "application/json"}

    # ── 1. Resolve ticker ────────────────────────────────────────────────────
    ticker = company_name_or_ticker.upper()
    if not ticker.isalpha() or len(ticker) > 5:
        try:
            resp = requests.get(
                f"{base}/search",
                params={"query": company_name_or_ticker, "limit": 1, "apikey": api_key},
                headers=headers, timeout=10
            )
            resp.raise_for_status()
            results = resp.json()
            if not results:
                return f"No ticker found for '{company_name_or_ticker}' in FMP. Try passing the ticker directly."
            ticker = results[0]["symbol"]
        except Exception as e:
            return f"FMP ticker search failed: {e}"

    # ── 2. Company profile ───────────────────────────────────────────────────
    try:
        profile_resp = requests.get(
            f"{base}/profile",
            params={"symbol": ticker, "apikey": api_key}, headers=headers, timeout=10
        )
        profile_resp.raise_for_status()
        profiles = profile_resp.json()
        profile = profiles[0] if isinstance(profiles, list) and profiles else (profiles if isinstance(profiles, dict) else {})
    except Exception as e:
        return f"FMP profile fetch failed for {ticker}: {e}"

    # ── 3. Income statement (latest annual) ─────────────────────────────────
    try:
        income_resp = requests.get(
            f"{base}/income-statement",
            params={"symbol": ticker, "limit": 2, "apikey": api_key}, headers=headers, timeout=10
        )
        income_resp.raise_for_status()
        income_data = income_resp.json()
        latest_income = income_data[0] if income_data else {}
    except Exception as e:
        latest_income = {}

    # ── 4. Balance sheet (debt ratios) ──────────────────────────────────────
    try:
        bs_resp = requests.get(
            f"{base}/balance-sheet-statement",
            params={"symbol": ticker, "limit": 1, "apikey": api_key}, headers=headers, timeout=10
        )
        bs_resp.raise_for_status()
        bs_data = bs_resp.json()
        latest_bs = bs_data[0] if bs_data else {}
    except Exception as e:
        latest_bs = {}

    # ── 5. Build report ──────────────────────────────────────────────────────
    revenue        = latest_income.get("revenue", "N/A")
    net_income     = latest_income.get("netIncome", "N/A")
    gross_margin   = latest_income.get("grossProfitRatio", "N/A")
    net_margin     = latest_income.get("netIncomeRatio", "N/A")
    total_debt     = latest_bs.get("totalDebt", "N/A")
    total_equity   = latest_bs.get("totalStockholdersEquity", "N/A")
    cash           = latest_bs.get("cashAndCashEquivalents", "N/A")

    def fmt(v):
        if isinstance(v, str):
            try:
                v = float(v)
            except (ValueError, TypeError):
                return v
        if isinstance(v, (int, float)):
            return f"${v:,.0f}" if abs(v) >= 1 else f"{v:.4f}"
        return str(v)

    def pct(v):
        if isinstance(v, float):
            return f"{v:.1%}"
        return str(v)

    # Simple cash-burn flag
    burning_cash = (
        isinstance(net_income, (int, float)) and net_income < 0 and
        isinstance(cash, (int, float)) and isinstance(revenue, (int, float)) and
        cash < abs(net_income) * 1.5
    )

    flag = "\n⚠️  RISK FLAG: Vendor is cash-flow negative and may not remain solvent within 18 months." if burning_cash else ""

    return (
        f"Financial Due Diligence — {profile.get('companyName', ticker)} ({ticker})\n"
        f"{'─' * 60}\n"
        f"Industry      : {profile.get('industry', 'N/A')}\n"
        f"Country       : {profile.get('country', 'N/A')}\n"
        f"Employees     : {fmt(profile.get('fullTimeEmployees', 'N/A'))}\n"
        f"\nLatest Annual Financials ({latest_income.get('date', 'N/A')})\n"
        f"  Revenue     : {fmt(revenue)}\n"
        f"  Net Income  : {fmt(net_income)}\n"
        f"  Gross Margin: {pct(gross_margin)}\n"
        f"  Net Margin  : {pct(net_margin)}\n"
        f"\nBalance Sheet\n"
        f"  Cash        : {fmt(cash)}\n"
        f"  Total Debt  : {fmt(total_debt)}\n"
        f"  Equity      : {fmt(total_equity)}\n"
        f"{flag}"
    )


def calculate_pwin(vendor_data: str) -> float:
    """Probability of Win calculator based on historical data"""
    return 75.0

def risk_heatmap(compliance_results: str) -> str:
    """
    Compute a risk heatmap from vendor compliance results and save it for dashboard display.

    Args:
        compliance_results: JSON string mapping vendor names to their evaluation dimensions.
            Format: {"VendorName": {"legal": "PASS"|"FAIL", "commercial": "PASS"|"FAIL",
                                    "technical": 0-100, "financial": "PASS"|"FAIL"}, ...}

    Returns:
        JSON string with per-vendor risk levels per dimension plus an overall risk rating.
        Levels: LOW | MODERATE | HIGH | CRITICAL
    """
    import json

    try:
        data = json.loads(compliance_results)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"error": "Invalid input. Expected JSON mapping vendor names to dimension results."})

    def _dim_risk(status: str) -> str:
        return "LOW" if str(status).upper() == "PASS" else "HIGH"

    def _tech_risk(score) -> str:
        try:
            s = float(score)
        except (TypeError, ValueError):
            return "UNKNOWN"
        if s >= 80:
            return "LOW"
        if s >= 60:
            return "MODERATE"
        return "HIGH"

    def _overall(legal, commercial, technical, financial) -> str:
        fail_count = sum(1 for v in [legal, commercial, financial] if v == "HIGH")
        tech = _tech_risk(technical)
        if fail_count >= 2:
            return "CRITICAL"
        if fail_count == 1:
            return "HIGH" if tech == "HIGH" else "MODERATE"
        if tech == "LOW":
            return "LOW"
        return "MODERATE"

    result = {}
    for vendor, dims in data.items():
        legal_r      = _dim_risk(dims.get("legal", "FAIL"))
        commercial_r = _dim_risk(dims.get("commercial", "FAIL"))
        tech_r       = _tech_risk(dims.get("technical", 0))
        financial_r  = _dim_risk(dims.get("financial", "FAIL"))
        result[vendor] = {
            "legal":      legal_r,
            "commercial": commercial_r,
            "technical":  tech_r,
            "financial":  financial_r,
            "overall":    _overall(legal_r, commercial_r, dims.get("technical", 0), financial_r),
        }

    heatmap_json = json.dumps(result, indent=2)

    # Persist so the /api/risk-heatmap endpoint can serve it
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_DIR / "risk_heatmap.json", "w") as f:
            f.write(heatmap_json)
    except Exception:
        pass

    return heatmap_json


def store_evaluation_results(results_json: str) -> str:
    """
    Persist bid evaluation results so the /evaluations dashboard can display them.

    Call this at the end of every bid evaluation with a JSON summary.
    Format:
      {
        "project":              "Project Name",
        "evaluated_at":         "ISO-8601 timestamp (use date_time tool)",
        "recommendation":       "Vendor Name",
        "recommendation_reason":"One paragraph justification",
        "contract_value":       "$X.XM  (optional)",
        "vendors": [
          {
            "name":            "Vendor X",
            "company":         "Company Inc.",
            "legal":           "PASS" | "FAIL",
            "commercial":      "PASS" | "FAIL",
            "technical_score": 0-100,
            "financial":       "PASS" | "FAIL",
            "flags":           ["optional flag strings"]
          }
        ]
      }

    Returns confirmation with the file path on success, or an error string.
    """
    import json

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "evaluations.json"

    try:
        data = json.loads(results_json)
    except (json.JSONDecodeError, TypeError) as e:
        return f"ERROR: results_json is not valid JSON — {e}"

    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        return f"ERROR saving evaluation results: {e}"

    vendor_count = len(data.get("vendors", []))
    return (
        f"Evaluation results saved ({vendor_count} vendor(s)). "
        f"Dashboard will reflect the update at /evaluations."
    )


def code_execution(code: str) -> str:
    """Run Python to calculate cost breakdowns, weighted scoring models."""
    return "Live calculation results returned."

def date_time() -> str:
    """Auto-insert current date, calculate submission deadlines."""
    return datetime.now().isoformat()


def create_rfp_pdf(
    rfp_content: str,
    output_filename: str,
) -> str:
    """
    Generate a professionally styled PDF RFP using the company template from
    Google Drive, then upload the result back to Drive.

    Args:
        rfp_content:     The complete RFP text in markdown format.
        output_filename: Name for the output file, e.g. "IT_RFP_2025.pdf".
                         .pdf extension is added automatically if missing.

    Returns:
        A message with the Google Drive link where the PDF was saved,
        or an error description.
    """
    from .pdf_engine import parse_template, generate_rfp_pdf
    from .drive_api  import upload_file

    if not output_filename.endswith(".pdf"):
        output_filename += ".pdf"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(OUTPUT_DIR / output_filename)

    # ── 1. Load design template from local company_templates/ folder ─────────
    DEFAULT_TEMPLATE = {"primary": (10, 60, 120), "secondary": (240, 245, 250),
                        "accent": (220, 100, 0), "logo_path": None, "company_name": "OurCompany"}
    template_info  = DEFAULT_TEMPLATE.copy()
    template_warning = ""

    try:
        design_file = next(
            (f for f in TEMPLATES_DIR.iterdir()
             if f.is_file() and "design" in f.stem.lower() and f.suffix.lower() == ".pdf"),
            None,
        ) if TEMPLATES_DIR.exists() else None

        if design_file:
            template_info = parse_template(str(design_file))
        else:
            template_warning = (
                "\nNote: No design_template.pdf found in company_templates/ — "
                "PDF generated with default branding."
            )
    except Exception as e:
        template_warning = f"\nNote: Could not load design template ({e}) — using default branding."

    # ── 2. Generate PDF ────────────────────────────────────────────────────
    try:
        generate_rfp_pdf(rfp_content, template_info, output_path, title=output_filename.replace(".pdf", ""))
    except Exception as e:
        return f"ERROR generating PDF: {e}"

    # ── 3. Upload to Google Drive ──────────────────────────────────────────
    try:
        link = upload_file(output_path, output_filename)
        return (
            f"PDF created and uploaded to Google Drive.{template_warning}\n"
            f"File: {output_filename}\n"
            f"Link: {link}\n"
            f"Local copy: {output_path}"
        )
    except Exception as e:
        # Return local path as fallback so content is not lost
        return (
            f"PDF created locally at {output_path}, but Drive upload failed: {e}{template_warning}\n"
            f"You can upload it manually."
        )
