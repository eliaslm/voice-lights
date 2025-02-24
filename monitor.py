import time
import re
import os
import requests

OUTPUT_FILE = "outputs.txt"
API_URL = "http://localhost:6121/lights/439/brightness"  # FastAPI endpoint
BRIGHTNESS_VALUE = 0  # The brightness value to set when 'hey_elias' is detected

def parse_latest_classification():
    """ Reads the latest classification results from the file. """
    scores = {}
    with open(OUTPUT_FILE, "r") as file:
        lines = file.readlines()

    # Reverse search for classification results (most recent first)
    for i in range(len(lines) - 1, -1, -1):
        if "#Classification results:" in lines[i]:
            # Extract scores for hey_elias, noise, and unknown
            for j in range(i + 1, min(i + 4, len(lines))):  # Look at next 3 lines
                match = re.search(r"(\w+):\s([\d.]+)", lines[j])
                if match:
                    class_name = match.group(1)
                    score = float(match.group(2))
                    scores[class_name] = score
            break  # Stop after the latest block is found

    return scores

def trigger_light_adjustment():
    """ Sends a POST request to the FastAPI server to set brightness. """
    payload = {"value": BRIGHTNESS_VALUE}
    try:
        response = requests.post(API_URL, json=payload, timeout=60)
        if response.status_code == 200:
            print(f"✅ Brightness set to {BRIGHTNESS_VALUE} in room 439!")
        else:
            print(f"⚠️ Failed to set brightness: {response.status_code}, {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error contacting API: {e}")

def monitor_output():
    """ Monitors the output file and triggers brightness adjustment if hey_elias is detected. """
    print("Monitoring output file for 'hey_elias' detection...")

    last_checked_size = 0  # Track the file size to detect new content

    while True:
        try:
            current_size = os.path.getsize(OUTPUT_FILE)
            if current_size != last_checked_size:  # New content detected
                scores = parse_latest_classification()

                if scores:
                    highest_class = max(scores, key=scores.get)  # Get the class with the highest score
                    print(f"Latest Classification: {scores}")

                    if highest_class == "hey_elias":
                        print("🚀 'hey_elias' detected with highest confidence! Sending API request...")
                        trigger_light_adjustment()

                last_checked_size = current_size  # Update file size tracker

            time.sleep(1)  # Check for updates every second
        except KeyboardInterrupt:
            print("Stopping monitoring...")
            break
        except FileNotFoundError:
            print(f"Waiting for {OUTPUT_FILE} to be created...")
            time.sleep(2)

if __name__ == "__main__":
    monitor_output()
