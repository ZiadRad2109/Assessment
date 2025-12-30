"""
TCP client
wraps the socket in a file object
so we can use readline() to read the data
"""

from PyQt6.QtWidgets import QTabWidget
import sys
import socket
import json
import time
from collections import deque
from PyQt6.QtCore import QRunnable, QThreadPool, QThread, pyqtSignal, QObject, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
)
import pyqtgraph as pg
from queue import Queue, Empty


# import configuration from config.json
with open("config.json", "r") as f:
    config = json.load(f)

HOST = config["host"]
PORT = config["port"]
sensor_list = config["sensors"]
number_of_sensors = len(sensor_list)
thread_communication_queue_list = list(
    Queue() for _ in range(number_of_sensors)
)  # thread communication queue


# 3amalna thread communication queue list by using the sensor id as the index 3ashan ne kol sensor mayakhodsh el haga beta3to we yermy el ba2y
class sensor_system:
    def __init__(self):
        self.sensor_list = sensor_list
        self.number_of_sensors = number_of_sensors

    class sensor_worker_signals(QObject):
        """Signals for sensor worker"""

        # the full packet received from the server
        global_data_received = pyqtSignal(str)

        # sensor data (id, name, data,timestamp)
        sensor_data_received = pyqtSignal(dict)

        # system status (ONLINE, OFFLINE)
        system_status_received = pyqtSignal(str)

        # alarm (status, alarm,alarm_message)
        alarm_received = pyqtSignal(dict)

    class SensorTask(QRunnable):
        # brief: sensor task that handles the sensor data
        # param sensor_config: sensor configuration
        def __init__(self, sensor_id: int):
            super().__init__()
            self.sensor_worker_signals = sensor_system.sensor_worker_signals()
            self.is_running = True
            self.sensor_id = sensor_id

        def run(self):
            try:
                while self.is_running:
                    raw_data = self.get_data(self.sensor_id - 1)
                    if raw_data:
                        data = json.loads(json.loads(raw_data))
                    else:
                        continue
                    # print(data)
                    if data:
                        sensor_id_rx = data["sensor_id"]
                        if sensor_id_rx == self.sensor_id:
                            # extract data from the global data
                            sensor_data = data["data"]
                            sensor_name = data["sensor_name"]

                            system_status = data["system_status"]
                            sensor_timestamp = data["timestamp"]
                            max_value = data["max_value"]
                            min_value = data["min_value"]
                            sensor_status = data["sensor_status"]
                            print(
                                f"sensor_id: {sensor_id_rx}, sensor_name: {sensor_name}, sensor_data: {sensor_data}, sensor_timestamp: {sensor_timestamp}, max_value: {max_value}, min_value: {min_value}, sensor_status: {sensor_status}"
                            )
                            if sensor_status == "OK":
                                # alarm handling
                                if (
                                    sensor_data >= min_value
                                    and sensor_data <= max_value
                                ):
                                    sensor_status = "OK"
                                    alarm = False
                                    alarm_message = ""
                                else:
                                    sensor_status = "ALARM"
                                    alarm = True
                                    if sensor_data < min_value:
                                        alarm_message = f"{sensor_name} reading is LOW"
                                    else:
                                        alarm_message = f"{sensor_name} reading is HIGH"
                                    alarm_timestamp = sensor_timestamp
                                    # self.sensor_worker_signals.alarm_received.emit(
                                    #     alarm, alarm_message, alarm_timestamp
                                    # )
                            else:
                                alarm = True
                                alarm_message = f"{sensor_name} is {sensor_status}"
                                alarm_timestamp = sensor_timestamp
                                # self.sensor_worker_signals.alarm_received.emit(
                                #     alarm, alarm_message, alarm_timestamp
                                # )
                                # extract sensor data from data by using the sensor_config["sensor_id"] as the key to the data

                        # check if the alarm is present
                        if not alarm:
                            # emit the sensor data
                            self.sensor_worker_signals.sensor_data_received.emit(data)
                        else:
                            # emit the alarm
                            self.sensor_worker_signals.alarm_received.emit(data)
                            self.sensor_worker_signals.sensor_data_received.emit(data)

            except Exception as e:
                print(f"SensorTask data error: {e}")
                self.is_running = False
                self.sensor_worker_signals.system_status_received.emit("OFFLINE")

        def get_data(self, index):
            try:
                # get data from the queue with timeout
                raw_data = thread_communication_queue_list[index].get(timeout=10.0)
                return raw_data
            except Empty:
                return None
            except Exception as e:
                print(f"thread_communication_queue error: {e}")
                return None

    class TCPTask(QRunnable):
        def __init__(self, sensor_config_list: list):
            super().__init__()
            self.sensor_worker_signals = sensor_system.sensor_worker_signals()
            self.is_running = True
            self.sensor_config_list = sensor_config_list

        def run(self):
            try:
                sket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                with sket:
                    sket.connect((HOST, PORT))
                    sket.settimeout(10.0)
                    socket_file = sket.makefile("r", encoding="utf-8")

                    while self.is_running:
                        try:
                            data_line = socket_file.readline()
                            if not data_line:
                                break
                            try:
                                global_data = json.loads(json.loads(data_line))
                                self.sensor_worker_signals.global_data_received.emit(
                                    data_line
                                )
                                sensor_id = global_data.get("sensor_id")
                                if sensor_id is not None:
                                    thread_communication_queue_list[sensor_id - 1].put(
                                        data_line
                                    )
                            except json.JSONDecodeError as e:
                                print(f"Error decoding JSON: {e}")
                        except socket.timeout:
                            continue
            except Exception as e:
                print(f"Error: {e}")
                self.is_running = False
                self.sensor_worker_signals.system_status_received.emit("OFFLINE")


# gui class
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Si-Ware Sensor Dashboard Simulator")
        self.setGeometry(100, 100, 1200, 800)

        # set up tabs
        self.tabs = QTabWidget()

        # create dashboard tab
        dashboard_tab = self.create_dashboard_tab()
        self.tabs.addTab(dashboard_tab, "Dashboard")

        # set up main widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
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

        # declare containers dictionaries to map the data to its respective sensor
        self.sensor_data = {}
        self.active_tasks = []
        self.graph_widgets = {}
        self.data_curves = {}
        self.alarms = {}
        self.time_axis_data = {}
        main_task = sensor_system.TCPTask(sensor_list)
        self.active_tasks.append(main_task)
        main_task.sensor_worker_signals.global_data_received.connect(self.refresh_gui)
        # main_task.sensor_worker_signals.alarm_received.connect(self.refresh_alarms)
        self.threadpool.start(main_task)
        for i in range(number_of_sensors):
            self.start_workers(i + 1)
        # update sensor data rows in the table widget
        # self.update_sensor_data_rows()

    def start_workers(self, sensor_id):
        self.is_running = True

        sensor_task = sensor_system.SensorTask(sensor_id)
        self.active_tasks.append(sensor_task)
        sensor_task.sensor_worker_signals.sensor_data_received.connect(self.refresh_gui)
        # sensor_task.sensor_worker_signals.alarm_received.connect(self.refresh_alarms)
        self.threadpool.start(sensor_task)

    def refresh_gui(self, data):
        # update table cells values
        if not isinstance(data, dict):
            data = json.loads(json.loads(data))
        sensor_id = data.get("sensor_id")
        if sensor_id:
            row = sensor_id - 1
            # ["Sensor ID", "Sensor Name", "Status", "Timestamp", "Data"]

        # Sensor ID
        self.table_widget.setItem(row, 0, QTableWidgetItem(str(sensor_id)))

        # Sensor Name
        self.table_widget.setItem(
            row, 1, QTableWidgetItem(str(data.get("sensor_name")))
        )

        # Status
        status = data.get("sensor_status", "UNKNOWN")
        self.table_widget.setItem(row, 2, QTableWidgetItem(status))

        # Timestamp
        self.table_widget.setItem(row, 3, QTableWidgetItem(str(data.get("timestamp"))))

        # Data
        self.table_widget.setItem(row, 4, QTableWidgetItem(str(data.get("data"))))
        self.table_widget.resizeColumnsToContents()

    def create_dashboard_tab(self):
        dashboard_tab = QWidget()
        dashboard_layout = QVBoxLayout()
        dashboard_tab.setLayout(dashboard_layout)

        # add system status label
        self.system_status_label = QLabel("System Status: OFFLINE")
        dashboard_layout.addWidget(
            self.system_status_label,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )

        # add table widget
        self.table_widget = QTableWidget()
        self.table_widget.setRowCount(6)
        self.table_widget.setColumnCount(5)
        self.table_widget.setHorizontalHeaderLabels(
            ["Sensor ID", "Sensor Name", "Status", "Timestamp", "Data"]
        )
        self.table_widget.resizeColumnsToContents()

        # Initialize rows with placeholders
        for i in range(number_of_sensors):
            # self.table_widget.insertRow(i)
            self.table_widget.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.table_widget.setItem(i, 1, QTableWidgetItem(f"Sensor {i + 1}"))
            self.table_widget.setItem(i, 2, QTableWidgetItem("WAITING"))
            self.table_widget.setItem(i, 3, QTableWidgetItem("-"))
            self.table_widget.setItem(i, 4, QTableWidgetItem("-"))

        dashboard_layout.addWidget(self.table_widget)
        return dashboard_tab

    def closeEvent(self, event):
        for task in self.active_tasks:
            task.is_running = False

        print("All workers stopped")
        self.threadpool.waitForDone()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())
    # try:
    #     client_run()
    # except KeyboardInterrupt:
    #     print("\nClient stopped by user")
    #     sys.exit(0)
