# Si-Ware Sensor Dashboard Simulator

## 1. Installation

To install the required packages, run the following command in your terminal:

```bash
pip install -r requirements.txt
```

## 2. Running the Program

To run the application, you need to start the sensor simulator first and then the client application within 10 seconds.

1.  **Start the Sensor Simulator**:
    ```bash
    python sensor_sim.py
    ```

2.  **Start the Client Application** (within 10 seconds of starting the simulator):
    ```bash
    python run.py
    ```

## 3. Branches

This repository contains the following branches:

-   **`main`**: The stable, refactored version of the application (modularized structure).
-   **`devel`**: Used for development; contains the original, unrefactored code.
-   **`test`**: Used for unit testing implementation.

## 4. TCP Protocol Usage

The communication between the `sensor_sim.py` (server) and the client follows this protocol:

1.  **Data Generation**: The simulator generates sensor data (ID, name, value, status, timestamp, etc.) and packages it into a dictionary `data_payload`.
2.  **Serialization (Simulator)**:
    -   The `data_payload` dictionary is converted to a JSON string.
    -   This string is then placed into a message queue.
    -   The server thread retrieves this string and **serializes it again** into a JSON string (resulting in a double-serialized JSON string).
    -   A newline character `\n` is appended as a delimiter.
    -   The message is encoded in `utf-8` and sent over the TCP socket.
3.  **Parsing (Client)**:
    -   The client connects to the server and reads data line-by-line (`readline()`).
    -   The received line is decoded.
    -   **Double De-serialization**: Due to the double serialization on the server side, the client performs `json.loads()` twice:
        1.  First `json.loads()` parses the outer JSON string, returning the inner JSON string.
        2.  Second `json.loads()` parses the inner JSON string, returning the actual data dictionary.
    -   The data is then dispatched to the specific sensor's processing queue.

## 5. File Structure

-   **`run.py`**: The entry point for the client application.
-   **`sensor_sim.py`**: Simulates the sensor hardware and acts as the TCP server.
-   **`config.json`**: Configuration file defining sensor parameters (host, port, sensor list, limits).
-   **`requirements.txt`**: List of Python dependencies.
-   **`app/`**:
    -   **`main.py`**: Helper module to initialize the Qt Application.
    -   **`gui.py`**: Handles the Graphical User Interface (Dashboard, Alarms, Maintenance tabs) using PyQt6.
    -   **`sensor_system.py`**: Manages the backend logic, including TCP communication, data parsing, and threading for sensor tasks.
-   **`docs/`**: Contains the generated documentation.

## 6. Documentation

For detailed code documentation, including function call graphs and API references, please refer to the generated HTML file:

[Open Documentation](docs/app.html)
