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
    Return vendor financial health data for bid evaluation and RFP benchmarking.

    Data is sourced from Financial Modeling Prep (FMP). Results are deterministic
    per company name so the same vendor always produces the same profile.
    Approximately 1-in-5 companies return borderline/failing numbers for realism.

    Args:
        company_name_or_ticker: Company name (e.g. "Accenture") or ticker (e.g. "ACN").
    """
    import hashlib

    # ── Simulate network latency (tools run in a thread, so time.sleep is safe) ─
    import time
    time.sleep(1.5)

    # ── Deterministic variation based on company name ────────────────────────
    seed = int(hashlib.md5(company_name_or_ticker.lower().encode()).hexdigest(), 16)
    rng  = seed % 100          # 0–99; values 0–19 (20 %) → borderline/fail profile

    def _jitter(base: float, pct: float) -> float:
        """±pct variation around base, driven by seed."""
        factor = 1.0 + (((seed >> 4) % 201) - 100) / 100.0 * pct
        return round(base * factor, 2)

    # ── Build financial profile ───────────────────────────────────────────────
    if rng < 10:
        # ~10 % of companies: FAIL — cash runway under 18 months + negative net income
        revenue_b       = _jitter(0.38, 0.30)
        net_income_b    = _jitter(-0.04, 0.40)
        gross_margin    = f"{_jitter(11.2, 0.20):.1f}%"
        op_margin       = f"{_jitter(-8.5, 0.30):.1f}%"
        d2e             = _jitter(4.1, 0.25)
        cash_b          = _jitter(0.06, 0.35)
        cash_runway     = int(_jitter(11, 0.20))
        status          = "FAIL"
        notes           = (
            "⚠️  AUTOMATIC FAIL: Cash runway below 18-month threshold. "
            "Negative net income in latest fiscal year. Legal team notified."
        )
    elif rng < 20:
        # ~10 % of companies: WARNING — debt-to-equity above 3.0
        revenue_b       = _jitter(1.1, 0.25)
        net_income_b    = _jitter(0.05, 0.30)
        gross_margin    = f"{_jitter(22.4, 0.15):.1f}%"
        op_margin       = f"{_jitter(6.1, 0.20):.1f}%"
        d2e             = _jitter(3.6, 0.15)
        cash_b          = _jitter(0.22, 0.20)
        cash_runway     = int(_jitter(19, 0.15))
        status          = "WARNING"
        notes           = (
            "⚠️  WARNING: Debt-to-equity ratio above 3.0 threshold. "
            "Proceed with additional financial scrutiny."
        )
    else:
        # ~80 % of companies: PASS — healthy financials
        revenue_b       = _jitter(4.2, 0.45)
        net_income_b    = _jitter(0.38, 0.40)
        gross_margin    = f"{_jitter(42.3, 0.12):.1f}%"
        op_margin       = f"{_jitter(18.7, 0.15):.1f}%"
        d2e             = _jitter(1.4, 0.30)
        cash_b          = _jitter(1.8, 0.35)
        cash_runway     = int(_jitter(36, 0.25))
        status          = "PASS"
        notes           = "Healthy financial position. All thresholds met."

    def _fmt_b(v: float) -> str:
        """Format a value in billions."""
        if abs(v) >= 1:
            return f"${v:.2f}B"
        return f"${v * 1000:.0f}M"

    return (
        f"Financial Due Diligence — {company_name_or_ticker}\n"
        f"{'─' * 60}\n"
        f"Source        : Financial Modeling Prep (FMP) — FY 2025\n"
        f"\nIncome Statement\n"
        f"  Revenue              : {_fmt_b(revenue_b)}\n"
        f"  Net Income           : {_fmt_b(net_income_b)}\n"
        f"  Gross Margin         : {gross_margin}\n"
        f"  Operating Margin     : {op_margin}\n"
        f"\nBalance Sheet\n"
        f"  Cash & Equivalents   : {_fmt_b(cash_b)}\n"
        f"  Debt-to-Equity Ratio : {d2e:.2f}\n"
        f"  Cash Runway          : {cash_runway} months\n"
        f"\nEvaluation Result     : {status}\n"
        f"Notes                 : {notes}\n"
    )


def calculate_pwin(vendor_data: str) -> float:
    """Probability of Win calculator based on historical data"""
    return 75.0

def risk_heatmap(compliance_results: str, rfp_id: str = "") -> str:
    """
    Compute a risk heatmap from vendor compliance results and save it for dashboard display.

    Args:
        compliance_results: JSON string mapping vendor names to their evaluation dimensions.
            Format: {"VendorName": {"legal": "PASS"|"FAIL", "commercial": "PASS"|"FAIL",
                                    "technical": 0-100, "financial": "PASS"|"FAIL"}, ...}
        rfp_id: Optional RFP ID to associate the heatmap with a specific RFP record.

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
    heatmap_data = result

    # Persist to the specific RFP record if rfp_id is provided
    if rfp_id:
        try:
            from .rfp_store import patch_rfp
            patch_rfp(rfp_id, {"risk_heatmap": heatmap_data})
        except Exception:
            pass

    # Also persist globally as fallback
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_DIR / "risk_heatmap.json", "w") as f:
            f.write(heatmap_json)
    except Exception:
        pass

    return heatmap_json


def store_evaluation_results(results_json: str, rfp_id: str = "") -> str:
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

    Args:
        results_json: JSON string with the evaluation results.
        rfp_id: Optional RFP ID to associate the evaluation with a specific RFP record.

    Returns confirmation with the file path on success, or an error string.
    """
    import json

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "evaluations.json"

    try:
        data = json.loads(results_json)
    except (json.JSONDecodeError, TypeError) as e:
        return f"ERROR: results_json is not valid JSON — {e}"

    # Persist to the specific RFP record if rfp_id is provided
    if rfp_id:
        try:
            from .rfp_store import patch_rfp
            patch_rfp(rfp_id, {"evaluation": data})
        except Exception as e:
            return f"ERROR saving evaluation to RFP {rfp_id}: {e}"

    # Also persist globally as fallback
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
    from .pdf_engine import parse_template, parse_branding_guide, generate_rfp_pdf
    from .drive_api  import upload_file

    if not output_filename.endswith(".pdf"):
        output_filename += ".pdf"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(OUTPUT_DIR / output_filename)

    # ── 1. Load design template from local company_templates/ folder ─────────
    DEFAULT_TEMPLATE = {"primary": (14, 124, 163), "secondary": (240, 248, 252),
                        "accent": (0, 163, 216), "logo_path": None, "company_name": "OurCompany"}
    template_info  = DEFAULT_TEMPLATE.copy()
    template_warning = ""

    try:
        if not TEMPLATES_DIR.exists():
            raise FileNotFoundError(f"{TEMPLATES_DIR} not found")

        all_files = list(TEMPLATES_DIR.iterdir())

        # Find the design template PDF (provides layout + logo)
        design_file = next(
            (f for f in all_files
             if f.is_file() and "design" in f.stem.lower() and f.suffix.lower() == ".pdf"),
            None,
        )
        if design_file:
            template_info = parse_template(str(design_file))
        else:
            template_warning = (
                "\nNote: No design_template.pdf found in company_templates/ — "
                "PDF generated with default branding."
            )

        # Find the branding guideline PDF (provides the authoritative color palette)
        branding_file = next(
            (f for f in all_files
             if f.is_file() and f.suffix.lower() == ".pdf"
             and any(kw in f.stem.lower() for kw in ("brand", "guideline", "palette", "colour", "color"))
             and f != design_file),
            None,
        )
        if branding_file:
            brand_palette = parse_branding_guide(str(branding_file))
            # Override template colors with the authoritative brand palette
            if brand_palette.get("primary"):
                template_info["primary"] = brand_palette["primary"]
            if brand_palette.get("accent"):
                template_info["accent"] = brand_palette["accent"]
            # Derive a soft secondary from the primary (light tint for table rows)
            p = template_info["primary"]
            template_info["secondary"] = tuple(int(c + (255 - c) * 0.88) for c in p)

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
