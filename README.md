# 🎙️ Edge Impulse + Nordic Thingy:53 + Light Control Demo

<img src="https://github.com/user-attachments/assets/82eb08c7-b659-42a3-8d05-a9b4d5782d22" width=400 />


## **Overview**
This is a demo script for a **Lunch & Learn** session on how to:
- Train a **voice classification model** using [Edge Impulse](https://www.edgeimpulse.com/).
- Deploy it to a **Nordic Thingy:53**.
- Monitor the model’s **real-time output**.
- Use the results to **control the lights** in the building via the [Simula Lights API](https://github.com/Northo/simula-lights-api).

The script listens to inference results streamed from `edge-impulse-run-impulse`, detects the most confident class (`off`, `white`, or `yellow`), and adjusts the lights accordingly.

---

## **Setup**
### Install Dependencies**
Make sure you have Python installed, then install dependencies:
```bash
pip install -r requirements.txt
```

### Create a FIFO Pipe
We'll use a named pipe to capture the inference output:

```bash
mkfifo inference_pipe
```

### Start Edge Impulse on the Thingy:53
Run this on your machine to stream the inference results:

```bash
edge-impulse-run-impulse | tee inference_pipe
```

### Run the Monitor Script
Run the script with the room number where the lights should be controlled:

```bash
python monitor.py 451
```
Replace 451 with the actual room number.
By default, the script reads from ./inference_pipe, but you can specify a different path:

```bash
python monitor.py 451 --pipe-path /tmp/inference_pipe
```

### What the Script Does
Reads inference results from the FIFO pipe.
Detects whether "off", "white", or "yellow" is the most confident classification.
If confidence is above 0.40, it sends a request to the Simula Lights API:
"off" → Turns off the lights.
"white" → Sets brightness to 3, then color to 4.
"yellow" → Sets brightness to 3, then color to 0.
Ensures that old results don’t pile up while waiting for the API to respond.

### Simula Lights API
This script interacts with the Simula Lights API.
It sends requests to:

```
Brightness Control: POST /lights/{room}/brightness
Color Control: POST /lights/{room}/color
```

### What This Demo Shows
How to go from training a model to deploying it on hardware.
How to stream and process inference results in real-time.
How to use AI-driven decisions to interact with the physical world.

## Credits
Edge Impulse for voice classification.

Nordic Thingy:53 for running the model.

[Simula Lights API](https://github.com/Northo/simula-lights-api) for smart lighting.
