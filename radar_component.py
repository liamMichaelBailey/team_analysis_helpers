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
        rounding: int = 1,
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
    rounding : int
        Decimal places for displayed values.
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
            actual_values[m] = round(val, rounding) if isinstance(val, float) else val
        else:
            actual_values[m] = None

    # Build labels
    labels = []
    for m in metrics:
        if metric_labels and m in metric_labels:
            labels.append(metric_labels[m])
        else:
            label = m.replace('count_', '').replace('_phases_per_90', ' P90')
            label = label.replace('_percentage', '').replace('_', ' ').title()
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
      <link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;500;600;700&display=swap" rel="stylesheet">
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
          font-family: 'Chakra Petch', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          background: white;
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 0;
        }}
        .radar-container {{
          position: relative;
          width: 700px;
          height: 700px;
        }}
        canvas {{
          display: block;
        }}
      </style>
    </head>
    <body>
      <div class="radar-container" id="radar-container">
        <canvas id="radar" width="700" height="700"></canvas>
      </div>

      <script>
        const data = {json.dumps(data)};

        function drawRadar() {{
        const canvas = document.getElementById('radar');
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;

        const W = 700;
        const H = 700;
        canvas.width = W * dpr;
        canvas.height = H * dpr;
        canvas.style.width = W + 'px';
        canvas.style.height = H + 'px';
        ctx.scale(dpr, dpr);

        const cx = W / 2;
        const cy = H / 2;

        // Matplotlib coordinate mapping:
        // ylim = [0, 120], bottom = 10, so bars go from r=10 to r=10+pct
        // Rings: 25th=35, 50th=60, 75th=85, 100th=110
        const scale = 1.85;
        function yToR(y) {{ return y * scale; }}

        const innerR = yToR(10);        // ~24.5
        const ring25 = yToR(35);        // ~85.8
        const ring50 = yToR(60);        // ~147
        const ring75 = yToR(85);        // ~208.3
        const ring100 = yToR(110);      // ~269.5
        const valueY = yToR(105);       // where actual values sit
        const titleY = yToR(138);       // title position above

        const n = data.labels.length;
        const sliceWidth = (2 * Math.PI) / n;

        // Replicate matplotlib theta: linspace then rotate last to front
        // theta_offset = pi/2 (start at top), direction = -1 (clockwise)
        // In canvas: 0 rad = right, so top = -pi/2
        // matplotlib angle -> canvas angle: canvas_angle = -(mpl_angle) - pi/2
        const mplTheta = [];
        for (let i = 0; i < n; i++) {{
          mplTheta.push((2 * Math.PI * i) / n);
        }}
        // Rotate last to front (like theta.insert(0, theta.pop(-1)))
        mplTheta.unshift(mplTheta.pop());

        // Convert mpl polar angle to canvas angle
        // mpl: theta_offset=pi/2, direction=-1 → theta=0 at top, clockwise
        // canvas: angle=0 at right, clockwise
        // So: canvas_angle = mpl_theta - pi/2
        function toCanvasAngle(mplAngle) {{
          return mplAngle - Math.PI / 2;
        }}

        const canvasAngles = mplTheta.map(t => toCanvasAngle(t));

        // --- Draw dashed percentile rings ---
        ctx.save();
        ctx.strokeStyle = data.text_color;
        ctx.lineWidth = 1;
        ctx.setLineDash([6, 6]);
        [ring25, ring50, ring75, ring100].forEach(r => {{
          ctx.beginPath();
          ctx.arc(cx, cy, r, 0, 2 * Math.PI);
          ctx.stroke();
        }});
        ctx.setLineDash([]);
        ctx.restore();

        // --- Draw filled bars ---
        data.percentiles.forEach((pct, i) => {{
          if (pct === null || pct === 0) return;
          const barR = yToR(10 + pct);
          const angle = canvasAngles[i];
          const aStart = angle - sliceWidth / 2;
          const aEnd = angle + sliceWidth / 2;

          ctx.beginPath();
          ctx.arc(cx, cy, barR, aStart, aEnd);
          ctx.arc(cx, cy, innerR, aEnd, aStart, true);
          ctx.closePath();
          ctx.fillStyle = data.bar_color;
          ctx.globalAlpha = 0.95;
          ctx.fill();
          ctx.globalAlpha = 1.0;
        }});

        // --- Draw white spoke dividers on top of bars ---
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 2;
        canvasAngles.forEach(angle => {{
          const a = angle - sliceWidth / 2;
          ctx.beginPath();
          ctx.moveTo(cx + innerR * Math.cos(a), cy + innerR * Math.sin(a));
          ctx.lineTo(cx + ring100 * Math.cos(a), cy + ring100 * Math.sin(a));
          ctx.stroke();
        }});

        // --- White inner circle ---
        ctx.beginPath();
        ctx.arc(cx, cy, innerR, 0, 2 * Math.PI);
        ctx.fillStyle = 'white';
        ctx.fill();

        // --- Percentile ring labels on one spoke ---
        // In matplotlib: y_axis_pos = closest theta to 1.8 rad, offset by width*0.5
        let ringLabelMpl = mplTheta.reduce((prev, curr) =>
          Math.abs(curr - 1.8) < Math.abs(prev - 1.8) ? curr : prev
        );
        ringLabelMpl += sliceWidth * 0.5;
        const ringLabelAngle = toCanvasAngle(ringLabelMpl);

        ctx.font = 'bold 10px Chakra Petch, -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        const ringLabels = [
          {{ r: ring25, text: '25' }},
          {{ r: ring50, text: '50' }},
          {{ r: ring75, text: '75' }},
        ];

        ringLabels.forEach(rl => {{
          const lx = cx + rl.r * Math.cos(ringLabelAngle);
          const ly = cy + rl.r * Math.sin(ringLabelAngle);
          ctx.strokeStyle = 'white';
          ctx.lineWidth = 3;
          ctx.fillStyle = data.text_color;
          ctx.font = 'bold 10px Chakra Petch, -apple-system, BlinkMacSystemFont, sans-serif';
          ctx.strokeText(rl.text, lx, ly);
          ctx.fillText(rl.text, lx, ly);
        }});

        // 100th Percentile label
        const lx100 = cx + ring100 * Math.cos(ringLabelAngle);
        const ly100 = cy + ring100 * Math.sin(ringLabelAngle);
        ctx.font = 'bold 10px Chakra Petch, -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.textAlign = 'left';
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 3;
        ctx.strokeText('100th', lx100 + 2, ly100 - 6);
        ctx.fillText('100th', lx100 + 2, ly100 - 6);
        ctx.strokeText('Percentile', lx100 + 2, ly100 + 6);
        ctx.fillText('Percentile', lx100 + 2, ly100 + 6);
        ctx.textAlign = 'center';

        // --- Helper: compute canvas rotation from mpl theta ---
        // Matplotlib set_rotation formula:
        //   mpl_angle_deg = mplTheta * 180 / pi
        //   if 0<=deg<=90 or 270<=deg<=360: rot = -deg (CW in mpl = CCW screen)
        //   else: rot = 180 - deg
        // mpl rotation is CCW degrees, canvas rotate() is CW radians
        // So canvas_rot = -mpl_rot_deg * pi / 180
        function spokeRotation(mplAngle) {{
          const deg = ((mplAngle * 180 / Math.PI) % 360 + 360) % 360;
          let mplRotDeg;
          if ((deg >= 0 && deg <= 90) || (deg >= 270 && deg <= 360)) {{
            mplRotDeg = -deg;
          }} else {{
            mplRotDeg = 180 - deg;
          }}
          return -mplRotDeg * Math.PI / 180;
        }}

        // --- Actual values at fixed radius just inside the outer ring ---
        const fixedValueR = yToR(95);
        ctx.font = 'bold 11px Chakra Petch, -apple-system, BlinkMacSystemFont, sans-serif';
        data.actuals.forEach((val, i) => {{
          if (val === null) return;
          const cAngle = canvasAngles[i];
          const vx = cx + fixedValueR * Math.cos(cAngle);
          const vy = cy + fixedValueR * Math.sin(cAngle);

          ctx.save();
          ctx.translate(vx, vy);
          ctx.rotate(spokeRotation(mplTheta[i]));

          const text = String(val);
          const tw = ctx.measureText(text).width;
          const pad = 3;

          // White background pill instead of strokeText (avoids spiky artifacts)
          ctx.fillStyle = 'rgba(255,255,255,0.85)';
          ctx.beginPath();
          const rr = 3;
          const rx = -tw / 2 - pad;
          const ry = -7;
          const rw = tw + pad * 2;
          const rh = 14;
          ctx.roundRect(rx, ry, rw, rh, rr);
          ctx.fill();

          ctx.fillStyle = data.text_color;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(text, 0, 0);

          ctx.restore();
        }});

        // --- Metric labels (uppercase, bold green, outside, rotated along spoke) ---
        const labelR = ring100 + 22;

        data.labels.forEach((label, i) => {{
          const cAngle = canvasAngles[i];
          const lx = cx + labelR * Math.cos(cAngle);
          const ly = cy + labelR * Math.sin(cAngle);

          ctx.save();
          ctx.translate(lx, ly);
          ctx.rotate(spokeRotation(mplTheta[i]));

          ctx.fillStyle = data.bar_color;
          ctx.font = 'bold 14px Chakra Petch, -apple-system, BlinkMacSystemFont, sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';

          // Word-wrap uppercase
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

          const lineHeight = 16;
          lines.forEach((line, li) => {{
            ctx.fillText(line, 0, (li - (lines.length - 1) / 2) * lineHeight);
          }});

          ctx.restore();
        }});

        // Title removed — shown via PPTX slide title instead

        // --- Grid: no x-grid, y-grid already drawn as dashed rings ---
        // Remove polar spine (nothing to do in canvas, already clean)

        }} // end drawRadar

        // Wait for Chakra Petch font to load before drawing
        document.fonts.ready.then(() => {{ drawRadar(); }});
      </script>
    </body>
    </html>
    """

    return html
