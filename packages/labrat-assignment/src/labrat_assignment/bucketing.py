import hashlib


def bucket_for(feature_flag_name: str, user_id: int) -> int:
    """
    Returns the assigned bucket number for a given feature flag name and user id.
    """
    token = f"{feature_flag_name}:{user_id}"
    sha = hashlib.sha256(token.encode())

    return int.from_bytes(sha.digest()[:8]) % 100