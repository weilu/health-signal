def test_package_exposes_public_api():
    import health_signal
    assert hasattr(health_signal, "create_app")
    assert hasattr(health_signal, "load_config")
