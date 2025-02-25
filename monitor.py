import os
import re
import requests
import typer
from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file
load_dotenv()

app = typer.Typer()

CONFIDENCE_THRESHOLD = 0.40  # Minimum confidence to trigger an action
classification_buffer = []  # Buffer to store classification results
is_processing = False  # Tracks if the API is currently adjusting the lights

# Get PIPE_PATH from environment variables or CLI argument
DEFAULT_PIPE_PATH = os.getenv("PIPE_PATH", "./inference_pipe")

# Regex to match only classification scores (off, white, yellow, noise, unknown)
CLASSIFICATION_REGEX = re.compile(r"^\s*(off|white|yellow|noise|unknown):\s([\d.]+)\s*$")

# Configure Loguru Logger
logger.add("monitor.log", rotation="10MB", retention="7 days", level="DEBUG")

def send_request(base_api_url, endpoint, value):
    """ Sends a POST request to the given API endpoint with the specified value. """
    payload = {"value": value}
    url = f"{base_api_url}/{endpoint}"

    try:
        logger.info(f"📡 Sending request: {endpoint} = {value}")
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.success(f"✅ API response ({endpoint}={value}): {response.json()}")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error contacting API: {e}")

def process_classification_block(base_api_url, block):
    """ Processes a full classification result block and triggers an action if needed. """
    global is_processing
    if is_processing:
        logger.warning("⏳ API is still processing, discarding this block...")
        return  # Ignore new classifications while API is adjusting the lights

    scores = {}

    # Extract class scores from the block
    for line in block:
        match = CLASSIFICATION_REGEX.match(line)
        if match:
            class_name = match.group(1)  # e.g., off, white, yellow
            score = float(match.group(2))  # e.g., 0.738281
            scores[class_name] = score

    if scores:
        logger.info(f"🔍 Full Classification Detected: {scores}")

        # Determine the class with the highest score
        highest_class = max(scores, key=scores.get)
        highest_score = scores[highest_class]

        # If it's off, white, or yellow AND score > 0.40, trigger API request
        if highest_class in {"off", "white", "yellow"} and highest_score > CONFIDENCE_THRESHOLD:
            logger.info(f"🚀 Detected {highest_class} with confidence {highest_score}. Sending API request...")

            is_processing = True  # Block new commands until API is done

            if highest_class == "off":
                send_request(base_api_url, "brightness", 0)  # Set brightness to 0
            elif highest_class in {"white", "yellow"}:
                send_request(base_api_url, "brightness", 3)  # Set brightness to 3 first
                color_value = 4 if highest_class == "white" else 0  # 4 for white, 0 for yellow
                send_request(base_api_url, "color", color_value)

            is_processing = False  # API finished, allow new commands
            flush_fifo(base_api_url)  # Discard old data and wait for fresh results

def flush_fifo(pipe_path):
    """ Discards old results from the FIFO until a new classification block begins. """
    logger.info(f"🧹 Flushing old FIFO data from {pipe_path}...")

    try:
        with open(pipe_path, "r") as pipe:
            while True:
                line = pipe.readline().strip()
                if not line:
                    break  # No more data in the pipe, stop flushing

                # Stop flushing once a new classification block starts
                if "#Classification results:" in line:
                    logger.info("🟢 Found new classification block, resuming processing...")
                    return  
    except Exception as e:
        logger.warning(f"⚠️ Error while flushing FIFO: {e}")

def monitor_pipe(room_number: int, pipe_path: str):
    """ Reads classification results in real-time from the named pipe and processes full blocks. """
    base_api_url = f"http://localhost:6121/lights/{room_number}"
    
    logger.info(f"📡 Monitoring room {room_number} - Inference results from {pipe_path}...")

    try:
        with open(pipe_path, "r") as pipe:
            while True:
                line = pipe.readline().strip()

                if not line:  # Detect EOF (command stopped or disconnected)
                    logger.warning("⚠️ No more data. Exiting...")
                    break

                # Add line to buffer
                classification_buffer.append(line)

                # If the line signals the start of a new classification block, process the previous one
                if "#Classification results:" in line and len(classification_buffer) > 1:
                    process_classification_block(base_api_url, classification_buffer)
                    classification_buffer.clear()  # Clear buffer for next block

    except FileNotFoundError:
        logger.error(f"❌ Named pipe {pipe_path} not found! Run: mkfifo {pipe_path}")
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
    else:
        monitor_pipe(room_number, pipe_path)

if __name__ == "__main__":
    app()
