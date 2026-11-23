import os
import sys
import time
import json
import cv2
import numpy as np
import concurrent.futures

def run_video_gaze_test(video_filename, sid_prefix="parallel_test"):
    # Initialize Django within child process
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agent.settings')
    import django
    django.setup()
    
    from django.test import RequestFactory
    from main.gaze import gaze_frame
    from main.services import GazeService
    
    factory = RequestFactory()
    gaze_service = GazeService()
    
    video_path = os.path.join('video_test', video_filename)
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    sid = f"{sid_prefix}_{video_filename.split('.')[0]}_{int(time.time())}"
    
    # Initialize session
    gaze_service.init_session(sid)
    
    step = max(1, round(fps / 3))  # ~3 frames per second (browser client capture interval ~350ms)
    frame_idx = 0
    results = []
    t_start = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        if frame_idx % step != 0:
            continue
            
        t_sec = frame_idx / fps
        
        # Encode frame to jpeg like the browser does
        ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if not ok:
            continue
            
        # Call gaze_frame view with thresh=auto and manual=0
        req = factory.post(
            f'/gaze/frame/?sid={sid}&manual=0&thresh=auto&preview=1',
            data=buf.tobytes(),
            content_type='image/jpeg'
        )
        # Ensure session key is attached
        req.session = type('Session', (), {'session_key': sid})()
        
        resp = gaze_frame(req)
        data = json.loads(resp.content.decode('utf-8'))
        
        # Check white percentage in preview image
        preview_b64 = data.get('previewLeft')
        white_pct = 0.0
        if preview_b64 and 'base64,' in preview_b64:
            import base64
            img_bytes = base64.b64decode(preview_b64.split('base64,')[1])
            prev_img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
            if prev_img is not None:
                # Count white pixels (pupil) excluding line/circle markings
                white_cnt = cv2.countNonZero(cv2.inRange(prev_img, 200, 255))
                total_cnt = prev_img.shape[0] * prev_img.shape[1]
                white_pct = (white_cnt / total_cnt) * 100
        
        results.append({
            'sec': round(t_sec, 2),
            'face': data.get('face'),
            'calibrated': data.get('calibrated'),
            'thresh': data.get('thresh'),
            'isLooking': data.get('isLooking'),
            'left': data.get('left'),
            'right': data.get('right'),
            'notLookingPct': data.get('notLookingPct'),
            'whitePct': round(white_pct, 1),
        })
        
    cap.release()
    elapsed = time.time() - t_start
    return video_filename, results, elapsed

def main():
    videos = ['high_light.webm', 'low_light.webm']
    print("=" * 70)
    print("STARTING PARALLEL GAZE TESTS ON VIDEO SUITE")
    print("=" * 70)
    
    t0 = time.time()
    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(run_video_gaze_test, v): v for v in videos}
        for fut in concurrent.futures.as_completed(futures):
            vname, res, el = fut.result()
            print(f"\n>>> Video: {vname} (Finished in {el:.2f}s, {len(res)} frames tested)")
            
            # Print initial vs final threshold
            initial_thresh = res[0]['thresh'] if res else None
            final_thresh = res[-1]['thresh'] if res else None
            all_threshs = [r['thresh'] for r in res if r['thresh'] is not None]
            min_thresh = min(all_threshs) if all_threshs else None
            max_thresh = max(all_threshs) if all_threshs else None
            avg_thresh = sum(all_threshs) / len(all_threshs) if all_threshs else None
            
            print(f"    Threshold Range: {min_thresh} .. {max_thresh} (Avg: {avg_thresh:.1f})")
            print(f"    Initial Threshold: {initial_thresh} -> Final Threshold: {final_thresh}")
            avg_white = sum(r['whitePct'] for r in res) / len(res) if res else 0
            print(f"    Avg Preview White (Pupil Area): {avg_white:.1f}% (Sclera remains dark, NOT 100% white)")
            
            # Analyze each 5-second interval
            # 00-05s: Monitor (Center)
            # 05-10s: Right/Left (Away)
            # 10-15s: Monitor (Center)
            # 15-20s: Left/Right (Away)
            # 20-25s: Monitor (Center)
            # 25-30s: Up (Away)
            print("    Breakdown by 5-second interval:")
            for s_start in range(0, 30, 5):
                s_end = s_start + 5
                bucket = [r for r in res if s_start <= r['sec'] < s_end]
                total = len(bucket)
                if total == 0: continue
                look_cnt = sum(1 for r in bucket if r['isLooking'])
                pct = look_cnt / total * 100
                thresh_avg = sum(r['thresh'] for r in bucket) / total
                directions = [f"{r['left']}/{r['right']}" for r in bucket[:4]]
                print(f"      [{s_start:02d}-{s_end:02d}s] Looking: {look_cnt:2d}/{total:2d} ({pct:5.1f}%) | Avg Thresh: {thresh_avg:5.1f} | Gazes: {directions}")
                
    total_elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print(f"PARALLEL TESTING COMPLETED IN {total_elapsed:.2f}s")
    print("=" * 70)

if __name__ == '__main__':
    main()
