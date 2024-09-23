import math
import statistics
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

def calculate_step(start_time, end_time, desired_points=100):
    total_seconds = (end_time - start_time).total_seconds()
    step_seconds = max(total_seconds / desired_points, 2)  # Minimum step of 2s
    return f'{int(step_seconds)}s'

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
        queries = query_string.split('|')
        label_args = label_arg_string.split('|') if label_arg_string else []

        start_time = parse_time_input(start_time_input)
        end_time = parse_time_input(end_time_input)

        if start_time > end_time:
            return jsonify({"error": "Start time must be before end time"}), 400

        prom = PrometheusConnect(url=prometheus_server, disable_ssl=True)

        step = calculate_step(start_time, end_time)

        # Create the graph with the specified figure size
        fig, ax = plt.subplots(figsize=(width, height))

        # Loop through each query and plot the results
        for i, query in enumerate(queries):
            label_arg = label_args[i] if len(label_args) > i else None

            data = prom.custom_query_range(
                query=query.strip(),
                start_time=start_time,
                end_time=end_time,
                step=step
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

                if len(times) < 2:
                    app.logger.warning(f"Insufficient data points for series: {series['metric']}")
                    continue

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

@app.route('/stats')
def stats():
    prometheus_server = request.args.get('server', 'http://localhost:9090')
    query_string = request.args.get('query')
    start_time_input = request.args.get('start', '1min')
    end_time_input = request.args.get('end', 'now')
    label_arg_string = request.args.get('label')

    if not query_string:
        return "Please provide a Prometheus query using the 'query' parameter."

    try:
        queries = query_string.split('|')
        label_args = label_arg_string.split('|') if label_arg_string else []
        print(f"Queries: {len(queries)}")

        start_time = parse_time_input(start_time_input)
        end_time = parse_time_input(end_time_input)

        if start_time > end_time:
            return jsonify({"error": "Start time must be before end time"}), 400

        prom = PrometheusConnect(url=prometheus_server, disable_ssl=True)

        step = calculate_step(start_time, end_time)

        # Initialisiere ein Dictionary, um Werte pro Label zu speichern
        label_data = {}

        # Schleife durch jede Abfrage
        for i, query in enumerate(queries):
            label_arg = label_args[i] if len(label_args) > i else None

            data = prom.custom_query_range(
                query=query.strip(),
                start_time=start_time,
                end_time=end_time,
                step=step
            )

            if not data:
                app.logger.error(f"No data returned from Prometheus for query: {query}")
                continue

            # Verarbeite die Daten
            for series in data:
                # Bestimme das Label
                if label_arg and label_arg in series['metric']:
                    label = series['metric'][label_arg]
                else:
                    if 'instance' in series['metric']:
                        label = series['metric']['instance']
                    elif 'job' in series['metric']:
                        label = series['metric']['job']
                    else:
                        label = 'Unknown'

                # Hole die Werte
                values = [float(value[1]) for value in series['values']]

                # Füge die Werte zum label_data hinzu
                if label not in label_data:
                    label_data[label] = []

                label_data[label].extend(values)


        # Berechne nun die Statistiken pro Label
        result = {}
        for label, values in label_data.items():
            if not values:
                continue

            # Filtern von NaN-Werten
            values = [v for v in values if not math.isnan(v)]

            # Überprüfen, ob nach dem Filtern noch Daten vorhanden sind
            if not values:
                app.logger.warning(f"No valid data points for label {label} after removing NaN values.")
                continue

            try:
                mean_value = statistics.mean(values)
                median_value = statistics.median(values)
                try:
                    mode_value = statistics.mode(values)
                except statistics.StatisticsError:
                    mode_value = None  # Kein eindeutiger Modus
                stdev_value = statistics.stdev(values) if len(values) > 1 else 0
                variance_value = statistics.variance(values) if len(values) > 1 else 0
                min_value = min(values)
                max_value = max(values)
                count = len(values)
                sum_value = sum(values)
                range_value = max_value - min_value
                avg_deviation = statistics.mean([abs(x - mean_value) for x in values])
                # Berechne die Quartile
                quartiles = statistics.quantiles(values, n=4, method='inclusive')
                percentile_25 = quartiles[0]
                percentile_50 = quartiles[1]
                percentile_75 = quartiles[2]
                iqr = percentile_75 - percentile_25  # Interquartilsabstand
            except Exception as e:
                app.logger.error(f"Error computing statistics for label {label}: {e}")
                continue

            result[label] = {
                'mean': mean_value,
                'median': median_value,
                'mode': mode_value,
                'stdev': stdev_value,
                'variance': variance_value,
                'min': min_value,
                'max': max_value,
                'count': count,
                'sum': sum_value,
                'range': range_value,
                'average_deviation': avg_deviation,
                'percentile_25': percentile_25,
                'percentile_50': percentile_50,
                'percentile_75': percentile_75,
                'iqr': iqr
            }

        return jsonify(result)

    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}")
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
