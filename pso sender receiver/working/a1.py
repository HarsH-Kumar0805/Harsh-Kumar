
import streamlit as st
import numpy as np
import cv2
import hashlib
import random
import string
import json
import os
from PIL import Image

st.set_page_config(page_title="PSO Secure Transfer", layout="centered")

STORAGE_DIR = "storage"
os.makedirs(STORAGE_DIR, exist_ok=True)

# generate code
def generate_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

# PSO
class PSO:
    def __init__(self, n_particles, dimensions, max_iter):
        self.n_particles = n_particles
        self.dimensions = dimensions
        self.max_iter = max_iter
        self.positions = np.random.randint(0, 256, (n_particles, dimensions))
        self.velocities = np.random.randn(n_particles, dimensions)
        self.pbest_pos = self.positions.copy()
        self.pbest_scores = np.full(n_particles, np.inf)
        self.gbest_pos = None
        self.gbest_score = np.inf

    def fitness(self, particle):
        hist, _ = np.histogram(particle, bins=256, range=(0,255))
        prob = hist / np.sum(hist)
        prob = prob[prob > 0]
        return -np.sum(prob * np.log2(prob))

    def optimize(self):
        w, c1, c2 = 0.7, 1.5, 1.5
        for _ in range(self.max_iter):
            for i in range(self.n_particles):
                score = self.fitness(self.positions[i])
                if score < self.pbest_scores[i]:
                    self.pbest_scores[i] = score
                    self.pbest_pos[i] = self.positions[i]
                if score < self.gbest_score:
                    self.gbest_score = score
                    self.gbest_pos = self.positions[i]
            for i in range(self.n_particles):
                r1, r2 = np.random.rand(), np.random.rand()
                self.velocities[i] = (
                    w * self.velocities[i]
                    + c1 * r1 * (self.pbest_pos[i] - self.positions[i])
                    + c2 * r2 * (self.gbest_pos - self.positions[i])
                )
                self.positions[i] = np.clip(
                    self.positions[i] + self.velocities[i], 0, 255
                ).astype(np.uint8)
        return self.gbest_pos

# password key
def password_to_key(password, size):
    raw = hashlib.sha256(password.encode()).digest()
    key = np.frombuffer(raw, dtype=np.uint8)
    return np.tile(key, size // len(key) + 1)[:size]

# diffusion
def diffuse(flat, key):
    flat = flat.astype(np.int32).copy()
    for i in range(1, len(flat)):
        flat[i] = ((flat[i] ^ key[i]) + flat[i-1]) % 256
    return flat.astype(np.uint8)

def inverse_diffuse(flat, key):
    flat = flat.astype(np.int32).copy()
    for i in range(len(flat)-1, 0, -1):
        flat[i] = ((flat[i] - flat[i-1]) ^ key[i]) % 256
    return flat.astype(np.uint8)

# encrypt
def encrypt_image(image, key):
    xored = np.bitwise_xor(image.flatten(), key)
    return diffuse(xored, key).reshape(image.shape)

# decrypt
def decrypt_image(encrypted, key):
    undiff = inverse_diffuse(encrypted.flatten(), key)
    return np.bitwise_xor(undiff, key).reshape(encrypted.shape)

# UI
st.title("PSO Secure Image Transfer")

mode = st.radio("Mode", ["Sender", "Receiver"])

# Sender
if mode == "Sender":
    file = st.file_uploader("Upload Image")
    password = st.text_input("Password", type="password")

    if file and password:
        if st.button("Encrypt & Send"):
            image = np.array(Image.open(file).convert("L"))
            image = cv2.resize(image, (256,256))

            dim = image.size
            pso_key = PSO(8, dim, 15).optimize()
            pass_key = password_to_key(password, dim)
            final_key = np.bitwise_xor(pso_key, pass_key)

            encrypted = encrypt_image(image, final_key)

            code = generate_code()

            # save to file
            data = {
                "encrypted": encrypted.flatten().tolist(),
                "key": final_key.tolist(),
                "shape": image.shape
            }

            with open(f"{STORAGE_DIR}/{code}.json", "w") as f:
                json.dump(data, f)

            st.success(f"Code: {code}")
            st.image(encrypted, caption="Encrypted")

# Receiver
else:
    code = st.text_input("Enter Code")
    password = st.text_input("Password", type="password")

    if st.button("Receive"):
        path = f"{STORAGE_DIR}/{code}.json"

        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)

            encrypted = np.array(data["encrypted"], dtype=np.uint8).reshape(data["shape"])
            key = np.array(data["key"], dtype=np.uint8)

            decrypted = decrypt_image(encrypted, key)

            col1, col2 = st.columns(2)
            with col1:
                st.image(encrypted, caption="Encrypted")
            with col2:
                st.image(decrypted, caption="Decrypted")

            st.success("Success")
        else:
            st.error("Invalid Code")
