import pandas as pd
import json


def safe_json(df):
    def convert_value(x):
        if isinstance(x, pd.Timestamp):
            return x.isoformat()
        elif pd.isna(x):
            return None
        return x

    df_clean = df.applymap(convert_value)
    return df_clean


DEFAULT_INVERTED_PLAYER_METRICS = [
    'count_fouls_per_90',
    'count_beaten_by_possession_per_90',
    'count_beaten_by_movement_per_90',
]

POSITION_ORDER = {
    'GK': 0,
    'CB': 1, 'LCB': 1, 'RCB': 1,
    'LB': 2, 'RB': 2, 'LWB': 2, 'RWB': 2,
    'CDM': 3, 'DM': 3, 'LDM': 3, 'RDM': 3,
    'CM': 4, 'LCM': 4, 'RCM': 4, 'CAM': 4, 'LAM': 4, 'RAM': 4, 'AM': 4,
    'LM': 5, 'RM': 5, 'LW': 5, 'RW': 5,
    'CF': 6, 'ST': 6, 'LF': 6, 'RF': 6, 'SS': 6,
}


def ranking_component(
        df: pd.DataFrame,
        questions: dict,
        highlight_group: list,
        data_point_label: str = 'player_name',
        data_point_id: str = 'player_name',
        metric_labels: dict = None,
        plot_title: str = None,
        text_color: str = "#333333",
        container_width: int = 1200,
        invert_metric_ranks: list = DEFAULT_INVERTED_PLAYER_METRICS,
        highlight_entity: str = None
):
    """
    Streamlit custom component for a ranking/percentile bar chart.

    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame containing entity data with metric values
    questions : dict
        Dict of group_name -> list of metric column names
    highlight_group : list
        List of entity IDs to display as columns
    data_point_label : str
        Column name for display labels (column headers)
    data_point_id : str
        Column name for entity IDs (to filter highlight_group)
    metric_labels : dict, optional
        Dict mapping metric names to display labels
    plot_title : str, optional
        Title displayed above the chart
    text_color : str
        Color for text elements
    container_width : int
        Total width available for the component
    invert_metric_ranks : list, optional
        List of metrics where lower values are better (rank is inverted)
    highlight_entity : str, optional
        Entity name to highlight with bold text in column header
    """

    if invert_metric_ranks is None:
        invert_metric_ranks = DEFAULT_INVERTED_PLAYER_METRICS

    BUBBLE_MAX = 550
    bins = [-0.1, 0.2, 0.4, 0.6, 0.8, 1.1]

    # Collect all metrics from questions
    all_metrics = []
    for key in questions:
        all_metrics += questions[key]

    # Compute percentile ranks
    for m in all_metrics:
        df[m + '_pct_rank'] = df[m].rank(pct=True)
        if m in invert_metric_ranks:
            df[m + '_pct_rank'] = 1 - df[m + '_pct_rank']
        df[m + '_colour'] = pd.cut(df[m + '_pct_rank'], bins=bins, labels=False, right=True)

    # Filter to highlighted entities and order by position
    plot_df = df[df[data_point_id].isin(highlight_group)].reset_index(drop=True)
    if 'most_common_position' in plot_df.columns:
        plot_df['_position_order'] = plot_df['most_common_position'].map(POSITION_ORDER).fillna(99)
        plot_df = plot_df.sort_values('_position_order').reset_index(drop=True)
        plot_df = plot_df.drop(columns=['_position_order'])

    # Build entity names, positions + minutes played
    entity_names = plot_df[data_point_label].tolist()
    entity_positions = (
        plot_df['most_common_position'].tolist()
        if 'most_common_position' in plot_df.columns
        else [None] * len(entity_names)
    )
    entity_minutes = (
        plot_df['total_minutes_played'].tolist()
        if 'total_minutes_played' in plot_df.columns
        else [None] * len(entity_names)
    )

    # Build row data: list of { group: str | null, label: str, metric: str, values: [...] }
    rows = []
    for group_key in questions:
        group_label = group_key.replace('_', ' ').title()
        rows.append({
            "is_group": True,
            "label": group_label,
            "metric": None,
            "values": []
        })
        for metric in questions[group_key]:
            if metric_labels and metric in metric_labels:
                label = metric_labels[metric]
            else:
                label = metric.replace('count_', '').replace('_', ' ').title()
                label = label.replace('Per 30 Tip', 'P30 TIP')

            values = []
            for _, row in plot_df.iterrows():
                pct_rank = row.get(metric + '_pct_rank', None)
                colour_bin = row.get(metric + '_colour', None)
                actual_val = row.get(metric, None)
                if pd.isna(pct_rank):
                    pct_rank = None
                if pd.isna(colour_bin):
                    colour_bin = None
                else:
                    colour_bin = int(colour_bin)
                if pd.isna(actual_val):
                    actual_val = None
                elif isinstance(actual_val, float):
                    actual_val = round(actual_val, 2)

                values.append({
                    "pct_rank": round(pct_rank, 4) if pct_rank is not None else None,
                    "colour_bin": colour_bin,
                    "actual": actual_val
                })

            rows.append({
                "is_group": False,
                "label": label,
                "metric": metric,
                "values": values
            })

    data = {
        "entity_names": entity_names,
        "entity_positions": entity_positions,
        "entity_minutes": entity_minutes,
        "rows": rows,
        "title": plot_title,
        "text_color": text_color,
        "container_width": container_width,
        "highlight_entity": highlight_entity
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
          padding: 0;
        }}
        .title {{
          font-size: 16px;
          font-weight: bold;
          color: {text_color};
          margin-bottom: 8px;
          text-align: center;
        }}
        .main-container {{
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          width: 100%;
        }}
        .ranking-table {{
          border-collapse: collapse;
          table-layout: fixed;
          width: 100%;
          font-size: 13px;
        }}
        .ranking-table th {{
          padding: 6px 4px;
          text-align: center;
          font-size: 12px;
          font-weight: bold;
          color: {text_color};
          vertical-align: bottom;
          border-bottom: 2px solid #e0e0e0;
        }}
        .ranking-table th.entity-header {{
          cursor: default;
        }}
        .ranking-table th.label-header {{
          text-align: right;
          padding-right: 12px;
          width: 20%;
        }}
        .ranking-table td {{
          padding: 0;
          height: 28px;
          vertical-align: middle;
          border-bottom: 1px solid #f0f0f0;
        }}
        .ranking-table td.label-cell {{
          text-align: right;
          padding-right: 12px;
          font-size: 12px;
          color: {text_color};
          word-wrap: break-word;
          overflow-wrap: break-word;
          width: 20%;
        }}
        .ranking-table td.group-cell {{
          text-align: right;
          padding-right: 12px;
          font-size: 13px;
          font-weight: bold;
          color: {text_color};
          word-wrap: break-word;
          overflow-wrap: break-word;
          width: 20%;
          padding-top: 8px;
          padding-bottom: 4px;
          border-bottom: none;
        }}
        .ranking-table td.bar-cell {{
          position: relative;
          padding: 2px 4px;
        }}
        .bar-bg {{
          position: absolute;
          top: 3px;
          left: 4px;
          right: 4px;
          bottom: 3px;
          background: #f5f5f5;
          border-radius: 3px;
          border: 1px dashed #e0e0e0;
        }}
        .bar-fill {{
          position: absolute;
          top: 3px;
          left: 4px;
          bottom: 3px;
          border-radius: 3px;
          transition: width 0.3s ease;
        }}
        .bar-text {{
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          font-size: 11px;
          font-weight: bold;
          z-index: 2;
          white-space: nowrap;
        }}
        .ranking-table tbody tr:not(.group-row) {{
          transition: box-shadow 0.15s ease;
        }}
        .ranking-table tbody tr:not(.group-row):hover {{
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
          position: relative;
          z-index: 10;
        }}
        .legend {{
          display: flex;
          flex-direction: row;
          justify-content: center;
          gap: 15px;
          font-size: 11px;
          flex-wrap: wrap;
          padding-top: 10px;
          width: 100%;
        }}
        .legend-item {{
          display: flex;
          align-items: center;
          gap: 6px;
        }}
        .legend-color {{
          width: 20px;
          height: 16px;
          border-radius: 2px;
        }}
        .legend-label {{
          color: {text_color};
          line-height: 1.2;
        }}
        .entity-minutes {{
          font-size: 10px;
          font-weight: normal;
          color: #888888;
          display: block;
          margin-top: 2px;
        }}
      </style>
    </head>
    <body>
      <div class="main-container">
        <div id="ranking-container" style="width: 100%;">
          <table id="ranking-table" class="ranking-table"></table>
        </div>
        <div class="legend" id="legend">
          <div class="legend-item"><div class="legend-color" style="background:#FF1A1A"></div><span class="legend-label">0-20th</span></div>
          <div class="legend-item"><div class="legend-color" style="background:#FDA4A4"></div><span class="legend-label">20-40th</span></div>
          <div class="legend-item"><div class="legend-color" style="background:#D9D9D6"></div><span class="legend-label">40-60th</span></div>
          <div class="legend-item"><div class="legend-color" style="background:#99E59A"></div><span class="legend-label">60-80th</span></div>
          <div class="legend-item"><div class="legend-color" style="background:#00C800"></div><span class="legend-label">80-100th</span></div>
        </div>
      </div>

      <script>
        const data = {json.dumps(data)};

        const colors = ['#FF1A1A', '#FDA4A4', '#D9D9D6', '#99E59A', '#00C800'];

        function getColor(colourBin) {{
          if (colourBin === null || colourBin === undefined) return '#f0f0f0';
          return colors[Math.max(0, Math.min(colourBin, colors.length - 1))];
        }}

        function getTextColor(colourBin, pctRank) {{
          if (colourBin === null) return data.text_color;
          if (colourBin <= 0) return '#ffffff';
          return data.text_color;
        }}

        function ordinal(n) {{
          const s = ['th', 'st', 'nd', 'rd'];
          const v = n % 100;
          return n + (s[(v - 20) % 10] || s[v] || s[0]);
        }}

        const table = document.getElementById('ranking-table');
        const numEntities = data.entity_names.length;
        const entityColPct = (80 / Math.max(1, numEntities));

        function renderTable() {{
          table.innerHTML = '';

          // Header row
          const thead = document.createElement('thead');
          const headerRow = document.createElement('tr');

          // Label column header with download button
          const labelHeader = document.createElement('th');
          labelHeader.className = 'label-header';
          labelHeader.innerHTML = '';
          headerRow.appendChild(labelHeader);

          // Entity column headers
          data.entity_names.forEach((name, idx) => {{
            const th = document.createElement('th');
            th.className = 'entity-header';
            th.style.width = entityColPct + '%';

            // Split name onto multiple lines if needed
            const words = name.split(' ');
            let lines = [];
            let currentLine = '';
            const charsPerLine = Math.max(6, Math.floor(entityColPct * 1.2));

            words.forEach(word => {{
              const testLine = currentLine.length > 0 ? currentLine + ' ' + word : word;
              if (testLine.length > charsPerLine && currentLine.length > 0) {{
                lines.push(currentLine);
                currentLine = word;
              }} else {{
                currentLine = testLine;
              }}
            }});
            if (currentLine.length > 0) lines.push(currentLine);

            // Position sub-label
            const position = data.entity_positions[idx];
            const positionHtml = (position !== null && position !== undefined)
              ? '<span class="entity-minutes">' + position + '</span>'
              : '';

            // Minutes played sub-label
            const minutes = data.entity_minutes[idx];
            const minutesHtml = (minutes !== null && minutes !== undefined)
              ? '<span class="entity-minutes">' + Math.round(minutes) + ' mins</span>'
              : '';

            th.innerHTML = lines.join('<br>') + positionHtml + minutesHtml;

            if (data.highlight_entity && name === data.highlight_entity) {{
              th.style.fontWeight = '900';
              th.style.fontSize = '13px';
            }}

            headerRow.appendChild(th);
          }});

          thead.appendChild(headerRow);
          table.appendChild(thead);

          // Body rows
          const tbody = document.createElement('tbody');

          data.rows.forEach(rowData => {{
            const tr = document.createElement('tr');

            if (rowData.is_group) {{
              tr.className = 'group-row';
              const groupCell = document.createElement('td');
              groupCell.className = 'group-cell';
              groupCell.textContent = rowData.label;
              tr.appendChild(groupCell);
              // Empty cells to fill the entity columns
              for (let i = 0; i < numEntities; i++) {{
                const emptyCell = document.createElement('td');
                emptyCell.style.borderBottom = 'none';
                emptyCell.style.height = '28px';
                tr.appendChild(emptyCell);
              }}
            }} else {{
              // Label cell
              const labelCell = document.createElement('td');
              labelCell.className = 'label-cell';
              labelCell.textContent = rowData.label;
              tr.appendChild(labelCell);

              // Bar cells for each entity
              rowData.values.forEach(val => {{
                const td = document.createElement('td');
                td.className = 'bar-cell';
                td.style.width = entityColPct + '%';

                if (val.pct_rank !== null) {{
                  const barWidth = Math.max(0, Math.min(100, val.pct_rank * 100));
                  const barColor = getColor(val.colour_bin);
                  const txtColor = getTextColor(val.colour_bin, val.pct_rank);
                  const displayText = val.actual !== null && val.actual !== undefined ? String(val.actual) : '';

                  // Background
                  const bgDiv = document.createElement('div');
                  bgDiv.className = 'bar-bg';
                  td.appendChild(bgDiv);

                  // Fill bar
                  const fillDiv = document.createElement('div');
                  fillDiv.className = 'bar-fill';
                  fillDiv.style.width = 'calc(' + barWidth + '% - 8px)';
                  fillDiv.style.backgroundColor = barColor;
                  td.appendChild(fillDiv);

                  // Text
                  const textDiv = document.createElement('div');
                  textDiv.className = 'bar-text';
                  textDiv.textContent = displayText;
                  textDiv.style.color = txtColor;
                  td.appendChild(textDiv);
                }}

                tr.appendChild(td);
              }});
            }}

            tbody.appendChild(tr);
          }});

          table.appendChild(tbody);
        }}

        renderTable();
      </script>
    </body>
    </html>
    """

    return html