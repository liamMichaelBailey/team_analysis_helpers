import re

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from PIL import Image as PILImage
import os
import shutil
import subprocess
import tempfile
from html2image import Html2Image


def _find_chrome():
    """Find Chrome/Chromium executable, installing in Colab if needed."""
    candidates = [
        '/usr/bin/google-chrome-stable',
        '/usr/bin/google-chrome',
        '/usr/bin/chromium-browser',
        '/usr/bin/chromium',
        shutil.which('google-chrome-stable'),
        shutil.which('google-chrome'),
        shutil.which('chromium-browser'),
        shutil.which('chromium'),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path

    # Auto-install in Colab
    try:
        import google.colab  # noqa: F401
        subprocess.run(
            ['bash', '-c',
             'wget -q -O /tmp/chrome.deb '
             'https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb '
             '&& apt-get install -y -qq /tmp/chrome.deb '
             '&& rm /tmp/chrome.deb'],
            check=True, capture_output=True,
        )
        if os.path.exists('/usr/bin/google-chrome-stable'):
            return '/usr/bin/google-chrome-stable'
    except (ImportError, subprocess.CalledProcessError):
        pass

    raise FileNotFoundError(
        "No Chrome/Chromium found. In Colab, google-chrome-stable should be "
        "pre-installed. Try: !which google-chrome-stable"
    )


# ──────────────────────────────────────────────────────────────────────
# SkillCorner brand colours — exact values from template
# ──────────────────────────────────────────────────────────────────────
SC_BG = RGBColor(0x25, 0x25, 0x25)          # #252525 — title bar / dark panels
SC_GREEN = RGBColor(0x32, 0xFE, 0x6B)       # #32FE6B — neon green accent
SC_GREEN_LINE = RGBColor(0x32, 0xFF, 0x6A)  # #32FF6A — accent lines
SC_DARK_GREEN = RGBColor(0x00, 0xA8, 0x2F)  # #00A82F
SC_PANEL_GREY = RGBColor(0x88, 0x88, 0x88)  # #888888 — content panels
SC_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SC_GREY = RGBColor(0x87, 0x87, 0x87)        # #878787
SC_LIGHT_GREY = RGBColor(0xE8, 0xE8, 0xE8)  # #E8E8E8
SC_DARK_TEXT = RGBColor(0x57, 0x57, 0x57)    # #575757

# Template slide dimensions (10 x 5.625 inches — standard 16:9)
SLIDE_WIDTH = Inches(10)
SLIDE_HEIGHT = Inches(5.625)

# Template measurements (from inspecting the PPTX)
TITLE_LEFT = Inches(0.326)       # Title bar left edge
TITLE_TOP = Inches(0.082)        # Title bar top
TITLE_HEIGHT = Inches(0.572)     # Title bar height
SUBTITLE_TOP = Inches(0.503)     # Subtitle top
SUBTITLE_HEIGHT = Inches(0.283)  # Subtitle height
CONTENT_TOP = Inches(0.875)      # Where content area begins


def _strip_download_buttons(html_string):
    """Remove download/export buttons from HTML before rendering."""
    html_string = re.sub(
        r'<button[^>]*class="[^"]*download[^"]*"[^>]*>.*?</button>',
        '', html_string, flags=re.IGNORECASE | re.DOTALL
    )
    html_string = re.sub(
        r'<button[^>]*onclick="[^"]*download[^"]*"[^>]*>.*?</button>',
        '', html_string, flags=re.IGNORECASE | re.DOTALL
    )
    html_string = re.sub(
        r'<button[^>]*>.*?(?:download|export|save\s+png).*?</button>',
        '', html_string, flags=re.IGNORECASE | re.DOTALL
    )
    html_string = re.sub(
        r'<a[^>]*download[^>]*>.*?</a>',
        '', html_string, flags=re.IGNORECASE | re.DOTALL
    )
    html_string = re.sub(
        r'\.download-btn\s*\{[^}]*\}',
        '', html_string, flags=re.IGNORECASE
    )
    html_string = re.sub(
        r'\.download-button\s*\{[^}]*\}',
        '', html_string, flags=re.IGNORECASE
    )
    html_string = re.sub(
        r'\.pitch-download\s*\{[^}]*\}',
        '', html_string, flags=re.IGNORECASE
    )
    html_string = re.sub(
        r'\.download-button::before\s*\{[^}]*\}',
        '', html_string, flags=re.IGNORECASE
    )
    html_string = re.sub(
        r'\.download-button:hover\s*\{[^}]*\}',
        '', html_string, flags=re.IGNORECASE
    )
    html_string = re.sub(
        r'[^{]*\.pitch-download[^{]*\{[^}]*\}',
        '', html_string, flags=re.IGNORECASE
    )
    html_string = re.sub(
        r'function\s+downloadPNG\s*\(\)\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\}',
        '', html_string, flags=re.IGNORECASE
    )
    return html_string


def _html_to_image(html_string, output_path, size=(1400, 900)):
    """Render an HTML string to a PNG image using Chrome headless."""
    chrome_path = _find_chrome()
    output_dir = os.path.dirname(os.path.abspath(output_path))
    output_name = os.path.basename(output_path)

    html_string = _strip_download_buttons(html_string)

    inject_css = (
        '<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:'
        'wght@300;400;500;600;700&display=swap" rel="stylesheet">'
        '<style>'
        'html, body { margin: 0; padding: 0; background: #ffffff; '
        'overflow: hidden; } '
        '::-webkit-scrollbar { display: none !important; '
        'width: 0 !important; height: 0 !important; } '
        'body { font-family: "Chakra Petch", sans-serif; '
        '-ms-overflow-style: none; scrollbar-width: none; } '
        '</style>'
    )
    if '</head>' in html_string:
        html_string = html_string.replace('</head>', inject_css + '</head>')
    else:
        html_string = inject_css + html_string

    hti = Html2Image(
        browser_executable=chrome_path,
        output_path=output_dir,
        size=size,
        custom_flags=[
            '--no-sandbox',
            '--disable-gpu',
            '--hide-scrollbars',
            '--force-device-scale-factor=2',
            '--virtual-time-budget=5000',
        ],
    )
    hti.screenshot(html_str=html_string, save_as=output_name)

    _trim_whitespace(output_path)
    return output_path


def _trim_whitespace(image_path):
    """Crop trailing white/transparent space from bottom and right."""
    with PILImage.open(image_path) as img:
        img = img.convert('RGBA')
        pixels = img.load()
        w, h = img.size

        bottom = h
        for y in range(h - 1, -1, -1):
            for x in range(0, w, 4):
                r, g, b, a = pixels[x, y]
                if a > 10 and not (r > 250 and g > 250 and b > 250):
                    bottom = y + 2
                    break
            else:
                continue
            break

        right = w
        for x in range(w - 1, -1, -1):
            for y_s in range(0, h, 4):
                r, g, b, a = pixels[x, y_s]
                if a > 10 and not (r > 250 and g > 250 and b > 250):
                    right = x + 2
                    break
            else:
                continue
            break

        if bottom < h - 10 or right < w - 10:
            cropped = img.crop((0, 0, min(right, w), min(bottom, h)))
            cropped.save(image_path)


# ──────────────────────────────────────────────────────────────────────
# Slide helpers — directly replicating SkillCorner template
# ──────────────────────────────────────────────────────────────────────

def _add_filled_rect(slide, left, top, width, height, fill_color):
    """Add a solid-filled rectangle with no border."""
    shape = slide.shapes.add_shape(1, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    return shape


def _add_text_box(slide, left, top, width, height, text, font_size=18,
                  font_color=SC_WHITE, bold=True, alignment=PP_ALIGN.LEFT,
                  font_name='Chakra Petch'):
    """Add a text box with specified font."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = font_color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = alignment
    return txBox


def _set_slide_bg(slide, color):
    """Set the slide background to a solid color."""
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_title_slide(prs, team_name, report_title=None, report_subtitle=None):
    """
    Cover slide — dark background, matching template TITLE layout.
    Template: Chakra Petch Bold ~41pt title, 16pt subtitle in #32FE6B.
    """
    slide = prs.slides.add_slide(prs.slide_layouts[10])  # BLANK layout
    _set_slide_bg(slide, SC_BG)

    # Title — Chakra Petch Bold, large
    title_text = report_title if report_title else f"{team_name} Analysis Report"
    _add_text_box(slide, Inches(0.6), Inches(1.6), Inches(8.5), Inches(1.2),
                  title_text, font_size=41, font_color=SC_WHITE, bold=True)

    # Green accent bar under title
    _add_filled_rect(slide, Inches(0.6), Inches(2.75), Inches(2.2),
                     Inches(0.05), SC_GREEN)

    # Subtitle — Chakra Petch, #32FE6B green
    subtitle_text = report_subtitle if report_subtitle else team_name
    _add_text_box(slide, Inches(0.6), Inches(3.0), Inches(8.5), Inches(0.8),
                  subtitle_text, font_size=16, font_color=SC_GREEN, bold=False)


def _add_section_divider(prs, section_title, section_number=None):
    """
    Section divider — dark background, large green number + white title.
    Template style: Chakra Petch Bold ~65-80pt number, ~34pt title.
    """
    slide = prs.slides.add_slide(prs.slide_layouts[10])  # BLANK layout
    _set_slide_bg(slide, SC_BG)

    # Large green section number
    if section_number is not None:
        _add_text_box(slide, Inches(0.6), Inches(0.8), Inches(3), Inches(1.8),
                      str(section_number).zfill(2), font_size=72,
                      font_color=SC_GREEN, bold=True)

    # Section title — Chakra Petch Bold ~34pt
    title_top = Inches(1.2) if section_number is None else Inches(2.6)
    _add_text_box(slide, Inches(0.6), title_top, Inches(8.5), Inches(1.2),
                  section_title, font_size=34, font_color=SC_WHITE, bold=True)

    # Green accent bar
    bar_top = title_top + Inches(1.2)
    _add_filled_rect(slide, Inches(0.6), bar_top, Inches(2), Inches(0.05),
                     SC_GREEN)


def _add_content_slide(prs, title, image_path, subtitle=None):
    """
    Content / analysis slide — WHITE background.

    Matches template content slide structure:
    - #252525 title bar at top (left=0.326in, top=0.082in, h=0.572in)
    - Chakra Petch Bold ~23pt white title text
    - Chakra Petch ~13pt subtitle
    - Content starts at top=0.875in
    - Chart/image fills the remaining white area
    """
    slide = prs.slides.add_slide(prs.slide_layouts[10])  # BLANK layout

    # White slide background
    _set_slide_bg(slide, SC_WHITE)

    # Title bar — #252525 filled rectangle spanning full width
    # Template: title placeholder at (0.326in, 0.082in), h=0.572in
    _add_filled_rect(slide, TITLE_LEFT, TITLE_TOP,
                     Inches(9.375), TITLE_HEIGHT, SC_BG)

    # Green accent line under title bar
    green_line_top = TITLE_TOP + TITLE_HEIGHT
    _add_filled_rect(slide, TITLE_LEFT, green_line_top,
                     Inches(9.375), Inches(0.03), SC_GREEN_LINE)

    # Title text — Chakra Petch Bold ~23pt, white
    _add_text_box(slide, Inches(0.45), Inches(0.13), Inches(9), Inches(0.45),
                  title, font_size=23, font_color=SC_WHITE, bold=True)

    # Subtitle — Chakra Petch ~13pt, white
    if subtitle:
        _add_text_box(slide, Inches(0.45), SUBTITLE_TOP,
                      Inches(9), SUBTITLE_HEIGHT,
                      subtitle, font_size=13, font_color=SC_WHITE, bold=False)

    # Image — fitted proportionally into white content area
    if image_path and os.path.exists(image_path):
        with PILImage.open(image_path) as img:
            img_w, img_h = img.size

        # Content area: starts at CONTENT_TOP, with small padding
        content_top_in = 0.875
        pad = 0.2
        max_w = 10.0 - TITLE_LEFT.inches - pad  # match title bar width
        max_h = 5.625 - content_top_in - pad

        img_aspect = img_w / img_h
        area_aspect = max_w / max_h

        if img_aspect > area_aspect:
            fit_w = max_w
            fit_h = max_w / img_aspect
        else:
            fit_h = max_h
            fit_w = max_h * img_aspect

        # Centre horizontally within the content area
        left = TITLE_LEFT.inches + (max_w - fit_w) / 2

        slide.shapes.add_picture(
            image_path,
            Inches(left), Inches(content_top_in),
            width=Inches(fit_w), height=Inches(fit_h),
        )


# ──────────────────────────────────────────────────────────────────────
# Main report generator
# ──────────────────────────────────────────────────────────────────────

def generate_report(
        team_name: str,
        sections: list,
        output_path: str = "team_report.pptx",
        report_title: str = None,
        report_subtitle: str = None,
        template_path: str = None,
):
    """
    Generate a PPTX report from HTML visualizations or pre-saved images.
    HTML strings are automatically rendered to PNG via Chrome headless.

    Parameters
    ----------
    team_name : str
        The team name for the report.
    sections : list of dict
        Each dict has:
          - type: "content" (default) or "divider"
          - title: str
          - html: str (HTML string — rendered to PNG automatically)
          - image_path: str (pre-saved PNG — takes priority over html)
          - subtitle: str (optional)
          - size: tuple (viewport w,h for HTML rendering, default 1400x900)
    output_path : str
        Path to save the output PPTX file.
    report_title : str, optional
        Custom title for the report.
    report_subtitle : str, optional
        Subtitle text on the title slide.
    template_path : str, optional
        Path to a SkillCorner PPTX template. Slide dimensions and theme
        are inherited. All existing slides are removed before adding new ones.
    """
    if template_path and os.path.exists(template_path):
        prs = Presentation(template_path)
        # Remove all existing slides from the template
        while len(prs.slides) > 0:
            rId = prs.slides._sldIdLst[0].get('r:id')
            prs.part.drop_rel(rId)
            prs.slides._sldIdLst.remove(prs.slides._sldIdLst[0])
    else:
        prs = Presentation()
        prs.slide_width = SLIDE_WIDTH
        prs.slide_height = SLIDE_HEIGHT

    _add_title_slide(prs, team_name, report_title, report_subtitle)

    tmp_dir = tempfile.mkdtemp()
    tmp_files = []
    section_counter = 0

    for i, section in enumerate(sections):
        slide_type = section.get("type", "content")

        if slide_type == "divider":
            section_counter += 1
            _add_section_divider(prs, section.get("title", ""),
                                 section_number=section_counter)
        else:
            image_path = section.get("image_path", "")
            html_string = section.get("html", "")

            if (not image_path or not os.path.exists(image_path)) \
                    and html_string:
                tmp_path = os.path.join(tmp_dir, f"slide_{i}.png")
                size = section.get("size", (1400, 900))
                _html_to_image(html_string, tmp_path, size=size)
                image_path = tmp_path
                tmp_files.append(tmp_path)

            _add_content_slide(
                prs,
                title=section.get("title", ""),
                image_path=image_path,
                subtitle=section.get("subtitle", None),
            )

    prs.save(output_path)

    # Clean up temp files
    for f in tmp_files:
        try:
            os.remove(f)
        except OSError:
            pass
    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass

    return output_path
