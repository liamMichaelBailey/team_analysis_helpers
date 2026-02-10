import pandas as pd
import json
import numpy as np


def safe_json(df):
    def convert_value(x):
        if isinstance(x, pd.Timestamp):
            return x.isoformat()
        elif pd.isna(x):
            return None
        return x

    df_clean = df.applymap(convert_value)
    return df_clean


def pitch_component(
        events_df: pd.DataFrame,
        performance_df: pd.DataFrame,
        team_in_possession_id,
        phase: str,
        event_types=None,
        match_col: str = "match_id",
        match_label_col: str = None,
        title: str = "Team Shape",
        width_label: str = "Av. Width",
        length_label: str = "Av. Length",
        primary_color: str = "#006600",
        secondary_color: str = "#99E59A",
        base_color: str = "#888888",
        text_color: str = "#333333",
        highlight_entity: str = None,
        pitch_width_px: int = 350,
        pitch_height_px: int = 230,
        cols_per_row: int = 3,
        match_date_col: str = "match_date"
):
    """
    Streamlit custom component for football pitch plots showing average player positions.
    Creates a subplot for each match found in the DataFrame.
    Starts from raw events and computes average positions internally.

    Parameters:
    -----------
    events_df : pd.DataFrame
        Raw events DataFrame with columns: player_id, player_name, team_id,
        team_shortname, team_in_possession_phase_type, player_position,
        x_start, y_start, event_type, xthreat, xpass_completion, match_id
    performance_df : pd.DataFrame
        Performance DataFrame with columns: id, start_time, match_id
    team_in_possession_id : int/str
        The team_id to plot positions for.
    phase : str
        The phase type to filter on (e.g. 'build_up', 'create', etc.)
    match_col : str
        Column name for match identifier.
    match_label_col : str, optional
        Column to use for subplot titles. If None, uses match_col.
    title : str
        Overall title for the component.
    width_label : str
        Label text for width measurement.
    length_label : str
        Label text for length measurement.
    primary_color : str
        Color for average/starter position dots.
    secondary_color : str
        Color for hull, width/length lines.
    base_color : str
        Color for substitute position dots.
    text_color : str
        Color for text elements.
    highlight_entity : str, optional
        Match label to highlight.
    pitch_width_px : int
        Width of each pitch in pixels.
    pitch_height_px : int
        Height of each pitch in pixels.
    cols_per_row : int
        Number of pitch subplots per row.
    """

    # SkillCorner pitch: 105x68, centered at 0,0
    # x: -52.5 to 52.5, y: -34 to 34
    if event_types is None:
        event_types = ["player_possession", "passing_option"]

    pitch_length = 105
    pitch_width = 68
    x_min, x_max = -pitch_length / 2, pitch_length / 2
    y_min, y_max = -pitch_width / 2, pitch_width / 2

    # Build dict of starter player_ids per match from performance_df
    team_perf = performance_df[performance_df['team_id'] == team_in_possession_id] if 'team_id' in performance_df.columns else performance_df
    starter_ids_by_match = {}
    for mid in events_df[match_col].unique():
        match_perf = team_perf[team_perf[match_col] == mid] if match_col in team_perf.columns else team_perf
        if 'player_role_acronym' in match_perf.columns:
            ids = set(match_perf[match_perf['player_role_acronym'] != 'SUB']['player_id'].tolist())
        elif 'start_time' in match_perf.columns:
            ids = set(match_perf[match_perf['start_time'] == '00:00:00']['player_id'].tolist())
        else:
            ids = set(match_perf['player_id'].tolist()) if 'player_id' in match_perf.columns else set()
        starter_ids_by_match[mid] = ids

    # Aggregate all events first
    relevant_events = events_df[events_df['event_type'].isin(event_types)]
    relevant_events = relevant_events.merge(performance_df[['match_id', 'player_id', 'start_time']], on=['match_id', 'player_id'])
    relevant_events = relevant_events[relevant_events['start_time'] == '00:00:00']

    average_pos_df = relevant_events.groupby([match_col, 'player_id', 'player_name', 'team_id',
                                     'team_shortname', 'team_in_possession_phase_type',
                                     'player_position'],observed=True).agg({'x_start': 'mean',
                                                              'y_start': 'mean',
                                                              'xthreat': 'sum',
                                                              'xpass_completion': 'sum',
                                                              }).reset_index()

    # Filter for team, phase, and only starters for each specific match
    avg_filtered = average_pos_df[
        (average_pos_df['team_id'] == team_in_possession_id) &
        (average_pos_df['team_in_possession_phase_type'] == phase)
    ].copy()
    avg_filtered = avg_filtered[
        avg_filtered.apply(
            lambda row: row['player_id'] in starter_ids_by_match.get(row[match_col], set()), axis=1
        )
    ]

    # Get unique matches sorted by date descending (newest first)
    if match_date_col in avg_filtered.columns:
        match_dates = avg_filtered.groupby(match_col,observed=True)[match_date_col].first().reset_index()
        match_dates[match_date_col] = pd.to_datetime(match_dates[match_date_col], errors='coerce')
        match_dates = match_dates.sort_values(match_date_col, ascending=False)
        matches = match_dates[match_col].tolist()
    elif match_date_col in events_df.columns:
        match_dates = events_df.groupby(match_col,observed=True)[match_date_col].first().reset_index()
        match_dates[match_date_col] = pd.to_datetime(match_dates[match_date_col], errors='coerce')
        match_dates = match_dates.sort_values(match_date_col, ascending=False)
        matches = match_dates[match_col].tolist()
    else:
        matches = sorted(avg_filtered[match_col].unique(), reverse=True)

    if match_label_col is None:
        match_label_col = match_col

    # Build data per match
    match_data = []
    for match_id in matches:
        match_df = avg_filtered[avg_filtered[match_col] == match_id]

        match_label = str(match_df[match_label_col].iloc[0]) if len(match_df) > 0 else str(match_id)

        # Player positions
        starters = []
        for _, row in match_df.iterrows():
            starters.append({
                "name": str(row['player_name']),
                "x": float(row['x_start']),
                "y": float(row['y_start']),
                "position": str(row.get('player_position', ''))
            })

        # Compute hull, width, length from starters (excluding GK)
        outfield = [p for p in starters if p['position'] != 'GK']
        if len(outfield) >= 3:
            xs = [p['x'] for p in outfield]
            ys = [p['y'] for p in outfield]
            team_width = round(max(ys) - min(ys), 1)
            team_length = round(max(xs) - min(xs), 1)
            y_min_of = min(ys)
            y_max_of = max(ys)
            x_min_of = min(xs)
            x_max_of = max(xs)

            # Compute convex hull
            points = np.array(list(zip(xs, ys)))
            from scipy.spatial import ConvexHull
            try:
                hull = ConvexHull(points)
                hull_points = [[float(points[v][0]), float(points[v][1])] for v in hull.vertices]
                # Close the polygon
                hull_points.append(hull_points[0])
            except Exception:
                hull_points = []
        else:
            team_width = 0
            team_length = 0
            y_min_of = 0
            y_max_of = 0
            x_min_of = 0
            x_max_of = 0
            hull_points = []

        match_data.append({
            "match_id": str(match_id),
            "label": match_label,
            "starters": starters,
            "hull": hull_points,
            "team_width": team_width,
            "team_length": team_length,
            "y_min": y_min_of,
            "y_max": y_max_of,
            "x_min": x_min_of,
            "x_max": x_max_of
        })

    data = {
        "matches": match_data,
        "title": title,
        "width_label": width_label,
        "length_label": length_label,
        "primary_color": primary_color,
        "secondary_color": secondary_color,
        "base_color": base_color,
        "text_color": text_color,
        "highlight_entity": highlight_entity,
        "pitch_width_px": pitch_width_px,
        "pitch_height_px": pitch_height_px,
        "cols_per_row": cols_per_row,
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max
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
          padding: 10px;
        }}
        .title {{
          font-size: 16px;
          font-weight: bold;
          color: {text_color};
          margin-bottom: 12px;
          text-align: center;
        }}
        .grid {{
          display: flex;
          flex-wrap: wrap;
          gap: 16px;
          justify-content: flex-start;
        }}
        .pitch-card {{
          display: flex;
          flex-direction: column;
          align-items: center;
          position: relative;
        }}
        .pitch-download {{
          width: 20px;
          height: 20px;
          border-radius: 50%;
          border: none;
          background: #006600;
          color: white;
          cursor: pointer;
          font-size: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          position: absolute;
          top: 0;
          right: 0;
          opacity: 0;
          transition: opacity 0.2s;
        }}
        .pitch-card:hover .pitch-download {{
          opacity: 1;
        }}
        .pitch-download:hover {{ transform: scale(1.1); }}
        .pitch-label {{
          font-size: 12px;
          font-weight: 600;
          color: {text_color};
          margin-bottom: 4px;
          text-align: center;
        }}
        .pitch-label.highlighted {{
          font-weight: bold;
          font-size: 13px;
          color: {primary_color};
        }}
        canvas {{
          border-radius: 4px;
        }}
        .download-btn {{
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
          margin-bottom: 8px;
        }}
        .download-btn:hover {{ transform: scale(1.1); }}
      </style>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    </head>
    <body>
      <button class="download-btn" onclick="downloadPNG()" title="Download PNG">&#11015;</button>
      <div id="export-area">
        <div class="grid" id="grid"></div>
      </div>

      <script>
        const data = {json.dumps(data)};
        const grid = document.getElementById('grid');
        const dpr = 4;
        const PW = data.pitch_width_px;
        const PH = data.pitch_height_px;

        // Pitch coordinate system: SkillCorner 105x68 centered at 0,0
        const xMin = data.x_min;
        const xMax = data.x_max;
        const yMin = data.y_min;
        const yMax = data.y_max;

        // Padding around pitch for measurement labels
        const padLeft = 35;
        const padRight = 35;
        const padTop = 15;
        const padBottom = 15;
        const canvasW = PW + padLeft + padRight;
        const canvasH = PH + padTop + padBottom;

        function toCanvasX(x) {{
          return padLeft + ((x - xMin) / (xMax - xMin)) * PW;
        }}

        function toCanvasY(y) {{
          // Flip y so positive y goes up on pitch
          return padTop + ((yMax - y) / (yMax - yMin)) * PH;
        }}

        function drawPitch(ctx) {{
          const left = padLeft;
          const top = padTop;
          const right = padLeft + PW;
          const bottom = padTop + PH;
          const cx = padLeft + PW / 2;
          const cy = padTop + PH / 2;

          // Pitch background
          ctx.fillStyle = '#f0f7f0';
          ctx.fillRect(left, top, PW, PH);

          ctx.strokeStyle = '#8a9a8a';
          ctx.lineWidth = 0.75;
          ctx.lineCap = 'round';
          ctx.lineJoin = 'round';

          // Outer boundary
          ctx.strokeRect(left, top, PW, PH);

          // Half line
          ctx.beginPath();
          ctx.moveTo(cx, top);
          ctx.lineTo(cx, bottom);
          ctx.stroke();

          // Center circle
          const centerR = (9.15 / 68) * PH;
          ctx.beginPath();
          ctx.arc(cx, cy, centerR, 0, 2 * Math.PI);
          ctx.stroke();

          // Center dot
          ctx.beginPath();
          ctx.arc(cx, cy, 1.5, 0, 2 * Math.PI);
          ctx.fillStyle = '#8a9a8a';
          ctx.fill();

          // Penalty areas (16.5m from goal line, 40.32m wide)
          const paW = (16.5 / 105) * PW;
          const paH = (40.32 / 68) * PH;
          const paTop = cy - paH / 2;

          // Left penalty area
          ctx.strokeRect(left, paTop, paW, paH);
          // Right penalty area
          ctx.strokeRect(right - paW, paTop, paW, paH);

          // Goal areas (5.5m from goal line, 18.32m wide)
          const gaW = (5.5 / 105) * PW;
          const gaH = (18.32 / 68) * PH;
          const gaTop = cy - gaH / 2;

          ctx.strokeRect(left, gaTop, gaW, gaH);
          ctx.strokeRect(right - gaW, gaTop, gaW, gaH);

          // Penalty spots
          const penSpotDist = (11 / 105) * PW;
          ctx.fillStyle = '#8a9a8a';
          ctx.beginPath();
          ctx.arc(left + penSpotDist, cy, 1.5, 0, 2 * Math.PI);
          ctx.fill();
          ctx.beginPath();
          ctx.arc(right - penSpotDist, cy, 1.5, 0, 2 * Math.PI);
          ctx.fill();

          // Penalty arcs
          const penArcR = (9.15 / 68) * PH;
          ctx.beginPath();
          ctx.arc(left + penSpotDist, cy, penArcR, -0.6, 0.6);
          ctx.stroke();
          ctx.beginPath();
          ctx.arc(right - penSpotDist, cy, penArcR, Math.PI - 0.6, Math.PI + 0.6);
          ctx.stroke();
        }}

        function drawHull(ctx, hull, color) {{
          if (hull.length < 3) return;
          ctx.beginPath();
          ctx.moveTo(toCanvasX(hull[0][0]), toCanvasY(hull[0][1]));
          for (let i = 1; i < hull.length; i++) {{
            ctx.lineTo(toCanvasX(hull[i][0]), toCanvasY(hull[i][1]));
          }}
          ctx.closePath();
          ctx.fillStyle = color + '30'; // ~19% alpha
          ctx.fill();
          ctx.strokeStyle = data.primary_color + 'AA';
          ctx.lineWidth = 1.2;
          ctx.setLineDash([4, 3]);
          ctx.stroke();
          ctx.setLineDash([]);
        }}

        function drawPlayer(ctx, x, y, name, radius, fillColor, fontSize, fontWeight) {{
          const cx = toCanvasX(x);
          const cy = toCanvasY(y);

          // Shadow for depth
          ctx.save();
          ctx.shadowColor = 'rgba(0,0,0,0.25)';
          ctx.shadowBlur = 4;
          ctx.shadowOffsetX = 1;
          ctx.shadowOffsetY = 1;

          // Circle
          ctx.beginPath();
          ctx.arc(cx, cy, radius, 0, 2 * Math.PI);
          ctx.fillStyle = fillColor;
          ctx.fill();
          ctx.restore();

          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(cx, cy, radius, 0, 2 * Math.PI);
          ctx.stroke();

          // Name with white outline effect
          ctx.font = fontWeight + ' ' + fontSize + 'px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';

          // White stroke
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 3;
          ctx.lineJoin = 'round';
          ctx.strokeText(name, cx, cy);

          // Text
          ctx.fillStyle = data.text_color;
          ctx.fillText(name, cx, cy);
        }}

        function drawWidthLines(ctx, matchData) {{
          if (matchData.team_width === 0) return;

          const color = data.secondary_color;
          const leftX = padLeft - 18;
          const rightX = padLeft + PW + 18;
          const yMinC = toCanvasY(matchData.y_max);
          const yMaxC = toCanvasY(matchData.y_min);

          ctx.strokeStyle = color;
          ctx.lineWidth = 1.5;

          // Left line
          ctx.beginPath();
          ctx.moveTo(leftX, yMinC);
          ctx.lineTo(leftX, yMaxC);
          ctx.stroke();

          // Right line
          ctx.beginPath();
          ctx.moveTo(rightX, yMinC);
          ctx.lineTo(rightX, yMaxC);
          ctx.stroke();

          // Arrow heads (top and bottom)
          const arrowSize = 5;
          // Left top arrow
          ctx.beginPath();
          ctx.moveTo(leftX - arrowSize, yMinC + arrowSize);
          ctx.lineTo(leftX, yMinC);
          ctx.lineTo(leftX + arrowSize, yMinC + arrowSize);
          ctx.stroke();
          // Left bottom arrow
          ctx.beginPath();
          ctx.moveTo(leftX - arrowSize, yMaxC - arrowSize);
          ctx.lineTo(leftX, yMaxC);
          ctx.lineTo(leftX + arrowSize, yMaxC - arrowSize);
          ctx.stroke();
          // Right top arrow
          ctx.beginPath();
          ctx.moveTo(rightX - arrowSize, yMinC + arrowSize);
          ctx.lineTo(rightX, yMinC);
          ctx.lineTo(rightX + arrowSize, yMinC + arrowSize);
          ctx.stroke();
          // Right bottom arrow
          ctx.beginPath();
          ctx.moveTo(rightX - arrowSize, yMaxC - arrowSize);
          ctx.lineTo(rightX, yMaxC);
          ctx.lineTo(rightX + arrowSize, yMaxC - arrowSize);
          ctx.stroke();

          // Width text (rotated)
          const midY = (yMinC + yMaxC) / 2;
          const widthText = data.width_label + ' ' + matchData.team_width + 'm';

          ctx.save();
          ctx.font = '10px sans-serif';
          ctx.fillStyle = data.text_color;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';

          // Left label
          ctx.save();
          ctx.translate(leftX - 8, midY);
          ctx.rotate(-Math.PI / 2);
          ctx.fillText(widthText, 0, 0);
          ctx.restore();

          // Right label
          ctx.save();
          ctx.translate(rightX + 8, midY);
          ctx.rotate(Math.PI / 2);
          ctx.fillText(widthText, 0, 0);
          ctx.restore();

          ctx.restore();
        }}

        function drawLengthLines(ctx, matchData) {{
          if (matchData.team_length === 0) return;

          const color = data.secondary_color;
          const lineY = padTop + PH + 10;
          const xMinC = toCanvasX(matchData.x_min);
          const xMaxC = toCanvasX(matchData.x_max);

          ctx.strokeStyle = color;
          ctx.lineWidth = 1.5;

          // Horizontal line
          ctx.beginPath();
          ctx.moveTo(xMinC, lineY);
          ctx.lineTo(xMaxC, lineY);
          ctx.stroke();

          // Arrow heads
          const arrowSize = 5;
          // Left arrow
          ctx.beginPath();
          ctx.moveTo(xMinC + arrowSize, lineY - arrowSize);
          ctx.lineTo(xMinC, lineY);
          ctx.lineTo(xMinC + arrowSize, lineY + arrowSize);
          ctx.stroke();
          // Right arrow
          ctx.beginPath();
          ctx.moveTo(xMaxC - arrowSize, lineY - arrowSize);
          ctx.lineTo(xMaxC, lineY);
          ctx.lineTo(xMaxC - arrowSize, lineY + arrowSize);
          ctx.stroke();

          // Length text
          const midX = (xMinC + xMaxC) / 2;
          const lengthText = data.length_label + ' ' + matchData.team_length + 'm';
          ctx.font = '10px sans-serif';
          ctx.fillStyle = data.text_color;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          ctx.fillText(lengthText, midX, lineY - 12);
        }}

        function renderPitch(matchData) {{
          const card = document.createElement('div');
          card.className = 'pitch-card';

          const dlBtn = document.createElement('button');
          dlBtn.className = 'pitch-download';
          dlBtn.innerHTML = '&#11015;';
          dlBtn.title = 'Download this pitch';
          dlBtn.onclick = function(e) {{
            e.stopPropagation();
            const cardCanvas = card.querySelector('canvas');
            if (cardCanvas) {{
              const link = document.createElement('a');
              link.href = cardCanvas.toDataURL('image/png');
              link.download = 'pitch_' + matchData.label.replace(/[^a-zA-Z0-9]/g, '_') + '.png';
              link.click();
            }}
          }};
          card.appendChild(dlBtn);

          const label = document.createElement('div');
          label.className = 'pitch-label';
          if (data.highlight_entity && matchData.label === data.highlight_entity) {{
            label.classList.add('highlighted');
          }}
          label.textContent = matchData.label;
          card.appendChild(label);

          const canvas = document.createElement('canvas');
          canvas.width = canvasW * dpr;
          canvas.height = canvasH * dpr;
          canvas.style.width = canvasW + 'px';
          canvas.style.height = canvasH + 'px';
          card.appendChild(canvas);

          const ctx = canvas.getContext('2d');
          ctx.scale(dpr, dpr);
          ctx.imageSmoothingEnabled = true;
          ctx.imageSmoothingQuality = 'high';
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(0, 0, canvasW, canvasH);

          // Draw pitch markings
          drawPitch(ctx);

          // Draw convex hull
          drawHull(ctx, matchData.hull, data.secondary_color);

          // Draw width and length measurement lines
          drawWidthLines(ctx, matchData);
          drawLengthLines(ctx, matchData);

          // Draw player positions
          matchData.starters.forEach(p => {{
            drawPlayer(ctx, p.x, p.y, p.name, 9, data.primary_color, 7, 'bold');
          }});

          return card;
        }}

        // Render all matches
        data.matches.forEach(matchData => {{
          const card = renderPitch(matchData);
          grid.appendChild(card);
        }});

        function downloadPNG() {{
          const downloadBtn = document.querySelector('.download-btn');
          if (downloadBtn) downloadBtn.style.visibility = 'hidden';

          const exportArea = document.getElementById('export-area');
          html2canvas(exportArea, {{
            scale: 5,
            useCORS: true,
            backgroundColor: '#ffffff'
          }}).then(sourceCanvas => {{
            const targetWidth = 3840;
            const targetHeight = 2160;
            const finalCanvas = document.createElement('canvas');
            finalCanvas.width = targetWidth;
            finalCanvas.height = targetHeight;
            const ctx = finalCanvas.getContext('2d');

            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, targetWidth, targetHeight);

            const padding = 60;
            const availableWidth = targetWidth - (padding * 2);
            const availableHeight = targetHeight - (padding * 2);
            const scaleX = availableWidth / sourceCanvas.width;
            const scaleY = availableHeight / sourceCanvas.height;
            const fitScale = Math.min(scaleX, scaleY);

            const scaledWidth = sourceCanvas.width * fitScale;
            const scaledHeight = sourceCanvas.height * fitScale;
            const offsetX = (targetWidth - scaledWidth) / 2;
            const offsetY = (targetHeight - scaledHeight) / 2;

            ctx.drawImage(sourceCanvas, offsetX, offsetY, scaledWidth, scaledHeight);

            const link = document.createElement('a');
            link.href = finalCanvas.toDataURL('image/png');
            link.download = 'pitch_positions.png';
            link.click();

            if (downloadBtn) downloadBtn.style.visibility = 'visible';
          }});
        }}
      </script>
    </body>
    </html>
    """

    return html
