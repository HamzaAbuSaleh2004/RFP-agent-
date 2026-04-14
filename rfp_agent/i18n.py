"""
Lightweight dict-based translation system for the RFP Director UI.
Supports two locales: "en" (English, LTR) and "ar" (Arabic, RTL).

Usage in Jinja2 templates:
    {{ t('nav.dashboard') }}          — uses locale already in context
    {{ t('nav.dashboard', 'ar') }}    — explicit locale

Usage in Python:
    from rfp_agent.i18n import t, is_rtl, get_locale_from_cookie
"""

from __future__ import annotations
from typing import Optional

# ── Translation table ─────────────────────────────────────────────────────────

_TRANSLATIONS: dict[str, dict[str, str]] = {

    # ── Navigation ────────────────────────────────────────────────────────────
    "nav.dashboard":    {"en": "Dashboard",    "ar": "لوحة التحكم"},
    "nav.documents":    {"en": "Documents",    "ar": "المستندات"},
    "nav.evaluations":  {"en": "Evaluations",  "ar": "التقييمات"},
    "nav.settings":     {"en": "Settings",     "ar": "الإعدادات"},
    "nav.flowchart":    {"en": "Flowchart",    "ar": "مخطط التدفق"},
    "nav.create_rfp":   {"en": "Create RFP",   "ar": "إنشاء طلب عروض"},

    # ── Page titles ───────────────────────────────────────────────────────────
    "page.dashboard":    {"en": "Enterprise Procurement Dashboard",  "ar": "لوحة تحكم المشتريات"},
    "page.create":       {"en": "New RFP",                          "ar": "طلب عروض جديد"},
    "page.chat":         {"en": "AI Assistant",                     "ar": "المساعد الذكي"},
    "page.documents":    {"en": "Documents",                        "ar": "المستندات"},
    "page.evaluations":  {"en": "Evaluations",                      "ar": "تقييم العروض"},
    "page.settings":     {"en": "Settings",                         "ar": "الإعدادات"},
    "page.editor":       {"en": "RFP Editor",                       "ar": "محرر طلب العروض"},

    # ── Dashboard headings ────────────────────────────────────────────────────
    "dashboard.welcome":     {"en": "Welcome back, Director.",             "ar": "مرحباً بعودتك، المدير."},
    "dashboard.efficiency":  {"en": "Your procurement pipeline is at 84% efficiency.",
                               "ar": "كفاءة خط المشتريات لديك تبلغ 84%."},
    "dashboard.pipeline":    {"en": "RFP Pipeline",                       "ar": "خط طلبات العروض"},

    # ── Stats cards ───────────────────────────────────────────────────────────
    "stats.active_rfps":         {"en": "Active RFPs",           "ar": "طلبات عروض نشطة"},
    "stats.pending_evaluations": {"en": "Pending Evaluations",   "ar": "تقييمات معلقة"},
    "stats.generated_docs":      {"en": "Generated Documents",   "ar": "مستندات تم إنشاؤها"},
    "stats.pdfs_drive":          {"en": "PDFs created and uploaded to Drive",
                                   "ar": "ملفات PDF تم إنشاؤها ورفعها إلى Drive"},

    # ── Filter tabs ───────────────────────────────────────────────────────────
    "filter.all":      {"en": "All",      "ar": "الكل"},
    "filter.draft":    {"en": "Draft",    "ar": "مسودة"},
    "filter.approved": {"en": "Approved", "ar": "معتمد"},
    "filter.done":     {"en": "Done",     "ar": "منتهي"},

    # ── Status labels ─────────────────────────────────────────────────────────
    "status.draft":    {"en": "Draft",    "ar": "مسودة"},
    "status.approved": {"en": "Approved", "ar": "معتمد"},
    "status.done":     {"en": "Done",     "ar": "منتهي"},

    # ── RFP card actions ──────────────────────────────────────────────────────
    "card.continue": {"en": "Continue", "ar": "متابعة"},
    "card.view":     {"en": "View",     "ar": "عرض"},
    "card.edit":     {"en": "Edit",     "ar": "تعديل"},
    "card.collaborators": {"en": "collaborator", "ar": "متعاون"},

    # ── Buttons ───────────────────────────────────────────────────────────────
    "btn.save":            {"en": "Save",             "ar": "حفظ"},
    "btn.save_changes":    {"en": "Save Changes",     "ar": "حفظ التغييرات"},
    "btn.save_draft":      {"en": "Save Draft",       "ar": "حفظ المسودة"},
    "btn.submit":          {"en": "Submit",           "ar": "إرسال"},
    "btn.cancel":          {"en": "Cancel",           "ar": "إلغاء"},
    "btn.approve":         {"en": "Approve",          "ar": "اعتماد"},
    "btn.create_rfp":      {"en": "Create New RFP",   "ar": "إنشاء طلب عروض جديد"},
    "btn.evaluate_bids":   {"en": "Evaluate Bids",    "ar": "تقييم العروض"},
    "btn.regen_pdf":       {"en": "Regenerate PDF",   "ar": "إعادة إنشاء PDF"},
    "btn.test_connection": {"en": "Test Connection",  "ar": "اختبار الاتصال"},
    "btn.preview":         {"en": "Preview",          "ar": "معاينة"},
    "btn.send":            {"en": "Send",             "ar": "إرسال"},

    # ── Form labels ───────────────────────────────────────────────────────────
    "form.title":          {"en": "RFP Title",        "ar": "عنوان طلب العروض"},
    "form.description":    {"en": "Description",      "ar": "الوصف"},
    "form.language":       {"en": "Language",         "ar": "اللغة"},
    "form.created_by":     {"en": "Created By",       "ar": "أنشئ بواسطة"},
    "form.invite":         {"en": "Invite Users",     "ar": "دعوة المستخدمين"},
    "form.search":         {"en": "Search RFPs, vendors, or docs…",
                             "ar": "ابحث عن طلبات عروض أو موردين أو مستندات…"},

    # ── Chat ──────────────────────────────────────────────────────────────────
    "chat.placeholder":    {"en": "Type a message…",  "ar": "اكتب رسالة…"},
    "chat.thinking":       {"en": "Thinking…",        "ar": "جارٍ التفكير…"},

    # ── Settings ──────────────────────────────────────────────────────────────
    "settings.guidelines":       {"en": "Company Guidelines",  "ar": "إرشادات الشركة"},
    "settings.integrations":     {"en": "Integrations",        "ar": "التكاملات"},
    "settings.legal":            {"en": "Legal",               "ar": "قانوني"},
    "settings.commercial":       {"en": "Commercial",          "ar": "تجاري"},
    "settings.technical":        {"en": "Technical",           "ar": "تقني"},
    "settings.financial":        {"en": "Financial",           "ar": "مالي"},
    "settings.last_modified":    {"en": "Last modified",       "ar": "آخر تعديل"},

    # ── Toast / feedback messages ─────────────────────────────────────────────
    "toast.saved":          {"en": "Guidelines saved successfully",   "ar": "تم حفظ الإرشادات بنجاح"},
    "toast.save_failed":    {"en": "Failed to save",                  "ar": "فشل الحفظ"},
    "toast.fmp_ok":         {"en": "FMP API is responding normally",  "ar": "واجهة برمجة FMP تعمل بشكل طبيعي"},
    "toast.pdf_ok":         {"en": "PDF regenerated",                 "ar": "تم إعادة إنشاء ملف PDF"},
    "toast.draft_saved":    {"en": "Draft saved successfully",        "ar": "تم حفظ المسودة بنجاح"},
    "toast.error_generic":  {"en": "Something went wrong",            "ar": "حدث خطأ ما"},

    # ── Empty states ──────────────────────────────────────────────────────────
    "empty.no_rfps":        {"en": "No RFPs yet",                     "ar": "لا توجد طلبات عروض بعد"},
    "empty.create_first":   {"en": "Create your first RFP to get started.",
                              "ar": "أنشئ طلب العروض الأول للبدء."},

    # ── Table headers (evaluations) ───────────────────────────────────────────
    "table.vendor":         {"en": "Vendor",          "ar": "المورد"},
    "table.legal":          {"en": "Legal",           "ar": "قانوني"},
    "table.commercial":     {"en": "Commercial",      "ar": "تجاري"},
    "table.technical":      {"en": "Technical Score", "ar": "الدرجة التقنية"},
    "table.financial":      {"en": "Financial",       "ar": "مالي"},
    "table.recommendation": {"en": "Recommendation",  "ar": "التوصية"},

    # ── Editor ────────────────────────────────────────────────────────────────
    "editor.back_dashboard":  {"en": "Dashboard",            "ar": "لوحة التحكم"},
    "editor.back_chat":       {"en": "Back to Chat",         "ar": "العودة إلى المحادثة"},
    "editor.locked":          {"en": "This RFP is locked — status:",
                                "ar": "طلب العروض هذا مقفل — الحالة:"},
    "editor.read_only_info":  {"en": "This RFP is read-only. To make changes, the status must be \"draft\".",
                                "ar": "طلب العروض للقراءة فقط. لإجراء تعديلات، يجب أن تكون الحالة \"مسودة\"."},

    # ── Documents page ────────────────────────────────────────────────────────
    "docs.title":             {"en": "RFP Documents",        "ar": "مستندات طلبات العروض"},
    "docs.subtitle":          {"en": "Browse and manage all RFP documents in your pipeline.",
                                "ar": "تصفح وإدارة جميع مستندات طلبات العروض."},
    "docs.no_content":        {"en": "No content generated yet. Open the chat to start drafting.",
                                "ar": "لم يتم إنشاء محتوى بعد. افتح المحادثة لبدء الصياغة."},
    "docs.open_editor":       {"en": "Open in Editor",      "ar": "فتح في المحرر"},
    "docs.open_chat":         {"en": "Open Chat",           "ar": "فتح المحادثة"},
    "docs.select_rfp":        {"en": "Select an RFP to preview its content",
                                "ar": "اختر طلب عروض لمعاينة محتواه"},

    # ── Evaluations page ──────────────────────────────────────────────────────
    "eval.select_rfp":        {"en": "Select RFP",          "ar": "اختر طلب العروض"},
    "eval.upload_bids":       {"en": "Upload Bids",         "ar": "رفع العروض"},
    "eval.award_rfp":         {"en": "Award RFP",           "ar": "ترسية طلب العروض"},
    "eval.close_rfp":         {"en": "Close RFP",           "ar": "إغلاق طلب العروض"},
    "eval.awarded_to":        {"en": "Awarded to",          "ar": "تمت الترسية إلى"},
    "eval.choose_rfp_first":  {"en": "Choose an RFP to evaluate bids against.",
                                "ar": "اختر طلب عروض لتقييم العروض المقدمة."},
    "eval.start_evaluation":  {"en": "Start Evaluation",    "ar": "بدء التقييم"},
    "eval.no_bids":           {"en": "No bids uploaded yet. Upload vendor bids to begin evaluation.",
                                "ar": "لم يتم رفع عروض بعد. قم برفع عروض الموردين لبدء التقييم."},
}

# ── Public API ────────────────────────────────────────────────────────────────

SUPPORTED_LOCALES = ("en", "ar")
_FALLBACK = "en"


def t(key: str, locale: str = "en") -> str:
    """
    Return the translated string for *key* in *locale*.
    Falls back to English if the key or locale is missing.
    """
    entry = _TRANSLATIONS.get(key)
    if entry is None:
        return key                                  # key not found → return raw key
    return entry.get(locale) or entry.get(_FALLBACK) or key


def is_rtl(locale: str) -> bool:
    """True when *locale* requires right-to-left layout."""
    return locale == "ar"


def get_locale_from_cookie(cookie_header: Optional[str]) -> str:
    """
    Parse the ``ui_lang`` cookie from a raw Cookie header string.
    Returns "en" if the cookie is absent or invalid.
    """
    if not cookie_header:
        return _FALLBACK
    for part in cookie_header.split(";"):
        name, _, value = part.strip().partition("=")
        if name.strip() == "ui_lang" and value.strip() in SUPPORTED_LOCALES:
            return value.strip()
    return _FALLBACK


def all_translations(locale: str) -> dict[str, str]:
    """Return a flat dict of every key → translated string for *locale*."""
    return {k: t(k, locale) for k in _TRANSLATIONS}
