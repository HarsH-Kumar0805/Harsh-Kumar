PSO Secure Image Transfer — Setup Guide
========================================

Requirements
------------
pip install streamlit numpy opencv-python pillow requests


How to Run
----------
Step 1 — Start the file server (keep this terminal open):
    python file_server.py

Step 2 — In a second terminal, start the Streamlit app:
    streamlit run app.py


How to Use
----------
Sender:
  1. Open the app in a browser (http://localhost:8501)
  2. Select "Sender" mode
  3. Upload an image
  4. Set a transfer password
  5. Click "Encrypt and Upload"
  6. Share the 6-digit code AND the password with the receiver

Receiver:
  1. Open the app (can be on the same or a different machine on the same network)
  2. Select "Receiver" mode
  3. Enter the 6-digit transfer code
  4. Enter the transfer password
  5. Click "Retrieve and Decrypt"
  6. Download the decrypted image


Project Structure
-----------------
pso_realworld/
    app.py              Main Streamlit application (sender + receiver)
    file_server.py      Local HTTP file server for storing encrypted files
    server_storage/     Encrypted files are stored here as JSON records
    README.txt          This file


Notes
-----
- The file server runs on localhost:8765 by default.
- For a demo on two machines on the same network, change SERVER_URL in app.py
  from "http://localhost:8765" to "http://<sender-machine-ip>:8765".
- server_storage/ can be cleared between demos to remove old encrypted files.
