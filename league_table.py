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
        highlight_team: str = None
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
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ 
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
          flex-direction: row;
          gap: 15px;
          align-items: flex-start;
        }}
        .heatmap-section {{
          flex: 1;
          min-width: 0;
        }}

        .container {{
          display: flex;
          flex-direction: column;
          gap: 10px;
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
          font-size: 11px;
        }}
        .heatmap th.metric-header {{
          text-align: center;
          cursor: pointer;
          transition: background 0.2s;
          vertical-align: bottom;
          padding: 6px 2px;
          overflow: hidden;
          word-wrap: break-word;
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
          height: 32px;
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
          gap: 15px;
          font-size: 11px;
          flex-wrap: wrap;
          padding-top: 8px;
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
          margin-bottom: 3px;
        }}
        .download-btn:hover {{ transform: scale(1.1); }}
        .metric-header-content {{
          display: flex;
          flex-direction: column;
          align-items: center;
        }}

      </style>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
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
          // Use percentage-based widths for responsive layout
          const team_name_pct = 15;  // 15% for team name column
          const metric_col_pct = (100 - team_name_pct) / Math.max(1, numMetrics);

          let cell_font_size, header_font_size, chars_per_line;
          if (numMetrics <= 3) {{
            cell_font_size = 12;
            header_font_size = 12;
            chars_per_line = 14;
          }} else if (numMetrics <= 5) {{
            cell_font_size = 11;
            header_font_size = 11;
            chars_per_line = 11;
          }} else if (numMetrics <= 7) {{
            cell_font_size = 10;
            header_font_size = 10;
            chars_per_line = 8;
          }} else if (numMetrics <= 10) {{
            cell_font_size = 9;
            header_font_size = 9;
            chars_per_line = 6;
          }} else {{
            cell_font_size = 8;
            header_font_size = 8;
            chars_per_line = 5;
          }}

          return {{ metric_col_pct, cell_font_size, header_font_size, chars_per_line, team_name_pct }};
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
          teamHeader.innerHTML = '<button class="download-btn" onclick="downloadPNG()" title="Download PNG">⬇</button>';
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

            const words = label.split(' ');
            let lines = [];
            let currentLine = '';

            words.forEach(word => {{
              const testLine = currentLine.length > 0 ? currentLine + ' ' + word : word;
              if (testLine.length > sizing.chars_per_line && currentLine.length > 0) {{
                lines.push(currentLine);
                currentLine = word;
              }} else {{
                currentLine = testLine;
              }}
            }});

            if (currentLine.length > 0) {{
              lines.push(currentLine);
            }}

            const multiLineLabel = lines.join('<br>');
            th.innerHTML = '<div class="metric-header-content">' + multiLineLabel + '</div>';

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
              teamCell.style.fontSize = '12.5px';
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

        function downloadPNG() {{
          // Hide download button before capture
          const downloadBtn = document.querySelector('.download-btn');
          if (downloadBtn) downloadBtn.style.visibility = 'hidden';

          // Capture both table and legend with high DPI
          const exportContainer = document.querySelector('.container');
          const scale = 3;  // 3x scale for high DPI

          html2canvas(exportContainer, {{
            scale: scale,
            useCORS: true,
            backgroundColor: '#ffffff'
          }}).then(sourceCanvas => {{
            // Create 16:9 canvas
            const targetWidth = 1920;
            const targetHeight = 1080;

            const finalCanvas = document.createElement('canvas');
            finalCanvas.width = targetWidth;
            finalCanvas.height = targetHeight;
            const ctx = finalCanvas.getContext('2d');

            // Fill with white background
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, targetWidth, targetHeight);

            // Calculate scaling to fit content within 16:9 with padding
            const padding = 60;
            const availableWidth = targetWidth - (padding * 2);
            const availableHeight = targetHeight - (padding * 2);

            const scaleX = availableWidth / sourceCanvas.width;
            const scaleY = availableHeight / sourceCanvas.height;
            const fitScale = Math.min(scaleX, scaleY);

            const scaledWidth = sourceCanvas.width * fitScale;
            const scaledHeight = sourceCanvas.height * fitScale;

            // Center the content
            const offsetX = (targetWidth - scaledWidth) / 2;
            const offsetY = (targetHeight - scaledHeight) / 2;

            ctx.drawImage(sourceCanvas, offsetX, offsetY, scaledWidth, scaledHeight);

            const link = document.createElement('a');
            link.href = finalCanvas.toDataURL('image/png');
            link.download = 'heatmap.png';
            link.click();

            // Restore download button visibility
            if (downloadBtn) downloadBtn.style.visibility = 'visible';
          }});
        }}

        renderTable();
      </script>
    </body>
    </html>
    """

    return html
