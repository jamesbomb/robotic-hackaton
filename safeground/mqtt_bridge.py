from __future__ import annotations

import json
from typing import Protocol


class MqttPublisher(Protocol):
    def publish(self, topic: str, payload: dict) -> None: ...


class PahoMqttPublisher:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        qos: int,
        timeout_s: float,
        client_id: str,
    ) -> None:
        self.host = host
        self.port = port
        self.qos = qos
        self.timeout_s = timeout_s
        self.client_id = client_id

    def publish(self, topic: str, payload: dict) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise RuntimeError("paho-mqtt is required for live MQTT robot commands") from exc

        client = mqtt.Client(client_id=self.client_id)
        client.connect(self.host, self.port, keepalive=max(1, int(self.timeout_s)))
        try:
            result = client.publish(topic, json.dumps(payload, ensure_ascii=True), qos=self.qos)
            result.wait_for_publish(timeout=self.timeout_s)
            if not result.is_published():
                raise TimeoutError(f"MQTT publish timed out for topic {topic}")
        finally:
            client.disconnect()
