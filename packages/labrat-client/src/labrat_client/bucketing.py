import hashlib


def bucket_for(experiment_slug: str, subject: str) -> int:
    """
    Returns the assigned bucket number for a given experiment slug and subject.
    """
    token = f"{experiment_slug}:{subject}"
    sha = hashlib.sha256(token.encode())

    return int.from_bytes(sha.digest()[:8]) % 100


def variant_for(experiment_slug: str, control_split: int, subject: str) -> str:
    return (
        # How do I have a canonical definition of these hardcoded values?
        "control"
        if bucket_for(experiment_slug, subject) < control_split
        else "treatment"
    )
