from codrut.core.security import hash_password, verify_password


def test_password_hash_round_trip() -> None:
    encoded = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)
