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
        cols_per_row: int = 3,
        player_col: str = "player_name",
        bar_chart_width: int = 180,
):
    """
    Streamlit custom component for dangerous off-ball runs heatmap on a football pitch.
    For each match, creates 3 sub-plots: All runs, Targeted runs, Received runs,
    plus a 4th column with a horizontal bar chart of player run counts.
    Clicking heatmap cells filters the bar chart to show players from selected zones.
    Multiple cells can be selected across any heatmap. By default shows all player totals.

    Parameters:
    -----------
    events_df : pd.DataFrame
        Raw events DataFrame with columns: event_type, x_start, y_start, team_id,
        match_id, targeted (bool), received (bool), player_name
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
        Event type to filter on (default: 'off_ball_run').
    dangerous_filter : bool
        Filter for dangerous runs.
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
        Number of match groups per row (each group has 3 pitches + bar chart).
    player_col : str
        Column name for player names.
    bar_chart_width : int
        Width of the player bar chart in pixels.
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

    has_player_col = player_col in filtered.columns

    def bin_events_with_players(df_subset):
        grid = np.zeros((grid_rows, grid_cols), dtype=int)
        cell_players = {}
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
            if has_player_col:
                key = f"{row_idx}_{col_idx}"
                player = str(row[player_col]) if pd.notna(row[player_col]) else "Unknown"
                if key not in cell_players:
                    cell_players[key] = {}
                cell_players[key][player] = cell_players[key].get(player, 0) + 1
        return grid, cell_players

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

        grid_all, players_all = bin_events_with_players(match_events)

        if 'targeted' in match_events.columns:
            targeted = match_events[match_events['targeted'] == True]
        else:
            targeted = pd.DataFrame()
        grid_targeted, players_targeted = bin_events_with_players(targeted)

        if 'received' in match_events.columns:
            received = match_events[match_events['received'] == True]
        else:
            received = pd.DataFrame()
        grid_received, players_received = bin_events_with_players(received)

        for g in [grid_all, grid_targeted, grid_received]:
            local_max = int(g.max())
            if local_max > global_max:
                global_max = local_max

        # Total player counts for default bar chart view
        total_players = {}
        for cell_data in players_all.values():
            for player, count in cell_data.items():
                total_players[player] = total_players.get(player, 0) + count

        match_data.append({
            "match_id": str(match_id),
            "label": match_label,
            "grid_all": grid_all.tolist(),
            "grid_targeted": grid_targeted.tolist(),
            "grid_received": grid_received.tolist(),
            "total_all": int(grid_all.sum()),
            "total_targeted": int(grid_targeted.sum()),
            "total_received": int(grid_received.sum()),
            "players": {
                "all": players_all,
                "targeted": players_targeted,
                "received": players_received,
            },
            "total_players": total_players,
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
        "y_max": y_max,
        "bar_chart_width": bar_chart_width,
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
          align-items: flex-start;
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
          cursor: pointer;
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

        /* Bar chart styles */
        .bar-chart-wrapper {{
          display: flex;
          flex-direction: column;
          align-items: stretch;
        }}
        .bar-chart-scroll {{
          overflow-y: auto;
          overflow-x: hidden;
        }}
        .bar-chart-scroll::-webkit-scrollbar {{
          width: 3px;
        }}
        .bar-chart-scroll::-webkit-scrollbar-thumb {{
          background: #ccc;
          border-radius: 2px;
        }}
        .bar-row {{
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 1.5px 0;
        }}
        .bar-name {{
          font-size: 9px;
          color: {text_color};
          width: 65px;
          text-overflow: ellipsis;
          overflow: hidden;
          white-space: nowrap;
          text-align: right;
          flex-shrink: 0;
        }}
        .bar-track {{
          flex: 1;
          height: 10px;
          background: #f0f0f0;
          border-radius: 2px;
          overflow: hidden;
        }}
        .bar-fill {{
          height: 100%;
          background: {primary_color};
          border-radius: 2px;
          transition: width 0.2s;
        }}
        .bar-count {{
          font-size: 9px;
          color: #888;
          width: 18px;
          text-align: right;
          flex-shrink: 0;
        }}
        .bar-chart-footer {{
          font-size: 9px;
          color: #888;
          margin-top: 2px;
          text-align: center;
          min-height: 13px;
        }}
        .bar-chart-clear {{
          color: {primary_color};
          cursor: pointer;
          text-decoration: underline;
          margin-left: 4px;
        }}
        .bar-chart-clear:hover {{
          opacity: 0.7;
        }}
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
        const BCW = data.bar_chart_width;

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

        // Per-match interaction state
        const matchStates = [];

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

        function drawSelectionHighlight(ctx, selectedCells, gridType) {{
          const cellW = PW / data.grid_cols;
          const cellH = PH / data.grid_rows;

          selectedCells.forEach(function(cellKey) {{
            const parts = cellKey.split('_');
            const type = parts[0];
            if (type !== gridType) return;
            const r = parseInt(parts[1]);
            const c = parseInt(parts[2]);

            const x = padLeft + c * cellW;
            const y = padTop + (data.grid_rows - 1 - r) * cellH;

            // White inner border + dark outer for contrast on any background
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2.5;
            ctx.strokeRect(x + 2, y + 2, cellW - 4, cellH - 4);
            ctx.strokeStyle = data.text_color;
            ctx.lineWidth = 1;
            ctx.strokeRect(x + 2, y + 2, cellW - 4, cellH - 4);
          }});
        }}

        function redrawCanvas(canvas, gridData, gridType, matchIdx) {{
          const ctx = canvas.getContext('2d');
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(0, 0, canvasW, canvasH);
          drawPitch(ctx);
          drawHeatmapGrid(ctx, gridData, data.global_max);
          drawSelectionHighlight(ctx, matchStates[matchIdx].selectedCells, gridType);
        }}

        function redrawMatch(matchIdx) {{
          const state = matchStates[matchIdx];
          const md = data.matches[matchIdx];
          redrawCanvas(state.canvases.all, md.grid_all, 'all', matchIdx);
          redrawCanvas(state.canvases.targeted, md.grid_targeted, 'targeted', matchIdx);
          redrawCanvas(state.canvases.received, md.grid_received, 'received', matchIdx);
        }}

        function getSelectedPlayerCounts(matchIdx) {{
          const state = matchStates[matchIdx];
          const md = data.matches[matchIdx];

          if (state.selectedCells.size === 0) {{
            return md.total_players;
          }}

          const counts = {{}};
          state.selectedCells.forEach(function(cellKey) {{
            const parts = cellKey.split('_');
            const type = parts[0];
            const r = parts[1];
            const c = parts[2];
            const playerKey = r + '_' + c;
            const cellPlayers = (md.players[type] || {{}})[playerKey] || {{}};
            for (const [player, count] of Object.entries(cellPlayers)) {{
              counts[player] = (counts[player] || 0) + count;
            }}
          }});
          return counts;
        }}

        function updateBarChart(matchIdx) {{
          const state = matchStates[matchIdx];
          const counts = getSelectedPlayerCounts(matchIdx);
          const scroll = state.barChartEl;
          const footer = state.footerEl;

          const sorted = Object.entries(counts).sort(function(a, b) {{ return b[1] - a[1]; }});
          const maxCount = sorted.length > 0 ? sorted[0][1] : 0;

          scroll.innerHTML = '';

          if (sorted.length === 0) {{
            scroll.innerHTML = '<div style="font-size:9px;color:#888;padding:8px;text-align:center;">No runs</div>';
          }} else {{
            sorted.forEach(function(entry) {{
              const player = entry[0];
              const count = entry[1];

              const row = document.createElement('div');
              row.className = 'bar-row';

              const name = document.createElement('div');
              name.className = 'bar-name';
              name.textContent = player;
              name.title = player;

              const track = document.createElement('div');
              track.className = 'bar-track';

              const fill = document.createElement('div');
              fill.className = 'bar-fill';
              fill.style.width = (maxCount > 0 ? (count / maxCount * 100) : 0) + '%';
              track.appendChild(fill);

              const countEl = document.createElement('div');
              countEl.className = 'bar-count';
              countEl.textContent = count;

              row.appendChild(name);
              row.appendChild(track);
              row.appendChild(countEl);
              scroll.appendChild(row);
            }});
          }}

          // Update footer status
          if (state.selectedCells.size === 0) {{
            footer.innerHTML = '<span style="color:#888;">All Runs</span>';
          }} else {{
            const n = state.selectedCells.size;
            footer.innerHTML = '<span style="color:#888;">' + n + ' zone' + (n > 1 ? 's' : '') + ' selected</span>'
              + ' <span class="bar-chart-clear" onclick="clearSelection(' + matchIdx + ')">clear</span>';
          }}
        }}

        function clearSelection(matchIdx) {{
          matchStates[matchIdx].selectedCells.clear();
          redrawMatch(matchIdx);
          updateBarChart(matchIdx);
        }}

        function createPitchCanvas(gridData, subtitle, total, gridType, matchIdx) {{
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

          // Click handler for cell selection
          canvas.addEventListener('click', function(e) {{
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const pitchX = x - padLeft;
            const pitchY = y - padTop;
            if (pitchX < 0 || pitchX >= PW || pitchY < 0 || pitchY >= PH) return;

            const cellW = PW / data.grid_cols;
            const cellH = PH / data.grid_rows;
            const col = Math.min(Math.floor(pitchX / cellW), data.grid_cols - 1);
            const visualRow = Math.min(Math.floor(pitchY / cellH), data.grid_rows - 1);
            const gridRow = data.grid_rows - 1 - visualRow;

            const cellKey = gridType + '_' + gridRow + '_' + col;
            const state = matchStates[matchIdx];

            if (state.selectedCells.has(cellKey)) {{
              state.selectedCells.delete(cellKey);
            }} else {{
              state.selectedCells.add(cellKey);
            }}

            redrawMatch(matchIdx);
            updateBarChart(matchIdx);
          }});

          const totalEl = document.createElement('div');
          totalEl.className = 'pitch-total';
          totalEl.textContent = total + ' runs';
          wrapper.appendChild(totalEl);

          return wrapper;
        }}

        function createBarChart(matchIdx) {{
          const wrapper = document.createElement('div');
          wrapper.className = 'bar-chart-wrapper';
          wrapper.style.width = BCW + 'px';

          const title = document.createElement('div');
          title.className = 'pitch-subtitle';
          title.textContent = 'Players';
          wrapper.appendChild(title);

          const scroll = document.createElement('div');
          scroll.className = 'bar-chart-scroll';
          scroll.style.height = canvasH + 'px';
          wrapper.appendChild(scroll);

          const footer = document.createElement('div');
          footer.className = 'bar-chart-footer';
          wrapper.appendChild(footer);

          matchStates[matchIdx].barChartEl = scroll;
          matchStates[matchIdx].footerEl = footer;

          updateBarChart(matchIdx);
          return wrapper;
        }}

        function renderMatchGroup(matchData, matchIdx) {{
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
            html2canvas(group, {{ scale: 4, useCORS: true, backgroundColor: '#ffffff' }}).then(function(c) {{
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

          const allWrapper = createPitchCanvas(matchData.grid_all, 'All', matchData.total_all, 'all', matchIdx);
          matchStates[matchIdx].canvases.all = allWrapper.querySelector('canvas');
          row.appendChild(allWrapper);

          const targetedWrapper = createPitchCanvas(matchData.grid_targeted, 'Targeted', matchData.total_targeted, 'targeted', matchIdx);
          matchStates[matchIdx].canvases.targeted = targetedWrapper.querySelector('canvas');
          row.appendChild(targetedWrapper);

          const receivedWrapper = createPitchCanvas(matchData.grid_received, 'Received', matchData.total_received, 'received', matchIdx);
          matchStates[matchIdx].canvases.received = receivedWrapper.querySelector('canvas');
          row.appendChild(receivedWrapper);

          row.appendChild(createBarChart(matchIdx));

          group.appendChild(row);
          return group;
        }}

        // Render all matches
        data.matches.forEach(function(matchData, matchIdx) {{
          matchStates.push({{
            selectedCells: new Set(),
            canvases: {{}},
            barChartEl: null,
            footerEl: null
          }});

          const group = renderMatchGroup(matchData, matchIdx);
          matchesGrid.appendChild(group);
        }});

        // Main download
        function downloadPNG() {{
          const exportArea = document.getElementById('export-area');
          html2canvas(exportArea, {{
            scale: 5,
            useCORS: true,
            backgroundColor: '#ffffff'
          }}).then(function(sourceCanvas) {{
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
