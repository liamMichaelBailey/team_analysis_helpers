import pandas as pd
import json
import numpy as np

PRIMARY_HIGHLIGHT_COLOR = '#00C800'
BASE_COLOR = '#D9D9D6'
TEXT_COLOR = '#001400'

class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles NumPy types."""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        return super().default(obj)

def scatter_chart_component(
        df: pd.DataFrame,
        x_metric: str,
        y_metric: str,
        x_label: str = None,
        y_label: str = None,
        primary_highlight_group=None,
        x_sd_highlight: float = None,
        y_sd_highlight: float = None,
        include_below_average: bool = True,
        data_point_id: str = "player_id",
        data_point_label: str = "short_name",
        primary_color: str = PRIMARY_HIGHLIGHT_COLOR,
        base_color: str = BASE_COLOR,
        text_color: str = TEXT_COLOR,
        sample_avg_filter: str = None,
        x_lims: tuple = None,  # New parameter for x-axis limits
        y_lims: tuple = None   # New parameter for y-axis limits
):
    if primary_highlight_group is None:
        primary_highlight_group = []

    # Filter out rows with NaN values in either metric
    df_filtered = df.dropna(subset=[x_metric, y_metric])

    # Calculate means in Python (fixing the logic - if sample_avg_filter is not None, filter by it)
    if sample_avg_filter is not None:
        # Filter by competition_edition_name for mean calculation
        df_for_mean = df_filtered[df_filtered['competition_edition_name'] == sample_avg_filter]
        # If no data matches the filter, fall back to all data
        if len(df_for_mean) == 0:
            df_for_mean = df_filtered
    else:
        # Use all data if no filter specified
        df_for_mean = df_filtered

    x_mean = df_for_mean[x_metric].mean()
    y_mean = df_for_mean[y_metric].mean()

    data = {
        "df": df_filtered.to_dict(orient="records"),
        "x_metric": x_metric,
        "y_metric": y_metric,
        "x_label": x_label,
        "y_label": y_label,
        "primary_highlight_group": primary_highlight_group,
        "x_sd_highlight": x_sd_highlight,
        "y_sd_highlight": y_sd_highlight,
        "include_below_average": include_below_average,
        "data_point_id": data_point_id,
        "data_point_label": data_point_label,
        "primary_color": primary_color,
        "base_color": base_color,
        "text_color": text_color,
        "sample_avg_filter": sample_avg_filter,
        "x_mean": x_mean,
        "y_mean": y_mean,
        "x_lims": x_lims,  # Pass x limits to JavaScript
        "y_lims": y_lims   # Pass y limits to JavaScript
    }

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
      <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@1.4.0"></script>
      <style>
        body {{ margin: 0; padding: 0; background-color: white; }}
        .chart-wrapper {{ position: relative; width: 100%; padding-bottom: 50%; }}
        canvas {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; background-color: white; cursor: pointer; }}
        .button-wrapper {{ position: absolute; top: 15px; right: 15px; z-index: 1000; }}
        .download-button {{ 
          width: 32px; 
          height: 32px; 
          border-radius: 50%; 
          border: none; 
          cursor: pointer; 
          display: flex; 
          align-items: center; 
          justify-content: center;
          font-size: 14px;
          color: white;
          box-shadow: 0 2px 4px rgba(0,0,0,0.2);
          transition: transform 0.2s ease;
        }}
        .download-button:hover {{
          transform: scale(1.1);
        }}
        .download-button::before {{
          content: '⬇';
          font-weight: bold;
        }}
      </style>
    </head>
    <body>
      <div class="chart-wrapper">
        <canvas id="scatterChart"></canvas>
        <div class="button-wrapper">
          <button class="download-button" onclick="downloadPNG()"></button>
        </div>
      </div>
      <script>
        const data = {json.dumps(data, cls=NumpyEncoder)};
        const df = data.df;
        const xMetric = data.x_metric;
        const yMetric = data.y_metric;
        const labelMetric = data.data_point_label;
        let highlightGroup = [...data.primary_highlight_group] || []; // Make it mutable
        const xSD = data.x_sd_highlight;
        const ySD = data.y_sd_highlight;
        const includeBelow = data.include_below_average;
        const sampleAvgFilter = data.sample_avg_filter;

        // Use the means calculated in Python
        const xMean = data.x_mean;
        const yMean = data.y_mean;

        // Get custom axis limits if provided
        const customXLims = data.x_lims;
        const customYLims = data.y_lims;

        // Set download button background color to primary color
        document.addEventListener('DOMContentLoaded', function() {{
          const downloadBtn = document.querySelector('.download-button');
          if (downloadBtn) {{
            downloadBtn.style.backgroundColor = data.primary_color;
          }}
        }});

        // Filter out rows with null/undefined/NaN values in either metric
        const validRows = df.filter(row => {{
          const xValue = row[xMetric];
          const yValue = row[yMetric];
          return xValue !== null && xValue !== undefined && !isNaN(xValue) &&
                 yValue !== null && yValue !== undefined && !isNaN(yValue);
        }});

        // Set up label text
        let avgLabelText = ['Sample Avg'];
        if (sampleAvgFilter !== null && sampleAvgFilter !== undefined) {{
          avgLabelText = [`Avg of ${{sampleAvgFilter}}`, 'players in sample'];
        }}

        const xValues = validRows.map(row => row[xMetric]);
        const yValues = validRows.map(row => row[yMetric]);
        const xMin = Math.min(...xValues);
        const xMax = Math.max(...xValues);
        const yMin = Math.min(...yValues);
        const yMax = Math.max(...yValues);
        const xRange = xMax - xMin;
        const yRange = yMax - yMin;
        const xPadding = xRange * 0.05;
        const yPadding = yRange * 0.05;

        // Calculate nice step sizes for even tick spacing
        function calculateNiceStep(range, targetTicks = 5) {{
          const roughStep = range / targetTicks;
          const magnitude = Math.pow(10, Math.floor(Math.log10(roughStep)));
          const normalizedStep = roughStep / magnitude;

          let niceStep;
          if (normalizedStep <= 1) niceStep = 1;
          else if (normalizedStep <= 2) niceStep = 2;
          else if (normalizedStep <= 5) niceStep = 5;
          else niceStep = 10;

          return niceStep * magnitude;
        }}

        function calculateNiceBounds(min, max, step) {{
          const niceMin = Math.floor(min / step) * step;
          const niceMax = Math.ceil(max / step) * step;
          return {{ min: niceMin, max: niceMax }};
        }}

        // Calculate step sizes based on original data range (not custom limits)
        const xStep = calculateNiceStep(xRange);
        const yStep = calculateNiceStep(yRange);

        // Use custom limits if provided, otherwise calculate nice bounds
        let xBounds, yBounds;

        if (customXLims && customXLims.length === 2) {{
          // Add padding to custom x limits (3% of the custom range on each side)
          const xCustomRange = customXLims[1] - customXLims[0];
          const xCustomPadding = xCustomRange * 0.03;
          xBounds = {{ 
            min: customXLims[0] - xCustomPadding, 
            max: customXLims[1] + xCustomPadding 
          }};
        }} else {{
          xBounds = calculateNiceBounds(xMin - xPadding, xMax + xPadding, xStep);
        }}

        if (customYLims && customYLims.length === 2) {{
          // Add padding to custom y limits (3% of the custom range on each side)
          const yCustomRange = customYLims[1] - customYLims[0];
          const yCustomPadding = yCustomRange * 0.03;
          yBounds = {{ 
            min: customYLims[0] - yCustomPadding, 
            max: customYLims[1] + yCustomPadding 
          }};
        }} else {{
          yBounds = calculateNiceBounds(yMin - yPadding, yMax + yPadding, yStep);
        }}

        const highlight = row => {{
          let xOutlier = false;
          let yOutlier = false;

          // Filter rows for standard deviation calculation
          const sampleRows = sampleAvgFilter !== null && sampleAvgFilter !== undefined
            ? validRows.filter(r => r.competition_edition_name === sampleAvgFilter)
            : validRows;

          const sampleXValues = sampleRows.map(r => r[xMetric]);
          const sampleYValues = sampleRows.map(r => r[yMetric]);

          if (xSD !== null && xSD !== undefined) {{
            const xStd = Math.sqrt(sampleXValues.map(v => (v - xMean) ** 2).reduce((a, b) => a + b, 0) / sampleXValues.length);
            xOutlier = row[xMetric] > xMean + xSD * xStd || (includeBelow && row[xMetric] < xMean - xSD * xStd);
          }}
          if (ySD !== null && ySD !== undefined) {{
            const yStd = Math.sqrt(sampleYValues.map(v => (v - yMean) ** 2).reduce((a, b) => a + b, 0) / sampleYValues.length);
            yOutlier = row[yMetric] > yMean + ySD * yStd || (includeBelow && row[yMetric] < yMean - ySD * yStd);
          }}
          return xOutlier || yOutlier || highlightGroup.includes(row[data.data_point_id]);
        }};

        // Function to rebuild datasets based on current highlight group
        function rebuildDatasets() {{
          const regularPoints = [];
          const highlightedPoints = [];

          validRows.forEach((row, i) => {{
            const isHighlighted = highlight(row);
            const point = {{
              x: row[xMetric],
              y: row[yMetric],
              label: row[labelMetric],
              team_name: labelMetric === 'team_name' ? '' : (row.team_name || ''),
              competition_edition_name: row.competition_edition_name || '',
              dataIndex: i,  // Store original data index
              playerId: row[data.data_point_id]  // Store player ID for click handling
            }};

            if (isHighlighted) {{
              highlightedPoints.push(point);
            }} else {{
              regularPoints.push(point);
            }}
          }});

          return {{ regularPoints, highlightedPoints }};
        }}

        // Initial dataset creation
        let {{ regularPoints, highlightedPoints }} = rebuildDatasets();

        // Label positioning algorithm
        function calculateLabelPositions(points, xScale, yScale) {{
          // Define possible positions relative to the point
          const positions = [
            {{ x: 'center', y: 'start', xOffset: 0, yOffset: -15 }},   // top
            {{ x: 'center', y: 'end', xOffset: 0, yOffset: 15 }},      // bottom
            {{ x: 'start', y: 'center', xOffset: -15, yOffset: 0 }},   // left
            {{ x: 'end', y: 'center', xOffset: 15, yOffset: 0 }},      // right
            {{ x: 'start', y: 'start', xOffset: -10, yOffset: -10 }},  // top-left
            {{ x: 'end', y: 'start', xOffset: 10, yOffset: -10 }},     // top-right
            {{ x: 'start', y: 'end', xOffset: -10, yOffset: 10 }},     // bottom-left
            {{ x: 'end', y: 'end', xOffset: 10, yOffset: 10 }}         // bottom-right
          ];

          // Estimate label dimensions
          const labelWidth = 60;  // Approximate width in pixels
          const labelHeight = 20; // Approximate height in pixels

          // Track occupied spaces
          const occupiedSpaces = [];

          // Calculate positions for each point
          const labelPositions = [];

          points.forEach(point => {{
            const pixelX = xScale.getPixelForValue(point.x);
            const pixelY = yScale.getPixelForValue(point.y);

            // Try each position until we find one without overlap
            let bestPosition = null;
            let minOverlap = Infinity;

            for (const pos of positions) {{
              const labelX = pixelX + pos.xOffset;
              const labelY = pixelY + pos.yOffset;

              // Calculate label bounds based on position
              const labelLeft = pos.x === 'end' ? labelX : labelX - labelWidth;
              const labelRight = pos.x === 'start' ? labelX : labelX + labelWidth;
              const labelTop = pos.y === 'end' ? labelY : labelY - labelHeight;
              const labelBottom = pos.y === 'start' ? labelY : labelY + labelHeight;

              // Check for overlaps with existing labels
              let overlap = 0;
              for (const space of occupiedSpaces) {{
                if (!(labelRight < space.left || labelLeft > space.right || 
                      labelBottom < space.top || labelTop > space.bottom)) {{
                  // Calculate overlap area
                  const overlapWidth = Math.min(labelRight, space.right) - Math.max(labelLeft, space.left);
                  const overlapHeight = Math.min(labelBottom, space.bottom) - Math.max(labelTop, space.top);
                  overlap += overlapWidth * overlapHeight;
                }}
              }}

              // Check if this position is better than our current best
              if (overlap < minOverlap) {{
                minOverlap = overlap;
                bestPosition = {{ 
                  position: pos,
                  bounds: {{ left: labelLeft, right: labelRight, top: labelTop, bottom: labelBottom }},
                }};

                // If we found a position with no overlap, use it immediately
                if (overlap === 0) break;
              }}
            }}

            // Use the best position we found
            occupiedSpaces.push(bestPosition.bounds);
            labelPositions.push({{
              point: point,
              position: bestPosition.position
            }});
          }});

          return labelPositions;
        }}

        // Custom plugin to draw labels on top of everything
        const labelPlugin = {{
          id: 'playerLabels',
          afterDatasetsDraw: function(chart) {{
            const ctx = chart.ctx;
            const xScale = chart.scales.x;
            const yScale = chart.scales.y;

            // Get current highlighted points from the chart data
            const currentHighlightedPoints = chart.data.datasets[1].data;

            // Calculate optimal label positions
            const labelPositions = calculateLabelPositions(currentHighlightedPoints, xScale, yScale);

            // Set font properties
            ctx.font = 'bold 12px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            // Draw each label
            labelPositions.forEach(item => {{
              const pixelX = xScale.getPixelForValue(item.point.x);
              const pixelY = yScale.getPixelForValue(item.point.y);

              const labelX = pixelX + item.position.xOffset;
              const labelY = pixelY + item.position.yOffset;

              // Adjust text alignment based on position
              if (item.position.x === 'start') {{
                ctx.textAlign = 'right';
              }} else if (item.position.x === 'end') {{
                ctx.textAlign = 'left';
              }} else {{
                ctx.textAlign = 'center';
              }}

              if (item.position.y === 'start') {{
                ctx.textBaseline = 'bottom';
              }} else if (item.position.y === 'end') {{
                ctx.textBaseline = 'top';
              }} else {{
                ctx.textBaseline = 'middle';
              }}

              // Draw white stroke for better visibility
              ctx.strokeStyle = 'white';
              ctx.lineWidth = 3;
              ctx.strokeText(item.point.label, labelX, labelY);

              // Draw the actual text
              ctx.fillStyle = data.text_color;
              ctx.fillText(item.point.label, labelX, labelY);
            }});
          }}
        }};

        // Register the custom plugin
        Chart.register(labelPlugin);

        // Create annotations for average lines with lower z-order
        const avgAnnotations = [
          {{ 
            type: 'line', 
            xMin: xMean, 
            xMax: xMean, 
            borderColor: data.text_color, 
            borderWidth: 1, 
            borderDash: [4, 4],
            z: -1,
            label: {{ 
              content: avgLabelText, 
              enabled: true, 
              position: 'start',
              color: data.text_color,
              font: {{ size: 11 }},
              backgroundColor: 'transparent',
              padding: 0,
              textStrokeColor: 'white',
              textStrokeWidth: 4,
              z: 5
            }} 
          }},
          {{ 
            type: 'line', 
            yMin: yMean, 
            yMax: yMean, 
            borderColor: data.text_color, 
            borderWidth: 1, 
            borderDash: [4, 4],
            z: -1,
            label: {{ 
              content: avgLabelText, 
              enabled: true, 
              position: 'start',
              color: data.text_color,
              font: {{ size: 11 }},
              backgroundColor: 'transparent',
              padding: 0,
              textStrokeColor: 'white',
              textStrokeWidth: 4,
              z: 5
            }} 
          }}
        ];

        const chartConfig = {{
          type: 'scatter',
          data: {{
            datasets: [
              {{
                label: 'Regular Players',
                data: regularPoints,
                parsing: false,
                backgroundColor: data.base_color,
                pointRadius: 8,
                pointHoverRadius: 12,  // Larger on hover
                borderColor: '#fff',
                borderWidth: 1,
                pointHoverBorderWidth: 2,  // Slightly thicker border on hover
                order: 2
              }},
              {{
                label: 'Highlighted Players',
                data: highlightedPoints,
                parsing: false,
                backgroundColor: data.primary_color,
                pointRadius: 10,
                pointHoverRadius: 14,  // Larger on hover
                borderColor: '#fff',
                borderWidth: 1,
                pointHoverBorderWidth: 2,  // Slightly thicker border on hover
                order: 1
              }}
            ]
          }},
          options: {{
            responsive: true,
            maintainAspectRatio: false,
            layout: {{ padding: 20 }},
            // Disable animations for immediate rendering
            animation: false,
            hover: {{
              mode: 'nearest',
              intersect: true,
              animationDuration: 150,
              onHover: function(event, activeElements) {{
                // Ensure hover state is properly managed
                if (activeElements.length > 0) {{
                  this.canvas.style.cursor = 'pointer';
                }} else {{
                  this.canvas.style.cursor = 'default';
                }}
              }}
            }},
            onClick: function(event, elements) {{
              if (elements.length > 0) {{
                const element = elements[0];
                const datasetIndex = element.datasetIndex;
                const dataIndex = element.index;

                // Get the clicked point data
                const clickedPoint = this.data.datasets[datasetIndex].data[dataIndex];
                const playerId = clickedPoint.playerId;

                // Toggle the player in the highlight group
                const index = highlightGroup.indexOf(playerId);
                if (index > -1) {{
                  // Remove from highlight group
                  highlightGroup.splice(index, 1);
                }} else {{
                  // Add to highlight group
                  highlightGroup.push(playerId);
                }}

                // Rebuild datasets with new highlight group
                const newDatasets = rebuildDatasets();

                // Update chart data
                this.data.datasets[0].data = newDatasets.regularPoints;
                this.data.datasets[1].data = newDatasets.highlightedPoints;

                // Clear any active hover states before updating
                this.tooltip.setActiveElements([], {{x: 0, y: 0}});
                this.setActiveElements([]);

                // Update the chart and reset hover state
                this.update('none');

                // Force a hover state reset by triggering a fake mouse move outside the chart
                setTimeout(() => {{
                  const rect = this.canvas.getBoundingClientRect();
                  const fakeEvent = new MouseEvent('mousemove', {{
                    clientX: rect.left - 10,
                    clientY: rect.top - 10
                  }});
                  this.canvas.dispatchEvent(fakeEvent);
                }}, 10);
              }}
            }},
            plugins: {{
              tooltip: {{
                backgroundColor: 'white',
                titleColor: 'black',
                bodyColor: 'black',
                borderColor: '#ccc',
                borderWidth: 1,
                callbacks: {{
                  label: function(context) {{
                    const point = context.raw;
                    const lines = [point.label];
                    if (point.team_name) lines.push(`${{point.team_name}}`);
                    if (point.competition_edition_name) lines.push(`${{point.competition_edition_name}}`);
                    return lines;
                  }}
                }}
              }},
              legend: {{ display: false }},
              annotation: {{ 
                annotations: avgAnnotations,
                drawTime: 'beforeDatasetsDraw'
              }},
              playerLabels: {{}} // Enable our custom label plugin
            }},
            scales: {{
              x: {{
                min: xBounds.min,
                max: xBounds.max,
                title: {{ 
                  display: true, 
                  text: data.x_label || xMetric, 
                  color: data.text_color,
                  font: {{ weight: 'bold', size: 18 }}
                }},
                grid: {{ color: '#eee' }},
                border: {{ display: false }},
                ticks: {{ 
                  color: data.text_color,
                  stepSize: xStep,
                  maxTicksLimit: 8
                }}
              }},
              y: {{
                min: yBounds.min,
                max: yBounds.max,
                title: {{ 
                  display: true, 
                  text: data.y_label || yMetric, 
                  color: data.text_color,
                  font: {{ weight: 'bold', size: 18 }}
                }},
                grid: {{ color: '#eee' }},
                border: {{ display: false }},
                ticks: {{ 
                  color: data.text_color,
                  stepSize: yStep,
                  maxTicksLimit: 8
                }}
              }}
            }}
          }}
        }};

        const chartCanvas = document.getElementById('scatterChart');
        const scatterChart = new Chart(chartCanvas, chartConfig);

        // Set download button color after chart is created
        const downloadBtn = document.querySelector('.download-button');
        if (downloadBtn) {{
          downloadBtn.style.backgroundColor = data.primary_color;
        }}

        function downloadPNG() {{
          // Calculate dimensions for 300 DPI
          // Standard print sizes: 8.5x11 inches at 300 DPI = 2550x3300 pixels
          // For landscape chart, use 11x8.5 inches = 3300x2550 pixels
          // Or for a more reasonable size: 10x5 inches = 3000x1500 pixels
          const dpi = 900;
          const widthInches = 8;  // 10 inches wide
          const heightInches = 4;  // 5 inches tall
          const exportWidth = widthInches * dpi;  // 3000 pixels
          const exportHeight = heightInches * dpi; // 1500 pixels

          // Create high-resolution canvas
          const exportCanvas = document.createElement('canvas');
          exportCanvas.width = exportWidth;
          exportCanvas.height = exportHeight;
          const exportCtx = exportCanvas.getContext('2d');

          // Set high-quality rendering
          exportCtx.imageSmoothingEnabled = true;
          exportCtx.imageSmoothingQuality = 'high';

          // Fill with white background
          exportCtx.fillStyle = 'white';
          exportCtx.fillRect(0, 0, exportWidth, exportHeight);

          // Get the current chart canvas
          const chartCanvas = document.getElementById('scatterChart');

          // Draw the chart scaled up to high resolution
          exportCtx.drawImage(chartCanvas, 0, 0, exportWidth, exportHeight);

          // Create download link
          const link = document.createElement('a');
          link.download = 'skillcorner_scatter_plot.png';
          link.href = exportCanvas.toDataURL('image/png');
          link.click();
        }}
      </script>
    </body>
    </html>
    """

    return html
