from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import os
import tempfile
from html2image import Html2Image


# SkillCorner brand colours
SC_DARK = RGBColor(0x00, 0x14, 0x00)
SC_GREEN = RGBColor(0x00, 0xC8, 0x00)
SC_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SC_GREY = RGBColor(0xD9, 0xD9, 0xD6)

# Widescreen 16:9 dimensions
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

# Content slide image positioning
IMAGE_LEFT = Inches(0.4)
IMAGE_TOP = Inches(1.2)
IMAGE_WIDTH = Inches(12.5)


def _html_to_image(html_string, output_path, size=(1200, 800)):
    """Render an HTML string to a PNG image using Chrome headless."""
    output_dir = os.path.dirname(os.path.abspath(output_path))
    output_name = os.path.basename(output_path)
    hti = Html2Image(output_path=output_dir, size=size)
    hti.screenshot(html_str=html_string, save_as=output_name)
    return output_path


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

    _add_filled_rect(slide, Inches(0.8), Inches(3.5), Inches(3), Inches(0.06), SC_GREEN)

    subtitle_text = report_subtitle if report_subtitle else team_name
    _add_text_box(slide, Inches(0.8), Inches(3.8), Inches(11), Inches(1),
                  subtitle_text, font_size=20, font_color=SC_GREY, bold=False)

    _add_filled_rect(slide, 0, SLIDE_HEIGHT - Inches(0.08), SLIDE_WIDTH, Inches(0.08), SC_GREEN)


def _add_section_divider(prs, section_title):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_filled_rect(slide, 0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, SC_DARK)
    _add_filled_rect(slide, 0, 0, SLIDE_WIDTH, Inches(0.08), SC_GREEN)
    _add_filled_rect(slide, 0, SLIDE_HEIGHT - Inches(0.08), SLIDE_WIDTH, Inches(0.08), SC_GREEN)

    _add_text_box(slide, Inches(0.8), Inches(2.8), Inches(11), Inches(1.5),
                  section_title, font_size=36, font_color=SC_WHITE, bold=True)

    _add_filled_rect(slide, Inches(0.8), Inches(4.2), Inches(2.5), Inches(0.06), SC_GREEN)


def _add_content_slide(prs, title, image_path, subtitle=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    _add_filled_rect(slide, 0, 0, SLIDE_WIDTH, Inches(1.0), SC_DARK)
    _add_filled_rect(slide, 0, Inches(1.0), SLIDE_WIDTH, Inches(0.04), SC_GREEN)

    _add_text_box(slide, Inches(0.5), Inches(0.15), Inches(12), Inches(0.7),
                  title, font_size=24, font_color=SC_WHITE, bold=True)

    if subtitle:
        _add_text_box(slide, Inches(0.5), Inches(0.6), Inches(12), Inches(0.4),
                      subtitle, font_size=12, font_color=SC_GREY, bold=False)

    if image_path and os.path.exists(image_path):
        pic = slide.shapes.add_picture(image_path, IMAGE_LEFT, IMAGE_TOP, IMAGE_WIDTH)
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
          - html: str (HTML string to render — used if image_path not provided)
          - image_path: str (path to pre-saved PNG — takes priority over html)
          - subtitle: str (optional)
          - size: tuple (optional, width/height for HTML rendering, default (1200, 800))
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
                size = section.get("size", (1200, 800))
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
