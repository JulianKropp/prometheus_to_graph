# Prometheus Matplotlib Graph Server

A Flask-based application that generates graphs from Prometheus queries using Matplotlib. This server allows you to visualize Prometheus metrics by fetching data over a specified time range and rendering it as a graph image.

## Features

- Fetches data from a Prometheus server based on a provided query.
- Supports both relative and absolute time specifications for `start` and `end` parameters.
- Generates line graphs using Matplotlib.
- Customizable graph attributes such as title, labels, size, and legend.
- Returns the generated graph as a PNG image.

## Prerequisites

- Python 3.6 or higher
- Prometheus server accessible via HTTP

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/JulianKropp/prometheus_to_graph.git
   cd prometheus_to_graph
   ```

2. **Create a Virtual Environment (Optional but Recommended)**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies**

   ```bash
   pip3 install -r requirements.txt
   ```

## Usage

### Starting the Server

Run the Flask application using the following command:

```bash
python main.py
```

The server will start on `http://0.0.0.0:5000` by default.

### API Endpoint

- **`GET /graph`**

  Generates a graph based on the provided Prometheus query and parameters.

### Parameters

- **`server`** (optional)
  - The URL of the Prometheus server.
  - Default: `http://localhost:9090`

- **`query`** (required)
  - The Prometheus query to execute.
  - Example: `rate(http_requests_total[5m])`

- **`start`** (optional)
  - The start time for the data range.
  - Supports both relative time (e.g., `15min`, `2h`) and absolute time (`YYYY-MM-DD HH:MM:SS`).
  - Default: `1min`

- **`end`** (optional)
  - The end time for the data range.
  - Supports both relative time and absolute time.
  - Default: `now`

- **`title`** (optional)
  - The title of the graph.
  - Default: `Prometheus Query Result`

- **`xlabel`** (optional)
  - The label for the x-axis.
  - Default: `Time`

- **`ylabel`** (optional)
  - The label for the y-axis.
  - Default: `Value`

- **`width`** (optional)
  - The width of the graph in inches.
  - Default: `14`

- **`height`** (optional)
  - The height of the graph in inches.
  - Default: `8`

- **`legend`** (optional)
  - Whether to display the legend.
  - Accepts `true` or `false`.
  - Default: `true`

- **`label`** (optional)
  - The metric label to use for the legend entries.
  - If not specified, the application will attempt to use the first available label other than `instance` or `job`.

### Examples

#### Example 1: Relative Time Range

Generate a graph for the last 15 minutes.

```plaintext
GET /graph?query=rate(http_requests_total[1m])&start=15min&end=now&title=HTTP Requests&xlabel=Time&ylabel=Requests&legend=true
```

**URL Encoded:**

```plaintext
http://localhost:5000/graph?query=rate(http_requests_total[1m])&start=15min&end=now&title=HTTP%20Requests&xlabel=Time&ylabel=Requests&legend=true
```

#### Example 2: Absolute Time Range

Generate a graph from `2024-09-19 09:45:18` to `2024-09-19 10:00:18`.

```plaintext
GET /graph?query=rate(http_requests_total[1m])&start=2024-09-19%2009:45:18&end=2024-09-19%2010:00:18&title=HTTP Requests&xlabel=Time&ylabel=Requests&legend=true
```

**Note:** Spaces are URL encoded as `%20`.

#### Example 3: Custom Graph Size and Labels

```plaintext
GET /graph?query=up&width=10&height=6&xlabel=Timestamp&ylabel=Status&title=Service Status&legend=false
```

### Accessing the Graph

Open your web browser and navigate to the constructed URL to view the generated graph.

### Error Handling

- If no data is returned from Prometheus, you will receive a JSON error message.
- Ensure that your Prometheus server is accessible and the query is correct.
- Check that your time formats are valid and properly URL encoded.

## License

This project is licensed under the [MIT License](LICENSE).

---