import platform

from podkernel.kernelspec import user_kernelspec_store


def test_user_kernelspec_store():
    """Test the user kernelspec store function works"""
    result = user_kernelspec_store(platform.system())
    assert result.is_absolute()
