"""Regression tests for Pexels source-duration filtering and manual clip URLs."""

from types import SimpleNamespace
from unittest.mock import patch

from app.config import config
from app.models.schema import VideoAspect
from app.services import material


class _Response:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.headers = {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


def _rendition():
    return {
        "id": 900,
        "width": 1080,
        "height": 1920,
        "link": "https://videos.pexels.com/video-files/123/123-hd_1080_1920_30fps.mp4",
    }


def test_pexels_search_keeps_only_durations_strictly_between_three_and_twenty():
    original_keys = config.app.get("pexels_api_keys")
    config.app["pexels_api_keys"] = ["test-pexels-key"]
    payload = {
        "videos": [
            {"id": 3, "duration": 3, "url": "https://www.pexels.com/video/test-3/", "video_files": [_rendition()]},
            {"id": 4, "duration": 4, "url": "https://www.pexels.com/video/test-4/", "video_files": [_rendition()]},
            {"id": 19, "duration": 19, "url": "https://www.pexels.com/video/test-19/", "video_files": [_rendition()]},
            {"id": 20, "duration": 20, "url": "https://www.pexels.com/video/test-20/", "video_files": [_rendition()]},
        ]
    }
    try:
        with patch("app.services.material.requests.get", return_value=_Response(payload)):
            results = material.search_videos_pexels(
                "space", minimum_duration=4, video_aspect=VideoAspect.portrait
            )
        assert [item.duration for item in results] == [4, 19]
    finally:
        if original_keys is None:
            config.app.pop("pexels_api_keys", None)
        else:
            config.app["pexels_api_keys"] = original_keys


def test_manual_pexels_page_url_resolves_to_downloadable_clip():
    original_keys = config.app.get("pexels_api_keys")
    config.app["pexels_api_keys"] = ["test-pexels-key"]
    payload = {
        "id": 12345,
        "url": "https://www.pexels.com/video/space-12345/",
        "duration": 8,
        "image": "https://images.pexels.com/videos/12345/preview.jpeg",
        "video_files": [_rendition()],
    }
    try:
        with patch("app.services.material.requests.get", return_value=_Response(payload)) as get:
            item = material.resolve_pexels_video_url(
                "https://www.pexels.com/video/space-12345/",
                video_aspect=VideoAspect.portrait,
            )
        assert item.provider == "pexels"
        assert item.duration == 8
        assert item.url == _rendition()["link"]
        assert item.source_info["asset_id"] == "12345"
        assert get.call_args.args[0].endswith("/videos/videos/12345")
    finally:
        if original_keys is None:
            config.app.pop("pexels_api_keys", None)
        else:
            config.app["pexels_api_keys"] = original_keys


def test_manual_pexels_url_accepts_landscape_source_for_portrait_center_crop():
    original_keys = config.app.get("pexels_api_keys")
    config.app["pexels_api_keys"] = ["test-pexels-key"]
    landscape_1080p = {
        "id": 901,
        "width": 1920,
        "height": 1080,
        "link": "https://videos.pexels.com/video-files/123/landscape-1080p.mp4",
    }
    payload = {
        "id": 12345,
        "duration": 8,
        "url": "https://www.pexels.com/video/space-12345/",
        "video_files": [
            {
                "width": 640,
                "height": 360,
                "link": "https://videos.pexels.com/video-files/123/too-small.mp4",
            },
            {
                "id": 902,
                "width": 3840,
                "height": 2160,
                "link": "https://videos.pexels.com/video-files/123/landscape-4k.mp4",
            },
            landscape_1080p,
        ],
    }
    try:
        with patch("app.services.material.requests.get", return_value=_Response(payload)):
            item = material.resolve_pexels_video_url(
                "https://www.pexels.com/video/space-12345/",
                video_aspect=VideoAspect.portrait,
            )
        assert item.url == landscape_1080p["link"]
        assert item.source_info["rendition"]["width"] == 1920
        assert item.source_info["rendition"]["height"] == 1080
    finally:
        if original_keys is None:
            config.app.pop("pexels_api_keys", None)
        else:
            config.app["pexels_api_keys"] = original_keys


def test_manual_pexels_url_prefers_native_orientation_when_available():
    original_keys = config.app.get("pexels_api_keys")
    config.app["pexels_api_keys"] = ["test-pexels-key"]
    portrait = _rendition()
    payload = {
        "id": 12345,
        "duration": 8,
        "url": "https://www.pexels.com/video/space-12345/",
        "video_files": [
            {
                "width": 3840,
                "height": 2160,
                "link": "https://videos.pexels.com/video-files/123/landscape-4k.mp4",
            },
            portrait,
        ],
    }
    try:
        with patch("app.services.material.requests.get", return_value=_Response(payload)):
            item = material.resolve_pexels_video_url(
                "https://www.pexels.com/video/space-12345/",
                video_aspect=VideoAspect.portrait,
            )
        assert item.url == portrait["link"]
    finally:
        if original_keys is None:
            config.app.pop("pexels_api_keys", None)
        else:
            config.app["pexels_api_keys"] = original_keys


def test_manual_pexels_url_rejects_non_pexels_hosts():
    import pytest

    with pytest.raises(ValueError, match="Pexels"):
        material.resolve_pexels_video_url("https://example.com/video/space-12345/")
