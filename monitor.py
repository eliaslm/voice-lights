import os
import re
import requests

PIPE_PATH = "./inference_pipe"  # Named pipe path
API_URL = "http://localhost:6121/lights/451/brightness"
BRIGHTNESS_VALUE = 3

classification_buffer = []  # Buffer to store relevant classification results

# Regex to match only classification scores (labels like 'hey_elias', 'noise', 'unknown')
CLASSIFICATION_REGEX = re.compile(r"^\s*(hey_elias|noise|unknown):\s([\d.]+)\s*$")


def trigger_light_adjustment():
    """Sends a POST request to adjust brightness in room 439."""
    payload = {"value": BRIGHTNESS_VALUE}
    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        print(f"✅ API response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error contacting API: {e}")


def process_classification_block(block):
    """Processes a full classification result block and triggers action if needed."""
    scores = {}

    # Extract class scores from the block
    for line in block:
        match = CLASSIFICATION_REGEX.match(line)
        if match:
            class_name = match.group(1)  # e.g., hey_elias
            score = float(match.group(2))  # e.g., 0.003906
            scores[class_name] = score

    if scores:
        print(f"🔍 Full Classification Detected: {scores}")

        # Determine the class with the highest score
        highest_class = max(scores, key=scores.get)

        if highest_class == "hey_elias":
            print("🚀 'hey_elias' detected with highest confidence! Triggering API...")
            trigger_light_adjustment()


def monitor_pipe():
    """Reads classification results in real-time from the named pipe and processes full blocks."""
    print(f"📡 Listening for inference results in {PIPE_PATH}...")

    try:
        with open(PIPE_PATH, "r") as pipe:
            while True:
                line = pipe.readline().strip()

                if not line:  # Detect EOF (command stopped or disconnected)
                    print("⚠️ No more data. Exiting...")
                    break

                # Add line to buffer
                classification_buffer.append(line)

                # If the line signals the start of a new classification block, process the previous one
                if (
                    "#Classification results:" in line
                    and len(classification_buffer) > 1
                ):
                    process_classification_block(classification_buffer)
                    classification_buffer.clear()  # Clear buffer for next block

    except FileNotFoundError:
        print(f"❌ Named pipe {PIPE_PATH} not found! Run: mkfifo {PIPE_PATH}")
    except KeyboardInterrupt:
        print("\n🛑 Stopping monitoring...")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    if not os.path.exists(PIPE_PATH):
        print(f"❌ Named pipe {PIPE_PATH} not found! Run: mkfifo {PIPE_PATH}")
    else:
        monitor_pipe()
