import hashlib


def bucket_for(experiment_slug: str, user_id: str) -> int:
    """
    Returns the assigned bucket number for a given experiment slug and user id.
    """
    token = f"{experiment_slug}:{user_id}"
    sha = hashlib.sha256(token.encode())

    return int.from_bytes(sha.digest()[:8]) % 100
