import os
import re
import requests
import time

PIPE_PATH = "./inference_pipe"  # Named pipe path
BASE_API_URL = "http://localhost:6121/lights/439"
CONFIDENCE_THRESHOLD = 0.40  # Minimum confidence to trigger an action

classification_buffer = []  # Buffer to store classification results
is_processing = False  # Tracks if the API is currently adjusting the lights

# Regex to match only classification scores (off, white, yellow, noise, unknown)
CLASSIFICATION_REGEX = re.compile(r"^\s*(off|white|yellow|noise|unknown):\s([\d.]+)\s*$")

def send_request(endpoint, value):
    """ Sends a POST request to the given API endpoint with the specified value. """
    global is_processing
    payload = {"value": value}
    url = f"{BASE_API_URL}/{endpoint}"

    try:
        print(f"📡 Sending request: {endpoint} = {value}")
        response = requests.post(url, json=payload, timeout=10)
        print(f"✅ API response ({endpoint}={value}): {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error contacting API: {e}")

def process_classification_block(block):
    """ Processes a full classification result block and triggers an action if needed. """
    global is_processing
    if is_processing:
        print("⏳ API is still processing, discarding this block...")
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
        print(f"🔍 Full Classification Detected: {scores}")

        # Determine the class with the highest score
        highest_class = max(scores, key=scores.get)
        highest_score = scores[highest_class]

        # If it's off, white, or yellow AND score > 0.40, trigger API request
        if highest_class in {"off", "white", "yellow"} and highest_score > CONFIDENCE_THRESHOLD:
            print(f"🚀 Detected {highest_class} with confidence {highest_score}. Sending API request...")

            is_processing = True  # Block new commands until API is done

            if highest_class == "off":
                send_request("brightness", 0)  # Set brightness to 0
            elif highest_class in {"white", "yellow"}:
                send_request("brightness", 3)  # Set brightness to 3 first
                color_value = 4 if highest_class == "white" else 0  # 4 for white, 0 for yellow
                send_request("color", color_value)

            is_processing = False  # API finished, allow new commands
            flush_fifo()  # Discard old data and wait for fresh results

def flush_fifo():
    """ Discards old results from the FIFO until a new classification block begins. """
    print("🧹 Flushing old FIFO data...")

    try:
        with open(PIPE_PATH, "r") as pipe:
            while True:
                line = pipe.readline().strip()
                if not line:
                    break  # No more data in the pipe, stop flushing

                # Stop flushing once a new classification block starts
                if "#Classification results:" in line:
                    print("🟢 Found new classification block, resuming processing...")
                    return  
    except Exception as e:
        print(f"⚠️ Error while flushing FIFO: {e}")

def monitor_pipe():
    """ Reads classification results in real-time from the named pipe and processes full blocks. """
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
                if "#Classification results:" in line and len(classification_buffer) > 1:
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
