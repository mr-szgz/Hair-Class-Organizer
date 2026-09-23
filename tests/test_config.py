from platformdirs import user_config_path

from app.config import APP_STATE_DIR, CACHE_DIR, CONFIG_PATH, HF_CACHE_DIR, LOG_PATH, MOVES_DIR, TEMP_DIR, AppSettings


def test_app_owned_paths_share_user_config_root():
    assert APP_STATE_DIR == user_config_path("Hair-Class-Organizer", appauthor=False)
    for path in (CACHE_DIR, CONFIG_PATH, HF_CACHE_DIR, LOG_PATH, MOVES_DIR, TEMP_DIR):
        assert path.is_relative_to(APP_STATE_DIR)


def test_default_worker_counts_are_optimized_for_parallel_media_operations():
    assert AppSettings().video_workers == 12
    assert AppSettings().move_workers == 12
