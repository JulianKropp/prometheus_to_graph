from flask import Flask, Response, request, jsonify
import matplotlib.pyplot as plt
from prometheus_api_client import PrometheusConnect  # type: ignore
from io import BytesIO
import logging
from datetime import datetime, timedelta, timezone
import re
from PIL import Image

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.DEBUG)

def parse_time(value):
    """Parse a time string like '2min', '3sec', '5day', '1year' into a timedelta object."""
    pattern = r'(\d+)([a-zA-Z]+)'
    match = re.match(pattern, value)
    if not match:
        raise ValueError(f"Invalid time format: {value}")

    amount, unit = int(match.group(1)), match.group(2)

    if unit == 'sec':
        return timedelta(seconds=amount)
    elif unit == 'min':
        return timedelta(minutes=amount)
    elif unit == 'h':
        return timedelta(hours=amount)
    elif unit == 'day':
        return timedelta(days=amount)
    elif unit == 'year':
        return timedelta(days=amount * 365)
    else:
        raise ValueError(f"Unsupported time unit: {unit}")

def parse_time_input(value):
    """Parse input time string into a datetime object."""
    if value == 'now':
        return datetime.now(timezone.utc)
    else:
        # Try to parse as an absolute time
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            # Try to parse as a relative time
            try:
                delta = parse_time(value)
                return datetime.now(timezone.utc) - delta
            except ValueError:
                raise ValueError(f"Invalid time format: {value}")

@app.route('/')
def home():
    return "Welcome to the Prometheus Matplotlib Graph Server!"

@app.route('/graph')
def graph():
    prometheus_server = request.args.get('server', 'http://localhost:9090')
    query_string = request.args.get('query')
    start_time_input = request.args.get('start', '1min')
    end_time_input = request.args.get('end', 'now')
    title = request.args.get('title', 'Prometheus Query Result')
    width = request.args.get('width', 14, type=int)
    height = request.args.get('height', 8, type=int)
    xlabel = request.args.get('xlabel', 'Time')
    ylabel = request.args.get('ylabel', 'Value')
    legend = request.args.get('legend', 'true').lower() == 'true'
    label_arg_string = request.args.get('label')

    if not query_string:
        return "Please provide a Prometheus query using the 'query' parameter."

    try:
        # Split the query string by '|' to handle multiple queries
        queries = query_string.split('|')
        label_args = label_arg_string.split('|') if label_arg_string else []

        # Convert start_time and end_time to datetime objects
        start_time = parse_time_input(start_time_input)
        end_time = parse_time_input(end_time_input)

        if start_time > end_time:
            return jsonify({"error": "Start time must be before end time"}), 400

        prom = PrometheusConnect(url=prometheus_server, disable_ssl=True)

        # Create the graph with the specified figure size
        fig, ax = plt.subplots(figsize=(width, height))

        # Loop through each query and plot the results
        for i, query in enumerate(queries):
            
            if len(label_args) > i:
                label_arg = label_args[i]
            
            data = prom.custom_query_range(
                query=query.strip(),
                start_time=start_time,
                end_time=end_time,
                step='60s'
            )

            if not data:
                app.logger.error(f"No data returned from Prometheus for query: {query}")
                continue

            # Loop through each series in the data
            for series in data:
                times = [datetime.fromtimestamp(value[0], tz=timezone.utc) for value in series['values']]
                values = [float(value[1]) for value in series['values']]

                # Determine the label
                if label_arg and label_arg in series['metric']:
                    label = series['metric'][label_arg]
                else:
                    # Fallback to the first available label that is not 'instance' or 'job'
                    label = 'Unknown'
                    for key in series['metric']:
                        if key not in ['instance', 'job']:
                            label = series['metric'][key]
                            break

                ax.plot(times, values, label=label)

        ax.set(xlabel=xlabel, ylabel=ylabel, title=title)
        ax.grid()

        # Automatically adjust x-axis labels to prevent overlap
        fig.autofmt_xdate(rotation=45)

        # Save the plot without legend
        graph_output = BytesIO()
        plt.savefig(graph_output, format='png', bbox_inches='tight')
        graph_output.seek(0)

        # Now add the legend and save only the legend
        fig_legend = plt.figure(figsize=(width, 2))
        ax_legend = fig_legend.add_subplot(111)
        ax_legend.legend(*ax.get_legend_handles_labels(), loc='center', frameon=True)
        ax_legend.axis('off')

        legend_output = BytesIO()
        plt.savefig(legend_output, format='png', bbox_inches='tight')
        legend_output.seek(0)

        # Combine the graph and the legend
        graph_img = Image.open(graph_output)
        legend_img = Image.open(legend_output)
        combined_img = graph_img

        # Create a new image with a white background
        if legend:
            total_height = graph_img.height + legend_img.height
            combined_img = Image.new('RGB', (graph_img.width, total_height), "white")
            combined_img.paste(graph_img, (0, 0))
            combined_img.paste(legend_img, (int((graph_img.width/2)-(legend_img.width/2)), graph_img.height))

        # Save the combined image to BytesIO
        combined_output = BytesIO()
        combined_img.save(combined_output, format='png')
        combined_output.seek(0)

        return Response(combined_output, mimetype='image/png')
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}")
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
