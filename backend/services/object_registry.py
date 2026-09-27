"""
Dynamic Object Registry — Runtime Object Registration via ORB Descriptors.
Enables instant registration of novel tools/samples without retraining AI models.
"""
import os
import glob
import json
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_OBJECTS_DIR = BASE_DIR / "storage" / "objects"
STORAGE_OBJECTS_DIR.mkdir(parents=True, exist_ok=True)


class DynamicObjectRegistry:
    """Manages ORB descriptors for runtime dynamically registered tools and containers."""

    def __init__(self):
        self.orb = cv2.ORB_create(nfeatures=500)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self.registered_descriptors: Dict[str, List[np.ndarray]] = {}
        self.load_all_registered()

    def load_all_registered(self):
        """Load all registered object descriptors from disk on startup."""
        for slug_dir in STORAGE_OBJECTS_DIR.iterdir():
            if slug_dir.is_dir():
                manifest_file = slug_dir / "manifest.json"
                if manifest_file.exists():
                    self.load_dynamic_object(slug_dir.name)

    def load_dynamic_object(self, slug: str) -> int:
        """Extracts and caches ORB keypoint descriptors for an object's reference photos."""
        obj_dir = STORAGE_OBJECTS_DIR / slug
        if not obj_dir.exists():
            return 0

        descriptors_list = []
        image_files = sorted(glob.glob(str(obj_dir / "capture_*.jpg")))
        for img_path in image_files:
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                _, des = self.orb.detectAndCompute(img, None)
                if des is not None and len(des) > 0:
                    descriptors_list.append(des)

        self.registered_descriptors[slug] = descriptors_list
        logger.info(f"Loaded {len(descriptors_list)} reference descriptors for dynamic object '{slug}'")
        return len(descriptors_list)

    def detect_object(self, frame: np.ndarray, slug: str, min_matches: int = 15) -> bool:
        """Evaluates whether the dynamic object is present in the frame using ORB feature matching."""
        ref_descriptors = self.registered_descriptors.get(slug, [])
        if not ref_descriptors or frame is None:
            return False

        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            _, des_query = self.orb.detectAndCompute(gray, None)
            if des_query is None or len(des_query) == 0:
                return False

            best_match_count = 0
            for des_train in ref_descriptors:
                matches = self.bf.match(des_query, des_train)
                # Keep good matches with low Hamming distance
                good_matches = [m for m in matches if m.distance < 50.0]
                if len(good_matches) > best_match_count:
                    best_match_count = len(good_matches)
                if best_match_count >= min_matches:
                    return True
        except Exception as exc:
            logger.debug(f"ORB matching error for '{slug}': {exc}")

        return False

    def list_objects(self) -> List[Dict[str, Any]]:
        objects = []
        for slug_dir in STORAGE_OBJECTS_DIR.iterdir():
            if slug_dir.is_dir():
                manifest_file = slug_dir / "manifest.json"
                img_count = len(glob.glob(str(slug_dir / "capture_*.jpg")))
                if manifest_file.exists():
                    try:
                        with open(manifest_file, "r") as f:
                            data = json.load(f)
                        data["image_count"] = img_count
                        data["registered"] = True
                        objects.append(data)
                    except Exception:
                        pass
                else:
                    objects.append({
                        "slug": slug_dir.name,
                        "name": slug_dir.name.replace("_", " ").title(),
                        "image_count": img_count,
                        "registered": False,
                        "created_at": None,
                    })
        return objects

    def capture_frame(self, slug: str, frame: np.ndarray) -> int:
        obj_dir = STORAGE_OBJECTS_DIR / slug
        obj_dir.mkdir(parents=True, exist_ok=True)
        existing = glob.glob(str(obj_dir / "capture_*.jpg"))
        next_idx = len(existing) + 1
        path = obj_dir / f"capture_{next_idx}.jpg"
        cv2.imwrite(str(path), frame)
        return next_idx

    def finalize_registration(self, slug: str, display_name: str) -> Dict[str, Any]:
        obj_dir = STORAGE_OBJECTS_DIR / slug
        if not obj_dir.exists():
            raise FileNotFoundError(f"No captured images found for '{slug}'")

        images = glob.glob(str(obj_dir / "capture_*.jpg"))
        if len(images) < 3:
            raise ValueError(f"Need at least 3 reference images, got {len(images)}")

        loaded_count = self.load_dynamic_object(slug)
        manifest = {
            "slug": slug,
            "name": display_name,
            "image_count": len(images),
            "orb_refs_loaded": loaded_count,
            "registered": True,
            "created_at": datetime.now().isoformat(),
        }
        with open(obj_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        return manifest

    def delete_object(self, slug: str) -> bool:
        import shutil
        obj_dir = STORAGE_OBJECTS_DIR / slug
        if obj_dir.exists():
            shutil.rmtree(str(obj_dir))
            self.registered_descriptors.pop(slug, None)
            return True
        return False


dynamic_object_registry = DynamicObjectRegistry()
