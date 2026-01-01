"""
GUI Module.

This module implements the main window of the application, including the
dashboard, alarms, and maintenance tabs. It handles the visualization of
sensor data and user interactions.
"""

from PyQt6.QtCore import QTimer, QThreadPool, Qt
from PyQt6.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QStackedLayout,
    QLineEdit,
    QFormLayout,
    QPushButton,
    QPlainTextEdit,
    QTabWidget,
    QHeaderView,
)
from PyQt6.QtGui import QColor, QFont
import pyqtgraph as pg
import sys
import json
import time
from collections import deque
from . import sensor_system

# Import shared globals from sensor_system
# Note: In a larger app these might be better in a separate config class
from .sensor_system import sensor_list, number_of_sensors, alarm_list, START_TIME


# gui class
class MainWindow(QMainWindow):
    """
    The main application window.

    This class manages the UI layout, updates data displays (tables, plots),
    and handles user input across Dashboard, Alarms, and Maintenance tabs.

    Calls:
        - `create_dashboard_tab`
        - `create_alarms_tab`
        - `create_maintenance_tab`
        - `sensor_system.TCPTask`
        - `start_workers`

    Called by:
        - `app.main.main`
    """

    def __init__(self):
        """
        Initialize the MainWindow.
        """
        super().__init__()
        # declare containers dictionaries to map the data to its respective sensor
        self.sensor_data = {}
        self.active_tasks = []
        self.graph_widgets = []
        self.data_curves = []
        self.alarms = {}
        self.time_axis_data = {}

        # set window title and size
        self.setWindowTitle("Si-Ware Sensor Dashboard Simulator")
        self.window_width = 1600
        self.window_height = 900
        self.setGeometry(100, 100, self.window_width, self.window_height)

        # set up tabs
        self.tabs = QTabWidget()

        # create dashboard tab
        dashboard_tab = self.create_dashboard_tab()
        self.tabs.addTab(dashboard_tab, "Dashboard")

        # create alarms tab
        alarms_tab = self.create_alarms_tab()
        self.tabs.addTab(alarms_tab, "Alarms")

        # create maintenance tab
        maintenance_tab = self.create_maintenance_tab()
        self.tabs.addTab(maintenance_tab, "Maintenance")

        # set up main widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        # set up main layout
        self.mainlayout = QVBoxLayout()
        central_widget.setLayout(self.mainlayout)

        # set up title label
        self.title_label = QLabel("Si-Ware Sensor Dashboard Simulator")
        self.title_label.setStyleSheet("font-size: 24px; font-weight: bold;")

        # add title label to main layout and set alignment to center and top
        self.mainlayout.addWidget(
            self.title_label,
            alignment=Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop,
        )

        # add tabs to main layout
        self.mainlayout.addWidget(self.tabs)

        # create a thread pool to handle the sensor data threads
        self.threadpool = QThreadPool.globalInstance()

        # Deques for plotting: (time_seconds, value)
        self.plot_data_deques = [deque(maxlen=20) for _ in range(number_of_sensors)]

        # create the main task (tcp connection and data parsing)
        main_task = sensor_system.TCPTask(sensor_list)

        # append the task to the list of active tasks (to be monitored later)
        self.active_tasks.append(main_task)

        # system status update callback
        main_task.sensor_worker_signals.system_status_received.connect(
            self.update_system_status
        )

        # system stop callback
        main_task.sensor_worker_signals.system_stop.connect(self.stop_workers)

        # global data received callback to refresh the log in the maintenance tab
        main_task.sensor_worker_signals.global_data_received.connect(self.refresh_log)

        # start the main task
        self.threadpool.start(main_task)

        # start the worker threads (sensor tasks)
        self.start_workers()

    # this tab's widgets should only be accessed after prompting the user for a username and password and verifying the correct credentials
    # the credentials are: username = admin, password = admin
    def create_maintenance_tab(self):
        """
        Create the maintenance tab widget.

        Returns:
            QWidget: The constructed maintenance tab.

        Calls:
            - `check_credentials` (connected to login button)
            - `restart_workers` (connected to restart button)
            - `stop_workers` (connected to stop button)
            - `clear_logs` (connected to clear logs button)
            - `clear_alarms` (connected to clear alarms button)

        Called by:
            - `__init__`
        """
        # create the maintenance main widget using a stacked layout (for login and maintenance content)
        maintenance_tab = QWidget()
        self.maintenance_stacked_layout = QStackedLayout()
        maintenance_tab.setLayout(self.maintenance_stacked_layout)

        # create the login page widget and layout
        login_page = QWidget()
        login_page_layout = QVBoxLayout(login_page)

        # create the login widget using a form layout
        login_widget = QWidget()
        login_widget.setFixedWidth(300)
        login_layout = QFormLayout(login_widget)

        # create the username and password inputs
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()

        # password mode echo ( to cover the password while typing it )
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        # add the username and password inputs to the login  form layout
        login_layout.addRow("Username:", self.username_input)
        login_layout.addRow("Password:", self.password_input)

        # create the login error label
        self.login_error_label = QLabel("")
        self.login_error_label.setStyleSheet("color: red;")
        login_layout.addRow(self.login_error_label)

        # create the login button and connect it to the check_credentials method
        login_button = QPushButton("Login")
        login_button.clicked.connect(self.check_credentials)
        login_layout.addRow(login_button)

        # add the login widget to the login page layout and center it
        login_page_layout.addWidget(
            login_widget, alignment=Qt.AlignmentFlag.AlignCenter
        )
        self.maintenance_stacked_layout.addWidget(login_page)

        # create the maintenance content page widget and layout
        maintenance_content_widget = QWidget()
        maintenance_layout = QVBoxLayout()
        maintenance_content_widget.setLayout(maintenance_layout)

        # add title label to maintenance layout and set alignment to center and top
        maintenance_title_label = QLabel("Maintenance")
        maintenance_title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        maintenance_layout.addWidget(
            maintenance_title_label,
            alignment=Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop,
        )

        # create the log widget using plain text edit widget so that it mimics the terminal and add it to the maintenance layout
        self.log_widget = QPlainTextEdit()
        self.log_widget.setReadOnly(True)
        maintenance_layout.addWidget(self.log_widget)

        # create the maintenance buttons layout and add it to the maintenance layout
        maintenance_buttons_layout = QHBoxLayout()
        maintenance_layout.addLayout(maintenance_buttons_layout)

        # create the restart button to restart the sensor tasks
        self.restart_button = QPushButton("Restart")
        self.restart_button.setStyleSheet("background-color: green; color: black;")
        self.restart_button.clicked.connect(self.restart_workers)
        maintenance_buttons_layout.addWidget(self.restart_button)

        # create the stop button to stop the sensor tasks but maintain the connection
        self.stop_button = QPushButton("Stop")
        self.stop_button.setStyleSheet("background-color: red; color: black;")
        self.stop_button.clicked.connect(self.stop_workers)
        maintenance_buttons_layout.addWidget(self.stop_button)

        # create the clear logs button to clear the log widget
        self.clear_logs_button = QPushButton("Clear Logs")
        self.clear_logs_button.setStyleSheet("background-color: yellow; color: black;")
        self.clear_logs_button.clicked.connect(self.clear_logs)
        maintenance_buttons_layout.addWidget(self.clear_logs_button)

        # create the clear alarms button to clear the alarms
        self.clear_alarms_button = QPushButton("Clear Alarms")
        self.clear_alarms_button.setStyleSheet(
            "background-color: orange; color: black;"
        )
        self.clear_alarms_button.clicked.connect(self.clear_alarms)
        maintenance_buttons_layout.addWidget(self.clear_alarms_button)

        # add the maintenance content widget to the maintenance stacked layout
        self.maintenance_stacked_layout.addWidget(maintenance_content_widget)

        return maintenance_tab

    def check_credentials(self):
        """
        Verify the username and password entered by the user.

        Called by:
            - Login button (signal)
        """
        # get the username and password from the inputs
        username = self.username_input.text()
        password = self.password_input.text()

        # check if the credentials are correct
        if username == "admin" and password == "admin":
            self.maintenance_stacked_layout.setCurrentIndex(1)
            self.login_error_label.setText("")
            # Clear credentials for security
            self.username_input.clear()
            self.password_input.clear()
        else:
            # show error message if wrong credentials are entered
            self.login_error_label.setText("Wrong credentials")

    def clear_alarms(self):
        """
        Clear the alarms table and the global alarm list.

        Called by:
            - Clear Alarms button (signal)
        """
        # clear the alarms table and alarms list and restore the table to its original state
        self.log_widget.appendPlainText("Clearing alarms ... ")
        self.alarms_table.clearContents()
        self.alarms_table.setRowCount(0)
        alarm_list.clear()

    def clear_logs(self):
        """
        Clear the maintenance log widget.

        Called by:
            - Clear Logs button (signal)
        """
        # clear the log terminal
        self.log_widget.clear()

    def refresh_log(self, data):
        """
        Append new data to the log widget.

        Args:
            data: The data string or object to log.

        Called by:
            - `sensor_system.TCPTask` (via signal `global_data_received`)
        """
        # append the data to the log terminal
        self.log_widget.appendPlainText(str(data))

    def stop_workers(self, data=""):
        """
        Stop the sensor workers.

        Args:
            data (str, optional): Message prompting the stop. Defaults to "".

        Called by:
            - Stop Button (signal)
            - `sensor_system.TCPTask` (via signal `system_stop`)
            - `restart_workers`
        """
        # stop the sensor tasks
        print("STOP received ... ")
        for task in self.active_tasks:  # skip the first task as it is the main task
            if task is not self.active_tasks[0]:
                task.is_running = False
            else:
                # stop the data collection but keep the main task running
                task.stop_pressed_flag = True
            # update the system status label
            self.system_status_label.setText("System Status: OFFLINE")
            self.system_status_label.setStyleSheet("color: red;")
        if data == "STOP":
            self.log_widget.appendPlainText(
                "Server terminated the connection, alf salama :)"
            )
            print("Server terminated the connection, alf salama :)")
            time.sleep(1)
            sys.exit(0)

    def update_system_status(self, system_status):
        """
        Update the system status label.

        Args:
            system_status (str): New status (e.g., 'ONLINE', 'OFFLINE').

        Called by:
            - `sensor_system.TCPTask` (via signal `system_status_received`)
        """
        # update the system status label
        self.system_status_label.setText(f"System Status: {system_status}")
        # set the label color based on the system status
        if system_status == "ONLINE":
            self.system_status_label.setStyleSheet("color: green;")
        else:
            self.system_status_label.setStyleSheet("color: red;")

    def restart_workers(self):
        """
        Restart the sensor workers.

        Calls:
            - `stop_workers`
            - `start_workers` (via QTimer)

        Called by:
            - Restart Button (signal)
        """
        # restart the sensor tasks
        self.log_widget.appendPlainText("Restarting workers ... ")

        # stop the sensor tasks
        self.stop_workers()

        # update the system status label
        self.system_status_label.setText("System Status: ONLINE")
        self.system_status_label.setStyleSheet("color: green;")

        # start the sensor tasks after 3 seconds
        QTimer.singleShot(3000, self.start_workers)

    def start_workers(self):
        """
        Start the sensor workers and connect signals.

        Calls:
            - `sensor_system.SensorTask`

        Called by:
            - `__init__`
            - `restart_workers` (delayed)
        """
        # start the sensor tasks
        self.is_running = True

        # restart the data collection of the main task
        self.active_tasks[0].stop_pressed_flag = False
        # for each sensor task, create a new task and start it and connect its signals to their respective callbacks
        for sensor_id in range(number_of_sensors):
            sensor_task = sensor_system.SensorTask(sensor_id + 1)
            # add the sensor task to the active tasks list (for monitoring purposes)
            self.active_tasks.append(sensor_task)
            sensor_task.sensor_worker_signals.sensor_data_received.connect(
                self.refresh_gui
            )
            sensor_task.sensor_worker_signals.plot_data_updated.connect(
                self.update_plot
            )
            sensor_task.sensor_worker_signals.alarm_received.connect(
                self.refresh_alarms
            )
            print(f"Sensor Task {sensor_id + 1} has started")
            self.log_widget.appendPlainText(f"Sensor Task {sensor_id + 1} has started")

            # start the sensor task
            self.threadpool.start(sensor_task)

    def update_plot(self, data):
        """
        Update the plot with new sensor data.

        Args:
            data (dict): Data containing sensor_id and data value.

        Called by:
            - `sensor_system.SensorTask` (via signal `plot_data_updated`)
        """
        # update plot
        sensor_id = data.get("sensor_id")

        # timestamp = data.get("timestamp")
        value = data.get("data")

        # get the relative time, by subtracting the start time from the current time
        # Access START_TIME from sensor_system module
        relative_time = time.time() - sensor_system.START_TIME
        # deques have a window of 20 data points
        # Use self.plot_data_deques instead of global
        self.plot_data_deques[sensor_id - 1].append((relative_time, value))
        # get the x and y values from the deque
        data_x = [x for x, _ in self.plot_data_deques[sensor_id - 1]]
        data_y = [y for _, y in self.plot_data_deques[sensor_id - 1]]
        # update the plot
        self.data_curves[sensor_id - 1].setData(data_x, data_y)

    def refresh_alarms(self, data):
        """
        Add a new alarm to the alarms table.

        Args:
            data (dict or str): Alarm data.

        Called by:
            - `sensor_system.SensorTask` (via signal `alarm_received`)
        """
        # update table cells values
        self.alarms_table.setRowCount(len(alarm_list))
        # if the data is a string, convert it to a dictionary
        if not isinstance(data, dict):
            data = json.loads(
                json.loads(data)
            )  # for some reason the data dictionary is a string wrapped in a string
        sensor_id = data.get("sensor_id")
        alarm_type = data.get("alarm_type")
        timestamp = data.get("timestamp")
        message = data.get("message")
        sensor_name = data.get("sensor_name")
        if sensor_id:
            # get the row index
            row = len(alarm_list) - 1
            # ["Sensor ID", "Sensor Name", "Alarm Type", "Timestamp", "Message"]
            self.alarms_table.setItem(row, 0, QTableWidgetItem(str(sensor_id)))
            self.alarms_table.setItem(row, 1, QTableWidgetItem(str(sensor_name)))
            self.alarms_table.setItem(row, 2, QTableWidgetItem(str(alarm_type)))
            self.alarms_table.setItem(row, 3, QTableWidgetItem(str(timestamp)))
            self.alarms_table.setItem(row, 4, QTableWidgetItem(str(message)))

            # set the background color of the row
            color_map = {
                "LOW": QColor(75, 0, 130),
                "HIGH": QColor(165, 0, 0),
                "FAULTY": QColor(0, 102, 204),
            }
            bg_color = color_map.get(alarm_type, QColor(75, 0, 130))
            # set the background color of the row
            for i in range(self.alarms_table.columnCount()):
                item = self.alarms_table.item(row, i)
                if item:
                    item.setBackground(bg_color)

    def refresh_gui(self, data):
        """
        Update the dashboard table with new sensor status and value.

        Args:
            data (dict or str): Sensor data.

        Called by:
            - `sensor_system.SensorTask` (via signal `sensor_data_received`)
        """
        # update table cells values
        if not isinstance(data, dict):
            # for some reason the data dictionary is a string wrapped in a string
            data = json.loads(json.loads(data))
        # get the row index
        sensor_id = data.get("sensor_id")

        if sensor_id:
            row = sensor_id - 1

        # Sensor ID
        self.table_widget.setItem(row, 0, QTableWidgetItem(str(sensor_id)))

        # Sensor Name
        self.table_widget.setItem(
            row, 1, QTableWidgetItem(str(data.get("sensor_name")))
        )

        # Status
        # set the background color of the status cell based on the status
        status = data.get("sensor_status", "UNKNOWN")
        self.table_widget.setItem(row, 2, QTableWidgetItem(status))

        # set the background color of the row depending on the status
        color_map = {
            "OK": QColor(0, 100, 0),
            "UNKNOWN": QColor(75, 0, 130),
            "FAULTY": QColor(255, 140, 0),
            "ALARM": QColor(139, 0, 0),
        }
        bg_color = color_map.get(status)
        for i in range(self.table_widget.columnCount()):
            item = self.table_widget.item(row, i)
            if item:
                item.setBackground(bg_color)

        # Timestamp
        self.table_widget.setItem(row, 3, QTableWidgetItem(str(data.get("timestamp"))))

        # Data
        self.table_widget.setItem(row, 4, QTableWidgetItem(str(data.get("data"))))
        self.table_widget.item(row, 4).setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def create_alarms_tab(self):
        """
        Create the alarms tab widget.

        Returns:
            QWidget: The constructed alarms tab.

        Called by:
            - `__init__`
        """
        # alarms tab
        alarms_tab = QWidget()
        alarms_layout = QVBoxLayout()
        alarms_tab.setLayout(alarms_layout)

        # alarms label
        alarms_label = QLabel("Alarms")
        alarms_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        alarms_label.setStyleSheet("color: red;font-size: 20px;")
        alarms_layout.addWidget(alarms_label)

        # alarms table
        self.alarms_table = QTableWidget()
        # the row count should be dynamic based on the number of alarms in the alarm list
        self.alarms_table.setRowCount(len(alarm_list))
        self.alarms_table.setColumnCount(5)
        self.alarms_table.setHorizontalHeaderLabels(
            ["Sensor ID", "Sensor Name", "Alarm Type", "Timestamp", "Message"]
        )
        # resize columns
        header = self.alarms_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        alarms_layout.addWidget(self.alarms_table)

        return alarms_tab

    def create_dashboard_tab(self):
        """
        Create the dashboard tab widget.

        Returns:
            QWidget: The constructed dashboard tab.

        Called by:
            - `__init__`
        """
        dashboard_tab = QWidget()
        dashboard_layout = QVBoxLayout()
        dashboard_tab.setLayout(dashboard_layout)

        # add system status label
        self.system_status_label = QLabel("System Status: OFFLINE")
        dashboard_layout.addWidget(
            self.system_status_label,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )
        self.system_status_label.setStyleSheet("color: red;font-size: 20px;")

        # add table widget
        self.table_widget = QTableWidget()
        self.table_widget.setRowCount(number_of_sensors)
        self.table_widget.setColumnCount(5)
        self.table_widget.setHorizontalHeaderLabels(
            ["Sensor ID", "Sensor Name", "Status", "Timestamp", "Data"]
        )

        # Set font for the table
        font = QFont()
        font.setPointSize(14)
        self.table_widget.setFont(font)

        # header is auto-fit except for the data column which is stretched to the remaining space
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Name
        header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )  # Status
        header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )  # Timestamp
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Data

        # Fit rows to content (font size)
        self.table_widget.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        # Initialize rows with placeholders
        for i in range(number_of_sensors):
            # self.table_widget.insertRow(i)
            self.table_widget.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.table_widget.setItem(i, 1, QTableWidgetItem(f"Sensor {i + 1}"))
            self.table_widget.setItem(i, 2, QTableWidgetItem("UNKNOWN"))
            self.table_widget.setItem(i, 3, QTableWidgetItem("-"))
            self.table_widget.setItem(i, 4, QTableWidgetItem("-"))

        dashboard_layout.addWidget(self.table_widget)

        # add plots distributed evenly accross the width of the screen
        # and number of plots is equal to the number of sensors
        plot_layout = QHBoxLayout()
        dashboard_layout.addLayout(plot_layout)
        for i in range(number_of_sensors):
            # loop through the sensors and add a plot for each sensor
            # each plot has a title, left and bottom labels, grid, and a curve
            # each plot also has a color
            plot_colors = ["r", "g", "c", "y", "w"][i % 5]
            # Use sensor_list from sensor_system
            plot_widget = pg.PlotWidget(title=f"{sensor_list[i]['sensor_name']}")
            plot_widget.setLabel("left", "Data")
            plot_widget.setLabel("bottom", "Time")
            plot_widget.showGrid(x=True, y=True)
            plot_layout.addWidget(plot_widget)
            self.graph_widgets.append(plot_widget)
            self.data_curves.append(plot_widget.plot(pen=plot_colors))

        return dashboard_tab

    def closeEvent(self, event):
        """
        Handle the close event.

        Stops all workers and threads before closing the application.

        Called by:
            - PyQt Event Loop (on window close)
        """
        # clean close the application
        for task in self.active_tasks:
            task.is_running = False
        self.threadpool.waitForDone()
        print("All workers stopped")
        event.accept()
