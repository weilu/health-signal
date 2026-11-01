from health_signal.analytics.aedseo_r import build_version


def test_a_build_installed_from_a_commit_is_named_by_it():
    # Every development build reports the same version; only the commit tells two of them apart.
    assert build_version("1.2.0.9000", "de5c15e0a1b2c3d4") == "1.2.0.9000+de5c15e"


def test_a_released_build_is_named_by_its_version():
    assert build_version("1.1.0", None) == "1.1.0"
