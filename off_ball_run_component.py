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

    Renders a Season Summary row at the top (% distribution per cell, colored by
    league-wide percentile rank using 5-band league table colors), followed by
    per-match rows (3 heatmaps: All / Targeted / Received + interactive player
    bar chart).

    Clicking heatmap cells filters the bar chart to show players from selected zones.
    Multiple cells can be selected across any heatmap. By default shows all player totals.

    Parameters:
    -----------
    events_df : pd.DataFrame
        Raw events DataFrame. Must contain all teams in the competition so that
        league-wide percentile comparison can be computed for the summary row.
    team_id : int/str
        The team_id to plot.
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
        Base color for per-match heatmap intensity.
    text_color : str
        Color for text elements.
    highlight_entity : str, optional
        Match label to highlight.
    pitch_width_px : int
        Width of each pitch in pixels.
    pitch_height_px : int
        Height of each pitch in pixels.
    cols_per_row : int
        Number of match groups per row.
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

    # ----------------------------------------------------------------
    # Filter events for the target team
    # ----------------------------------------------------------------
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

    # ----------------------------------------------------------------
    # Binning helpers
    # ----------------------------------------------------------------
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

    def compute_pct_grid_fast(df_subset):
        """Vectorised % distribution grid (no player breakdown)."""
        grid = np.zeros((grid_rows, grid_cols), dtype=float)
        if len(df_subset) == 0:
            return grid
        x_vals = np.clip(df_subset['x_start'].values.astype(float), x_min, x_max - 0.001)
        y_vals = np.clip(df_subset['y_start'].values.astype(float), y_min, y_max - 0.001)
        c_idx = np.clip(((x_vals - x_min) / (x_max - x_min) * grid_cols).astype(int), 0, grid_cols - 1)
        r_idx = np.clip(((y_vals - y_min) / (y_max - y_min) * grid_rows).astype(int), 0, grid_rows - 1)
        np.add.at(grid, (r_idx, c_idx), 1)
        total = grid.sum()
        if total > 0:
            grid = grid / total * 100
        return grid

    # ----------------------------------------------------------------
    # Per-match data
    # ----------------------------------------------------------------
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

    # ----------------------------------------------------------------
    # Summary: aggregate across all matches for the target team
    # ----------------------------------------------------------------
    summary_grid_all = np.zeros((grid_rows, grid_cols), dtype=int)
    summary_grid_targeted = np.zeros((grid_rows, grid_cols), dtype=int)
    summary_grid_received = np.zeros((grid_rows, grid_cols), dtype=int)
    summary_players = {"all": {}, "targeted": {}, "received": {}}
    summary_total_players = {}

    for md in match_data:
        summary_grid_all += np.array(md["grid_all"])
        summary_grid_targeted += np.array(md["grid_targeted"])
        summary_grid_received += np.array(md["grid_received"])

        for grid_type in ("all", "targeted", "received"):
            for cell_key, players in md["players"][grid_type].items():
                if cell_key not in summary_players[grid_type]:
                    summary_players[grid_type][cell_key] = {}
                for player, count in players.items():
                    summary_players[grid_type][cell_key][player] = (
                        summary_players[grid_type][cell_key].get(player, 0) + count
                    )

        for player, count in md["total_players"].items():
            summary_total_players[player] = summary_total_players.get(player, 0) + count

    def grid_to_pct(grid):
        total = grid.sum()
        if total > 0:
            return np.round(grid / total * 100, 1).tolist()
        return np.zeros_like(grid, dtype=float).tolist()

    summary_pct_all = grid_to_pct(summary_grid_all)
    summary_pct_targeted = grid_to_pct(summary_grid_targeted)
    summary_pct_received = grid_to_pct(summary_grid_received)

    # ----------------------------------------------------------------
    # League comparison: compute % grids for every team, then rank
    # ----------------------------------------------------------------
    league_mask = ((events_df['event_type'] == event_type_filter) &
                   (events_df['dangerous'] == dangerous_filter))
    if phase is not None and 'team_in_possession_phase_type' in events_df.columns:
        league_mask = league_mask & (events_df['team_in_possession_phase_type'] == phase)
    league_events = events_df[league_mask]

    all_team_ids = league_events['team_id'].unique()

    league_pct = {}  # team_id -> {"all": grid, "targeted": grid, "received": grid}
    for tid in all_team_ids:
        te = league_events[league_events['team_id'] == tid]
        league_pct[tid] = {"all": compute_pct_grid_fast(te)}
        if 'targeted' in te.columns:
            league_pct[tid]["targeted"] = compute_pct_grid_fast(te[te['targeted'] == True])
        else:
            league_pct[tid]["targeted"] = np.zeros((grid_rows, grid_cols), dtype=float)
        if 'received' in te.columns:
            league_pct[tid]["received"] = compute_pct_grid_fast(te[te['received'] == True])
        else:
            league_pct[tid]["received"] = np.zeros((grid_rows, grid_cols), dtype=float)

    n_teams = len(all_team_ids)

    def compute_color_grid(grid_type):
        """Percentile-rank each cell vs the league → 5-band color index."""
        color = np.full((grid_rows, grid_cols), -1, dtype=int)
        if n_teams == 0:
            return color.tolist()
        for r in range(grid_rows):
            for c in range(grid_cols):
                vals = [league_pct[tid][grid_type][r][c] for tid in all_team_ids]
                team_val = league_pct.get(team_id, {}).get(grid_type, np.zeros((grid_rows, grid_cols)))[r][c]
                if max(vals) == 0:
                    continue  # no team has runs here
                n_below = sum(1 for v in vals if v < team_val)
                n_equal = sum(1 for v in vals if v == team_val)
                pct_rank = (n_below + 0.5 * n_equal) / n_teams
                if pct_rank < 0.2:
                    color[r][c] = 0
                elif pct_rank < 0.4:
                    color[r][c] = 1
                elif pct_rank < 0.6:
                    color[r][c] = 2
                elif pct_rank < 0.8:
                    color[r][c] = 3
                else:
                    color[r][c] = 4
        return color.tolist()

    summary_color_all = compute_color_grid("all")
    summary_color_targeted = compute_color_grid("targeted")
    summary_color_received = compute_color_grid("received")

    # ----------------------------------------------------------------
    # Payload
    # ----------------------------------------------------------------
    data = {
        "summary": {
            "pct_all": summary_pct_all,
            "pct_targeted": summary_pct_targeted,
            "pct_received": summary_pct_received,
            "color_all": summary_color_all,
            "color_targeted": summary_color_targeted,
            "color_received": summary_color_received,
            "total_all": int(summary_grid_all.sum()),
            "total_targeted": int(summary_grid_targeted.sum()),
            "total_received": int(summary_grid_received.sum()),
            "players": summary_players,
            "total_players": summary_total_players,
        },
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

    # ================================================================
    # HTML / JS
    # ================================================================
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
        .summary-label {{
          font-size: 14px;
          font-weight: 800;
          color: {text_color};
          margin-bottom: 6px;
          text-align: center;
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

        /* Bar chart */
        .bar-chart-wrapper {{
          display: flex;
          flex-direction: column;
          align-items: stretch;
        }}
        .bar-chart-scroll {{
          overflow-y: auto;
          overflow-x: hidden;
        }}
        .bar-chart-scroll::-webkit-scrollbar {{ width: 3px; }}
        .bar-chart-scroll::-webkit-scrollbar-thumb {{ background: #ccc; border-radius: 2px; }}
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
        .bar-chart-clear:hover {{ opacity: 0.7; }}

        /* Legend */
        .legend-row {{
          display: flex;
          justify-content: center;
          gap: 12px;
          margin-top: 6px;
          font-size: 9px;
          color: {text_color};
        }}
        .legend-item {{
          display: flex;
          align-items: center;
          gap: 4px;
        }}
        .legend-swatch {{
          width: 14px;
          height: 10px;
          border-radius: 2px;
        }}

        /* Divider */
        .section-divider {{
          width: 100%;
          border: none;
          border-top: 1px solid #e0e0e0;
          margin: 16px 0 12px 0;
        }}
      </style>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    </head>
    <body>
      <button class="download-btn" onclick="downloadPNG()" title="Download PNG">&#11015;</button>
      <div id="export-area">
        <div id="summaryArea"></div>
        <hr class="section-divider" id="summaryDivider" style="display:none;">
        <div class="matches-grid" id="matchesGrid"></div>
      </div>

      <script>
        const data = {json.dumps(data)};
        const matchesGrid = document.getElementById('matchesGrid');
        const summaryArea = document.getElementById('summaryArea');
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

        const LEAGUE_COLORS = ['#FF1A1A', '#FDA4A4', '#D9D9D6', '#99E59A', '#00C800'];
        const LEAGUE_LABELS = ['Very Low', 'Low', 'Average', 'High', 'Very High'];

        // Per-match interaction state
        const matchStates = [];
        // Summary interaction state
        const summaryState = {{
          selectedCells: new Set(),
          canvases: {{}},
          barChartEl: null,
          footerEl: null
        }};

        /* ==========================================================
           Shared drawing helpers
           ========================================================== */
        function hexToRgb(hex) {{
          const result = /^#?([a-f\\d]{{2}})([a-f\\d]{{2}})([a-f\\d]{{2}})$/i.exec(hex);
          return result ? {{
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
          }} : {{ r: 0, g: 102, b: 0 }};
        }}

        function drawPitch(ctx) {{
          const left = padLeft, top = padTop;
          const right = padLeft + PW, bottom = padTop + PH;
          const cx = padLeft + PW / 2, cy = padTop + PH / 2;

          ctx.fillStyle = '#f0f7f0';
          ctx.fillRect(left, top, PW, PH);
          ctx.strokeStyle = '#8a9a8a';
          ctx.lineWidth = 0.75;
          ctx.lineCap = 'round';
          ctx.lineJoin = 'round';
          ctx.strokeRect(left, top, PW, PH);

          ctx.beginPath(); ctx.moveTo(cx, top); ctx.lineTo(cx, bottom); ctx.stroke();

          const centerR = (9.15 / 68) * PH;
          ctx.beginPath(); ctx.arc(cx, cy, centerR, 0, 2 * Math.PI); ctx.stroke();
          ctx.beginPath(); ctx.arc(cx, cy, 1.5, 0, 2 * Math.PI); ctx.fillStyle = '#8a9a8a'; ctx.fill();

          const paW = (16.5 / 105) * PW, paH = (40.32 / 68) * PH, paTop = cy - paH / 2;
          ctx.strokeRect(left, paTop, paW, paH);
          ctx.strokeRect(right - paW, paTop, paW, paH);

          const gaW = (5.5 / 105) * PW, gaH = (18.32 / 68) * PH, gaTop = cy - gaH / 2;
          ctx.strokeRect(left, gaTop, gaW, gaH);
          ctx.strokeRect(right - gaW, gaTop, gaW, gaH);

          const penSpotDist = (11 / 105) * PW;
          ctx.fillStyle = '#8a9a8a';
          ctx.beginPath(); ctx.arc(left + penSpotDist, cy, 1.5, 0, 2 * Math.PI); ctx.fill();
          ctx.beginPath(); ctx.arc(right - penSpotDist, cy, 1.5, 0, 2 * Math.PI); ctx.fill();

          const penArcR = (9.15 / 68) * PH;
          ctx.beginPath(); ctx.arc(left + penSpotDist, cy, penArcR, -0.6, 0.6); ctx.stroke();
          ctx.beginPath(); ctx.arc(right - penSpotDist, cy, penArcR, Math.PI - 0.6, Math.PI + 0.6); ctx.stroke();
        }}

        function drawSelectionHighlight(ctx, selectedCells, gridType) {{
          const cellW = PW / data.grid_cols;
          const cellH = PH / data.grid_rows;
          selectedCells.forEach(function(cellKey) {{
            const parts = cellKey.split('_');
            if (parts[0] !== gridType) return;
            const r = parseInt(parts[1]), c = parseInt(parts[2]);
            const x = padLeft + c * cellW;
            const y = padTop + (data.grid_rows - 1 - r) * cellH;
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2.5;
            ctx.strokeRect(x + 2, y + 2, cellW - 4, cellH - 4);
            ctx.strokeStyle = data.text_color;
            ctx.lineWidth = 1;
            ctx.strokeRect(x + 2, y + 2, cellW - 4, cellH - 4);
          }});
        }}

        /* ==========================================================
           Per-match heatmap (alpha intensity from primary_color)
           ========================================================== */
        function drawHeatmapGrid(ctx, gridData, globalMax) {{
          if (globalMax === 0) return;
          const cellW = PW / data.grid_cols;
          const cellH = PH / data.grid_rows;
          const rgb = hexToRgb(data.primary_color);
          for (let r = 0; r < data.grid_rows; r++) {{
            for (let c = 0; c < data.grid_cols; c++) {{
              const count = gridData[r][c];
              if (count === 0) continue;
              const intensity = count / globalMax;
              const alpha = 0.1 + intensity * 0.7;
              const x = padLeft + c * cellW;
              const y = padTop + (data.grid_rows - 1 - r) * cellH;
              ctx.fillStyle = 'rgba(' + rgb.r + ',' + rgb.g + ',' + rgb.b + ',' + alpha + ')';
              ctx.beginPath(); ctx.roundRect(x + 1, y + 1, cellW - 2, cellH - 2, 2); ctx.fill();
              ctx.font = 'bold 9px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
              ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
              ctx.fillStyle = intensity > 0.5 ? '#ffffff' : data.text_color;
              ctx.fillText(count, x + cellW / 2, y + cellH / 2);
            }}
          }}
        }}

        /* ==========================================================
           Summary heatmap (discrete league colors, % text)
           ========================================================== */
        function drawSummaryHeatmapGrid(ctx, pctData, colorData) {{
          const cellW = PW / data.grid_cols;
          const cellH = PH / data.grid_rows;
          for (let r = 0; r < data.grid_rows; r++) {{
            for (let c = 0; c < data.grid_cols; c++) {{
              const pct = pctData[r][c];
              const colorIdx = colorData[r][c];
              const x = padLeft + c * cellW;
              const y = padTop + (data.grid_rows - 1 - r) * cellH;

              if (colorIdx >= 0) {{
                ctx.fillStyle = LEAGUE_COLORS[colorIdx];
                ctx.beginPath(); ctx.roundRect(x + 1, y + 1, cellW - 2, cellH - 2, 2); ctx.fill();
              }}
              if (pct > 0) {{
                ctx.font = 'bold 8px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
                ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
                ctx.fillStyle = (colorIdx === 0 || colorIdx === 4) ? '#ffffff' : data.text_color;
                const txt = pct >= 10 ? Math.round(pct) + '%' : pct.toFixed(1) + '%';
                ctx.fillText(txt, x + cellW / 2, y + cellH / 2);
              }}
            }}
          }}
        }}

        /* ==========================================================
           Shared bar-chart renderer
           ========================================================== */
        function getPlayerCounts(state, dataObj) {{
          if (state.selectedCells.size === 0) return dataObj.total_players;
          const counts = {{}};
          state.selectedCells.forEach(function(cellKey) {{
            const parts = cellKey.split('_');
            const type = parts[0], r = parts[1], c = parts[2];
            const playerKey = r + '_' + c;
            const cp = (dataObj.players[type] || {{}})[playerKey] || {{}};
            for (const [player, count] of Object.entries(cp)) {{
              counts[player] = (counts[player] || 0) + count;
            }}
          }});
          return counts;
        }}

        function renderBarContent(scroll, footer, counts, nSelected, clearFn) {{
          const sorted = Object.entries(counts).sort(function(a, b) {{ return b[1] - a[1]; }});
          const maxCount = sorted.length > 0 ? sorted[0][1] : 0;
          scroll.innerHTML = '';
          if (sorted.length === 0) {{
            scroll.innerHTML = '<div style="font-size:9px;color:#888;padding:8px;text-align:center;">No runs</div>';
          }} else {{
            sorted.forEach(function(entry) {{
              const player = entry[0], count = entry[1];
              const row = document.createElement('div'); row.className = 'bar-row';
              const name = document.createElement('div'); name.className = 'bar-name';
              name.textContent = player; name.title = player;
              const track = document.createElement('div'); track.className = 'bar-track';
              const fill = document.createElement('div'); fill.className = 'bar-fill';
              fill.style.width = (maxCount > 0 ? (count / maxCount * 100) : 0) + '%';
              track.appendChild(fill);
              const countEl = document.createElement('div'); countEl.className = 'bar-count';
              countEl.textContent = count;
              row.appendChild(name); row.appendChild(track); row.appendChild(countEl);
              scroll.appendChild(row);
            }});
          }}
          if (nSelected === 0) {{
            footer.innerHTML = '<span style="color:#888;">All Runs</span>';
          }} else {{
            footer.innerHTML = '<span style="color:#888;">' + nSelected + ' zone' + (nSelected > 1 ? 's' : '') + ' selected</span>'
              + ' <span class="bar-chart-clear" onclick="' + clearFn + '">clear</span>';
          }}
        }}

        /* ==========================================================
           Summary-specific functions
           ========================================================== */
        function redrawSummaryCanvas(canvas, pctData, colorData, gridType) {{
          const ctx = canvas.getContext('2d');
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(0, 0, canvasW, canvasH);
          drawPitch(ctx);
          drawSummaryHeatmapGrid(ctx, pctData, colorData);
          drawSelectionHighlight(ctx, summaryState.selectedCells, gridType);
        }}

        function redrawSummary() {{
          const s = data.summary;
          redrawSummaryCanvas(summaryState.canvases.all, s.pct_all, s.color_all, 'all');
          redrawSummaryCanvas(summaryState.canvases.targeted, s.pct_targeted, s.color_targeted, 'targeted');
          redrawSummaryCanvas(summaryState.canvases.received, s.pct_received, s.color_received, 'received');
        }}

        function updateSummaryBarChart() {{
          const counts = getPlayerCounts(summaryState, data.summary);
          renderBarContent(summaryState.barChartEl, summaryState.footerEl, counts,
                           summaryState.selectedCells.size, 'clearSummarySelection()');
        }}

        function clearSummarySelection() {{
          summaryState.selectedCells.clear();
          redrawSummary();
          updateSummaryBarChart();
        }}

        function createSummaryPitchCanvas(pctData, colorData, subtitle, total, gridType) {{
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
          drawSummaryHeatmapGrid(ctx, pctData, colorData);

          canvas.addEventListener('click', function(e) {{
            const rect = canvas.getBoundingClientRect();
            const px = e.clientX - rect.left - padLeft;
            const py = e.clientY - rect.top - padTop;
            if (px < 0 || px >= PW || py < 0 || py >= PH) return;
            const cellW = PW / data.grid_cols, cellH = PH / data.grid_rows;
            const col = Math.min(Math.floor(px / cellW), data.grid_cols - 1);
            const vr = Math.min(Math.floor(py / cellH), data.grid_rows - 1);
            const gr = data.grid_rows - 1 - vr;
            const key = gridType + '_' + gr + '_' + col;
            if (summaryState.selectedCells.has(key)) {{ summaryState.selectedCells.delete(key); }}
            else {{ summaryState.selectedCells.add(key); }}
            redrawSummary();
            updateSummaryBarChart();
          }});

          const totalEl = document.createElement('div');
          totalEl.className = 'pitch-total';
          totalEl.textContent = total + ' runs';
          wrapper.appendChild(totalEl);

          return wrapper;
        }}

        function renderSummary() {{
          const s = data.summary;
          const group = document.createElement('div');
          group.className = 'match-group';

          const dlBtn = document.createElement('button');
          dlBtn.className = 'pitch-download';
          dlBtn.innerHTML = '&#11015;';
          dlBtn.title = 'Download summary';
          dlBtn.onclick = function(e) {{
            e.stopPropagation();
            dlBtn.style.visibility = 'hidden';
            html2canvas(group, {{ scale: 4, useCORS: true, backgroundColor: '#ffffff' }}).then(function(c) {{
              const link = document.createElement('a');
              link.href = c.toDataURL('image/png');
              link.download = 'runs_season_summary.png';
              link.click();
              dlBtn.style.visibility = 'visible';
            }});
          }};
          group.appendChild(dlBtn);

          const label = document.createElement('div');
          label.className = 'summary-label';
          label.textContent = 'Season Summary';
          group.appendChild(label);

          const row = document.createElement('div');
          row.className = 'pitches-row';

          const allW = createSummaryPitchCanvas(s.pct_all, s.color_all, 'All', s.total_all, 'all');
          summaryState.canvases.all = allW.querySelector('canvas');
          row.appendChild(allW);

          const tgtW = createSummaryPitchCanvas(s.pct_targeted, s.color_targeted, 'Targeted', s.total_targeted, 'targeted');
          summaryState.canvases.targeted = tgtW.querySelector('canvas');
          row.appendChild(tgtW);

          const rcvW = createSummaryPitchCanvas(s.pct_received, s.color_received, 'Received', s.total_received, 'received');
          summaryState.canvases.received = rcvW.querySelector('canvas');
          row.appendChild(rcvW);

          // Bar chart
          const bcWrapper = document.createElement('div');
          bcWrapper.className = 'bar-chart-wrapper';
          bcWrapper.style.width = BCW + 'px';
          const bcTitle = document.createElement('div');
          bcTitle.className = 'pitch-subtitle';
          bcTitle.textContent = 'Players';
          bcWrapper.appendChild(bcTitle);
          const bcScroll = document.createElement('div');
          bcScroll.className = 'bar-chart-scroll';
          bcScroll.style.height = canvasH + 'px';
          bcWrapper.appendChild(bcScroll);
          const bcFooter = document.createElement('div');
          bcFooter.className = 'bar-chart-footer';
          bcWrapper.appendChild(bcFooter);
          summaryState.barChartEl = bcScroll;
          summaryState.footerEl = bcFooter;
          row.appendChild(bcWrapper);

          group.appendChild(row);

          // Legend
          const legend = document.createElement('div');
          legend.className = 'legend-row';
          LEAGUE_COLORS.forEach(function(col, i) {{
            const item = document.createElement('div'); item.className = 'legend-item';
            const swatch = document.createElement('div'); swatch.className = 'legend-swatch';
            swatch.style.background = col;
            const lbl = document.createElement('span'); lbl.textContent = LEAGUE_LABELS[i];
            item.appendChild(swatch); item.appendChild(lbl);
            legend.appendChild(item);
          }});
          group.appendChild(legend);

          summaryArea.appendChild(group);
          document.getElementById('summaryDivider').style.display = '';
          updateSummaryBarChart();
        }}

        /* ==========================================================
           Per-match functions
           ========================================================== */
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

        function updateBarChart(matchIdx) {{
          const state = matchStates[matchIdx];
          const counts = getPlayerCounts(state, data.matches[matchIdx]);
          renderBarContent(state.barChartEl, state.footerEl, counts,
                           state.selectedCells.size, 'clearSelection(' + matchIdx + ')');
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

          canvas.addEventListener('click', function(e) {{
            const rect = canvas.getBoundingClientRect();
            const px = e.clientX - rect.left - padLeft;
            const py = e.clientY - rect.top - padTop;
            if (px < 0 || px >= PW || py < 0 || py >= PH) return;
            const cellW = PW / data.grid_cols, cellH = PH / data.grid_rows;
            const col = Math.min(Math.floor(px / cellW), data.grid_cols - 1);
            const vr = Math.min(Math.floor(py / cellH), data.grid_rows - 1);
            const gr = data.grid_rows - 1 - vr;
            const key = gridType + '_' + gr + '_' + col;
            const state = matchStates[matchIdx];
            if (state.selectedCells.has(key)) {{ state.selectedCells.delete(key); }}
            else {{ state.selectedCells.add(key); }}
            redrawMatch(matchIdx);
            updateBarChart(matchIdx);
          }});

          const totalEl = document.createElement('div');
          totalEl.className = 'pitch-total';
          totalEl.textContent = total + ' runs';
          wrapper.appendChild(totalEl);

          return wrapper;
        }}

        function renderMatchGroup(matchData, matchIdx) {{
          const group = document.createElement('div');
          group.className = 'match-group';

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

          const allW = createPitchCanvas(matchData.grid_all, 'All', matchData.total_all, 'all', matchIdx);
          matchStates[matchIdx].canvases.all = allW.querySelector('canvas');
          row.appendChild(allW);

          const tgtW = createPitchCanvas(matchData.grid_targeted, 'Targeted', matchData.total_targeted, 'targeted', matchIdx);
          matchStates[matchIdx].canvases.targeted = tgtW.querySelector('canvas');
          row.appendChild(tgtW);

          const rcvW = createPitchCanvas(matchData.grid_received, 'Received', matchData.total_received, 'received', matchIdx);
          matchStates[matchIdx].canvases.received = rcvW.querySelector('canvas');
          row.appendChild(rcvW);

          // Bar chart
          const bcWrapper = document.createElement('div');
          bcWrapper.className = 'bar-chart-wrapper';
          bcWrapper.style.width = BCW + 'px';
          const bcTitle = document.createElement('div');
          bcTitle.className = 'pitch-subtitle';
          bcTitle.textContent = 'Players';
          bcWrapper.appendChild(bcTitle);
          const bcScroll = document.createElement('div');
          bcScroll.className = 'bar-chart-scroll';
          bcScroll.style.height = canvasH + 'px';
          bcWrapper.appendChild(bcScroll);
          const bcFooter = document.createElement('div');
          bcFooter.className = 'bar-chart-footer';
          bcWrapper.appendChild(bcFooter);
          matchStates[matchIdx].barChartEl = bcScroll;
          matchStates[matchIdx].footerEl = bcFooter;
          row.appendChild(bcWrapper);

          group.appendChild(row);
          return group;
        }}

        /* ==========================================================
           Render everything
           ========================================================== */
        // 1. Summary first
        if (data.summary.total_all > 0) {{
          renderSummary();
        }}

        // 2. Per-match groups
        data.matches.forEach(function(matchData, matchIdx) {{
          matchStates.push({{
            selectedCells: new Set(),
            canvases: {{}},
            barChartEl: null,
            footerEl: null
          }});
          const group = renderMatchGroup(matchData, matchIdx);
          matchesGrid.appendChild(group);
          updateBarChart(matchIdx);
        }});

        /* ==========================================================
           Full-page PNG download
           ========================================================== */
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
