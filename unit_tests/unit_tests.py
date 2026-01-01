"""
This file is used to test the following logic:
    alarm logic
    sensor data parsing and mapping
"""
import unittest
from unittest.mock import MagicMock, patch
import json
import sys
import os
from PyQt6.QtWidgets import QApplication
from datetime import datetime
from unittest import TextTestRunner, TextTestResult


# Ensure the parent directory is in the path to import TCP_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock plyer before importing TCP_client
sys.modules["plyer"] = MagicMock()
sys.modules["plyer.notification"] = MagicMock()
import TCP_client


class TestSensorSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create QApplication instance if it doesn't exist (needed for QRunnable/Signals)
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)

    def setUp(self):
        # Create an instance of the sensor system container
        self.sensor_system = TCP_client.sensor_system()

    def test_sensor_data_parsing_and_mapping(self):
        """
        Test that a message for sensor_id X is correctly parsed and associated with that ID.
        We simulate this by verifying the Process Logic inside SensorTask.
        """
        sensor_id = 1
        task = self.sensor_system.SensorTask(sensor_id)

        inner_data = {
            "sensor_id": 1,
            "sensor_name": "TEMP",
            "data": 50.0,
            "timestamp": "01/01/2026 at 12:00:00",
            "max_value": 100.0,
            "min_value": 0.0,
            "sensor_status": "OK",
            "system_status": "ONLINE",
        }
        json_str = json.dumps(inner_data)
        double_json_str = json.dumps(json_str)

        #Mock the get_data method to return our data once, then stop
        def prevent_flag_changes(*args, **kwargs):
            task.is_running = False
            return double_json_str
        task.get_data = MagicMock(side_effect=prevent_flag_changes)
        task.sensor_worker_signals = MagicMock()

        task.run()

        #Verify the parsing logic extracted the right ID and Name
        args, _ = task.sensor_worker_signals.sensor_data_received.emit.call_args
        emitted_data = args[0]

        # Verify the parsing logic extracted the right ID and Name
        self.assertEqual(emitted_data["sensor_id"], 1)
        self.assertEqual(emitted_data["sensor_name"], "TEMP")
        self.assertEqual(emitted_data["data"], 50.0)

    def test_alarm_logic_high(self):
        """Test HIGH alarm generation"""
        sensor_id = 1
        task = self.sensor_system.SensorTask(sensor_id)

        #Max is 100. Data is 150 -> HIGH Alarm
        inner_data = {
            "sensor_id": 1,
            "sensor_name": "TEMP",
            "data": 150.0,
            "timestamp": "01/01/2026 at 12:00:00",
            "max_value": 100.0,
            "min_value": 0.0,
            "sensor_status": "OK",  # Initially OK, logic detects alarm
            "system_status": "ONLINE",
        }
        double_json_str = json.dumps(json.dumps(inner_data))

        #Mock the get_data method to return our data once, then stop
        def prevent_flag_changes(*args, **kwargs):
            task.is_running = False
            return double_json_str

        task.get_data = MagicMock(side_effect=prevent_flag_changes)
        task.sensor_worker_signals = MagicMock()

        #Need to patch notification to prevent message popups
        with patch("TCP_client.notification.notify") as _:
            task.run()

            #Verify logic emitted the right alarm type and message
            args, _ = task.sensor_worker_signals.alarm_received.emit.call_args
            alarm_data = args[0]

            self.assertEqual(alarm_data["alarm_type"], "HIGH")
            self.assertTrue("HIGH" in alarm_data["message"])
            self.assertEqual(alarm_data["data"], 150.0)

    def test_alarm_logic_low(self):
        """Test LOW alarm generation"""
        sensor_id = 1
        task = self.sensor_system.SensorTask(sensor_id)

        #Min is 0. Data is -10 -> LOW Alarm
        inner_data = {
            "sensor_id": 1,
            "sensor_name": "TEMP",
            "data": -10.0,
            "timestamp": "01/01/2026 at 12:00:00",
            "max_value": 100.0,
            "min_value": 0.0,
            "sensor_status": "OK",
            "system_status": "ONLINE",
        }
        double_json_str = json.dumps(json.dumps(inner_data))

        def prevent_flag_changes(*args, **kwargs):
            task.is_running = False
            return double_json_str

        task.get_data = MagicMock(side_effect=prevent_flag_changes)
        task.sensor_worker_signals = MagicMock()

        with patch("TCP_client.notification.notify") as _:
            task.run()

            args, _ = task.sensor_worker_signals.alarm_received.emit.call_args
            alarm_data = args[0]

            self.assertEqual(alarm_data["alarm_type"], "LOW")
            self.assertTrue("LOW" in alarm_data["message"])

    def test_alarm_logic_faulty(self):
        """Test FAULTY status alarm"""
        sensor_id = 1
        task = self.sensor_system.SensorTask(sensor_id)

        inner_data = {
            "sensor_id": 1,
            "sensor_name": "TEMP",
            "data": 50.0,
            "timestamp": "01/01/2026 at 12:00:00",
            "max_value": 100.0,
            "min_value": 0.0,
            "sensor_status": "FAULTY",  # Incoming status is FAULTY
            "system_status": "ONLINE",
        }
        double_json_str = json.dumps(json.dumps(inner_data))

        def prevent_flag_changes(*args, **kwargs):
            task.is_running = False
            return double_json_str

        task.get_data = MagicMock(side_effect=prevent_flag_changes)
        task.sensor_worker_signals = MagicMock()

    
        with patch("TCP_client.notification.notify") as _:
            task.run()

            args, _ = task.sensor_worker_signals.alarm_received.emit.call_args
            alarm_data = args[0]
            # Verify logic emitted the right alarm type and message
            self.assertEqual(alarm_data["alarm_type"], "FAULTY")
            self.assertTrue("FAULTY" in alarm_data["message"])





LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_results.log")


class LoggingTestResult(TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.log_fp = open(LOG_FILE, "a", encoding="utf-8")
        self.log_fp.write(f"\n=== Test run started at {datetime.now().isoformat()} ===\n")
        self.log_fp.flush()

    def startTest(self, test):
        super().startTest(test)
        self._test_start_time = datetime.now()

    def addSuccess(self, test):
        super().addSuccess(test)
        t = datetime.now()
        duration = (t - self._test_start_time).total_seconds()
        entry = f"{t.isoformat()} - {test.id()} - SUCCESS - {duration:.3f}s\n"
        self.log_fp.write(entry)
        self.log_fp.flush()

    def addFailure(self, test, err):
        super().addFailure(test, err)
        t = datetime.now()
        duration = (t - self._test_start_time).total_seconds()
        tb = self._exc_info_to_string(err, test)
        entry = f"{t.isoformat()} - {test.id()} - FAILURE - {duration:.3f}s - {tb}\n"
        self.log_fp.write(entry)
        self.log_fp.flush()

    def addError(self, test, err):
        super().addError(test, err)
        t = datetime.now()
        duration = (t - self._test_start_time).total_seconds()
        tb = self._exc_info_to_string(err, test)
        entry = f"{t.isoformat()} - {test.id()} - ERROR - {duration:.3f}s - {tb}\n"
        self.log_fp.write(entry)
        self.log_fp.flush()

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        t = datetime.now()
        duration = (t - self._test_start_time).total_seconds()
        entry = f"{t.isoformat()} - {test.id()} - SKIPPED - {duration:.3f}s - {reason}\n"
        self.log_fp.write(entry)
        self.log_fp.flush()

    def stopTestRun(self):
        try:
            self.log_fp.write(f"=== Test run finished at {datetime.now().isoformat()} ===\n")
            self.log_fp.flush()
        finally:
            try:
                self.log_fp.close()
            except Exception:
                pass


class LoggingTextTestRunner(TextTestRunner):
    resultclass = LoggingTestResult


if __name__ == "__main__":
    runner = LoggingTextTestRunner(verbosity=2)
    unittest.main(testRunner=runner)
