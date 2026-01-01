"""
Sensor System Module.

This module handles the TCP communication with the sensor server,
processes incoming data, and manages sensor tasks. It also holds shared
global state like configuration and alarm lists.
"""

import socket
import json
import time
from collections import deque
from queue import Queue, Empty
from PyQt6.QtCore import QRunnable, QObject, pyqtSignal
from plyer import notification

# import configuration from config.json
with open("config.json", "r") as f:
    config = json.load(f)

HOST = config["host"]
PORT = config["port"]
START_TIME = time.time()
# sensor list and number of sensors are used to create the threads and the GUI for each sensor
sensor_list = config["sensors"]
number_of_sensors = len(sensor_list)

# thread communication queue list is used to pass data between the threads
# there's a queue for each sensor task
thread_communication_queue_list = []
for _ in range(number_of_sensors):
    thread_communication_queue_list.append(Queue())

# alarm list and alarm log file
alarm_list = []


class sensor_worker_signals(QObject):
    """
    Signals for sensor worker.

    Attributes:
        global_data_received (pyqtSignal): Signal emitting the full packet received from server.
        sensor_data_received (pyqtSignal): Signal emitting processed sensor data (id, name, data, timestamp).
        plot_data_updated (pyqtSignal): Signal emitting plot data (time, data).
        system_status_received (pyqtSignal): Signal emitting system status (ONLINE, OFFLINE).
        alarm_received (pyqtSignal): Signal emitting alarm details (status, alarm, alarm_message).
        system_stop (pyqtSignal): Signal emitting stop command.
    """

    # the full packet received from the server
    global_data_received = pyqtSignal(str)

    # sensor data (id, name, data,timestamp)
    sensor_data_received = pyqtSignal(dict)

    # plot data (time, data)
    plot_data_updated = pyqtSignal(dict)

    # system status (ONLINE, OFFLINE)
    system_status_received = pyqtSignal(str)

    # alarm (status, alarm,alarm_message)
    alarm_received = pyqtSignal(dict)

    system_stop = pyqtSignal(str)


class SensorTask(QRunnable):
    """
    Sensor task that handles the sensor data processing.

    This class runs in a separate thread, retrieves data from the queue,
    processes it, checks for alarms, and emits signals to update the UI.

    Calls:
        - `get_data`
        - Emits `sensor_worker_signals`

    Called by:
        - `app.gui.MainWindow.start_workers`
    """

    # brief: sensor task that handles the sensor data
    # param sensor_config: sensor configuration
    def __init__(self, sensor_id: int):
        """
        Initialize the SensorTask.

        Args:
            sensor_id (int): The ID of the sensor this task manages.
        """
        super().__init__()
        # declare the signals
        self.sensor_worker_signals = sensor_worker_signals()

        # set running flag and sensor id
        self.is_running = True
        self.sensor_id = sensor_id

    def run(self):
        """
        Main execution method for the sensor task.

        continuously reads data from the queue, processes it, detects alarms,
        and emits signals.

        Calls:
            - `get_data`
            - `sensor_worker_signals.sensor_data_received.emit`
            - `sensor_worker_signals.plot_data_updated.emit`
            - `sensor_worker_signals.alarm_received.emit`
            - `sensor_worker_signals.system_status_received.emit` (on error)
        """
        try:
            # while the sensor task is running receive data from the server
            while self.is_running:
                # read data from the server
                raw_data = self.get_data(self.sensor_id - 1)
                if raw_data:
                    # for some reason the data is received as a string of a string
                    data = json.loads(json.loads(raw_data))
                else:
                    continue
                # print(data)
                # create a dictionary from the data
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
                        # print(
                        #     f"sensor_id: {sensor_id_rx}, sensor_name: {sensor_name}, sensor_data: {sensor_data}, sensor_timestamp: {sensor_timestamp}, max_value: {max_value}, min_value: {min_value}, sensor_status: {sensor_status}"
                        # )
                        # check if the sensor is online or faulty
                        if sensor_status == "OK":
                            # alarm handling
                            if sensor_data >= min_value and sensor_data <= max_value:
                                sensor_status = "OK"
                                alarm = False
                                alarm_message = ""
                                alarm_timestamp = ""
                                alarm_type = ""
                            else:
                                sensor_status = "ALARM"
                                alarm = True
                                # define alarm messages
                                if sensor_data < min_value:
                                    alarm_message = f"{sensor_name} reading is LOW"
                                    alarm_type = "LOW"
                                else:
                                    alarm_message = f"{sensor_name} reading is HIGH"
                                    alarm_type = "HIGH"
                                alarm_timestamp = sensor_timestamp
                                # self.sensor_worker_signals.alarm_received.emit(
                                #     alarm, alarm_message, alarm_timestamp
                                # )
                        else:
                            alarm = True
                            alarm_type = "FAULTY"
                            alarm_message = f"{sensor_name} is {sensor_status}"
                            alarm_timestamp = sensor_timestamp
                            # self.sensor_worker_signals.alarm_received.emit(
                            #     alarm, alarm_message, alarm_timestamp
                            # )
                            # extract sensor data from data by using the sensor_config["sensor_id"] as the key to the data
                    data_dict = {
                        "sensor_id": sensor_id_rx,
                        "sensor_name": sensor_name,
                        "data": sensor_data,
                        "timestamp": sensor_timestamp,
                        "max_value": max_value,
                        "min_value": min_value,
                        "sensor_status": sensor_status,
                        "alarm": alarm,
                        "alarm_message": alarm_message,
                        "alarm_timestamp": alarm_timestamp,
                    }

                    if alarm:
                        # emit the sensor data
                        # emit the alarm
                        alarm_data = {
                            "sensor_id": sensor_id_rx,
                            "sensor_name": sensor_name,
                            "alarm_type": alarm_type,
                            "timestamp": alarm_timestamp,
                            "message": alarm_message,
                            "data": sensor_data,
                            "max_value": max_value,
                            "min_value": min_value,
                        }
                        # windows notification popup
                        notification.notify(
                            title=f"{sensor_name} SENSOR ALARM",
                            message=alarm_message,
                            app_name="Si-Ware Sensor System",
                            timeout=1,
                        )
                        self.sensor_worker_signals.alarm_received.emit(alarm_data)
                        # add the alarm to the alarm list
                        alarm_list.append(alarm_data)
                    # emit the sensor data update signal
                    self.sensor_worker_signals.sensor_data_received.emit(data_dict)
                    # emit the plot data update signal
                    self.sensor_worker_signals.plot_data_updated.emit(
                        {
                            "sensor_id": sensor_id_rx,
                            "data": sensor_data,
                        }
                    )
        except Exception as e:
            print(f"SensorTask data error: {e}")
            self.is_running = False
            self.sensor_worker_signals.system_status_received.emit("OFFLINE")

    def get_data(self, index):
        """
        Retrieve data from the global thread communication queue.

        Args:
            index (int): Index of the queue to read from.

        Returns:
            str or None: The raw data string if available, else None.

        Called by:
            - `run`
        """
        try:
            # get data from the queue with timeout
            raw_data = thread_communication_queue_list[index].get(timeout=1.0)
            return raw_data
        except Empty:
            return None
        except Exception as e:
            print(f"thread_communication_queue error: {e}")
            return None


class TCPTask(QRunnable):
    """
    Task for managing the TCP connection to the server.

    Handles connection establishment, receiving data line-by-line,
    parse global data, and dispatch to specific sensor queues.

    Calls:
        - `socket` methods
        - Emits `sensor_worker_signals`

    Called by:
        - `app.gui.MainWindow.__init__`
    """

    def __init__(self, sensor_config_list: list):
        """
        Initialize the TCPTask.

        Args:
            sensor_config_list (list): List of sensor configurations.
        """
        super().__init__()
        # initialize the sensor worker signals
        self.sensor_worker_signals = sensor_worker_signals()
        # initialize the running flag
        self.is_running = True
        # initialize the sensor config list
        self.sensor_config_list = sensor_config_list
        # initialize the stop pressed flag
        self.stop_pressed_flag = False

    def run(self):
        """
        Main execution method for the TCP task.

        Connects to the server, loops to receive data, and handles
        connection status updates.

        Calls:
            - `socket.connect`
            - `sensor_worker_signals.system_status_received.emit`
            - `sensor_worker_signals.global_data_received.emit`
            - `sensor_worker_signals.system_stop.emit`
        """
        try:
            # emit the system status signal
            self.sensor_worker_signals.system_status_received.emit("ONLINE")
            # create a socket
            self.sket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            with self.sket:
                # connect to the server
                self.sket.connect((HOST, PORT))
                # set the start time of the program to be used when plotting
                global START_TIME
                START_TIME = time.time()
                # set the socket timeout
                self.sket.settimeout(10.0)
                # create a file object
                socket_file = self.sket.makefile("r", encoding="utf-8")

                while self.is_running:
                    try:
                        if self.stop_pressed_flag:
                            # skip the rest of the loop (keep connection alive without reading data)
                            continue
                        # read the data line by line as a file (data delimited by \n)
                        data_line = socket_file.readline()
                        if not data_line:
                            break
                        # if the data line is STOP, break the loop
                        if data_line == "STOP":
                            self.is_running = False
                            # emit the system stop signal
                            self.sensor_worker_signals.system_stop.emit("STOP")
                            # close the socket
                            self.sket.close()
                            break
                        try:
                            # parse the data line, for some reason the data is presented as a string of a string of a dictionary
                            global_data = json.loads(json.loads(data_line))
                            # extract the sensor id
                            sensor_id = global_data.get("sensor_id")
                            # emit the global data received signal (to be used for logs)
                            self.sensor_worker_signals.global_data_received.emit(
                                json.loads(data_line)
                            )
                            # if the sensor id is not None, put the data in the queue for the sensor thread to process
                            if sensor_id is not None:
                                thread_communication_queue_list[sensor_id - 1].put(
                                    data_line
                                )
                        except json.JSONDecodeError as e:
                            print(f"Error decoding JSON: {e}")
                            self.sensor_worker_signals.system_status_received.emit(
                                "OFFLINE"
                            )
                    except socket.timeout:
                        self.sensor_worker_signals.system_status_received.emit(
                            "OFFLINE"
                        )
                        continue
        except Exception as e:
            print(f"Error: {e}")
            self.is_running = False
            self.sensor_worker_signals.system_status_received.emit("OFFLINE")
