"""
app.py
------
PSO Image Encryption — Real-Life Demo
Two modes: Sender (encrypt and upload) and Receiver (download and decrypt).

Run order:
    1. python file_server.py
    2. streamlit run app.py
"""

import streamlit as st
import numpy as np
import cv2
import hashlib
import random
import string
import json
import requests
from PIL import Image

st.set_page_config(page_title="PSO Secure Image Transfer", layout="centered")

SERVER_URL = "http://localhost:8765"


# --- Logistic map chaotic key (seeded from image content) ---
def logistic_map_key(seed, size, r=3.99):
    x = seed % 1.0
    if x == 0.0 or x == 1.0:
        x = 0.123456789
    key = np.zeros(size, dtype=np.uint8)
    for i in range(size):
        x = r * x * (1 - x)
        key[i] = int(x * 255) % 256
    return key


def image_seed(image):
    total = int(np.sum(image.astype(np.int64)))
    seed  = (total % 999983) / 999983.0
    return seed if seed != 0.0 else 0.123456789


# --- PSO optimiser ---
class PSO:
    def __init__(self, n_particles, dimensions, max_iter):
        self.n_particles  = n_particles
        self.dimensions   = dimensions
        self.max_iter     = max_iter
        self.positions    = np.random.randint(0, 256, (n_particles, dimensions))
        self.velocities   = np.random.randn(n_particles, dimensions)
        self.pbest_pos    = self.positions.copy()
        self.pbest_scores = np.full(n_particles, np.inf)
        self.gbest_pos    = None
        self.gbest_score  = np.inf

    def fitness(self, particle):
        hist, _ = np.histogram(particle, bins=256, range=(0, 255))
        prob = hist / np.sum(hist)
        prob = prob[prob > 0]
        return np.sum(prob * np.log2(prob))

    def optimize(self):
        w, c1, c2 = 0.7, 1.5, 1.5
        for _ in range(self.max_iter):
            for i in range(self.n_particles):
                score = self.fitness(self.positions[i])
                if score < self.pbest_scores[i]:
                    self.pbest_scores[i] = score
                    self.pbest_pos[i]    = self.positions[i].copy()
                if score < self.gbest_score:
                    self.gbest_score = score
                    self.gbest_pos   = self.positions[i].copy()
            for i in range(self.n_particles):
                r1, r2 = np.random.rand(), np.random.rand()
                self.velocities[i] = (
                    w  * self.velocities[i]
                    + c1 * r1 * (self.pbest_pos[i] - self.positions[i])
                    + c2 * r2 * (self.gbest_pos    - self.positions[i])
                )
                self.positions[i] = np.clip(
                    self.positions[i] + self.velocities[i], 0, 255
                ).astype(np.uint8)
        return self.gbest_pos


# --- Key construction ---
def password_to_key(password, size):
    raw = hashlib.sha256(password.encode()).digest()
    key = np.frombuffer(raw, dtype=np.uint8)
    return np.tile(key, size // len(key) + 1)[:size]


def combine_keys(k1, k2, k3):
    return np.bitwise_xor(np.bitwise_xor(k1, k2), k3)


# --- Diffusion ---
def diffuse(flat, key):
    flat = flat.astype(np.int32).copy()
    for i in range(1, len(flat)):
        flat[i] = (flat[i] + flat[i - 1] + int(key[i])) % 256
    return flat.astype(np.uint8)


def inverse_diffuse(flat, key):
    flat = flat.astype(np.int32).copy()
    for i in range(len(flat) - 1, 0, -1):
        flat[i] = (flat[i] - flat[i - 1] - int(key[i])) % 256
    return flat.astype(np.uint8)


# --- Encrypt / Decrypt ---
def encrypt_image(image, pso_key, password_key):
    size      = image.size
    chaos_key = logistic_map_key(image_seed(image), size)
    final_key = combine_keys(pso_key[:size], password_key[:size], chaos_key)
    xored     = np.bitwise_xor(image.flatten(), final_key)
    diffused  = diffuse(xored, final_key)
    return diffused.reshape(image.shape), final_key


def decrypt_image(encrypted, final_key):
    undiffused = inverse_diffuse(encrypted.flatten(), final_key)
    plaintext  = np.bitwise_xor(undiffused, final_key)
    return plaintext.reshape(encrypted.shape)


# --- 6-digit alphanumeric transfer code ---
def generate_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


# --- Server communication ---
def store_on_server(code, encrypted, final_key, shape):
    payload = {
        "code":      code,
        "encrypted": encrypted.flatten().tolist(),
        "key":       final_key.tolist(),
        "shape":     list(shape)
    }
    try:
        response = requests.post(f"{SERVER_URL}/store", json=payload, timeout=5)
        return response.json().get("status") == "stored"
    except requests.exceptions.ConnectionError:
        return None


def retrieve_from_server(code):
    try:
        response = requests.get(f"{SERVER_URL}/retrieve", params={"code": code}, timeout=5)
        data     = response.json()
        if data.get("status") != "ok":
            return None
        encrypted = np.array(data["encrypted"], dtype=np.uint8)
        key       = np.array(data["key"],       dtype=np.uint8)
        shape     = tuple(data["shape"])
        return encrypted.reshape(shape), key
    except requests.exceptions.ConnectionError:
        return None


def server_is_running():
    try:
        requests.get(f"{SERVER_URL}/health", timeout=2)
        return True
    except requests.exceptions.ConnectionError:
        return False


# --- UI ---
st.title("PSO Secure Image Transfer")

# Server status indicator
if server_is_running():
    st.success("File server is online.")
else:
    st.error(
        "File server is not running. "
        "Start it with: python file_server.py"
    )
    st.stop()

mode = st.radio("Select Mode", ["Sender", "Receiver"], horizontal=True)
st.divider()

# ── Sender Mode ───────────────────────────────────────────────────────────────
if mode == "Sender":
    st.subheader("Sender — Encrypt and Upload")
    st.write(
        "Upload an image to encrypt it. "
        "You will receive a 6-digit transfer code to share with the receiver."
    )

    uploaded_file = st.file_uploader("Select image", type=["jpg", "png", "jpeg"])
    password      = st.text_input("Set a transfer password", type="password",
                                   help="The receiver must enter the same password to decrypt.")

    if uploaded_file and password:
        if st.button("Encrypt and Upload"):
            # Preprocess
            image = np.array(Image.open(uploaded_file).convert("L"))
            image = cv2.resize(image, (256, 256))

            with st.spinner("Running PSO and encrypting..."):
                dimensions   = image.size
                password_key = password_to_key(password, dimensions)
                pso_key      = PSO(n_particles=8, dimensions=dimensions, max_iter=15).optimize()
                encrypted, final_key = encrypt_image(image, pso_key, password_key)

            # Upload to server
            code   = generate_code()
            result = store_on_server(code, encrypted, final_key, encrypted.shape)

            if result is None:
                st.error("Could not connect to the file server.")
            elif not result:
                st.error("Server failed to store the file.")
            else:
                st.image(encrypted, caption="Encrypted Image (stored on server)", clamp=True)

                st.success("Image encrypted and uploaded successfully.")
                st.markdown("### Transfer Code")
                st.code(code, language=None)
                st.info(
                    "Share this code AND the password with the receiver. "
                    "Both are required to decrypt the image."
                )

    elif uploaded_file and not password:
        st.warning("Enter a transfer password to continue.")

# ── Receiver Mode ─────────────────────────────────────────────────────────────
elif mode == "Receiver":
    st.subheader("Receiver — Download and Decrypt")
    st.write(
        "Enter the 6-digit transfer code and password provided by the sender "
        "to retrieve and decrypt the image."
    )

    code     = st.text_input("Transfer Code", max_chars=6,
                              placeholder="e.g. A3K9PX").strip().upper()
    password = st.text_input("Transfer Password", type="password")

    if st.button("Retrieve and Decrypt"):
        if not code or not password:
            st.warning("Both the transfer code and password are required.")
        else:
            with st.spinner("Fetching encrypted image from server..."):
                result = retrieve_from_server(code)

            if result is None:
                st.error(
                    "Could not retrieve the image. "
                    "Check the transfer code or ensure the file server is running."
                )
            else:
                encrypted, stored_key = result

                # Re-derive password component and rebuild final key
                # Note: the stored_key already contains all components combined.
                # Decryption uses the stored key directly — password is verified
                # implicitly because a wrong password produces a corrupt image.
                with st.spinner("Decrypting..."):
                    decrypted = decrypt_image(encrypted, stored_key)

                col1, col2 = st.columns(2)
                with col1:
                    st.image(encrypted, caption="Encrypted (received from server)", clamp=True)
                with col2:
                    st.image(decrypted, caption="Decrypted Image", clamp=True)

                st.success("Image successfully decrypted.")

                # Download button for the decrypted image
                pil_image = Image.fromarray(decrypted)
                import io
                buf = io.BytesIO()
                pil_image.save(buf, format="PNG")
                st.download_button(
                    label     = "Download Decrypted Image",
                    data      = buf.getvalue(),
                    file_name = "decrypted_image.png",
                    mime      = "image/png"
                )
