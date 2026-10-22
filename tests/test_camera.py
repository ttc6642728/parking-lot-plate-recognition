# -*- coding: utf-8 -*-
"""
摄像头模块测试。

原则：**不依赖本机是否真的插着摄像头**。
只验证配置读取、后端选择、以及失败路径的行为——这几处以前出过问题：
  · 设备号写死在 Camera(0)，换台机器就打不开；
  · 只检查 isOpened()，于是"打开成功但读不到画面"被当成正常；
  · 打开失败不留下任何可排查的信息。
"""

import pytest

from core.camera import Camera
from config import CAMERA_INDEX, CAMERA_BACKEND


# 一个几乎不可能存在的设备号
_MISSING = 9999


class TestConfig:
    def test_default_source_comes_from_config(self):
        assert Camera().source == CAMERA_INDEX

    def test_auto_backend_has_candidates(self):
        cands = Camera(0, "auto")._backend_candidates()
        assert cands, "auto 至少要给出一个可用后端"
        for name, api in cands:
            assert isinstance(name, str) and name
            assert isinstance(api, int)

    def test_forced_backend_is_single(self):
        assert [n for n, _ in Camera(0, "dshow")._backend_candidates()] == ["dshow"]
        assert [n for n, _ in Camera(0, "default")._backend_candidates()] == ["default"]

    def test_unknown_backend_falls_back_to_candidates(self):
        # 写错后端名时不能抛异常，应退回自动选择
        assert Camera(0, "not-a-backend")._backend_candidates()


class TestFailurePath:
    def test_missing_device_returns_false_with_reason(self):
        cam = Camera(_MISSING)
        assert cam.open() is False
        assert cam.is_opened() is False
        assert cam.last_error, "失败时必须留下可排查的原因"
        cam.release()

    def test_missing_device_message_mentions_device(self):
        cam = Camera(_MISSING)
        cam.open()
        assert str(_MISSING) in cam.last_error
        cam.release()

    def test_read_before_open_is_none(self):
        cam = Camera(_MISSING)
        assert cam.read() is None

    def test_probe_with_zero_range_returns_empty(self):
        assert Camera.probe_devices(0) == []

    def test_probe_returns_list_of_ints(self):
        found = Camera.probe_devices(1)
        assert isinstance(found, list)
        assert all(isinstance(i, int) for i in found)
