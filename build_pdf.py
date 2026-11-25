"""
Render the two dashboards to PDF.

  docs/Critical_Minerals_Report_Mockup.pdf   five landscape sheets, one per report page
  docs/Critical_Minerals_Dashboard.pdf        the matplotlib dashboard, portrait

Both are printed from the HTML through headless Chrome, so the PDF and the live
page can never drift apart. A print stylesheet is injected at render time rather
than left in the shipped HTML, because the rules that make a browser page break
cleanly into sheets are wrong for reading it on screen.

Usage: python build_pdf.py
"""

import os
import re
import shutil
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "docs")

# one landscape sheet per report page, sized to the mockup's own page box so
# nothing is scaled or clipped
POWERBI_PRINT_CSS = """
@page { size: 1400px __SHEET_H__px; margin: 0; }
html, body {
  background: #0E1016 !important;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.wrap { max-width: none !important; margin: 0 !important; padding: 0 !important; }
.hdr { display: none !important; }
footer {
  width: 1400px; margin: 0; padding: 56px;
  border: none; font-size: 15px; line-height: 1.9;
  display: flex; flex-direction: column; justify-content: center;
}
.page {
  width: 1400px; height: auto; margin: 0 !important;
  border: none !important; border-radius: 0 !important;
  padding: 30px 34px 24px !important;
  break-after: page; page-break-after: always;
  overflow: visible;
}
.tabs { display: none !important; }
.visual, .kpi, .formula { break-inside: avoid; }
/* Chrome derives the print layout width from the page box, which can be narrow
   enough to trip the responsive breakpoint and restack every grid. Pin the
   desktop layout so the sheet matches the screen regardless of that width. */
.kpis { grid-template-columns: repeat(6, 1fr) !important; }
.g1 { grid-template-columns: 1fr !important; }
.g2 { grid-template-columns: 1fr 1fr !important; }
.g3 { grid-template-columns: repeat(3, 1fr) !important; }
"""

# a long scrolling page, so let it flow across portrait sheets and only forbid
# breaks inside a panel
DASHBOARD_PRINT_CSS = """
@page { size: A4 portrait; margin: 10mm; }
html, body {
  background: #ffffff !important;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.wrap { max-width: none !important; padding: 0 !important; }
section, .kpi, .flag, header, table { break-inside: avoid; page-break-inside: avoid; }
section { margin-top: 14px !important; }
.dark-only { display: none !important; }
.light-only { display: block !important; }
img { max-width: 100% !important; }
"""


def chrome_path():
    return (
        shutil.which("google-chrome")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
        or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )


SHEET_W, SHEET_H = 1400, 800
# the content box left after the sheet's own padding
FIT_H = SHEET_H - 56


def measure_pages(src_html):
    """
    Lay the page out in a real browser and read back the natural height of each
    report page.

    This exists because a page that is taller than the sheet gets silently
    cropped, and a cropped table in a PDF looks like a complete table with fewer
    rows. Measuring first means every page can be scaled to fit instead, so
    nothing is ever cut off without anyone noticing.
    """
    chrome = chrome_path()
    html = open(src_html, encoding="utf-8").read()
    probe = """
<script>
window.addEventListener('load', function () {
  document.querySelectorAll('section.page').forEach(function (el, i) {
    el.setAttribute('data-h', Math.ceil(el.scrollHeight));
  });
});
</script>
"""
    # measure at the same width the sheet will use, with the print grid pinned
    pin = (
        "<style>.wrap{max-width:none;padding:0}.page{width:1400px;"
        "padding:30px 34px 20px;margin:0}"
        ".kpis{grid-template-columns:repeat(6,1fr)!important}"
        ".g1{grid-template-columns:1fr!important}"
        ".g2{grid-template-columns:1fr 1fr!important}"
        ".g3{grid-template-columns:repeat(3,1fr)!important}</style>"
    )
    tmp_dir = tempfile.mkdtemp()
    tmp_html = os.path.join(tmp_dir, "measure.html")
    with open(tmp_html, "w", encoding="utf-8") as fh:
        fh.write(html.replace("</head>", pin + probe + "</head>", 1))
    out = subprocess.run(
        [
            chrome, "--headless", "--disable-gpu", "--no-sandbox",
            "--window-size=1500,1000", "--virtual-time-budget=6000",
            "--dump-dom", "file://" + tmp_html,
        ],
        check=True, capture_output=True, text=True,
    ).stdout
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return [int(h) for h in re.findall(r'data-h="(\d+)"', out)]


def fit_css(heights):
    """
    Give every report page its own sheet, sized to that page.

    A PDF may carry a different page size per page, and CSS named pages are how
    you ask for it. Each report page gets a sheet exactly as tall as it needs,
    so a long table is never cropped and a short page never trails half a sheet
    of empty space. The alternative, one uniform sheet, forces a choice between
    cropping the tallest page and padding every other one.
    """
    rules = []
    for i, h in enumerate(heights, start=1):
        sheet = max(h + 4, 560)
        rules.append(
            "@page p" + str(i) + " { size: " + str(SHEET_W) + "px "
            + str(sheet) + "px; margin: 0; }"
        )
        rules.append(
            "section.page:nth-of-type(" + str(i) + ") { page: p" + str(i) + "; }"
        )
    rules.append("@page pfoot { size: " + str(SHEET_W) + "px 520px; margin: 0; }")
    rules.append("footer { page: pfoot; height: 520px; }")
    return "\n".join(rules)


def render(src_html, out_pdf, print_css, landscape):
    """Copy the page, inject the print rules, then print it."""
    chrome = chrome_path()
    if not os.path.exists(chrome):
        return None
    html = open(src_html, encoding="utf-8").read()
    marker = "</head>"
    injected = html.replace(
        marker, "<style>" + print_css + "</style>" + marker, 1
    )
    tmp_dir = tempfile.mkdtemp()
    tmp_html = os.path.join(tmp_dir, "print.html")
    with open(tmp_html, "w", encoding="utf-8") as fh:
        fh.write(injected)
    cmd = [
        chrome,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--virtual-time-budget=8000",
        "--print-to-pdf=" + out_pdf,
    ]
    if landscape:
        cmd.append("--landscape")
    cmd.append("file://" + tmp_html)
    subprocess.run(cmd, check=True, capture_output=True)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return out_pdf


def page_count(path):
    try:
        import pypdf

        return len(pypdf.PdfReader(path).pages)
    except Exception:
        return 0


def build(verbose=True):
    os.makedirs(DOCS, exist_ok=True)
    results = []

    mockup = os.path.join(HERE, "powerbi", "mockup", "report-mockup.html")
    css = POWERBI_PRINT_CSS.replace("__SHEET_H__", str(SHEET_H))
    heights = []
    if os.path.exists(chrome_path()):
        heights = measure_pages(mockup)
        css = css + "\n" + fit_css(heights)
    report = render(
        mockup,
        os.path.join(DOCS, "Critical_Minerals_Report_Mockup.pdf"),
        css,
        landscape=False,
    )
    if report:
        results.append(report)

    dashboard = render(
        os.path.join(HERE, "dashboard.html"),
        os.path.join(DOCS, "Critical_Minerals_Dashboard.pdf"),
        DASHBOARD_PRINT_CSS,
        landscape=False,
    )
    if dashboard:
        results.append(dashboard)

    if verbose:
        if heights:
            print("  report page heights: " + ", ".join(str(h) for h in heights)
                  + "  (sheet fits " + str(FIT_H) + ")")
        if not results:
            print("no Chrome found on this machine, skipped both PDFs")
        for path in results:
            size = os.path.getsize(path) / 1024
            print(
                "  "
                + os.path.basename(path).ljust(42)
                + f"{size:,.0f} KB   "
                + str(page_count(path))
                + " pages"
            )
    return results


if __name__ == "__main__":
    build()
