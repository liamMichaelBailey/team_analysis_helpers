from pptx import Presentation
from pptx.util import Inches, Pt
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


# SkillCorner brand colours
SC_DARK = RGBColor(0x00, 0x14, 0x00)
SC_GREEN = RGBColor(0x00, 0xC8, 0x00)
SC_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SC_GREY = RGBColor(0xD9, 0xD9, 0xD6)

# Widescreen 16:9 dimensions
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)


def _html_to_image(html_string, output_path, size=(1400, 900)):
    """Render an HTML string to a PNG image using Chrome headless."""
    chrome_path = _find_chrome()
    output_dir = os.path.dirname(os.path.abspath(output_path))
    output_name = os.path.basename(output_path)

    # Inject minimal CSS — prevent scrollbars without clipping content
    inject_css = (
        '<style>'
        'html, body { margin: 0; padding: 0; } '
        '::-webkit-scrollbar { display: none !important; } '
        'body { overflow: hidden; } '
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
        ],
    )
    hti.screenshot(html_str=html_string, save_as=output_name)

    # Trim bottom whitespace so images fit slides tightly
    _trim_whitespace(output_path)

    return output_path


def _trim_whitespace(image_path):
    """Crop trailing white/transparent space from bottom and right of image."""
    with PILImage.open(image_path) as img:
        # Convert to RGBA for consistent handling
        img = img.convert('RGBA')
        pixels = img.load()
        w, h = img.size

        # Find bottom boundary — scan upward for first non-white row
        bottom = h
        for y in range(h - 1, -1, -1):
            row_has_content = False
            for x in range(0, w, 4):  # Sample every 4th pixel for speed
                r, g, b, a = pixels[x, y]
                if a > 10 and not (r > 250 and g > 250 and b > 250):
                    row_has_content = True
                    break
            if row_has_content:
                bottom = y + 2  # 2px margin
                break

        # Find right boundary — scan leftward for first non-white column
        right = w
        for x in range(w - 1, -1, -1):
            col_has_content = False
            for y in range(0, h, 4):
                r, g, b, a = pixels[x, y]
                if a > 10 and not (r > 250 and g > 250 and b > 250):
                    col_has_content = True
                    break
            if col_has_content:
                right = x + 2
                break

        # Only crop if there's meaningful whitespace to remove
        if bottom < h - 10 or right < w - 10:
            cropped = img.crop((0, 0, min(right, w), min(bottom, h)))
            cropped.save(image_path)


def _add_filled_rect(slide, left, top, width, height, fill_color):
    shape = slide.shapes.add_shape(1, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    return shape


def _add_text_box(slide, left, top, width, height, text, font_size=18,
                  font_color=SC_WHITE, bold=True, alignment=PP_ALIGN.LEFT,
                  font_name='Calibri'):
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


def _add_title_slide(prs, team_name, report_title=None, report_subtitle=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_filled_rect(slide, 0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, SC_DARK)
    _add_filled_rect(slide, 0, 0, SLIDE_WIDTH, Inches(0.08), SC_GREEN)

    title_text = report_title if report_title else f"{team_name} Analysis Report"
    _add_text_box(slide, Inches(0.8), Inches(2.2), Inches(11), Inches(1.5),
                  title_text, font_size=40, font_color=SC_WHITE, bold=True)

    _add_filled_rect(slide, Inches(0.8), Inches(3.5), Inches(3), Inches(0.06),
                     SC_GREEN)

    subtitle_text = report_subtitle if report_subtitle else team_name
    _add_text_box(slide, Inches(0.8), Inches(3.8), Inches(11), Inches(1),
                  subtitle_text, font_size=20, font_color=SC_GREY, bold=False)

    _add_filled_rect(slide, 0, SLIDE_HEIGHT - Inches(0.08), SLIDE_WIDTH,
                     Inches(0.08), SC_GREEN)


def _add_section_divider(prs, section_title):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_filled_rect(slide, 0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, SC_DARK)
    _add_filled_rect(slide, 0, 0, SLIDE_WIDTH, Inches(0.08), SC_GREEN)
    _add_filled_rect(slide, 0, SLIDE_HEIGHT - Inches(0.08), SLIDE_WIDTH,
                     Inches(0.08), SC_GREEN)

    _add_text_box(slide, Inches(0.8), Inches(2.8), Inches(11), Inches(1.5),
                  section_title, font_size=36, font_color=SC_WHITE, bold=True)

    _add_filled_rect(slide, Inches(0.8), Inches(4.2), Inches(2.5),
                     Inches(0.06), SC_GREEN)


def _add_content_slide(prs, title, image_path, subtitle=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # White background for content area
    _add_filled_rect(slide, 0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, SC_WHITE)

    # Dark header bar
    _add_filled_rect(slide, 0, 0, SLIDE_WIDTH, Inches(0.9), SC_DARK)
    _add_filled_rect(slide, 0, Inches(0.9), SLIDE_WIDTH, Inches(0.04),
                     SC_GREEN)

    _add_text_box(slide, Inches(0.5), Inches(0.15), Inches(12), Inches(0.6),
                  title, font_size=22, font_color=SC_WHITE, bold=True)

    if subtitle:
        _add_text_box(slide, Inches(0.5), Inches(0.55), Inches(12),
                      Inches(0.35), subtitle, font_size=11,
                      font_color=SC_GREY, bold=False)

    if image_path and os.path.exists(image_path):
        with PILImage.open(image_path) as img:
            img_w, img_h = img.size

        # Available content area (below header, with padding)
        content_top = 1.1
        max_w = 12.2   # inches
        max_h = 6.1    # inches

        # Calculate proportional fit
        img_aspect = img_w / img_h
        area_aspect = max_w / max_h

        if img_aspect > area_aspect:
            fit_w = max_w
            fit_h = max_w / img_aspect
        else:
            fit_h = max_h
            fit_w = max_h * img_aspect

        # Centre on slide
        slide_w = 13.333
        left = (slide_w - fit_w) / 2

        pic = slide.shapes.add_picture(
            image_path,
            Inches(left), Inches(content_top),
            width=Inches(fit_w), height=Inches(fit_h),
        )
        # Send image to back
        ref_element = slide.shapes[0]._element
        ref_element.addprevious(pic._element)


def generate_report(
        team_name: str,
        sections: list,
        output_path: str = "team_report.pptx",
        report_title: str = None,
        report_subtitle: str = None,
):
    """
    Generate a PPTX report from HTML visualizations or pre-saved images.
    HTML strings are automatically rendered to PNG via Chrome headless.

    Parameters:
    -----------
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
    """
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    _add_title_slide(prs, team_name, report_title, report_subtitle)

    tmp_dir = tempfile.mkdtemp()
    tmp_files = []

    for i, section in enumerate(sections):
        slide_type = section.get("type", "content")

        if slide_type == "divider":
            _add_section_divider(prs, section.get("title", ""))
        else:
            image_path = section.get("image_path", "")
            html_string = section.get("html", "")

            # Render HTML to PNG if no image_path provided
            if (not image_path or not os.path.exists(image_path)) and html_string:
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
