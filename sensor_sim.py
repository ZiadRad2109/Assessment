"""
this script simulates sensors that send data to a server
the server is running in the same machine.
1) it reads configuration from 'config.json'
2) spawns worker threads to simulate each sensor independently
3) generates Gaussian-distributed data with alarm detection for values outside specified ranges.
4) messages are queued, serialized, and sent to the server.
5) handles system shutdown and cleanup.
"""

import socket
import json
import time
import random
import sys
from datetime import datetime
import threading
import queue

# import configuration from config.json
with open("config.json", "r") as f:
    config = json.load(f)

HOST = config["host"]
PORT = config["port"]
sensor_list = config["sensors"]
number_of_sensors = len(sensor_list)


class sensor_simulator:
    def __init__(self, num_sensors=number_of_sensors):
        # initialize the sensor simulator

        self.num_sensors = num_sensors
        self.system_running_flag = True
        self.worker_running_flag = False
        self.message_pipe = queue.Queue()  # queue is used to store the messages

    def sensor_worker(self, sensor_cfg: dict):
        sensor_id = sensor_cfg["sensor_id"]
        sensor_name = sensor_cfg["sensor_name"]
        data_rate = sensor_cfg["data_rate"]
        minimum_value = sensor_cfg["minimum_value"]
        maximum_value = sensor_cfg["maximum_value"]
        mean = (minimum_value + maximum_value) / 2
        interval = 1.0 / data_rate

        while self.worker_running_flag:
            system_status = "ONLINE"
            try:
                # generate a random reading around the minimum and maximum values
                sensor_reading = round(
                    random.gauss(mean, (maximum_value - minimum_value) / 2), 2
                )

                # generate a random number with gaussian distribution to simulate the sensor being faulty every now and then
                sensor_faulty = round(random.gauss(1, 1), 2)
                if sensor_faulty < 0.1:
                    sensor_status = "FAULTY"
                else:
                    sensor_status = "OK"

                # data payload
                data_payload = {
                    "system_status": system_status,
                    "sensor_id": sensor_id,
                    "sensor_name": sensor_name,
                    "data": sensor_reading,
                    "min_value": minimum_value,
                    "max_value": maximum_value,
                    "sensor_status": sensor_status,
                    "timestamp": datetime.now().strftime("%m/%d/%Y at %H:%M:%S"),
                }

                # serialize the data payload
                message = json.dumps(data_payload) + "\n"
                self.message_pipe.put(message)  # put the message in the queue

                # @todo we can account for the processing time for a more accurate data rate
                time.sleep(interval)  # sleep for the interval
            except Exception as e:
                print(f"Error: {e}")
                break

    def start_workers(self, sensor: dict):
        # start the workers
        self.system_running_flag = True
        self.worker_running_flag = True
        # loop through the sensor configuration list and create a thread for each sensor
        self.worker = threading.Thread(
            target=self.sensor_worker,
            args=(sensor,),
            name=f"{sensor['sensor_name']}_{sensor['sensor_id']}",
            daemon=True,
        )
        print(
            f"{sensor['sensor_name']}({sensor['sensor_id']}) has started with a data rate of {sensor['data_rate']} Hz"
        )
        self.worker.start()
        return self.worker

    def stop_workers(self):
        # stop the workers
        self.system_running_flag = False
        self.worker_running_flag = False
        # wait for the workers to finish
        self.worker.join()
        # put a stop message in the queue to signal the workers to stop
        self.message_pipe.put("STOP")
        print("All workers stopped")

    def server_run(self):
        # create a socket object
        # TCP socket details (address family, socket type)
        sket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        with sket:  # with statement to close the socket when we're done (infinite loop)
            # set socket options (allow reusing address if we restart the server) to prevent port binding error
            sket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # bind the socket to the address and port
            sket.bind((HOST, PORT))

            # listen for incoming connections
            sket.listen()  # listening for any number of connections

            print(f"Listening to server on {HOST}:{PORT} . . . \n")

            # accept incoming connections
            client_sket, client_address = sket.accept()
            with client_sket:  # verify active connection
                print(f"Connection established with {client_address}")
                # create a thread for each sensor
                threads = []
                for i in range(self.num_sensors):
                    thread = self.start_workers(sensor_list[i])
                    threads.append(thread)

                try:
                    while self.system_running_flag:
                        # serialize
                        # '\n' is used as a delimiter to separate messages
                        # serialization means converting the data into a string format
                        message = json.dumps(self.message_pipe.get()) + "\n"

                        # send the message
                        # sendall() is used to send the message in one go
                        # encode() is used to convert the message to bytes
                        # utf-8 is the encoding format which means universal transformation format
                        client_sket.sendall(message.encode("utf-8"))

                        # time.sleep(sensor_list[0]["data_rate"])
                    # handle exceptions
                except (BrokenPipeError, ConnectionResetError):
                    print("Client disconnected")
                finally:
                    print("shutting down the server . . .")
                    self.stop_workers()


if __name__ == "__main__":
    sensor_sim = sensor_simulator()
    try:
        sensor_sim.server_run()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        sys.exit(0)
