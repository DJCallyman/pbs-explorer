# PBS API Frontend

A basic HTML frontend for interacting with the PBS (Pharmaceutical Benefits Scheme) Public Data API.

## Overview

This frontend allows you to query various endpoints of the PBS API, which provides data on subsidized medicines in Australia. The API returns data in CSV format.

## Features

- Dropdown to select API endpoints
- Optional parameters: schedule_code and limit
- Displays response data in a scrollable text area

## Usage

1. Run the local server: `python3 server.py`
2. Open `http://localhost:8000` in a web browser.
3. Select an endpoint from the dropdown.
4. Optionally enter a schedule code (e.g., 3922) and/or limit the number of results (defaults to 100,000 if not specified).
5. Click "Fetch Data" to make the API call.
6. View the CSV response in the area below.

## API Details

- Base URL: `https://data-api.health.gov.au/pbs/api/v3/`
- Authentication: Uses a subscription key in the header.
- Response Format: CSV

## Troubleshooting

- **CORS Errors**: The server now proxies API requests to avoid CORS issues. If you still encounter problems, ensure the server is running and try a hard refresh.
- **API Key**: The subscription key is handled server-side for security.
- **Large Responses**: Some endpoints return large datasets. Use the limit parameter to restrict results.
- **Network Issues**: Ensure you have internet access and the API is available.

## Endpoints

See the dropdown in the app for all available endpoints. Key ones include:
- `/schedules`: Get PBS schedules
- `/items`: Get PBS items (medicines)
- `/restrictions`: Get prescribing restrictions

For full API documentation, refer to the official PBS API docs.