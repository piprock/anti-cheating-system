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
