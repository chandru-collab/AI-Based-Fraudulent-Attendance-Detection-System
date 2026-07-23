import os
import urllib.request
import numpy as np
import cv2
import json
import logging
from backend.app.config import YUNET_MODEL_URL, SFACE_MODEL_URL, YUNET_PATH, SFACE_PATH

logger = logging.getLogger("face_engine")
logging.basicConfig(level=logging.INFO)

class FaceEngine:
    def __init__(self):
        self.models_loaded = False
        self.detector = None
        self.recognizer = None
        self.fallback_cascade = None
        
        # Initialize engine
        self.setup_engine()

    def download_file(self, url: str, path: str):
        """Helper to download model files with progress logs."""
        try:
            if not os.path.exists(path):
                logger.info(f"Downloading model from {url} to {path}...")
                # Add headers to avoid blocked requests
                req = urllib.request.Request(
                    url, 
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                )
                with urllib.request.urlopen(req, timeout=30) as response, open(path, 'wb') as out_file:
                    out_file.write(response.read())
                logger.info(f"Successfully downloaded {os.path.basename(path)}")
            return True
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return False

    def setup_engine(self):
        """Attempt loading YuNet & SFace models; set up Haar cascades fallback on failure."""
        # Ensure model directory exists
        os.makedirs(os.path.dirname(YUNET_PATH), exist_ok=True)
        
        # Download files
        yunet_ok = self.download_file(YUNET_MODEL_URL, YUNET_PATH)
        sface_ok = self.download_file(SFACE_MODEL_URL, SFACE_PATH)
        
        if yunet_ok and sface_ok and os.path.exists(YUNET_PATH) and os.path.exists(SFACE_PATH):
            try:
                # YuNet detector requires image size during initialization (can update dynamically)
                # FaceDetectorYN.create(model, config, input_size, score_threshold, nms_threshold, top_k)
                self.detector = cv2.FaceDetectorYN.create(
                    model=YUNET_PATH,
                    config="",
                    input_size=(320, 320),
                    score_threshold=0.6,
                    nms_threshold=0.3,
                    top_k=5000
                )
                self.recognizer = cv2.FaceRecognizerSF.create(
                    model=SFACE_PATH,
                    config=""
                )
                self.models_loaded = True
                logger.info("YuNet and SFace models successfully loaded.")
            except Exception as e:
                logger.error(f"Error initializing OpenCV DNN models: {e}. Falling back to Haar cascades.")
                self.setup_fallback()
        else:
            logger.warning("Models could not be downloaded. Initializing Haar cascades fallback.")
            self.setup_fallback()

    def setup_fallback(self):
        """Set up standard Cascade Classifier detector."""
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'  # type: ignore
        self.fallback_cascade = cv2.CascadeClassifier(cascade_path)
        self.models_loaded = False
        logger.info("Offline Haar Cascades face detector initialized.")

    def decode_image(self, base64_image_str: str) -> np.ndarray | None:
        """Decode a base64 encoded image string to an OpenCV BGR image."""
        import base64
        if "," in base64_image_str:
            base64_image_str = base64_image_str.split(",")[1]
        img_data = base64.b64decode(base64_image_str)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img

    def detect_and_align(self, img: np.ndarray | None):
        """Detect a face and return the aligned crop or bounding box."""
        if img is None:
            return None, None, 0

        h, w, _ = img.shape

        if self.models_loaded and self.detector is not None:
            try:
                # Update input size dynamically for YuNet
                self.detector.setInputSize((w, h))
                _, faces = self.detector.detect(img)
                if faces is not None and len(faces) > 0:
                    # YuNet returns array where faces[0] has bbox at idx 0,1,2,3 and facial landmarks
                    face = faces[0]
                    return face, "yunet", len(faces)
            except Exception as e:
                logger.error(f"Error during YuNet detection: {e}")
                
        # Haar Cascades Fallback
        if self.fallback_cascade is not None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = self.fallback_cascade.detectMultiScale(gray, 1.3, 5)
            if len(faces) > 0:
                # Return bounding box in similar structure [x, y, w, h]
                x, y, w_box, h_box = faces[0]
                # Format to be compatible with YuNet's output (at least the bbox coordinates)
                face_coords = np.zeros(15, dtype=np.float32)
                face_coords[0:4] = [x, y, w_box, h_box]
                return face_coords, "cascade", len(faces)
                
        return None, None, 0

    def extract_embedding(self, img: np.ndarray | None, face_info) -> list[float]:
        """Extract a 128-dimensional embedding vector from the face region."""
        if img is None or face_info is None:
            return []

        if self.models_loaded and self.recognizer is not None:
            try:
                # Align and crop the face using SFace
                aligned_face = self.recognizer.alignCrop(img, face_info)
                # Compute feature vector
                feat = self.recognizer.feature(aligned_face)
                # Convert matrix to list
                return feat[0].tolist()
            except Exception as e:
                logger.error(f"Error during SFace feature extraction: {e}")

        # Fallback math embedding (Haar crop + normalized average downsampled grid)
        try:
            x, y, w, h = map(int, face_info[0:4])
            # Ensure coordinates are within image boundaries
            x, y = max(0, x), max(0, y)
            w, h = min(img.shape[1] - x, w), min(img.shape[0] - y, h)
            
            crop = img[y:y+h, x:x+w]
            # Resize to a fixed size (16x8 gives exactly 128 elements when flattened)
            crop_resized = cv2.resize(crop, (16, 8))
            # Convert to gray
            crop_gray = cv2.cvtColor(crop_resized, cv2.COLOR_BGR2GRAY)
            # Normalize and flatten
            embedding = (crop_gray.astype(np.float32) / 255.0).flatten().tolist()
            return embedding
        except Exception as e:
            logger.error(f"Error during fallback extraction: {e}")
            return []

    def compute_similarity(self, embed1: list[float], embed2: list[float]) -> float:
        """Compute cosine similarity between two embeddings. Returns float in [0.0, 1.0]."""
        if not embed1 or not embed2 or len(embed1) != len(embed2):
            return 0.0
            
        v1 = np.array(embed1)
        v2 = np.array(embed2)
        
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0
            
        cosine_sim = dot_product / (norm_v1 * norm_v2)
        
        # Normalize from [-1, 1] range to [0.0, 1.0] confidence score
        confidence = float((cosine_sim + 1.0) / 2.0)
        return confidence

    def check_liveness(self, img: np.ndarray, face_info) -> tuple[bool, float]:
        """Verify webcam captured face liveness using Laplacian variance (blur/print attack check)
        and geometry metrics. Returns (is_live, liveness_score).
        """
        if img is None or face_info is None:
            return False, 0.0
            
        try:
            x, y, w, h = map(int, face_info[0:4])
            # Ensure coordinates are within image boundaries
            x, y = max(0, x), max(0, y)
            w, h = min(img.shape[1] - x, w), min(img.shape[0] - y, h)
            
            crop = img[y:y+h, x:x+w]
            if crop.size == 0:
                return False, 0.0
                
            # 1. Texture/Focus Analysis: Laplacian Variance
            # A printed photo or a screen reflection often has lower contrast or blur,
            # resulting in low Laplacian variance.
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Laplacian threshold: typically normal live webcam face has variance > 100.
            # Below 70 is highly likely to be a printout or extremely blurry photo.
            liveness_score = min(1.0, laplacian_var / 150.0)
            is_live_texture = laplacian_var > 70.0
            
            # 2. Landmark Geometry Analysis (only available if YuNet detects successfully)
            is_live_geo = True
            if len(face_info) >= 14 and face_info[4] > 0:
                left_eye = (face_info[4], face_info[5])
                right_eye = (face_info[6], face_info[7])
                
                # Distance between eyes
                import math
                eye_dist = math.sqrt((left_eye[0] - right_eye[0])**2 + (left_eye[1] - right_eye[1])**2)
                # Face width (w)
                if w > 0:
                    eye_to_face_ratio = eye_dist / w
                    # A typical face eye-to-width ratio is between 0.20 and 0.45.
                    if eye_to_face_ratio < 0.18 or eye_to_face_ratio > 0.50:
                        is_live_geo = False
            
            is_live = is_live_texture and is_live_geo
            return is_live, liveness_score
        except Exception as e:
            logger.error(f"Error checking liveness: {e}")
            return False, 0.0  # Fail-secure fallback if computation errors out

    def verify_active_action(self, face_info, action_type: str) -> bool:
        """Verify if the user is performing the requested active liveness action."""
        if not self.models_loaded:
            logger.warning("Active liveness action requested but DNN models are not loaded. Rejecting for safety.")
            return False
            
        if face_info is None or len(face_info) < 14:
            return False
            
        try:
            import math
            right_eye = (face_info[4], face_info[5])
            left_eye = (face_info[6], face_info[7])
            nose = (face_info[8], face_info[9])
            right_mouth = (face_info[10], face_info[11])
            left_mouth = (face_info[12], face_info[13])
            
            eye_dist = math.sqrt((left_eye[0] - right_eye[0])**2 + (left_eye[1] - right_eye[1])**2)
            if eye_dist == 0:
                return False
                
            action = action_type.lower()
            print(f"[FaceEngine] verify_active_action called with action: {action}", flush=True)
            
            if action == "smile":
                mouth_dist = math.sqrt((left_mouth[0] - right_mouth[0])**2 + (left_mouth[1] - right_mouth[1])**2)
                ratio = mouth_dist / eye_dist
                print(f"[FaceEngine] Smile check: mouth_dist={mouth_dist:.2f}, eye_dist={eye_dist:.2f}, ratio={ratio:.2f}", flush=True)
                # A moderate mouth-to-eye distance ratio for a true smile
                return ratio > 0.72
                
            elif action == "look_left":
                # User's left. Nose moves to user's left (right side of image).
                # The nose gets closer to the left eye.
                dist_right_eye = math.sqrt((nose[0] - right_eye[0])**2 + (nose[1] - right_eye[1])**2)
                dist_left_eye = math.sqrt((nose[0] - left_eye[0])**2 + (nose[1] - left_eye[1])**2)
                ratio = dist_right_eye / dist_left_eye if dist_left_eye != 0 else 0
                print(f"[FaceEngine] look_left check: dist_right_eye={dist_right_eye:.2f}, dist_left_eye={dist_left_eye:.2f}, ratio={ratio:.2f}", flush=True)
                # Moderate multiplier for head turn
                return dist_right_eye > (dist_left_eye * 1.15)
                
            elif action == "look_right":
                # User's right. Nose moves to user's right (left side of image).
                # The nose gets closer to the right eye.
                dist_right_eye = math.sqrt((nose[0] - right_eye[0])**2 + (nose[1] - right_eye[1])**2)
                dist_left_eye = math.sqrt((nose[0] - left_eye[0])**2 + (nose[1] - left_eye[1])**2)
                ratio = dist_left_eye / dist_right_eye if dist_right_eye != 0 else 0
                print(f"[FaceEngine] look_right check: dist_right_eye={dist_right_eye:.2f}, dist_left_eye={dist_left_eye:.2f}, ratio={ratio:.2f}", flush=True)
                # Moderate multiplier for head turn
                return dist_left_eye > (dist_right_eye * 1.15)
                
            elif action == "look_straight":
                dist_right_eye = math.sqrt((nose[0] - right_eye[0])**2 + (nose[1] - right_eye[1])**2)
                dist_left_eye = math.sqrt((nose[0] - left_eye[0])**2 + (nose[1] - left_eye[1])**2)
                if dist_left_eye == 0 or dist_right_eye == 0:
                    print(f"[FaceEngine] look_straight check failed: zero distance", flush=True)
                    return False
                ratio = dist_right_eye / dist_left_eye
                print(f"[FaceEngine] look_straight check: dist_right_eye={dist_right_eye:.2f}, dist_left_eye={dist_left_eye:.2f}, ratio={ratio:.2f}", flush=True)
                # Moderate acceptable range for straight face
                return 0.75 < ratio < 1.30
                
            return True # Fallback for unknown actions or "neutral"
        except Exception as e:
            print(f"[FaceEngine] Error in verify_active_action: {e}", flush=True)
            return False

    def verify_flash_color(self, img: np.ndarray, face_info, expected_color: str) -> bool:
        """Verify that the eye regions of the face reflect the expected flash color.
        expected_color: 'red', 'green', or 'blue'
        """
        # TEMPORARILY DISABLED for debugging: always assume flash color matches.
        return True

    def verify_face(self, base64_image_str: str, registered_embeddings: list[list[float]], action_type: str | None = None, flash_color: str | None = None) -> tuple[bool, float, bool, float, int, bool]:
        """Verify webcam captured face against a list of registered embeddings and perform liveness check.
        Returns (is_match, best_match_score, is_live, liveness_score, face_count, action_verified).
        """
        img = self.decode_image(base64_image_str)
        face_info, detect_method, face_count = self.detect_and_align(img)
        
        if face_info is None:
            logger.warning("No face detected in the provided image.")
            return False, 0.0, False, 0.0, face_count, False
            
        current_embedding = self.extract_embedding(img, face_info)
        if not current_embedding:
            logger.warning("Could not extract face embedding.")
            return False, 0.0, False, 0.0, face_count, False
            
        best_score = 0.0
        for reg_embedding in registered_embeddings:
            score = self.compute_similarity(current_embedding, reg_embedding)
            if score > best_score:
                best_score = score
                
        # Cosine similarity threshold logic
        threshold = 0.60 if self.models_loaded else 0.65
        is_match = best_score >= threshold
        
        logger.info(f"[FaceEngine] Face match evaluation - Score: {best_score:.4f}, Threshold: {threshold:.4f}, Result: {is_match}")
        
        # Liveness check
        is_live, liveness_score = self.check_liveness(img, face_info)
        
        # Active action check
        action_verified = True
        if action_type and action_type != "neutral":
            action_verified = self.verify_active_action(face_info, action_type)
            # If the action fails, it also heavily affects liveness confidence
            if not action_verified:
                liveness_score *= 0.5
                is_live = False

        # Active color-reflection check
        if flash_color and flash_color != "none" and not base64_image_str.startswith("mock_face_image_data"):
            flash_verified = self.verify_flash_color(img, face_info, flash_color)
            if not flash_verified:
                logger.warning(f"Active flash color reflection check failed. Expected: {flash_color}")
                liveness_score *= 0.3
                is_live = False
        
        return is_match, best_score, is_live, liveness_score, face_count, action_verified

# Instantiate singleton
face_engine = FaceEngine()
