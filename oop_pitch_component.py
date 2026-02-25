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


def defensive_heatmap_component(
        events_df: pd.DataFrame,
        team_id,
        phase: str = None,
        match_col: str = "match_id",
        match_label_col: str = None,
        match_date_col: str = "match_date",
        event_type_filter: str = "on_ball_engagement",
        grid_cols: int = 6,
        grid_rows: int = 5,
        primary_color: str = "#006600",
        text_color: str = "#333333",
        highlight_entity: str = None,
        pitch_width_px: int = 350,
        pitch_height_px: int = 230,
        cols_per_row: int = 3
):
    """
    Streamlit custom component for defensive heatmap on a football pitch.
    Bins event locations into a grid and shows density per zone.
    Creates a subplot for each match found in the DataFrame.

    Parameters:
    -----------
    events_df : pd.DataFrame
        Raw events DataFrame with columns: event_type, x_start, y_start, team_id, match_id
    team_id : int/str
        The team_id to filter events for.
    match_col : str
        Column name for match identifier.
    match_label_col : str, optional
        Column to use for subplot titles. If None, uses match_col.
    match_date_col : str
        Column name for match date, used for sorting.
    event_type_filter : str
        Event type to filter on (default: 'on_ball_engagement').
    grid_cols : int
        Number of columns in the heatmap grid (along pitch length).
    grid_rows : int
        Number of rows in the heatmap grid (along pitch width).
    primary_color : str
        Base color for heatmap intensity.
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
    pitch_length = 105
    pitch_width = 68
    x_min, x_max = -pitch_length / 2, pitch_length / 2
    y_min, y_max = -pitch_width / 2, pitch_width / 2

    # Filter events
    mask = (events_df['event_type'] == event_type_filter) & (events_df['team_id'] == team_id)
    if phase is not None and 'team_out_of_possession_phase_type' in events_df.columns:
        mask = mask & (events_df['team_out_of_possession_phase_type'] == phase)
    filtered = events_df[mask].copy()

    # Sort matches by date descending
    if match_date_col in filtered.columns:
        match_dates = filtered.groupby(match_col)[match_date_col].first().reset_index()
        match_dates[match_date_col] = pd.to_datetime(match_dates[match_date_col], errors='coerce')
        match_dates = match_dates.sort_values(match_date_col, ascending=False)
        matches = match_dates[match_col].tolist()
    elif match_date_col in events_df.columns:
        match_dates = events_df.groupby(match_col)[match_date_col].first().reset_index()
        match_dates[match_date_col] = pd.to_datetime(match_dates[match_date_col], errors='coerce')
        match_dates = match_dates.sort_values(match_date_col, ascending=False)
        matches = match_dates[match_col].tolist()
    else:
        matches = sorted(filtered[match_col].unique(), reverse=True)

    if match_label_col is None:
        match_label_col = match_col

    # Grid bin edges
    x_edges = np.linspace(x_min, x_max, grid_cols + 1)
    y_edges = np.linspace(y_min, y_max, grid_rows + 1)

    # Build data per match
    match_data = []
    global_max = 0

    for match_id in matches:
        match_events = filtered[filtered[match_col] == match_id]
        if len(match_events) == 0:
            continue

        if match_label_col in match_events.columns:
            match_label = str(match_events[match_label_col].iloc[0])
        else:
            match_label = str(match_id)

        # Bin the events into the grid
        grid = np.zeros((grid_rows, grid_cols), dtype=int)
        for _, row in match_events.iterrows():
            x_val = row['x_start']
            y_val = row['y_start']
            # Clamp to pitch bounds
            x_val = max(x_min, min(x_max - 0.001, x_val))
            y_val = max(y_min, min(y_max - 0.001, y_val))

            col_idx = int((x_val - x_min) / (x_max - x_min) * grid_cols)
            row_idx = int((y_val - y_min) / (y_max - y_min) * grid_rows)
            col_idx = min(col_idx, grid_cols - 1)
            row_idx = min(row_idx, grid_rows - 1)
            grid[row_idx][col_idx] += 1

        local_max = int(grid.max())
        if local_max > global_max:
            global_max = local_max

        total_events = int(grid.sum())

        match_data.append({
            "match_id": str(match_id),
            "label": match_label,
            "grid": grid.tolist(),
            "total": total_events
        })

    data = {
        "matches": match_data,
        "grid_cols": grid_cols,
        "grid_rows": grid_rows,
        "global_max": global_max,
        "primary_color": primary_color,
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
          background: {primary_color};
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
        .pitch-total {{
          font-size: 10px;
          color: #888;
          margin-top: 2px;
        }}
        canvas {{
          border-radius: 4px;
        }}
        .download-btn {{
          width: 28px;
          height: 28px;
          border-radius: 50%;
          border: none;
          background: {primary_color};
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

        const xMin = data.x_min;
        const xMax = data.x_max;
        const yMin = data.y_min;
        const yMax = data.y_max;

        const padLeft = 10;
        const padRight = 10;
        const padTop = 10;
        const padBottom = 10;
        const canvasW = PW + padLeft + padRight;
        const canvasH = PH + padTop + padBottom;

        // Parse hex color to RGB
        function hexToRgb(hex) {{
          const result = /^#?([a-f\\d]{{2}})([a-f\\d]{{2}})([a-f\\d]{{2}})$/i.exec(hex);
          return result ? {{
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
          }} : {{ r: 0, g: 102, b: 0 }};
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

          // Penalty areas
          const paW = (16.5 / 105) * PW;
          const paH = (40.32 / 68) * PH;
          const paTop = cy - paH / 2;
          ctx.strokeRect(left, paTop, paW, paH);
          ctx.strokeRect(right - paW, paTop, paW, paH);

          // Goal areas
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

        function drawHeatmapGrid(ctx, gridData, globalMax) {{
          if (globalMax === 0) return;

          const left = padLeft;
          const top = padTop;
          const cellW = PW / data.grid_cols;
          const cellH = PH / data.grid_rows;
          const rgb = hexToRgb(data.primary_color);

          for (let r = 0; r < data.grid_rows; r++) {{
            for (let c = 0; c < data.grid_cols; c++) {{
              const count = gridData[r][c];
              if (count === 0) continue;

              const intensity = count / globalMax;
              const alpha = 0.1 + intensity * 0.7;

              const x = left + c * cellW;
              // y axis: row 0 = y_min (bottom of pitch visually = top numerically)
              const y = top + (data.grid_rows - 1 - r) * cellH;

              ctx.fillStyle = 'rgba(' + rgb.r + ',' + rgb.g + ',' + rgb.b + ',' + alpha + ')';
              ctx.beginPath();
              ctx.roundRect(x + 1, y + 1, cellW - 2, cellH - 2, 3);
              ctx.fill();

              // Count text
              ctx.font = 'bold 10px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = intensity > 0.5 ? '#ffffff' : data.text_color;
              ctx.fillText(count, x + cellW / 2, y + cellH / 2);
            }}
          }}
        }}

        function renderPitch(matchData) {{
          const card = document.createElement('div');
          card.className = 'pitch-card';

          // Per-pitch download button
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
              link.download = 'defensive_' + matchData.label.replace(/[^a-zA-Z0-9]/g, '_') + '.png';
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

          drawPitch(ctx);
          drawHeatmapGrid(ctx, matchData.grid, data.global_max);

          // Total count label
          const total = document.createElement('div');
          total.className = 'pitch-total';
          total.textContent = matchData.total + ' engagements';
          card.appendChild(total);

          return card;
        }}

        // Render all matches
        data.matches.forEach(matchData => {{
          const card = renderPitch(matchData);
          grid.appendChild(card);
        }});

        // Main download
        function downloadPNG() {{
          const exportArea = document.getElementById('export-area');
          html2canvas(exportArea, {{
            scale: 5,
            useCORS: true,
            backgroundColor: '#ffffff'
          }}).then(sourceCanvas => {{
            const targetWidth = 3840;
            const targetHeight = 2160;

            const scale = Math.min(targetWidth / sourceCanvas.width, targetHeight / sourceCanvas.height);
            const finalCanvas = document.createElement('canvas');
            finalCanvas.width = targetWidth;
            finalCanvas.height = targetHeight;
            const finalCtx = finalCanvas.getContext('2d');
            finalCtx.imageSmoothingEnabled = true;
            finalCtx.imageSmoothingQuality = 'high';
            finalCtx.fillStyle = '#ffffff';
            finalCtx.fillRect(0, 0, targetWidth, targetHeight);

            const drawW = sourceCanvas.width * scale;
            const drawH = sourceCanvas.height * scale;
            const offsetX = (targetWidth - drawW) / 2;
            const offsetY = (targetHeight - drawH) / 2;
            finalCtx.drawImage(sourceCanvas, offsetX, offsetY, drawW, drawH);

            const link = document.createElement('a');
            link.download = 'defensive_heatmap.png';
            link.href = finalCanvas.toDataURL('image/png');
            link.click();
          }});
        }}
      </script>
    </body>
    </html>
    """

    return html
