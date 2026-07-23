import os
import json
import logging
import urllib.request
import jwt
import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, status
from cryptography.x509 import load_pem_x509_certificate

logger = logging.getLogger("firebase")

FIREBASE_INITIALIZED = False
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "visageattend-2uiuc")

# Try initializing Firebase Admin SDK
try:
    firebase_admin.get_app()
    FIREBASE_INITIALIZED = True
    logger.info("Firebase Admin SDK already initialized.")
except ValueError:
    cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    cred_path = os.getenv("FIREBASE_CREDENTIALS_JSON_PATH")

    try:
        if cred_json:
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            FIREBASE_INITIALIZED = True
            logger.info("Firebase Admin SDK successfully initialized using JSON env variable.")
        elif cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            FIREBASE_INITIALIZED = True
            logger.info(f"Firebase Admin SDK successfully initialized using key file: {cred_path}")
        else:
            firebase_admin.initialize_app()
            FIREBASE_INITIALIZED = True
            logger.info("Firebase Admin SDK initialized using Google Application Default Credentials.")
    except Exception as e:
        logger.warning(
            f"Firebase Admin SDK could not be initialized: {e}.\n"
            "Falling back to manual public-key signature verification for Firebase tokens."
        )
        FIREBASE_INITIALIZED = False

# Cache for Google's public certificates
_google_certs_cache = {}

def fetch_google_public_keys():
    global _google_certs_cache
    if _google_certs_cache:
        return _google_certs_cache
    try:
        url = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
        logger.info(f"Fetching Google public certificates from: {url}")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            certs = json.loads(response.read().decode())
            _google_certs_cache = certs
            logger.info("Successfully fetched and cached Google certificates.")
            return certs
    except Exception as e:
        logger.error(f"Error fetching Google public certificates: {e}")
        return {}

def verify_firebase_token_manual(id_token: str) -> dict:
    """
    Manually decodes and verifies a Firebase ID token using public certificates
    without relying on the Firebase Admin SDK credentials.
    """
    try:
        logger.info("Starting manual Firebase token verification...")
        # 1. Unverified decode to inspect headers
        headers = jwt.get_unverified_header(id_token)
        kid = headers.get("kid")
        if not kid:
            raise Exception("No 'kid' claim in JWT header")
        logger.info(f"Unverified JWT header kid claim: {kid}")

        # 2. Get public keys matching the key ID
        certs = fetch_google_public_keys()
        cert_pem = certs.get(kid)
        if not cert_pem:
            # Refresh cache and try again
            logger.info("Key ID not found in cache. Refreshing Google certificates...")
            global _google_certs_cache
            _google_certs_cache = {}
            certs = fetch_google_public_keys()
            cert_pem = certs.get(kid)
            if not cert_pem:
                raise Exception(f"Public key for kid '{kid}' not found in Google certificates")

        # 3. Load the public key from the X.509 certificate PEM string
        try:
            cert_obj = load_pem_x509_certificate(cert_pem.encode())
            public_key = cert_obj.public_key()
        except Exception as cert_err:
            logger.error(f"Error loading public key from certificate: {cert_err}")
            raise Exception("Could not parse Google's public certificate key")

        # 4. Decode and verify using PyJWT
        project_id = os.getenv("FIREBASE_PROJECT_ID", "visageattend-2uiuc")
        logger.info(f"Decoding token for project ID: {project_id}")
        
        decoded = jwt.decode(
            id_token,
            public_key,  # type: ignore
            algorithms=["RS256"],
            audience=project_id,
            issuer=f"https://securetoken.google.com/{project_id}",
            leeway=300  # 5 minutes leeway for clock skew
        )
        logger.info("Manual token verification succeeded.")
        return decoded
    except Exception as e:
        logger.error(f"Manual Firebase token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase ID token: {str(e)}"
        )

def verify_firebase_token(id_token: str) -> dict:
    """
    Verifies a Firebase ID token sent from the client.
    First tries via Firebase Admin SDK (if initialized), then falls back to manual verification.
    """
    # Check for mock token fallback (only if specifically designated and in local/dev mode)
    if id_token.startswith("mock_firebase_token_"):
        env = os.getenv("ENV", "development").lower()
        if env == "production":
            logger.error("Attempted to use mock Firebase token in production mode! Rejected.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Security validation error: Mock authentication is disabled in production."
            )
        logger.info("Detected mock Firebase token prefix. Returning mock claims.")
        parts = id_token.split("_")
        username = parts[3] if len(parts) > 3 else "mock_student"
        email = f"{username}@example.com"
        uid = f"mock-uid-{username}"
        return {
            "uid": uid,
            "email": email,
            "name": username.replace(".", " ").title(),
            "firebase": {"sign_in_provider": "google.com"}
        }

    if FIREBASE_INITIALIZED:
        try:
            logger.info("Attempting to verify token via Firebase Admin SDK...")
            claims = auth.verify_id_token(id_token)
            logger.info("Firebase Admin SDK token verification succeeded.")
            return claims
        except Exception as e:
            logger.warning(f"Admin SDK token verification failed: {e}. Trying manual verification fallback.")
            return verify_firebase_token_manual(id_token)
    else:
        logger.info("Firebase Admin SDK not initialized. Using manual verification.")
        return verify_firebase_token_manual(id_token)
