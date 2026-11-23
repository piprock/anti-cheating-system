import pytest
from django.urls import reverse
from main.services import GazeService

@pytest.fixture
def gaze_service():
    return GazeService()

@pytest.mark.django_db
def test_gaze_page_get(client):
    url = reverse('gaze')
    response = client.get(url)
    assert response.status_code == 200
    assert "main/gaze.html" in [t.name for t in response.templates]
    assert "Моніторинг та налаштування погляду" in response.content.decode('utf-8')

@pytest.mark.django_db
def test_gaze_reset_post(client, gaze_service):
    sid = "test_reset_sid"
    gaze_service.init_session(sid)
    gaze_service.increment_frame(sid, not_looking=True)
    assert gaze_service.get_session(sid)['frames'] == 1

    url = reverse('gaze_reset', kwargs={'sid': sid})
    response = client.post(url)
    assert response.status_code == 200
    data = response.json()
    assert data.get('ok') is True
    assert data.get('stats', {}).get('frames') == 0

@pytest.mark.django_db
def test_gaze_reset_method_not_allowed(client):
    url = reverse('gaze_reset', kwargs={'sid': 'sid_any'})
    response = client.get(url)
    assert response.status_code == 405

@pytest.mark.django_db
def test_adaptive_threshold_illumination_scaling():
    import numpy as np
    from main.gaze import adaptive_threshold_from_eye
    
    # Simulate bright eye (values 140-240)
    bright_eye = np.full((30, 40), 200, dtype=np.uint8)
    bright_eye[10:20, 15:25] = 110  # iris
    
    # Simulate dark eye (values 30-100)
    dark_eye = np.full((30, 40), 80, dtype=np.uint8)
    dark_eye[10:20, 15:25] = 30  # iris
    
    bright_t = adaptive_threshold_from_eye(bright_eye)
    dark_t = adaptive_threshold_from_eye(dark_eye)
    
    assert bright_t > dark_t
    assert dark_t < 100
    assert bright_t > 120

@pytest.mark.django_db
def test_gaze_frame_auto_threshold_mode(client):
    import cv2
    import numpy as np
    
    # Create synthetic frame with dummy face
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    _, buf = cv2.imencode('.jpg', frame)
    
    url = reverse('gaze_frame') + "?sid=test_auto_sid&manual=0&thresh=auto"
    res = client.post(url, data=buf.tobytes(), content_type='image/jpeg')
    assert res.status_code == 200
    data = res.json()
    assert data["manual"] is False
    assert "thresh" in data
