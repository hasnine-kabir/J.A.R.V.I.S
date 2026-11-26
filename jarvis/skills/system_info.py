import datetime

import psutil
import requests

from jarvis.skills.base import BaseSkill, Tool

WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "freezing fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "heavy freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "violent showers", 85: "snow showers",
    86: "heavy snow showers", 95: "thunderstorm", 96: "thunderstorm with hail",
    99: "severe thunderstorm with hail",
}


class SystemInfoSkill(BaseSkill):
    name = "system_info"
    description = "System information: CPU, memory, battery, disk, date/time and weather"
    tools = [
        Tool(name="cpu_usage", description="Get CPU usage, RAM usage and battery level"),
        Tool(name="current_time", description="Get the current local date and time"),
        Tool(name="disk_usage", description="Get free/used space on each disk drive"),
        Tool(
            name="weather",
            description="Get the current weather. Uses the user's approximate location unless a city is given.",
            parameters={"city": {"type": "string", "description": "Optional city name, e.g. 'Dhaka'"}},
        ),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "cpu_usage":
            return self._cpu_usage()
        if action == "current_time":
            return datetime.datetime.now().strftime("It's %A, %B %d, %Y at %I:%M %p")
        if action == "disk_usage":
            return self._disk_usage()
        if action == "weather":
            return self._weather(args.get("city", ""))
        raise ValueError(f"Unknown action: {action}")

    def _cpu_usage(self) -> str:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        result = f"CPU: {cpu}%, RAM: {mem.percent}% of {mem.total / 2**30:.1f} GB"
        battery = psutil.sensors_battery()
        if battery:
            result += f", Battery: {battery.percent}%"
            if battery.power_plugged:
                result += " (plugged in)"
        return result

    def _disk_usage(self) -> str:
        lines = []
        for part in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue
            lines.append(
                f"{part.mountpoint} {u.free / 2**30:.1f} GB free of "
                f"{u.total / 2**30:.1f} GB ({u.percent}% used)"
            )
        return "\n".join(lines) or "No disks found."

    def _locate(self, city: str) -> tuple[float, float, str]:
        if city:
            r = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1},
                timeout=10,
            ).json()
            if not r.get("results"):
                raise ValueError(f"unknown city '{city}'")
            hit = r["results"][0]
            return hit["latitude"], hit["longitude"], f"{hit['name']}, {hit.get('country', '')}"
        r = requests.get("https://ipinfo.io/json", timeout=10).json()
        lat, lon = (float(x) for x in r["loc"].split(","))
        return lat, lon, f"{r.get('city', '')}, {r.get('country', '')}"

    def _weather(self, city: str) -> str:
        try:
            lat, lon, place = self._locate(city)
            data = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                               "weather_code,wind_speed_10m",
                },
                timeout=10,
            ).json()["current"]
            cond = WEATHER_CODES.get(data["weather_code"], "unknown conditions")
            return (
                f"{place}: {cond}, {data['temperature_2m']}°C "
                f"(feels like {data['apparent_temperature']}°C), "
                f"humidity {data['relative_humidity_2m']}%, wind {data['wind_speed_10m']} km/h"
            )
        except Exception as e:
            return f"Weather unavailable: {e}"
