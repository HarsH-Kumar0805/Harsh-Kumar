import streamlit as st
import numpy as np
import cv2
from PIL import Image
import hashlib

st.set_page_config(page_title="PSO Image Encryption", layout="centered")

ALLOWED_PASSWORD = "harsh123"

# login session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# login function
def login():
    st.title("Login")
    password = st.text_input("Enter Password", type="password")
    if st.button("Login"):
        if password == ALLOWED_PASSWORD:
            st.session_state.logged_in = True
        else:
            st.error("Wrong Password")

# logout button
def logout():
    if st.button("Logout"):
        st.session_state.logged_in = False

# PSO class for key generation
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

    # fitness based on entropy
    def fitness(self, particle):
        hist, _ = np.histogram(particle, bins=256, range=(0,255))
        prob = hist / np.sum(hist)
        prob = prob[prob > 0]
        entropy = -np.sum(prob * np.log2(prob))
        return -entropy

    # PSO optimization
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

# convert password into key
def password_to_key(password, size):
    hash_bytes = hashlib.sha256(password.encode()).digest()
    key = np.frombuffer(hash_bytes, dtype=np.uint8)
    return np.tile(key, size // len(key) + 1)[:size]

# combine PSO key and password key
def combine_keys(pso_key, password_key):
    return np.bitwise_xor(pso_key, password_key)

# encryption using XOR
def encrypt_image(image, key):
    key_matrix = key[:image.size].reshape(image.shape)
    return np.bitwise_xor(image, key_matrix)

# decryption using same key
def decrypt_image(encrypted, key):
    key_matrix = key[:encrypted.size].reshape(encrypted.shape)
    return np.bitwise_xor(encrypted, key_matrix)

# entropy calculation
def calculate_entropy(image):
    hist, _ = np.histogram(image.flatten(), bins=256, range=(0,255))
    prob = hist / np.sum(hist)
    prob = prob[prob > 0]
    return -np.sum(prob * np.log2(prob))

# correlation calculation
def calculate_correlation(image):
    image = image.flatten()
    x = image[:-1]
    y = image[1:]
    return np.corrcoef(x, y)[0,1]

# NPCR calculation
def calculate_npcr(img1, img2):
    diff = img1 != img2
    return np.sum(diff) / diff.size * 100

# UACI calculation
def calculate_uaci(img1, img2):
    return np.mean(np.abs(img1 - img2) / 255) * 100

# stop app if not logged in
if not st.session_state.logged_in:
    login()
    st.stop()

st.title("Image Encryption using PSO")
logout()

# upload image
uploaded_file = st.file_uploader("Upload Image", type=["jpg","png","jpeg"])

if uploaded_file:
    # preprocess image
    image = Image.open(uploaded_file).convert("L")
    image = np.array(image)
    image = cv2.resize(image, (256,256))

    st.image(image, caption="Original Image", use_container_width=True)

    # generate key
    password = ALLOWED_PASSWORD
    dimensions = image.size
    pso = PSO(n_particles=8, dimensions=dimensions, max_iter=15)
    pso_key = pso.optimize()
    password_key = password_to_key(password, dimensions)
    final_key = combine_keys(pso_key, password_key)

    # encrypt original
    encrypted = encrypt_image(image, final_key)

    # create slightly modified image for NPCR/UACI
    modified = image.copy()
    modified[0,0] = np.uint8(modified[0,0] + 1)
    encrypted2 = encrypt_image(modified, final_key)

    # decrypt
    decrypted = decrypt_image(encrypted, final_key)

    # display images
    col1, col2 = st.columns(2)
    with col1:
        st.image(encrypted, caption="Encrypted", use_container_width=True)
    with col2:
        st.image(decrypted, caption="Decrypted", use_container_width=True)

    # calculate metrics
    orig_entropy = calculate_entropy(image)
    enc_entropy = calculate_entropy(encrypted)

    orig_corr = calculate_correlation(image)
    enc_corr = calculate_correlation(encrypted)

    npcr = calculate_npcr(encrypted, encrypted2)
    uaci = calculate_uaci(encrypted, encrypted2)

    # display analysis
    st.subheader("Analysis")

    st.write("Original Entropy:", orig_entropy)
    st.write("Encrypted Entropy:", enc_entropy)

    st.write("Original Correlation:", orig_corr)
    st.write("Encrypted Correlation:", enc_corr)

    st.write("NPCR (%):", npcr)
    st.write("UACI (%):", uaci)

    st.success("Encryption Completed")
