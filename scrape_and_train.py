"""
Vault-OS Scraper & Trainer
Scrapes face images from Bing and trains the LBPH face recognition model.
"""
import os
import re
import cv2
import json
import time
import numpy as np
import requests

BROKER_HOST   = "192.168.1.100"
VAULT_NAME    = "vault111"
FACES_DIR     = "faces"
MODELS_DIR    = "models"
MODEL_PATH    = os.path.join(MODELS_DIR, "lbph_model.yml")
LABELS_PATH   = os.path.join(MODELS_DIR, "labels.json")

TARGETS = [
    "Friedrich Merz",
    "Angela Merkel",
]
IMAGES_PER_PERSON = 30

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def scrape_bing_image_urls(query: str, max_images: int = 60) -> list[str]:
    """Scrape direct image URLs from Bing Image Search."""
    from urllib.parse import quote
    urls   = []
    offset = 0

    while len(urls) < max_images:
        search_url = (
            f"https://www.bing.com/images/search"
            f"?q={quote(query + ' portrait face')}"
            f"&count=35&offset={offset}&mkt=de-DE"
        )
        try:
            resp = requests.get(search_url, headers=HEADERS, timeout=10)
            # Bing embeds JSON with "murl" (media URL) keys
            matches = re.findall(r'"murl":"(https?://[^"]+)"', resp.text)
            if not matches:
                break
            urls.extend(matches)
            offset += 35
            time.sleep(0.8)
        except Exception as e:
            print(f"  [WARN] Scrape request failed: {e}")
            break

    return list(dict.fromkeys(urls))[:max_images]  # deduplicate


def download_and_extract_faces(name: str, urls: list[str], target_dir: str, target_count: int = 30) -> int:
    """Download images, extract faces with Haar cascade, save grayscale 200×200 crops."""
    os.makedirs(target_dir, exist_ok=True)
    saved = 0

    for url in urls:
        if saved >= target_count:
            break
        try:
            resp = requests.get(url, headers=HEADERS, timeout=8, stream=True)
            if resp.status_code != 200:
                continue

            img_array = np.frombuffer(resp.content, dtype=np.uint8)
            img       = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if img is None:
                continue

            gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(60, 60))
            if len(faces) == 0:
                continue

            (x, y, w, h) = max(faces, key=lambda r: r[2] * r[3])
            face_crop    = cv2.resize(gray[y : y + h, x : x + w], (200, 200))

            cv2.imwrite(os.path.join(target_dir, f"{saved:04d}.jpg"), face_crop)
            saved += 1
            print(f"  [{name}] {saved}/{target_count} faces saved")

        except Exception as e:
            print(f"  [SKIP] {url[:70]!r}: {e}")

    return saved


def train_lbph():
    """Train LBPH model on all images in FACES_DIR and save to MODEL_PATH."""
    faces_data, labels, label_map = [], [], {}
    label_id = 0

    persons = [d for d in os.listdir(FACES_DIR) if os.path.isdir(os.path.join(FACES_DIR, d))]
    if not persons:
        print("[ERROR] No person folders found in faces/")
        return

    for person in persons:
        person_dir = os.path.join(FACES_DIR, person)
        images     = [f for f in os.listdir(person_dir) if f.endswith(".jpg")]
        label_map[label_id] = person

        for img_file in images:
            img = cv2.imread(os.path.join(person_dir, img_file), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                faces_data.append(img)
                labels.append(label_id)

        print(f"  Loaded {len(images)} images for '{person}' (label {label_id})")
        label_id += 1

    if not faces_data:
        print("[ERROR] No valid images found!")
        return

    print(f"\nTraining LBPH on {len(faces_data)} images ({label_id} persons) ...")
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces_data, np.array(labels))

    os.makedirs(MODELS_DIR, exist_ok=True)
    recognizer.save(MODEL_PATH)
    with open(LABELS_PATH, "w") as f:
        json.dump(label_map, f, indent=2, ensure_ascii=False)

    print(f"[OK] Model  → {MODEL_PATH}")
    print(f"[OK] Labels → {label_map}")


def main():
    print("=" * 50)
    print("  VAULT-OS  ::  SCRAPER & TRAINER")
    print("=" * 50)

    for name in TARGETS:
        print(f"\n[*] Scraping images for: {name}")
        urls = scrape_bing_image_urls(name, max_images=IMAGES_PER_PERSON * 2)
        print(f"  Found {len(urls)} image URLs")

        safe_name  = name.replace(" ", "_")
        target_dir = os.path.join(FACES_DIR, safe_name)
        saved      = download_and_extract_faces(name, urls, target_dir, IMAGES_PER_PERSON)
        print(f"  Saved {saved} face crops for '{name}'")

    print("\n[*] Training LBPH model ...")
    train_lbph()
    print("\n[DONE] Scraping and training complete!")


if __name__ == "__main__":
    main()
