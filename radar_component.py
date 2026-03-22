import pandas as pd
import json

from league_table import DEFAULT_INVERTED_HEATMAP_METRICS

DEFAULT_RADAR_METRICS = [
    'count_build_up_phases_per_90',
    'count_create_phases_per_90',
    'count_finish_phases_per_90',
    'count_direct_phases_per_90',
    'progressed_to_create_from_build_up_percentage',
    'progressed_to_finish_from_create_percentage',
    'finish_lead_to_shot_percentage',
    'regain_in_high_block_percentage',
    'regain_in_medium_block_percentage',
    'regain_in_low_block_percentage',
]


def radar_component(
        df: pd.DataFrame,
        team_name: str,
        metrics: list = DEFAULT_RADAR_METRICS,
        metric_labels: dict = None,
        plot_title: str = None,
        text_color: str = "#001400",
        bar_color: str = "#00C800",
        invert_metrics: list = DEFAULT_INVERTED_HEATMAP_METRICS,
        team_name_col: str = "team_shortname",
):
    """
    HTML/JS radar component styled after the SkillCorner radar.

    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame containing all teams with metric columns.
    team_name : str
        The team to highlight on the radar.
    metrics : list
        List of metric column names to display.
    metric_labels : dict, optional
        Dict mapping metric names to display labels.
    plot_title : str, optional
        Title displayed above the radar.
    text_color : str
        Color for text elements.
    bar_color : str
        Color for the radar bars.
    invert_metrics : list
        Metrics where lower values are better (percentile is inverted).
    team_name_col : str
        Column name for team names.
    """

    if invert_metrics is None:
        invert_metrics = []

    # Compute percentile ranks for each metric
    pct_ranks = {}
    actual_values = {}
    team_row = df[df[team_name_col] == team_name]

    if len(team_row) == 0:
        return "<p>Team not found</p>"

    team_row = team_row.iloc[0]

    for m in metrics:
        if m not in df.columns:
            pct_ranks[m] = None
            actual_values[m] = None
            continue

        rank = df[m].rank(pct=True)
        team_idx = df[df[team_name_col] == team_name].index[0]
        pct = rank[team_idx]

        if m in invert_metrics:
            pct = 1 - pct

        pct_ranks[m] = round(pct * 100, 1) if pd.notna(pct) else None

        val = team_row[m]
        if pd.notna(val):
            actual_values[m] = round(val, 1) if isinstance(val, float) else val
        else:
            actual_values[m] = None

    # Build labels
    labels = []
    for m in metrics:
        if metric_labels and m in metric_labels:
            labels.append(metric_labels[m])
        else:
            label = m.replace('count_', '').replace('_phases_per_90', ' P90')
            label = label.replace('_percentage', ' %').replace('_', ' ').title()
            labels.append(label)

    title = plot_title if plot_title else team_name

    data = {
        "percentiles": [pct_ranks[m] for m in metrics],
        "actuals": [actual_values[m] for m in metrics],
        "labels": labels,
        "title": title,
        "bar_color": bar_color,
        "text_color": text_color,
    }

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          background: white;
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 0;
        }}
        .radar-container {{
          position: relative;
          width: 900px;
          height: 900px;
        }}
        canvas {{
          display: block;
        }}
        .download-btn {{
          position: absolute;
          top: 10px;
          right: 10px;
          width: 28px;
          height: 28px;
          border-radius: 50%;
          border: none;
          background: #006600;
          color: white;
          cursor: pointer;
          font-size: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 10;
        }}
        .download-btn:hover {{ transform: scale(1.1); }}
      </style>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    </head>
    <body>
      <div class="radar-container" id="radar-container">
        <button class="download-btn" onclick="downloadPNG()" title="Download PNG">&#11015;</button>
        <canvas id="radar" width="900" height="900"></canvas>
      </div>

      <script>
        const data = {json.dumps(data)};
        const canvas = document.getElementById('radar');
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;

        const W = 900;
        const H = 900;
        canvas.width = W * dpr;
        canvas.height = H * dpr;
        canvas.style.width = W + 'px';
        canvas.style.height = H + 'px';
        ctx.scale(dpr, dpr);

        const cx = W / 2;
        const cy = W / 2 + 15;

        const innerRadius = 30;
        const outerRadius = 250;
        const valueRadius = outerRadius + 22;
        const labelRadius = outerRadius + 70;

        const n = data.labels.length;
        const sliceAngle = (2 * Math.PI) / n;
        const startOffset = -Math.PI / 2;

        const ringLevels = [25, 50, 75, 100];

        function pctToRadius(pct) {{
          return innerRadius + (pct / 100) * (outerRadius - innerRadius);
        }}

        // --- Draw percentile rings (dashed) ---
        ctx.strokeStyle = '#333333';
        ctx.lineWidth = 0.8;
        ctx.setLineDash([5, 5]);
        ringLevels.forEach(level => {{
          const r = pctToRadius(level);
          ctx.beginPath();
          ctx.arc(cx, cy, r, 0, 2 * Math.PI);
          ctx.stroke();
        }});
        ctx.setLineDash([]);

        // --- Draw bars (filled wedges) ---
        data.percentiles.forEach((pct, i) => {{
          if (pct === null) return;

          const angleStart = startOffset + i * sliceAngle;
          const angleEnd = startOffset + (i + 1) * sliceAngle;
          const barRadius = pctToRadius(pct);

          ctx.beginPath();
          ctx.arc(cx, cy, barRadius, angleStart, angleEnd);
          ctx.arc(cx, cy, innerRadius, angleEnd, angleStart, true);
          ctx.closePath();
          ctx.fillStyle = data.bar_color;
          ctx.globalAlpha = 0.9;
          ctx.fill();
          ctx.globalAlpha = 1;
        }});

        // --- Draw white spoke dividers (on top of bars) ---
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 2.5;
        for (let i = 0; i < n; i++) {{
          const angle = startOffset + i * sliceAngle;
          ctx.beginPath();
          ctx.moveTo(cx + innerRadius * Math.cos(angle), cy + innerRadius * Math.sin(angle));
          ctx.lineTo(cx + outerRadius * Math.cos(angle), cy + outerRadius * Math.sin(angle));
          ctx.stroke();
        }}

        // --- Inner circle (white fill) ---
        ctx.beginPath();
        ctx.arc(cx, cy, innerRadius, 0, 2 * Math.PI);
        ctx.fillStyle = 'white';
        ctx.fill();
        ctx.strokeStyle = '#333333';
        ctx.lineWidth = 0.8;
        ctx.setLineDash([5, 5]);
        ctx.stroke();
        ctx.setLineDash([]);

        // --- Percentile ring labels on one spoke (bottom-right) ---
        // Place them along the spoke between metrics closest to ~135 degrees (bottom-right)
        const ringLabelAngle = startOffset + Math.floor(n * 0.625) * sliceAngle + sliceAngle / 2;

        ctx.font = 'bold 11px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.fillStyle = '#555555';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        [25, 50, 75].forEach(level => {{
          const r = pctToRadius(level);
          const lx = cx + r * Math.cos(ringLabelAngle);
          const ly = cy + r * Math.sin(ringLabelAngle);

          // White background for readability
          ctx.strokeStyle = 'white';
          ctx.lineWidth = 4;
          ctx.strokeText(level.toString(), lx, ly);
          ctx.fillText(level.toString(), lx, ly);
        }});

        // 100th percentile label
        const r100 = pctToRadius(100);
        const lx100 = cx + r100 * Math.cos(ringLabelAngle);
        const ly100 = cy + r100 * Math.sin(ringLabelAngle);
        ctx.font = 'bold 10px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 4;
        ctx.strokeText('100th', lx100, ly100 - 6);
        ctx.fillText('100th', lx100, ly100 - 6);
        ctx.strokeText('Percentile', lx100, ly100 + 6);
        ctx.fillText('Percentile', lx100, ly100 + 6);

        // --- Draw actual values (rotated along spoke, between ring and label) ---
        ctx.font = 'bold 11px -apple-system, BlinkMacSystemFont, sans-serif';
        data.actuals.forEach((val, i) => {{
          if (val === null) return;

          const angleMid = startOffset + (i + 0.5) * sliceAngle;
          const vx = cx + valueRadius * Math.cos(angleMid);
          const vy = cy + valueRadius * Math.sin(angleMid);

          ctx.save();
          ctx.translate(vx, vy);

          // Rotate text along the spoke, flip if in bottom half so text reads correctly
          let rotation = angleMid;
          const midDeg = ((angleMid * 180 / Math.PI) % 360 + 360) % 360;
          if (midDeg > 90 && midDeg < 270) {{
            rotation += Math.PI;
          }}
          ctx.rotate(rotation);

          ctx.fillStyle = data.text_color;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.strokeStyle = 'white';
          ctx.lineWidth = 3;
          ctx.strokeText(String(val), 0, 0);
          ctx.fillText(String(val), 0, 0);

          ctx.restore();
        }});

        // --- Draw metric labels (uppercase, bold, green, outside) ---
        data.labels.forEach((label, i) => {{
          const angleMid = startOffset + (i + 0.5) * sliceAngle;
          const lx = cx + labelRadius * Math.cos(angleMid);
          const ly = cy + labelRadius * Math.sin(angleMid);

          ctx.save();
          ctx.translate(lx, ly);

          // Rotate along spoke, flip bottom half
          let rotation = angleMid;
          const midDeg = ((angleMid * 180 / Math.PI) % 360 + 360) % 360;
          if (midDeg > 90 && midDeg < 270) {{
            rotation += Math.PI;
          }}
          ctx.rotate(rotation);

          ctx.fillStyle = data.bar_color;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.font = 'bold 13px -apple-system, BlinkMacSystemFont, sans-serif';

          // Word-wrap and uppercase
          const upperLabel = label.toUpperCase();
          const words = upperLabel.split(' ');
          const maxChars = 14;
          const lines = [];
          let currentLine = '';
          words.forEach(word => {{
            const test = currentLine.length > 0 ? currentLine + ' ' + word : word;
            if (test.length > maxChars && currentLine.length > 0) {{
              lines.push(currentLine);
              currentLine = word;
            }} else {{
              currentLine = test;
            }}
          }});
          if (currentLine.length > 0) lines.push(currentLine);

          const lineHeight = 15;
          lines.forEach((line, li) => {{
            ctx.fillText(line, 0, (li - (lines.length - 1) / 2) * lineHeight);
          }});

          ctx.restore();
        }});

        // --- Title ---
        ctx.font = 'bold 20px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.fillStyle = data.text_color;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(data.title, cx, 12);

        // --- Download PNG ---
        function downloadPNG() {{
          const btn = document.querySelector('.download-btn');
          if (btn) btn.style.visibility = 'hidden';

          const container = document.getElementById('radar-container');
          html2canvas(container, {{
            scale: 3,
            useCORS: true,
            backgroundColor: '#ffffff'
          }}).then(sourceCanvas => {{
            const tw = 1920;
            const th = 1080;
            const finalCanvas = document.createElement('canvas');
            finalCanvas.width = tw;
            finalCanvas.height = th;
            const fctx = finalCanvas.getContext('2d');
            fctx.fillStyle = '#ffffff';
            fctx.fillRect(0, 0, tw, th);

            const pad = 60;
            const aw = tw - pad * 2;
            const ah = th - pad * 2;
            const sx = aw / sourceCanvas.width;
            const sy = ah / sourceCanvas.height;
            const fs = Math.min(sx, sy);
            const sw = sourceCanvas.width * fs;
            const sh = sourceCanvas.height * fs;
            const ox = (tw - sw) / 2;
            const oy = (th - sh) / 2;

            fctx.drawImage(sourceCanvas, ox, oy, sw, sh);

            const link = document.createElement('a');
            link.href = finalCanvas.toDataURL('image/png');
            link.download = 'radar_plot.png';
            link.click();

            if (btn) btn.style.visibility = 'visible';
          }});
        }}
      </script>
    </body>
    </html>
    """

    return html
