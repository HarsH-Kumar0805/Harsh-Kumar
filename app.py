import streamlit as st
import numpy as np
import cv2
from PIL import Image
import hashlib

st.set_page_config(page_title="PSO Image Encryption", layout="centered")

# --- Chaotic key via logistic map (seeded from image content) ---
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


# --- PSO optimiser for key generation ---
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
def generate_random_key(size):
    # Replace password-based key with a random key
    return np.random.randint(0, 256, size, dtype=np.uint8)


def combine_keys(k1, k2, k3):
    return np.bitwise_xor(np.bitwise_xor(k1, k2), k3)


# --- Diffusion layer ---
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


# --- Encryption and decryption ---
def encrypt_image(image, pso_key, random_key):
    size      = image.size
    chaos_key = logistic_map_key(image_seed(image), size)
    final_key = combine_keys(pso_key[:size], random_key[:size], chaos_key)

    xored    = np.bitwise_xor(image.flatten(), final_key)
    diffused = diffuse(xored, final_key)
    return diffused.reshape(image.shape), final_key


def decrypt_image(encrypted, final_key):
    undiffused = inverse_diffuse(encrypted.flatten(), final_key)
    plaintext  = np.bitwise_xor(undiffused, final_key)
    return plaintext.reshape(encrypted.shape)


# --- Security metrics ---
def entropy(image):
    hist, _ = np.histogram(image.flatten(), bins=256, range=(0, 255))
    prob = hist / np.sum(hist)
    prob = prob[prob > 0]
    return float(-np.sum(prob * np.log2(prob)))


def correlation(image):
    flat = image.flatten().astype(np.float64)
    return float(np.corrcoef(flat[:-1], flat[1:])[0, 1])


def npcr(img1, img2):
    return float(np.sum(img1 != img2) / img1.size * 100)


def uaci(img1, img2):
    return float(
        np.mean(np.abs(img1.astype(np.float64) - img2.astype(np.float64)) / 255) * 100
    )


# --- Main app ---
st.title("PSO Image Encryption")

uploaded_file = st.file_uploader("Upload a grayscale-compatible image", type=["jpg", "png", "jpeg"])

if uploaded_file:
    image = np.array(Image.open(uploaded_file).convert("L"))
    image = cv2.resize(image, (256, 256))

    st.image(image, caption="Original Image", clamp=True)

    dimensions  = image.size
    random_key  = generate_random_key(dimensions)

    with st.spinner("Running PSO optimisation..."):
        pso_key = PSO(n_particles=8, dimensions=dimensions, max_iter=15).optimize()

    encrypted, final_key = encrypt_image(image, pso_key, random_key)

    modified       = image.copy()
    modified[0, 0] = np.uint8((int(modified[0, 0]) + 1) % 256)
    encrypted2, _  = encrypt_image(modified, pso_key, random_key)

    decrypted = decrypt_image(encrypted, final_key)

    col1, col2 = st.columns(2)
    with col1:
        st.image(encrypted, caption="Encrypted Image", clamp=True)
    with col2:
        st.image(decrypted, caption="Decrypted Image", clamp=True)

    st.subheader("Security Analysis")

    r1c1, r1c2 = st.columns(2)
    r1c1.metric("Original Entropy",  f"{entropy(image):.4f}")
    r1c2.metric("Encrypted Entropy", f"{entropy(encrypted):.4f}", delta="Ideal = 8.0")

    r2c1, r2c2 = st.columns(2)
    r2c1.metric("Original Correlation",  f"{correlation(image):.4f}")
    r2c2.metric("Encrypted Correlation", f"{correlation(encrypted):.4f}", delta="Ideal = 0.0")

    r3c1, r3c2 = st.columns(2)
    r3c1.metric("NPCR (%)", f"{npcr(encrypted, encrypted2):.4f}", delta="Ideal = 99.6")
    r3c2.metric("UACI (%)", f"{uaci(encrypted, encrypted2):.4f}", delta="Ideal = 33.4")

    if np.array_equal(image, decrypted):
        st.success("Decryption verified: output matches original.")
    else:
        st.error("Decryption mismatch: output does not match original.")
