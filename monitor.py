import os
import re
import requests
import typer
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

app = typer.Typer()

CONFIDENCE_THRESHOLD = 0.40
DEFAULT_PIPE_PATH = os.getenv("PIPE_PATH", "./inference_pipe")

CLASSIFICATION_REGEX = re.compile(r"^\s*(off|white|yellow|noise|unknown):\s([\d.]+)\s*$")


class Monitor:
    def __init__(self, room_number: int, pipe_path: str):
        self.room_number = room_number
        self.pipe_path = pipe_path
        self.base_api_url = f"http://localhost:6121/lights/{room_number}"
        self.classification_buffer = []
        self.is_processing = False

    def send_request(self, endpoint: str, value: int):
        """Sends a POST request to the given API endpoint with the specified value."""
        payload = {"value": value}
        url = f"{self.base_api_url}/{endpoint}"

        try:
            logger.info(f"📡 Sending request: {endpoint} = {value}")
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.success(f"✅ API response ({endpoint}={value}): {response.json()}")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error contacting API: {e}")

    def process_classification_block(self):
        """Processes a full classification result block and triggers an action if needed."""
        if self.is_processing:
            logger.warning("⏳ API is still processing, discarding this block...")
            return

        scores = {}

        for line in self.classification_buffer:
            match = CLASSIFICATION_REGEX.match(line)
            if match:
                class_name = match.group(1)
                score = float(match.group(2))
                scores[class_name] = score

        if scores:
            logger.info(f"🔍 Full Classification Detected: {scores}")

            highest_class = max(scores, key=scores.get)
            highest_score = scores[highest_class]

            if highest_class in {"off", "white", "yellow"} and highest_score > CONFIDENCE_THRESHOLD:
                logger.info(f"🚀 Detected {highest_class} with confidence {highest_score}. Sending API request...")

                self.is_processing = True

                if highest_class == "off":
                    self.send_request("brightness", 0)
                elif highest_class in {"white", "yellow"}:
                    self.send_request("brightness", 3)
                    color_value = 4 if highest_class == "white" else 0
                    self.send_request("color", color_value)

                self.is_processing = False
                self.flush_fifo()

    def flush_fifo(self):
        """Discards old results from the FIFO until a new classification block begins."""
        logger.info(f"🧹 Flushing old FIFO data from {self.pipe_path}...")

        try:
            with open(self.pipe_path, "r") as pipe:
                while True:
                    line = pipe.readline().strip()
                    if not line:
                        break

                    if "#Classification results:" in line:
                        logger.info("🟢 Found new classification block, resuming processing...")
                        return
        except Exception as e:
            logger.warning(f"⚠️ Error while flushing FIFO: {e}")

    def monitor_pipe(self):
        """Reads classification results in real-time from the named pipe and processes full blocks."""
        logger.info(f"📡 Monitoring room {self.room_number} - Inference results from {self.pipe_path}...")

        try:
            with open(self.pipe_path, "r") as pipe:
                while True:
                    line = pipe.readline().strip()

                    if not line:
                        logger.warning("⚠️ No more data. Exiting...")
                        break

                    self.classification_buffer.append(line)

                    if "#Classification results:" in line and len(self.classification_buffer) > 1:
                        self.process_classification_block()
                        self.classification_buffer.clear()

        except FileNotFoundError:
            logger.error(f"❌ Named pipe {self.pipe_path} not found! Run: mkfifo {self.pipe_path}")
        except KeyboardInterrupt:
            logger.info("\n🛑 Stopping monitoring...")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")


@app.command()
def main(
    room_number: int,
    pipe_path: str = typer.Option(
        DEFAULT_PIPE_PATH,
        help="Path to the named pipe for inference output"
    ),
):
    """Start monitoring the FIFO pipe and adjust lights for the given room number."""
    if not os.path.exists(pipe_path):
        logger.error(f"❌ Named pipe {pipe_path} not found! Run: mkfifo {pipe_path}")
        return

    monitor = Monitor(room_number, pipe_path)
    monitor.monitor_pipe()


if __name__ == "__main__":
    app()
