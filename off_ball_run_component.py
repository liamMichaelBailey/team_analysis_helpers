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


def off_ball_run_component(
        events_df: pd.DataFrame,
        team_id,
        phase: str = None,
        match_col: str = "match_id",
        match_label_col: str = None,
        match_date_col: str = "match_date",
        event_type_filter: str = "off_ball_run",
        dangerous_filter: bool = True,
        grid_cols: int = 6,
        grid_rows: int = 5,
        primary_color: str = "#006600",
        text_color: str = "#333333",
        highlight_entity: str = None,
        pitch_width_px: int = 280,
        pitch_height_px: int = 185,
        cols_per_row: int = 3
):
    """
    Streamlit custom component for dangerous off-ball runs heatmap on a football pitch.
    For each match, creates 3 sub-plots: All runs, Targeted runs, Received runs.
    Bins event locations into a grid and shows density per zone.

    Parameters:
    -----------
    events_df : pd.DataFrame
        Raw events DataFrame with columns: event_type, x_start, y_start, team_id,
        match_id, is_targeted_run (bool), is_received_run (bool)
    team_id : int/str
        The team_id to filter events for.
    phase : str, optional
        Phase type to filter on (uses team_in_possession_phase_type).
    match_col : str
        Column name for match identifier.
    match_label_col : str, optional
        Column to use for subplot titles. If None, uses match_col.
    match_date_col : str
        Column name for match date, used for sorting.
    event_type_filter : str
        Event type to filter on (default: 'dangerous_off_ball_run').
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
        Number of match groups per row (each group has 3 pitches).
    """

    # SkillCorner pitch: 105x68, centered at 0,0
    pitch_length = 105
    pitch_width = 68
    x_min, x_max = -pitch_length / 2, pitch_length / 2
    y_min, y_max = -pitch_width / 2, pitch_width / 2

    # Filter events
    mask = ((events_df['event_type'] == event_type_filter) &
            (events_df['dangerous'] == dangerous_filter) &
            (events_df['team_id'] == team_id))

    if phase is not None and 'team_in_possession_phase_type' in events_df.columns:
        mask = mask & (events_df['team_in_possession_phase_type'] == phase)
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

    def bin_events(df_subset):
        grid = np.zeros((grid_rows, grid_cols), dtype=int)
        for _, row in df_subset.iterrows():
            x_val = row['x_start']
            y_val = row['y_start']
            x_val = max(x_min, min(x_max - 0.001, x_val))
            y_val = max(y_min, min(y_max - 0.001, y_val))
            col_idx = int((x_val - x_min) / (x_max - x_min) * grid_cols)
            row_idx = int((y_val - y_min) / (y_max - y_min) * grid_rows)
            col_idx = min(col_idx, grid_cols - 1)
            row_idx = min(row_idx, grid_rows - 1)
            grid[row_idx][col_idx] += 1
        return grid

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

        # All runs
        grid_all = bin_events(match_events)

        # Targeted runs
        if 'targeted' in match_events.columns:
            targeted = match_events[match_events['targeted'] == True]
        else:
            targeted = pd.DataFrame()
        grid_targeted = bin_events(targeted)

        # Received runs
        if 'received' in match_events.columns:
            received = match_events[match_events['received'] == True]
        else:
            received = pd.DataFrame()
        grid_received = bin_events(received)

        for g in [grid_all, grid_targeted, grid_received]:
            local_max = int(g.max())
            if local_max > global_max:
                global_max = local_max

        match_data.append({
            "match_id": str(match_id),
            "label": match_label,
            "grid_all": grid_all.tolist(),
            "grid_targeted": grid_targeted.tolist(),
            "grid_received": grid_received.tolist(),
            "total_all": int(grid_all.sum()),
            "total_targeted": int(grid_targeted.sum()),
            "total_received": int(grid_received.sum())
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
        .matches-grid {{
          display: flex;
          flex-wrap: wrap;
          gap: 24px;
          justify-content: flex-start;
        }}
        .match-group {{
          display: flex;
          flex-direction: column;
          align-items: center;
          position: relative;
        }}
        .match-label {{
          font-size: 13px;
          font-weight: 700;
          color: {text_color};
          margin-bottom: 6px;
          text-align: center;
        }}
        .match-label.highlighted {{
          color: {primary_color};
          font-size: 14px;
        }}
        .pitches-row {{
          display: flex;
          gap: 6px;
        }}
        .pitch-wrapper {{
          display: flex;
          flex-direction: column;
          align-items: center;
          position: relative;
        }}
        .pitch-subtitle {{
          font-size: 10px;
          font-weight: 600;
          color: {text_color};
          margin-bottom: 3px;
          text-align: center;
        }}
        .pitch-total {{
          font-size: 9px;
          color: #888;
          margin-top: 2px;
        }}
        .pitch-download {{
          width: 18px;
          height: 18px;
          border-radius: 50%;
          border: none;
          background: {primary_color};
          color: white;
          cursor: pointer;
          font-size: 9px;
          display: flex;
          align-items: center;
          justify-content: center;
          position: absolute;
          top: 0;
          right: 0;
          opacity: 0;
          transition: opacity 0.2s;
        }}
        .match-group:hover .pitch-download {{
          opacity: 1;
        }}
        .pitch-download:hover {{ transform: scale(1.1); }}
        canvas {{
          border-radius: 3px;
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
        <div class="matches-grid" id="matchesGrid"></div>
      </div>

      <script>
        const data = {json.dumps(data)};
        const matchesGrid = document.getElementById('matchesGrid');
        const dpr = 4;
        const PW = data.pitch_width_px;
        const PH = data.pitch_height_px;

        const xMin = data.x_min;
        const xMax = data.x_max;
        const yMin = data.y_min;
        const yMax = data.y_max;

        const padLeft = 8;
        const padRight = 8;
        const padTop = 8;
        const padBottom = 8;
        const canvasW = PW + padLeft + padRight;
        const canvasH = PH + padTop + padBottom;

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

          ctx.fillStyle = '#f0f7f0';
          ctx.fillRect(left, top, PW, PH);

          ctx.strokeStyle = '#8a9a8a';
          ctx.lineWidth = 0.75;
          ctx.lineCap = 'round';
          ctx.lineJoin = 'round';

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
              const y = top + (data.grid_rows - 1 - r) * cellH;

              ctx.fillStyle = 'rgba(' + rgb.r + ',' + rgb.g + ',' + rgb.b + ',' + alpha + ')';
              ctx.beginPath();
              ctx.roundRect(x + 1, y + 1, cellW - 2, cellH - 2, 2);
              ctx.fill();

              ctx.font = 'bold 9px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = intensity > 0.5 ? '#ffffff' : data.text_color;
              ctx.fillText(count, x + cellW / 2, y + cellH / 2);
            }}
          }}
        }}

        function createPitchCanvas(gridData, subtitle, total) {{
          const wrapper = document.createElement('div');
          wrapper.className = 'pitch-wrapper';

          const sub = document.createElement('div');
          sub.className = 'pitch-subtitle';
          sub.textContent = subtitle;
          wrapper.appendChild(sub);

          const canvas = document.createElement('canvas');
          canvas.width = canvasW * dpr;
          canvas.height = canvasH * dpr;
          canvas.style.width = canvasW + 'px';
          canvas.style.height = canvasH + 'px';
          wrapper.appendChild(canvas);

          const ctx = canvas.getContext('2d');
          ctx.scale(dpr, dpr);
          ctx.imageSmoothingEnabled = true;
          ctx.imageSmoothingQuality = 'high';
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(0, 0, canvasW, canvasH);

          drawPitch(ctx);
          drawHeatmapGrid(ctx, gridData, data.global_max);

          const totalEl = document.createElement('div');
          totalEl.className = 'pitch-total';
          totalEl.textContent = total + ' runs';
          wrapper.appendChild(totalEl);

          return wrapper;
        }}

        function renderMatchGroup(matchData) {{
          const group = document.createElement('div');
          group.className = 'match-group';

          // Download button for the whole match group
          const dlBtn = document.createElement('button');
          dlBtn.className = 'pitch-download';
          dlBtn.innerHTML = '&#11015;';
          dlBtn.title = 'Download this match';
          dlBtn.onclick = function(e) {{
            e.stopPropagation();
            dlBtn.style.visibility = 'hidden';
            html2canvas(group, {{ scale: 4, useCORS: true, backgroundColor: '#ffffff' }}).then(c => {{
              const link = document.createElement('a');
              link.href = c.toDataURL('image/png');
              link.download = 'runs_' + matchData.label.replace(/[^a-zA-Z0-9]/g, '_') + '.png';
              link.click();
              dlBtn.style.visibility = 'visible';
            }});
          }};
          group.appendChild(dlBtn);

          const label = document.createElement('div');
          label.className = 'match-label';
          if (data.highlight_entity && matchData.label === data.highlight_entity) {{
            label.classList.add('highlighted');
          }}
          label.textContent = matchData.label;
          group.appendChild(label);

          const row = document.createElement('div');
          row.className = 'pitches-row';

          row.appendChild(createPitchCanvas(matchData.grid_all, 'All', matchData.total_all));
          row.appendChild(createPitchCanvas(matchData.grid_targeted, 'Targeted', matchData.total_targeted));
          row.appendChild(createPitchCanvas(matchData.grid_received, 'Received', matchData.total_received));

          group.appendChild(row);
          return group;
        }}

        // Render all matches
        data.matches.forEach(matchData => {{
          const group = renderMatchGroup(matchData);
          matchesGrid.appendChild(group);
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
            link.download = 'offball_runs_heatmap.png';
            link.href = finalCanvas.toDataURL('image/png');
            link.click();
          }});
        }}
      </script>
    </body>
    </html>
    """

    return html
