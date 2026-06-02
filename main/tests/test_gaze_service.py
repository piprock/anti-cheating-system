import pytest
from main.services import GazeService

@pytest.fixture
def gaze_service():
    return GazeService()

@pytest.mark.django_db
def test_init_session_defaults(gaze_service):
    s = gaze_service.init_session('sid1')
    assert s['frames'] == 0
    assert s['not_looking'] == 0
    assert s['calibrated'] is False

@pytest.mark.django_db
def test_increment_frame_and_percentage(gaze_service):
    gaze_service.init_session('sid2')
    for i in range(10):
        gaze_service.increment_frame('sid2', not_looking=(i % 2 == 0))
    pct = gaze_service.compute_not_looking_percent('sid2')
    assert 40.0 <= pct <= 60.0  # roughly half

@pytest.mark.django_db
def test_calibration_update_and_samples(gaze_service):
    gaze_service.init_session('sid3')
    gaze_service.update_calibration('sid3', thresh_value=180, calibrated=True, manual=True)
    s = gaze_service.get_session('sid3')
    assert s['thresh_value'] == 180
    assert s['calibrated'] is True
    assert s['manual'] is True
    gaze_service.add_threshold_sample('sid3', 200)
    gaze_service.add_threshold_sample('sid3', 210)
    samples = gaze_service.get_threshold_samples('sid3')
    assert samples == [200, 210]

@pytest.mark.django_db
def test_stats_structure(gaze_service):
    gaze_service.init_session('sid4')
    gaze_service.increment_frame('sid4', not_looking=True)
    stats = gaze_service.get_stats('sid4')
    assert set(stats.keys()) >= {"frames", "not_looking", "not_looking_pct", "calibrated"}
