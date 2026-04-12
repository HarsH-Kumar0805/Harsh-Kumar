import streamlit as st
import numpy as np
import cv2
from PIL import Image
import hashlib

st.set_page_config(page_title="Image Encryption PSO", layout="centered")

ALLOWED_PASSWORD = "harsh123"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def login():
    st.title("Login")
    password = st.text_input("Enter Password", type="password")
    if st.button("Login"):
        if password == ALLOWED_PASSWORD:
            st.session_state.logged_in = True
        else:
            st.error("Invalid Password")

def logout():
    if st.button("Logout"):
        st.session_state.logged_in = False

class PSO:
    def __init__(self, n_particles, dimensions, max_iter):
        self.n_particles = n_particles
        self.dimensions = dimensions
        self.max_iter = max_iter
        self.positions = np.random.randint(0, 256, (n_particles, dimensions))
        self.velocities = np.random.randn(n_particles, dimensions)
        self.pbest_positions = self.positions.copy()
        self.pbest_scores = np.full(n_particles, np.inf)
        self.gbest_position = None
        self.gbest_score = np.inf

    def fitness(self, particle):
        hist, _ = np.histogram(particle, bins=256, range=(0,255))
        prob = hist / np.sum(hist)
        prob = prob[prob > 0]
        entropy = -np.sum(prob * np.log2(prob))
        return -entropy

    def optimize(self):
        w, c1, c2 = 0.7, 1.5, 1.5
        for _ in range(self.max_iter):
            for i in range(self.n_particles):
                score = self.fitness(self.positions[i])
                if score < self.pbest_scores[i]:
                    self.pbest_scores[i] = score
                    self.pbest_positions[i] = self.positions[i]
                if score < self.gbest_score:
                    self.gbest_score = score
                    self.gbest_position = self.positions[i]
            for i in range(self.n_particles):
                r1, r2 = np.random.rand(), np.random.rand()
                self.velocities[i] = (
                    w * self.velocities[i]
                    + c1 * r1 * (self.pbest_positions[i] - self.positions[i])
                    + c2 * r2 * (self.gbest_position - self.positions[i])
                )
                self.positions[i] = self.positions[i] + self.velocities[i]
                self.positions[i] = np.clip(self.positions[i], 0, 255).astype(np.uint8)
        return self.gbest_position

def password_to_key(password, size):
    hash_bytes = hashlib.sha256(password.encode()).digest()
    key = np.frombuffer(hash_bytes, dtype=np.uint8)
    return np.tile(key, size // len(key) + 1)[:size]

def combine_keys(pso_key, password_key):
    return np.bitwise_xor(pso_key, password_key)

def encrypt_image(image, key):
    key_matrix = key[:image.size].reshape(image.shape)
    return np.bitwise_xor(image, key_matrix)

def decrypt_image(encrypted, key):
    key_matrix = key[:encrypted.size].reshape(encrypted.shape)
    return np.bitwise_xor(encrypted, key_matrix)

if not st.session_state.logged_in:
    login()
    st.stop()

st.title("Image Encryption Using PSO")
logout()

uploaded_file = st.file_uploader("Upload Image", type=["jpg", "png", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file).convert("L")
    image = np.array(image)
    image = cv2.resize(image, (256, 256))

    st.image(image, caption="Original Image", use_container_width=True)

    password = ALLOWED_PASSWORD
    dimensions = image.size

    pso = PSO(n_particles=8, dimensions=dimensions, max_iter=15)
    pso_key = pso.optimize()

    password_key = password_to_key(password, dimensions)
    final_key = combine_keys(pso_key, password_key)

    encrypted = encrypt_image(image, final_key)
    decrypted = decrypt_image(encrypted, final_key)

    col1, col2 = st.columns(2)

    with col1:
        st.image(encrypted, caption="Encrypted Image", use_container_width=True)

    with col2:
        st.image(decrypted, caption="Decrypted Image", use_container_width=True)

    cv2.imwrite("encrypted.png", encrypted)
    cv2.imwrite("decrypted.png", decrypted)

    st.success("Process Completed")