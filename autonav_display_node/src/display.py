#!/usr/bin/env python3

import asyncio
import json
import threading
import time

import cv_bridge
import rclpy
from autonav_msgs.msg import Position, MotorFeedback, MotorInput, MotorControllerDebug, GPSFeedback, \
    IMUData
from scr.node import Node
from scr.states import DeviceStateEnum
from scr_msgs.msg import SystemState, DeviceState, ConfigUpdated
from scr_msgs.srv import SetSystemState, UpdateConfig, SetActivePreset, SaveActivePreset, GetPresets, DeletePreset
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Empty

async_loop = asyncio.new_event_loop()
bridge = cv_bridge.CvBridge()


# DELETEME
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


"""
By right I shouldn't need to mess with the inital setup of this node (no need 2 convert w/ websocket) 
"""


class BroadcastNode(Node):
    def __init__(self):
        super().__init__("autonav_display_broadcast")

        self.port = 8023
        self.host = "0.0.0.0"
        self.send_map = {}
        self.client_map = {}

        # Limiter
        self.constructor_limiter_setter()

        # Clients (not in use?)
        self.consturctor_client_setter()

        # Publishers
        self.broadcast_p = self.create_publisher(Empty, "/scr/state/broadcast", 20)

        # Subscriptions
        self.constructor_subscriptions_setters()

        self.loop_thread = threading.Thread(target=self.loopthread)
        self.loop_thread.start()

    # //DELETEME all limiters (since technically porting over to rtc)
    def constructor_limiter_setter(self):
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

    # //Not sure what should do w/ this?
    def consturctor_client_setter(self):
        self.system_state_c = self.create_subscription(SystemState, "/scr/system_state", self.systemStateCallback, 20)
        self.system_state_c = self.create_client(SetSystemState, "/scr/state/set_system_state")
        self.config_c = self.create_client(UpdateConfig, "/scr/update_config_client")
        self.get_presets_c = self.create_client(GetPresets, "/scr/get_presets")
        # //TODO 14/11/2024 clients (to implement in the future?)
        self.set_active_preset_c = self.create_client(SetActivePreset, "/scr/set_active_preset")
        self.save_active_preset_c = self.create_client(SaveActivePreset, "/scr/save_active_preset")
        self.delete_preset_c = self.create_client(DeletePreset, "/scr/delete_preset")

    # Helper for constructor
    def constructor_subscriptions_setters(self):
        self.device_state_s = self.create_subscription(DeviceState, "/scr/device_state", self.deviceStateCallback, 20)
        self.config_s = self.create_subscription(ConfigUpdated, "/scr/config_updated",
                                                 self.configurationInstructionCallback,
                                                 10)  # //TODO 14/11/2024 help lah
        self.position_s = self.create_subscription(Position, "/autonav/position", self.positionCallback, 20)
        self.motor_feedback_s = self.create_subscription(MotorFeedback, "/autonav/MotorFeedback",
                                                         self.motorFeedbackCallback, 20)
        self.motor_input_s = self.create_subscription(MotorInput, "/autonav/MotorInput", self.motorInputCallback, 20)
        self.motor_debug_s = self.create_subscription(MotorControllerDebug, "/autonav/MotorControllerDebug",
                                                      self.motorControllerDebugCallback, 20)
        self.gps_s = self.create_subscription(GPSFeedback, "/autonav/gps", self.gpsFeedbackCallback, 20)
        self.imu_s = self.create_subscription(IMUData, "/autonav/imu", self.imuDataCallback, 20)
        self.camera_left_s = self.create_subscription(CompressedImage, "/autonav/camera/compressed/left/cutout",
                                                      self.cameraCallbackLeft, self.qos_profile)
        self.camera_right_s = self.create_subscription(CompressedImage, "/autonav/camera/compressed/right/cutout",
                                                       self.cameraCallbackRight, self.qos_profile)
        self.filtered_left_s = self.create_subscription(CompressedImage, "/autonav/cfg_space/raw/image/left_small",
                                                        self.filteredCallbackLeftSmall, self.qos_profile)
        self.filtered_right_s = self.create_subscription(CompressedImage, "/autonav/cfg_space/raw/image/right_small",
                                                         self.filteredCallbackRightSmall, self.qos_profile)
        self.combined_s = self.create_subscription(CompressedImage, "/autonav/cfg_space/combined/image",
                                                   self.filteredCallbackCombined, self.qos_profile)
        self.inflated_s = self.create_subscription(CompressedImage, "/autonav/cfg_space/raw/debug",
                                                   self.inflated_callback, self.qos_profile)

    # Responsible for actually sending data to the server (see the websopcket arg)
    async def producer(self, websocket):
        unqiue_id = self.get_id_from_socket(websocket)
        while True:
            if len(self.send_map[unqiue_id]) > 0:
                await websocket.send(self.send_map[unqiue_id].pop(0))
            else:
                await asyncio.sleep(
                    0.01)  # //TODO 14/11/2024 optmize me so that its even faster to send messages (0.1 is too slow)

    # Listener for the websocket, handles data and callback requests
    async def consumer(self, websocket):
        unique_id = self.get_id_from_socket(websocket)
        async for message in websocket:
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
                    node_states[identifier] = self.device_states[identifier] if identifier in self.device_states else 0
                self.push_old(json.dumps({
                    "op": "get_nodes_callback",
                    "nodes": nodes,
                    "states": node_states,
                    "configs": self.node_configs,
                    "system": {
                        "state": self.system_state,
                        "mode": self.system_mode,
                        "mobility": self.mobility
                    }
                }), unique_id)

            if obj["op"] == "set_system_state":
                self.set_system_total_state(int(obj["state"]), int(obj["mode"]), bool(obj["mobility"]))

            await self.handle_presets(obj)

    # consumer helper
    async def handle_presets(self, obj):
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

    def get_presets_callback(self, future):
        response = future.result()
        self.push_old(json.dumps({
            "op": "get_presets_callback",
            "presets": response.presets,
            "active_preset": response.active_preset
        }))

    async def handler(self, websocket):
        unique_id = self.get_id_from_socket(websocket)
        if unique_id in self.client_map or unique_id is None:
            await websocket.close()
            return

        self.client_map[unique_id] = websocket
        self.send_map[unique_id] = []

        consumer_task = asyncio.create_task(self.consumer(websocket))
        producer_task = asyncio.create_task(self.producer(websocket))
        pending = await asyncio.wait(
            [consumer_task, producer_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            for t in task:
                t.cancel()

        del self.client_map[unique_id]
        del self.send_map[unique_id]


# handles all original callbacks
def callback(self, msg):
    topic_map = {
        SystemState: "/scr/state/system",
        DeviceState: "/scr/state/device",
        ConfigUpdated: "/scr/configuration",
        Position: "/autonav/position",
        MotorInput: "/autonav/MotorInput",
        MotorFeedback: "/autonav/MotorFeedback",
        IMUData: "/autonav/imu",
        GPSFeedback: "/autonav/gps",
        MotorControllerDebug: "/autonav/MotorControllerDebug",
        CompressedImage: {
            "left": "/autonav/camera/compressed/left",
            "right": "/autonav/camera/compressed/right",
            "left_small": "/autonav/cfg_space/raw/image/left_small",
            "right_small": "/autonav/cfg_space/raw/image/right_small",
            "combined": "/autonav/cfg_space/combined/image",
            "debug": "/autonav/cfg_space/raw/debug"
        }
    }

    if isinstance(msg, CompressedImage):
        if msg.header.frame_id in topic_map[CompressedImage]:
            self.push_image(topic_map[CompressedImage][msg.header.frame_id], msg)
    else:
        topic = topic_map.get(type(msg))
        if topic:
            self.push(topic, msg)

    # //TODO 14/11/2024 create another callBack for new pathNav (since astar was replaced with smtn else)

    # self.push_old(json.dumps({
    #     "op": "data",
    #     "topic": "/autonav/debug/astar",  # //TODO 14/11/2024 needs new topic to look after
    #     "desired_heading": msg.desired_heading,
    #     "desired_latitude": msg.desired_latitude,
    #     "desired_longitude": msg.desired_longitude,
    #     "distance_to_destination": msg.distance_to_destination,
    #     "waypoints": msg.waypoints.tolist(),
    #     "time_until_use_waypoints": msg.time_until_use_waypoints,
    # }))

    def init(self):
        self.set_device_state(DeviceStateEnum.OPERATING)


def main():
    rclpy.init()
    node = BroadcastNode()
    Node.run_node(node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()
