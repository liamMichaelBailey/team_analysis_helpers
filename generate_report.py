from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import os


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
    Generate a PPTX report from pre-saved visualization images.

    Parameters:
    -----------
    team_name : str
        The team name for the report.
    sections : list of dict
        Each dict has:
          - type: "content" (default) or "divider"
          - title: str
          - image_path: str (for content slides)
          - subtitle: str (optional, for content slides)
    output_path : str
        Path to save the output PPTX file.
    report_title : str, optional
        Custom title for the report.
    report_subtitle : str, optional
        Subtitle text on the title slide.

    Example:
    --------
    generate_report(
        team_name="Juventus",
        sections=[
            {"type": "divider", "title": "Team Overview Radars"},
            {"title": "In Possession Radar", "image_path": "ip_radar.png"},
            {"title": "Out of Possession Radar", "image_path": "oop_radar.png"},
            {"type": "divider", "title": "In Possession Phase Overview"},
            {"title": "Phase Profile Overview", "image_path": "ip_overview.png"},
            {"type": "divider", "title": "Build Up Phase"},
            {"title": "Team Build Up Metrics", "image_path": "build_up_heatmap.png"},
            {"title": "Team Build Up Shape", "image_path": "build_up_pitch.png"},
            {"title": "Player Build Up Metrics", "image_path": "build_up_players.png",
             "subtitle": "Line Breaks & Off-Ball Runs Per 90"},
        ],
        output_path="juventus_report.pptx",
        report_subtitle="Serie A 2025/26"
    )
    """
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    _add_title_slide(prs, team_name, report_title, report_subtitle)

    for section in sections:
        slide_type = section.get("type", "content")

        if slide_type == "divider":
            _add_section_divider(prs, section.get("title", ""))
        else:
            _add_content_slide(
                prs,
                title=section.get("title", ""),
                image_path=section.get("image_path", ""),
                subtitle=section.get("subtitle", None),
            )

    prs.save(output_path)
    return output_path
