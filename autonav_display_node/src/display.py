#!/usr/bin/env python3

import asyncio
import json
import threading
import time

import cv2
import cv_bridge
import rclpy
from aiohttp import web
from autonav_msgs.msg import (
    Position,
    MotorFeedback,
    MotorInput,
    MotorControllerDebug,
    PathingDebug,
    GPSFeedback,
    IMUData,
)
from scr.node import Node
from scr.states import DeviceStateEnum
from scr_msgs.msg import SystemState, DeviceState, ConfigUpdated
from scr_msgs.srv import (
    SetSystemState,
    UpdateConfig,
    SetActivePreset,
    SaveActivePreset,
    GetPresets,
    DeletePreset,
)
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Empty

async_loop = asyncio.new_event_loop()
bridge = cv_bridge.CvBridge()


class Limiter:
    def __init__(self) -> None:
        self.limits = {}
        self.nextAllowance = {}

    # Sets a limit for how many times per second a key can be used
    def setLimit(self, key, limit):
        self.limits[key] = limit
        self.nextAllowance[key] = 0

    # If it can be used, returns true and decrements the remaining uses
    def use(self, key):
        if key not in self.limits:
            return True

        nextUsageAfter = self.nextAllowance[key]
        if nextUsageAfter == 0:
            self.nextAllowance[key] = time.time() + (1.0 / self.limits[key])
            return True

        if time.time() >= nextUsageAfter:
            self.nextAllowance[key] = time.time() + (1.0 / self.limits[key])
            return True

        return False


class BroadcastNode(Node):  # //TODO 21/11/2024
    def __init__(self):
        super().__init__("autonav_display_broadcast")

        self.port = 8023
        self.host = "0.0.0.0"
        self.send_map = {}
        self.client_map = {}

        # Limiter
        self.limiter = Limiter()
        self.limiter.setLimit("/autonav/MotorInput", 2)
        self.limiter.setLimit("/autonav/MotorFeedback", 5)
        self.limiter.setLimit("/autonav/MotorControllerDebug", 1)
        self.limiter.setLimit("/autonav/imu", 1)
        self.limiter.setLimit("/autonav/gps", 3)
        self.limiter.setLimit("/autonav/position", 3)
        self.limiter.setLimit("/autonav/camera/compressed/left", 0.5)
        self.limiter.setLimit("/autonav/camera/compressed/right", 0.5)
        self.limiter.setLimit("/autonav/cfg_space/raw/image/left_small", 0.5)
        self.limiter.setLimit("/autonav/cfg_space/raw/image/right_small", 0.5)
        self.limiter.setLimit("/autonav/cfg_space/combined/image", 0.5)

        # Clients
        self.system_state_c = self.create_subscription(
            SystemState, "/scr/system_state", self.systemStateCallback, 20
        )
        self.system_state_c = self.create_client(
            SetSystemState, "/scr/state/set_system_state"
        )
        self.config_c = self.create_client(UpdateConfig, "/scr/update_config_client")
        self.get_presets_c = self.create_client(GetPresets, "/scr/get_presets")
        self.set_active_preset_c = self.create_client(
            SetActivePreset, "/scr/set_active_preset"
        )
        self.save_active_preset_c = self.create_client(
            SaveActivePreset, "/scr/save_active_preset"
        )
        self.delete_preset_c = self.create_client(DeletePreset, "/scr/delete_preset")

        # Publishers
        self.broadcast_p = self.create_publisher(Empty, "/scr/state/broadcast", 20)

        # Subscriptions
        self.device_state_s = self.create_subscription(
            DeviceState, "/scr/device_state", self.deviceStateCallback, 20
        )
        self.config_s = self.create_subscription(
            ConfigUpdated,
            "/scr/config_updated",
            self.configurationInstructionCallback,
            10,
        )
        self.position_s = self.create_subscription(
            Position, "/autonav/position", self.positionCallback, 20
        )
        self.motor_feedback_s = self.create_subscription(
            MotorFeedback, "/autonav/MotorFeedback", self.motorFeedbackCallback, 20
        )
        self.motor_input_s = self.create_subscription(
            MotorInput, "/autonav/MotorInput", self.motorInputCallback, 20
        )
        self.motor_debug_s = self.create_subscription(
            MotorControllerDebug,
            "/autonav/MotorControllerDebug",
            self.motorControllerDebugCallback,
            20,
        )
        self.gps_s = self.create_subscription(
            GPSFeedback, "/autonav/gps", self.gpsFeedbackCallback, 20
        )
        self.imu_s = self.create_subscription(
            IMUData, "/autonav/imu", self.imuDataCallback, 20
        )
        self.camera_left_s = self.create_subscription(
            CompressedImage,
            "/autonav/camera/compressed/left/cutout",
            self.cameraCallbackLeft,
            self.qos_profile,
        )
        self.camera_right_s = self.create_subscription(
            CompressedImage,
            "/autonav/camera/compressed/right/cutout",
            self.cameraCallbackRight,
            self.qos_profile,
        )
        self.filtered_left_s = self.create_subscription(
            CompressedImage,
            "/autonav/cfg_space/raw/image/left_small",
            self.filteredCallbackLeftSmall,
            self.qos_profile,
        )
        self.filtered_right_s = self.create_subscription(
            CompressedImage,
            "/autonav/cfg_space/raw/image/right_small",
            self.filteredCallbackRightSmall,
            self.qos_profile,
        )
        self.combined_s = self.create_subscription(
            CompressedImage,
            "/autonav/cfg_space/combined/image",
            self.filteredCallbackCombined,
            self.qos_profile,
        )
        self.inflated_s = self.create_subscription(
            CompressedImage,
            "/autonav/cfg_space/raw/debug",
            self.inflated_callback,
            self.qos_profile,
        )

        self.loop_thread = threading.Thread(target=self.loopthread)
        self.loop_thread.start()

    def loopthread(self):
        asyncio.set_event_loop(async_loop)
        async_loop.run_until_complete(self.startHttpApp())

    async def startHttpApp(self):
        app = web.Application()
        app.router.add_get(
            "/", self.handler
        )  # should this be index.html? , possible //FIXME 21/11/2024
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        self.get_logger().info(
            "Started webserver server on ws://%s:%d" % (self.host, self.port)
        )
        await asyncio.Future()

    def request(self, request):
        return request.query.get("id")

    def push_image(self, topic, msg):
        if not self.limiter.use(topic):
            return

        cvimg = bridge.compressed_imgmsg_to_cv2(msg)
        _, img = cv2.imencode(".jpg", cvimg)

        self.push_old(
            json.dumps(
                {
                    "op": "data",
                    "topic": topic,
                    "format": msg.format,
                    "data": list(img.tobytes()),
                }
            )
        )

    def push(self, topic, data, unique_id=None):
        # Check limiter
        if not self.limiter.use(topic):
            return

        # Create packet
        packet = {
            "op": "data",
            "topic": topic,
        }

        # Copy properties from data to packet
        for key in data.get_fields_and_field_types().keys():
            packet[key] = getattr(data, key)

        # Check if there are any clients
        if len(self.send_map) == 0:
            return

        # Convert to json
        message_json = json.dumps(packet)

        # Send it out as needed
        if unique_id is None:
            for unique_id in self.send_map:
                self.send_map[unique_id].append(message_json)
        else:
            self.send_map[unique_id].append(message_json)

    def push_old(self, message, unique_id=None):
        if len(self.send_map) == 0:
            return

        if unique_id is None:
            for unique_id in self.send_map:
                self.send_map[unique_id].append(message)
        else:
            self.send_map[unique_id].append(message)

    async def producer(self, request):
        unqiue_id = self.request(request)
        while True:
            if len(self.send_map[unqiue_id]) > 0:
                await request.send(self.send_map[unqiue_id].pop(0))
            else:
                await asyncio.sleep(0.01)

    async def consumer(self, request):
        unique_id = self.request(request)
        async for message in request:
            obj = json.loads(message)
            if obj["op"] == "broadcast":
                self.broadcast_p.publish(Empty())

            if obj["op"] == "configuration" and "device" in obj and "json" in obj:
                config_packet = UpdateConfig.Request()
                config_packet.device = obj["device"]
                config_packet.json = json.dumps(obj["json"])
                self.config_c.call_async(config_packet)

            if obj["op"] == "get_nodes":
                nodes = self.get_node_names()
                for i in range(len(nodes)):
                    nodes[i] = nodes[i].replace("/", "")
                node_states = {}
                for identifier in nodes:
                    node_states[identifier] = (
                        self.device_states[identifier]
                        if identifier in self.device_states
                        else 0
                    )
                self.push_old(
                    json.dumps(
                        {
                            "op": "get_nodes_callback",
                            "nodes": nodes,
                            "states": node_states,
                            "configs": self.node_configs,
                            "system": {
                                "state": self.system_state,
                                "mode": self.system_mode,
                                "mobility": self.mobility,
                            },
                        }
                    ),
                    unique_id,
                )

            if obj["op"] == "set_system_state":
                self.set_system_total_state(
                    int(obj["state"]), int(obj["mode"]), bool(obj["mobility"])
                )

            if obj["op"] == "get_presets":
                req = GetPresets.Request()
                req.empty = True
                res = self.get_presets_c.call_async(req)
                res.add_done_callback(self.get_presets_callback)

            if obj["op"] == "set_active_preset":
                req = SetActivePreset.Request()
                req.preset = obj["preset"]
                self.set_active_preset_c.call_async(req)

            if obj["op"] == "save_preset_mode":
                req = SaveActivePreset.Request()
                req.write_mode = True
                req.preset_name = ""
                self.save_active_preset_c.call_async(req)

            if obj["op"] == "save_preset_as":
                req = SaveActivePreset.Request()
                req.preset_name = obj["preset"]
                req.write_mode = False
                self.save_active_preset_c.call_async(req)

            if obj["op"] == "delete_preset":
                req = DeletePreset.Request()
                req.preset = obj["preset"]
                self.delete_preset_c.call_async(req)

    def get_presets_callback(self, future):
        response = future.result()
        self.push_old(
            json.dumps(
                {
                    "op": "get_presets_callback",
                    "presets": response.presets,
                    "active_preset": response.active_preset,
                }
            )
        )

    async def handler(self, request):
        unique_id = self.request(request)
        if unique_id in self.client_map or unique_id is None:
            await request.close()
            return

        self.client_map[unique_id] = request
        self.send_map[unique_id] = []

        consumer_task = asyncio.create_task(self.consumer(request))
        producer_task = asyncio.create_task(self.producer(request))
        pending = await asyncio.wait(
            [consumer_task, producer_task], return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            for t in task:
                t.cancel()

        del self.client_map[unique_id]
        del self.send_map[unique_id]

    def systemStateCallback(self, msg: SystemState):
        self.push("/scr/state/system", msg)

    def deviceStateCallback(self, msg: DeviceState):
        self.push("/scr/state/device", msg)

    def configurationInstructionCallback(self, msg: ConfigUpdated):
        self.push("/scr/configuration", msg)

    def positionCallback(self, msg: Position):
        self.push("/autonav/position", msg)

    def motorInputCallback(self, msg: MotorInput):
        self.push("/autonav/MotorInput", msg)

    def motorFeedbackCallback(self, msg: MotorFeedback):
        self.push("/autonav/MotorFeedback", msg)

    def imuDataCallback(self, msg: IMUData):
        self.push("/autonav/imu", msg)

    def gpsFeedbackCallback(self, msg: GPSFeedback):
        self.push("/autonav/gps", msg)

    def motorControllerDebugCallback(self, msg: MotorControllerDebug):
        self.push("/autonav/MotorControllerDebug", msg)

    def cameraCallbackLeft(self, msg: CompressedImage):
        self.push_image("/autonav/camera/compressed/left", msg)

    def cameraCallbackRight(self, msg: CompressedImage):
        self.push_image("/autonav/camera/compressed/right", msg)

    def filteredCallbackLeft(self, msg: CompressedImage):
        self.push_image("/autonav/cfg_space/raw/image/left", msg)

    def filteredCallbackRight(self, msg: CompressedImage):
        self.push_image("/autonav/cfg_space/raw/image/right", msg)

    def filteredCallbackLeftSmall(self, msg: CompressedImage):
        self.push_image("/autonav/cfg_space/raw/image/left_small", msg)

    def filteredCallbackRightSmall(self, msg: CompressedImage):
        self.push_image("/autonav/cfg_space/raw/image/right_small", msg)

    def filteredCallbackCombined(self, msg: CompressedImage):
        self.push_image("/autonav/cfg_space/combined/image", msg)

    # Both unused //FEATURE 21/11/2024 //DELETEME

    def inflated_callback(self, msg: CompressedImage):
        self.push_image("/autonav/cfg_space/raw/debug", msg)

    def pathingDebugCallback(self, msg: PathingDebug):  # //TODO 21/11/2024 Unused?
        self.push_old(
            json.dumps(
                {
                    "op": "data",
                    "desired_heading": msg.desired_heading,
                    "desired_latitude": msg.desired_latitude,
                    "desired_longitude": msg.desired_longitude,
                    "distance_to_destination": msg.distance_to_destination,
                    "waypoints": msg.waypoints.tolist(),
                    "time_until_use_waypoints": msg.time_until_use_waypoints,
                }
            )
        )

    def init(self):
        self.set_device_state(DeviceStateEnum.OPERATING)


def main():
    rclpy.init()
    node = BroadcastNode()
    Node.run_node(node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()