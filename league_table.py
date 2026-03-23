import pandas as pd
import json


DEFAULT_INVERTED_HEATMAP_METRICS = [
    # In-possession: losing the ball / playing backwards
    'possession_loss_in_build_up_percentage',
    'possession_loss_in_create_percentage',
    'possession_loss_in_finish_percentage',
    'played_back_to_build_up_from_create_percentage',
    'played_back_to_create_from_finish_percentage',
    # Out-of-possession: conceding shots / being pushed deeper
    'conceded_shot_in_low_block_percentage',
    'progressed_to_low_block_from_medium_block_percentage',
    'progressed_to_medium_block_from_high_block_percentage',
]


def safe_json(df):
    def convert_value(x):
        if isinstance(x, pd.Timestamp):
            return x.isoformat()
        elif pd.isna(x):
            return None
        return x

    df_clean = df.applymap(convert_value)
    return df_clean


def heatmap_component(
        df: pd.DataFrame,
        metrics: list,
        labels: list = None,
        team_name_col: str = "team_shortname",
        sort_by_col: str = "points_per_match",
        rotate_xticks: bool = True,
        title: str = "",
        text_color: str = "#333333",
        height: int = 600,
        container_width: int = 1200,
        all_metrics: list = None,
        default_metrics: list = None,
        highlight_team: str = None,
        invert_metrics: list = DEFAULT_INVERTED_HEATMAP_METRICS
):
    """
    Streamlit custom component for a team performance heatmap.

    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame containing team data with z-score normalized metrics
    metrics : list
        List of column names to display as heatmap columns (used if all_metrics not provided)
    labels : list, optional
        Display labels for metrics (defaults to metrics if not provided)
    team_name_col : str
        Column name for team names
    sort_by_col : str
        Column name to sort teams by (descending)
    rotate_xticks : bool
        Whether to rotate x-axis labels 45 degrees
    title : str
        Chart title
    text_color : str
        Color for text elements
    height : int
        Height of the component in pixels
    container_width : int
        Total width available for the heatmap (default 1200px)
    all_metrics : list, optional
        Full list of available metrics for selection panel
    default_metrics : list, optional
        List of metrics selected by default
    highlight_team : str, optional
        Team name to highlight with bold text
    """

    if all_metrics is None:
        all_metrics = metrics

    if default_metrics is None:
        default_metrics = metrics

    if invert_metrics is None:
        invert_metrics = DEFAULT_INVERTED_HEATMAP_METRICS

    if labels is None:
        labels = metrics.copy()

    all_labels = [m.replace('_', ' ').title() for m in all_metrics]

    df_sorted = df.sort_values(by=sort_by_col, ascending=False).copy()

    team_names = df_sorted[team_name_col].tolist()

    matrix_data = []
    actual_values = []
    for _, row in df_sorted.iterrows():
        row_data = []
        row_actual = []
        for metric in all_metrics:
            zscore_col = metric + '_competition_score'
            if zscore_col in df.columns:
                val = row[zscore_col]
                if pd.isna(val):
                    row_data.append(None)
                else:
                    if metric in invert_metrics:
                        val = -val
                    row_data.append(max(-2.5, min(2.5, val)))
            else:
                row_data.append(None)

            if metric in df.columns:
                actual_val = row[metric]
                if pd.isna(actual_val):
                    row_actual.append(None)
                else:
                    row_actual.append(round(actual_val, 2) if isinstance(actual_val, float) else actual_val)
            else:
                row_actual.append(None)
        matrix_data.append(row_data)
        actual_values.append(row_actual)

    data = {
        "team_names": team_names,
        "all_metrics": all_metrics,
        "all_labels": all_labels,
        "default_metrics": default_metrics,
        "matrix": matrix_data,
        "actual_values": actual_values,
        "rotate_xticks": rotate_xticks,
        "title": title,
        "text_color": text_color,
        "container_width": container_width,
        "highlight_team": highlight_team
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
          margin-bottom: 4px;
          text-align: center;
        }}
        .main-container {{
          display: flex;
          flex-direction: row;
          gap: 6px;
          align-items: flex-start;
        }}
        .heatmap-section {{
          flex: 1;
          min-width: 0;
        }}

        .container {{
          display: flex;
          flex-direction: column;
          gap: 3px;
          padding-left: 0;
        }}
        .heatmap-wrapper {{
          width: 100%;
          overflow-x: hidden;
        }}
        .heatmap {{
          border-collapse: collapse;
          font-size: 13px;
          /* use table-layout fixed to enforce column widths */
          table-layout: fixed;
          width: 100%;
        }}
        .heatmap th, .heatmap td {{
          padding: 4px 6px;
          text-align: left;
          white-space: nowrap;
        }}
        /* team cell percentage width */
        .heatmap .team-cell,
        .heatmap th:first-child,
        .heatmap td.team-name {{
          width: 15%;
          text-align: right;
          padding-right: 8px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          font-size: 13px;
          font-weight: 600;
        }}
        .heatmap th.metric-header {{
          text-align: center;
          cursor: pointer;
          transition: background 0.2s;
          vertical-align: bottom;
          padding: 4px 3px;
          overflow: hidden;
          word-wrap: break-word;
          white-space: normal;
          line-height: 1.25;
        }}
        .metric-header-content {{
          display: -webkit-box;
          -webkit-line-clamp: 3;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }}
        .heatmap th.metric-header.dragging {{
          opacity: 0.5;
          background: #ccc;
        }}
        .heatmap th.metric-header.drag-over {{
          border-left: 3px solid #333;
        }}
        .heatmap th.metric-header.sorted {{
          background: #e0e0e0;
        }}

        .heatmap td {{
          height: 28px;
          text-align: center;
          border: 1px solid #fff;
          position: relative;
          font-weight: 500;
          color: {text_color};
          overflow: hidden;
          text-overflow: ellipsis;
        }}

        .heatmap tbody tr {{
          transition: box-shadow 0.15s ease;
        }}
        .heatmap tbody tr:hover {{
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
          position: relative;
          z-index: 10;
        }}
        .legend {{
          display: flex;
          flex-direction: row;
          justify-content: center;
          gap: 8px;
          font-size: 11px;
          flex-wrap: wrap;
          padding-top: 3px;
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
        .metric-header-content {{
          display: flex;
          flex-direction: column;
          align-items: center;
        }}

      </style>
    </head>
    <body>
      <div class="main-container">
        <div class="heatmap-section">
          <div class="container">
            <div class="heatmap-wrapper" id="heatmap-container">
              <table id="heatmap-table" class="heatmap"></table>
            </div>
            <div class="legend" id="legend">
              <div class="legend-item"><div class="legend-color" style="background:#FF1A1A"></div><span class="legend-label">Very Low</span></div>
              <div class="legend-item"><div class="legend-color" style="background:#FDA4A4"></div><span class="legend-label">Low</span></div>
              <div class="legend-item"><div class="legend-color" style="background:#D9D9D6"></div><span class="legend-label">Average</span></div>
              <div class="legend-item"><div class="legend-color" style="background:#99E59A"></div><span class="legend-label">High</span></div>
              <div class="legend-item"><div class="legend-color" style="background:#00C800"></div><span class="legend-label">Very High</span></div>
            </div>
          </div>
        </div>

      </div>

      <script>
        const data = {json.dumps(data)};

        const colors = ['#FF1A1A', '#FDA4A4', '#D9D9D6', '#99E59A', '#00C800'];
        const bounds = [-2.5, -1.5, -0.5, 0.5, 1.5, 2.5];
        const ratings = [
          'Very Low For Competition',
          'Low For Competition', 
          'Average For Competition',
          'High For Competition',
          'Very High For Competition'
        ];

        function getColor(value) {{
          if (value === null || value === undefined) return '#f0f0f0';
          for (let i = 0; i < bounds.length - 1; i++) {{
            if (value >= bounds[i] && value < bounds[i + 1]) {{
              return colors[i];
            }}
          }}
          return value >= bounds[bounds.length - 1] ? colors[colors.length - 1] : colors[0];
        }}

        let selectedMetrics = new Set(data.default_metrics);





        function getSelectedIndices() {{
          const indices = [];
          data.all_metrics.forEach((metric, idx) => {{
            if (selectedMetrics.has(metric)) {{
              indices.push(idx);
            }}
          }});
          return indices;
        }}

        function updateColumnOrder() {{
          const selectedIndices = getSelectedIndices();
          columnOrder = selectedIndices.slice();
        }}

        function getColumnSizing() {{
          const numMetrics = columnOrder.length;
          const team_name_pct = numMetrics <= 4 ? 18 : (numMetrics <= 7 ? 15 : 13);
          const metric_col_pct = (100 - team_name_pct) / Math.max(1, numMetrics);

          let cell_font_size, header_font_size;
          if (numMetrics <= 3) {{
            cell_font_size = 15;
            header_font_size = 14;
          }} else if (numMetrics <= 5) {{
            cell_font_size = 14;
            header_font_size = 13;
          }} else if (numMetrics <= 7) {{
            cell_font_size = 13;
            header_font_size = 12;
          }} else if (numMetrics <= 10) {{
            cell_font_size = 12;
            header_font_size = 11;
          }} else {{
            cell_font_size = 11;
            header_font_size = 10;
          }}

          return {{ metric_col_pct, cell_font_size, header_font_size, team_name_pct }};
        }}

        const container = document.getElementById('heatmap-container');
        const table = document.getElementById('heatmap-table');
        let currentSortCol = null;
        let sortAscending = false;
        let columnOrder = getSelectedIndices();
        let draggedColIdx = null;

        let tableData = data.team_names.map((team, idx) => ({{
          team: team,
          matrix: data.matrix[idx],
          actual: data.actual_values[idx]
        }}));

        function renderTable() {{
          table.innerHTML = '';

          const sizing = getColumnSizing();

          const thead = document.createElement('thead');
          const headerRow = document.createElement('tr');
          const teamHeader = document.createElement('th');
          teamHeader.style.width = sizing.team_name_pct + '%';
          teamHeader.innerHTML = '';
          headerRow.appendChild(teamHeader);



          columnOrder.forEach((originalIdx, displayIdx) => {{
            const label = data.all_labels[originalIdx];
            const th = document.createElement('th');
            th.className = 'metric-header';
            th.draggable = true;
            th.dataset.colIdx = displayIdx;
            th.style.width = sizing.metric_col_pct + '%';
            th.style.fontSize = sizing.header_font_size + 'px';

            if (currentSortCol === 'metric_' + originalIdx) {{
              th.classList.add('sorted');
            }}

            // Let CSS handle wrapping — use full column width
            th.innerHTML = '<div class="metric-header-content" style="word-wrap:break-word;overflow-wrap:break-word;hyphens:auto;">' + label + '</div>';

            th.addEventListener('click', (e) => {{
              if (!th.classList.contains('dragging')) {{
                sortByColumn('metric_' + originalIdx);
              }}
            }});

            th.addEventListener('dragstart', (e) => {{
              draggedColIdx = displayIdx;
              th.classList.add('dragging');
              e.dataTransfer.effectAllowed = 'move';
            }});

            th.addEventListener('dragend', () => {{
              th.classList.remove('dragging');
              draggedColIdx = null;
              document.querySelectorAll('.metric-header').forEach(el => el.classList.remove('drag-over'));
            }});

            th.addEventListener('dragover', (e) => {{
              e.preventDefault();
              e.dataTransfer.dropEffect = 'move';
              if (draggedColIdx !== null && draggedColIdx !== displayIdx) {{
                th.classList.add('drag-over');
              }}
            }});

            th.addEventListener('dragleave', () => {{
              th.classList.remove('drag-over');
            }});

            th.addEventListener('drop', (e) => {{
              e.preventDefault();
              th.classList.remove('drag-over');
              if (draggedColIdx !== null && draggedColIdx !== displayIdx) {{
                const draggedOriginalIdx = columnOrder[draggedColIdx];
                columnOrder.splice(draggedColIdx, 1);
                const targetDisplayIdx = parseInt(th.dataset.colIdx);
                const insertIdx = draggedColIdx < targetDisplayIdx ? targetDisplayIdx : targetDisplayIdx;
                columnOrder.splice(insertIdx, 0, draggedOriginalIdx);
                renderTable();
              }}
            }});

            headerRow.appendChild(th);
          }});
          thead.appendChild(headerRow);
          table.appendChild(thead);

          const tbody = document.createElement('tbody');
          tableData.forEach((rowData, rowIdx) => {{
            const tr = document.createElement('tr');

            const teamCell = document.createElement('td');
            teamCell.className = 'team-name';
            teamCell.textContent = rowData.team;
            if (data.highlight_team && rowData.team === data.highlight_team) {{
              teamCell.style.fontWeight = 'bold';
              teamCell.style.fontSize = '13px';
            }}
            tr.appendChild(teamCell);



            columnOrder.forEach((originalIdx) => {{
              const zScore = rowData.matrix[originalIdx];
              const td = document.createElement('td');
              td.style.backgroundColor = getColor(zScore);
              td.style.width = sizing.metric_col_pct + '%';
              td.style.fontSize = sizing.cell_font_size + 'px';

              const actualVal = rowData.actual[originalIdx];
              td.textContent = actualVal !== null ? actualVal : '';

              if (zScore !== null && zScore < -0.5) {{
                td.style.color = '#fff';
              }}
              tr.appendChild(td);
            }});

            tbody.appendChild(tr);
          }});
          table.appendChild(tbody);

        }}

        function sortByColumn(colKey) {{
          if (currentSortCol === colKey) {{
            sortAscending = !sortAscending;
          }} else {{
            currentSortCol = colKey;
            sortAscending = false;
          }}

          tableData.sort((a, b) => {{
            let valA, valB;

            const idx = parseInt(colKey.split('_')[1]);
            valA = a.matrix[idx];
            valB = b.matrix[idx];

            if (valA === null && valB === null) return 0;
            if (valA === null) return 1;
            if (valB === null) return -1;

            const diff = valA - valB;
            return sortAscending ? diff : -diff;
          }});

          renderTable();
        }}

        renderTable();
      </script>
    </body>
    </html>
    """

    return html
