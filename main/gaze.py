import os, time, base64, logging
import numpy as np
import cv2, dlib
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .services import GazeService
from .constants import GAZE_DEFAULT_THRESH

gaze_service = GazeService()
logger = logging.getLogger(__name__)

PREDICTOR_PATH = os.path.join(settings.BASE_DIR, 'shape_predictor_68_face_landmarks.dat')
face_detector = dlib.get_frontal_face_detector()
landmark_predictor = dlib.shape_predictor(PREDICTOR_PATH)

CENTER_SCALE_FACTOR = 1.3

def _get_sid(request):
    """Get or create session ID and ensure gaze session is initialized."""
    sid = request.GET.get('sid') or request.POST.get('sid')
    if not sid:
        if not request.session.session_key:
            request.session.save()
        sid = request.session.session_key
    # Ensure initialized in cache via service
    gaze_service.init_session(sid)
    return sid

def shape_to_np(shape, dtype="int"):
    coords = np.zeros((68, 2), dtype=dtype)
    for i in range(68):
        coords[i] = (shape.part(i).x, shape.part(i).y)
    return coords

def get_eye_roi(frame, eye_landmarks, return_mask=False):
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [eye_landmarks], 255)
    eye_roi = cv2.bitwise_and(frame, frame, mask=mask)
    x, y, w, h = cv2.boundingRect(eye_landmarks)
    cropped_roi = eye_roi[y:y + h, x:x + w]
    cropped_mask = mask[y:y + h, x:x + w]
    if return_mask:
        return cropped_roi, cropped_mask, x, y
    return cropped_roi, x, y

def adaptive_threshold_from_eye(eye_gray, eye_mask=None, ambient_brightness=None):
    """
    Dynamically calculate binarization threshold for pupil isolation based on illumination.
    Target: isolate the dark pupil/iris (~30-35% of the eye area) from the brighter sclera,
    adapting smoothly to changing lighting conditions.
    """
    if eye_gray is None or eye_gray.size == 0:
        return GAZE_DEFAULT_THRESH
    if eye_mask is not None:
        pixels = eye_gray[eye_mask > 0]
    else:
        pixels = eye_gray[eye_gray > 0]
    if len(pixels) < 10:
        pixels = eye_gray.flatten()
        if len(pixels) == 0:
            return GAZE_DEFAULT_THRESH

    # Pupil and iris occupy ~30-35% of the visible eye area.
    # The 35th percentile segments pupil as white and keeps sclera black.
    p35 = float(np.percentile(pixels, 35))
    min_v = float(np.min(pixels))
    sclera_v = float(np.percentile(pixels, 85))
    range_t = min_v + 0.42 * (sclera_v - min_v)
    thresh = 0.7 * p35 + 0.3 * range_t
    return int(max(15, min(240, round(thresh))))

def gaze_from_sclera(eye_roi_color, thresh_value, center_scale_factor=CENTER_SCALE_FACTOR, eye_mask=None):
    if eye_roi_color is None or eye_roi_color.size == 0:
        return "unknown", 0, 0, None
    gray = cv2.cvtColor(eye_roi_color, cv2.COLOR_BGR2GRAY)
    _, raw_thresh = cv2.threshold(gray, thresh_value, 255, cv2.THRESH_BINARY_INV)
    if eye_mask is not None:
        thresh = cv2.bitwise_and(raw_thresh, raw_thresh, mask=eye_mask)
    else:
        thresh = raw_thresh
    h, w = thresh.shape
    if h == 0 or w == 0:
        return "unknown", 0, 0, None
    cx, cy = w // 2, h // 2
    radius = max(int(min(w, h) * 0.25), 3)
    center_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(center_mask, (cx, cy), radius, 255, -1)
    if eye_mask is not None:
        center_mask = cv2.bitwise_and(center_mask, eye_mask)
    center_region = cv2.bitwise_and(thresh, thresh, mask=center_mask)
    center_white = cv2.countNonZero(center_region)
    total_circle_pixels = cv2.countNonZero(center_mask)
    center_white_pct = (center_white / total_circle_pixels * 100) if total_circle_pixels > 0 else 0

    disp = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
    cv2.circle(disp, (cx, cy), radius, (0, 255, 0), 2)
    cv2.circle(disp, (cx, cy), 2, (0, 0, 255), -1)
    cv2.line(disp, (w//3, 0), (w//3, h), (100, 100, 100), 1)
    cv2.line(disp, (2*w//3, 0), (2*w//3, h), (100, 100, 100), 1)

    if center_white_pct < 60:
        left_side = thresh[:, :w//3]
        right_side = thresh[:, 2*w//3:]
        left_white = cv2.countNonZero(left_side)
        right_white = cv2.countNonZero(right_side)
        if left_white > right_white * center_scale_factor:
            gaze = "left"
        elif right_white > left_white * center_scale_factor:
            gaze = "right"
        else:
            gaze = "off"
    else:
        gaze = "center"
    return gaze, int(center_white_pct), total_circle_pixels, disp

def _encode_b64_jpeg(img, quality=80):
    if img is None:
        return None
    try:
        h, w = img.shape[:2]
        scale = 200.0 / max(h, w) if max(h, w) > 0 else 1.0
        if scale < 1.0:
            img = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
        if not ok:
            return None
        return 'data:image/jpeg;base64,' + base64.b64encode(buf).decode('ascii')
    except Exception:
        return None

@csrf_exempt
def gaze_frame(request):
    """Process gaze tracking frame and return analysis results."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    sid = _get_sid(request)
    sess = gaze_service.init_session(sid)

    manual_param = request.GET.get('manual', '').strip().lower()
    thresh_param = request.GET.get('thresh', '').strip().lower()

    is_auto = (thresh_param == 'auto') or (manual_param in ('0', 'false', 'off', 'no', 'auto'))
    manual_flag = (not is_auto) and (manual_param in ('1', 'true', 'on', 'yes'))
    manual_off   = is_auto or (manual_param == '0')
    preview_flag = request.GET.get('preview', '').lower() in ('1', 'true', 'on', 'yes')

    if manual_flag:
        if thresh_param and thresh_param != 'auto':
            try:
                tv = int(thresh_param)
                tv = max(1, min(255, tv))
                gaze_service.update_calibration(sid, thresh_value=tv, manual=True)
            except ValueError:
                gaze_service.update_calibration(sid, manual=True)
        else:
            gaze_service.update_calibration(sid, manual=True)
    elif manual_off:
        gaze_service.update_calibration(sid, manual=False)

    if 'frame' in request.FILES:
        data = np.frombuffer(request.FILES['frame'].read(), np.uint8)
    else:
        data = np.frombuffer(request.body, np.uint8)
    frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if frame is None:
        logger.warning("Bad image data sid=%s", sid)
        return JsonResponse({"sid": sid, "error": "bad image"}, status=400)

    frame = cv2.resize(frame, (640, 360))
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_detector(gray)

    # Refresh session after potential updates
    sess = gaze_service.get_session(sid)

    if len(faces) == 0:
        gaze_service.increment_frame(sid, not_looking=True)
        stats = gaze_service.get_stats(sid)
        resp = {
            "sid": sid,
            "manual": sess["manual"],
            "face": False,
            "calibrated": sess["calibrated"],
            "thresh": sess["thresh_value"],
            "isLooking": False,
            "notLookingPct": stats["not_looking_pct"],
            "elapsedSec": stats["elapsed_sec"]
        }
        if preview_flag:
            resp["previewLeft"] = None
            resp["previewRight"] = None
        logger.debug("No face detected sid=%s notLookingPct=%.2f", sid, stats["not_looking_pct"])
        return JsonResponse(resp)

    face = max(faces, key=lambda r: r.width() * r.height())
    landmarks = landmark_predictor(gray, face)
    pts = shape_to_np(landmarks)
    left_eye = pts[36:42]
    right_eye = pts[42:48]
    left_roi, left_mask, _, _ = get_eye_roi(frame, left_eye, return_mask=True)
    right_roi, right_mask, _, _ = get_eye_roi(frame, right_eye, return_mask=True)

    if not sess["manual"]:
        face_roi = gray[max(0, face.top()):min(360, face.bottom()), max(0, face.left()):min(640, face.right())]
        face_brightness = float(np.mean(face_roi)) if face_roi.size > 0 else float(np.mean(gray))

        t_samples = []
        for eye_roi, eye_mask in ((left_roi, left_mask), (right_roi, right_mask)):
            if eye_roi is not None and eye_roi.size > 0:
                t = adaptive_threshold_from_eye(cv2.cvtColor(eye_roi, cv2.COLOR_BGR2GRAY), eye_mask, face_brightness)
                t_samples.append(t)
                gaze_service.add_threshold_sample(sid, int(t))

        samples = gaze_service.get_threshold_samples(sid)
        if len(samples) > 60:
            sess = gaze_service.get_session(sid)
            sess["thresh_samples"] = samples[-60:]
            gaze_service.save_session(sid, sess)
            samples = sess["thresh_samples"]

        # Dynamic auto threshold: smooth median over recent window (last 15 samples)
        recent_samples = samples[-15:] if len(samples) >= 15 else samples
        if recent_samples:
            dynamic_thresh = int(round(float(np.median(recent_samples))))
        elif t_samples:
            dynamic_thresh = int(round(float(np.mean(t_samples))))
        else:
            dynamic_thresh = sess.get("thresh_value", GAZE_DEFAULT_THRESH)

        gaze_service.update_calibration(sid, thresh_value=dynamic_thresh, calibrated=True)
        sess = gaze_service.get_session(sid)

    thresh = sess["thresh_value"]
    gl, cpL, _, dispL = gaze_from_sclera(left_roi, thresh, eye_mask=left_mask)
    gr, cpR, _, dispR = gaze_from_sclera(right_roi, thresh, eye_mask=right_mask)
    is_looking = (gl == "center" and gr == "center")

    gaze_service.increment_frame(sid, not_looking=not is_looking)
    stats = gaze_service.get_stats(sid)

    resp = {
        "sid": sid,
        "manual": sess["manual"],
        "face": True,
        "calibrated": sess["calibrated"],
        "thresh": thresh,
        "left": gl,
        "right": gr,
        "isLooking": is_looking,
        "centerPct": int((cpL + cpR) / 2),
        "notLookingPct": stats["not_looking_pct"],
        "elapsedSec": stats["elapsed_sec"]
    }
    if preview_flag:
        resp["previewLeft"]  = _encode_b64_jpeg(dispL)
        resp["previewRight"] = _encode_b64_jpeg(dispR)
    logger.debug("Gaze frame processed sid=%s looking=%s pct=%.2f", sid, is_looking, stats["not_looking_pct"])
    return JsonResponse(resp)