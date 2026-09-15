"""Authenticated encryption for data leaving the database.

A database backup, an audit archive or an exported report is patient data
sitting on a filesystem, a USB stick or a cloud bucket, outside every control
the application enforces. HIPAA §164.312(a)(2)(iv) and §164.312(e)(2)(ii) make
encryption addressable for exactly that situation, and GDPR Article 32 names it
directly.

This restores the AES-256-GCM protection the Next.js implementation had in
``src/lib/security.ts``, which was lost in the Django rewrite.

Format
------
Files are self-describing so a future reader needs nothing but the passphrase::

    magic(8) | version(1) | salt(16) | nonce(12) | ciphertext… | tag(16)

* **AES-256-GCM**, so tampering is detected rather than silently decrypted into
  plausible-looking rubbish — which matters more for a clinical archive than
  confidentiality alone.
* **scrypt** for key derivation (n=2^15, r=8, p=1), which is memory-hard and so
  far more expensive to attack with commodity hardware than PBKDF2.
* A **fresh random salt and nonce per file**. Reusing a nonce under the same key
  breaks GCM completely, so they are never derived from anything.

Streaming
---------
Backups are larger than memory, so both directions work in chunks. Decryption
only releases plaintext after the authentication tag verifies — it will not
hand back a partially-written, unverified file.
"""
from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path
from typing import BinaryIO, Iterator

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"DXCRYPT1"
VERSION = 1
SALT_BYTES = 16
NONCE_BYTES = 12
TAG_BYTES = 16
KEY_BYTES = 32
CHUNK = 64 * 1024

#: scrypt cost. n=2^15 keeps derivation around a tenth of a second on a modern
#: CPU while costing an attacker 32 MB of memory per guess.
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1

HEADER_BYTES = len(MAGIC) + 1 + SALT_BYTES + NONCE_BYTES


class EncryptionError(Exception):
    """Raised when a file cannot be encrypted or decrypted."""


class IntegrityError(EncryptionError):
    """Raised when a file's authentication tag does not verify.

    The file has been altered, truncated, or the passphrase is wrong — the
    three are indistinguishable by design, so an attacker learns nothing from
    the error.
    """


def derive_key(passphrase: str, salt: bytes) -> bytes:
    if not passphrase:
        raise EncryptionError("A passphrase is required.")
    kdf = Scrypt(salt=salt, length=KEY_BYTES, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_bytes(plaintext: bytes, passphrase: str) -> bytes:
    """Encrypt a value that comfortably fits in memory."""
    salt = secrets.token_bytes(SALT_BYTES)
    nonce = secrets.token_bytes(NONCE_BYTES)
    header = MAGIC + bytes([VERSION]) + salt + nonce
    # The header is authenticated but not encrypted, so tampering with the
    # salt or nonce is detected rather than merely producing a wrong key.
    sealed = AESGCM(derive_key(passphrase, salt)).encrypt(nonce, plaintext, header)
    return header + sealed


def decrypt_bytes(payload: bytes, passphrase: str) -> bytes:
    """Decrypt a value produced by :func:`encrypt_bytes`."""
    if len(payload) < HEADER_BYTES + TAG_BYTES:
        raise IntegrityError("The file is too short to be a Dx encrypted archive.")

    header, body = payload[:HEADER_BYTES], payload[HEADER_BYTES:]
    if not hmac.compare_digest(header[: len(MAGIC)], MAGIC):
        raise EncryptionError("This is not a Dx encrypted archive.")
    if header[len(MAGIC)] != VERSION:
        raise EncryptionError(f"Unsupported archive version {header[len(MAGIC)]}.")

    salt = header[len(MAGIC) + 1: len(MAGIC) + 1 + SALT_BYTES]
    nonce = header[len(MAGIC) + 1 + SALT_BYTES:]

    try:
        return AESGCM(derive_key(passphrase, salt)).decrypt(nonce, body, header)
    except InvalidTag as error:
        raise IntegrityError(
            "The archive failed its integrity check. Either the passphrase is "
            "wrong or the file has been altered since it was written."
        ) from error


# ── Streaming, for files larger than memory ──────────────────────────────────


def _chunks(handle: BinaryIO) -> Iterator[bytes]:
    while True:
        data = handle.read(CHUNK)
        if not data:
            return
        yield data


def encrypt_file(source: Path, destination: Path, passphrase: str) -> Path:
    """Encrypt ``source`` into ``destination``.

    Each chunk is sealed independently under the same key with its own counter
    nonce, so a multi-gigabyte backup never has to be held in memory. The
    counter is part of the nonce, so no two chunks share one.
    """
    salt = secrets.token_bytes(SALT_BYTES)
    prefix = secrets.token_bytes(NONCE_BYTES - 4)
    key = derive_key(passphrase, salt)
    cipher = AESGCM(key)
    header = MAGIC + bytes([VERSION]) + salt + prefix + b"\x00\x00\x00\x00"

    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, destination.open("wb") as writer:
        writer.write(header)
        for counter, chunk in enumerate(_chunks(reader)):
            nonce = prefix + counter.to_bytes(4, "big")
            sealed = cipher.encrypt(nonce, chunk, header)
            # Length-prefixed, so truncation is detected rather than read as
            # a short final chunk.
            writer.write(len(sealed).to_bytes(4, "big"))
            writer.write(sealed)
        writer.write((0).to_bytes(4, "big"))  # end marker
    return destination


def decrypt_file(source: Path, destination: Path, passphrase: str) -> Path:
    """Decrypt a file written by :func:`encrypt_file`.

    Written to a temporary file and moved into place only once every chunk has
    authenticated, so a failed decryption never leaves a plausible-looking
    partial file behind.
    """
    with source.open("rb") as reader:
        header = reader.read(HEADER_BYTES)
        if len(header) < HEADER_BYTES or not hmac.compare_digest(header[: len(MAGIC)], MAGIC):
            raise EncryptionError("This is not a Dx encrypted archive.")
        if header[len(MAGIC)] != VERSION:
            raise EncryptionError(f"Unsupported archive version {header[len(MAGIC)]}.")

        salt = header[len(MAGIC) + 1: len(MAGIC) + 1 + SALT_BYTES]
        prefix = header[len(MAGIC) + 1 + SALT_BYTES:][: NONCE_BYTES - 4]
        cipher = AESGCM(derive_key(passphrase, salt))

        destination.parent.mkdir(parents=True, exist_ok=True)
        working = destination.with_suffix(destination.suffix + ".partial")
        try:
            with working.open("wb") as writer:
                counter = 0
                while True:
                    size_bytes = reader.read(4)
                    if len(size_bytes) < 4:
                        raise IntegrityError("The archive ends unexpectedly.")
                    size = int.from_bytes(size_bytes, "big")
                    if size == 0:
                        break
                    sealed = reader.read(size)
                    if len(sealed) < size:
                        raise IntegrityError("The archive ends unexpectedly.")
                    nonce = prefix + counter.to_bytes(4, "big")
                    try:
                        writer.write(cipher.decrypt(nonce, sealed, header))
                    except InvalidTag as error:
                        raise IntegrityError(
                            "The archive failed its integrity check. Either the "
                            "passphrase is wrong or the file has been altered."
                        ) from error
                    counter += 1
            working.replace(destination)
        finally:
            working.unlink(missing_ok=True)

    return destination


def is_encrypted(path: Path) -> bool:
    """Whether a file carries the Dx archive header."""
    try:
        with path.open("rb") as handle:
            return hmac.compare_digest(handle.read(len(MAGIC)), MAGIC)
    except OSError:
        return False
