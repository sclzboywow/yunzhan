from __future__ import annotations

import os
from hashlib import sha256
from typing import Tuple

from Crypto.Cipher import AES

from .config import get_settings


def _get_key() -> bytes:
    key_src = get_settings().enc_master_key.encode("utf-8")
    if len(key_src) >= 32:
        return key_src[:32]
    return sha256(key_src).digest()


def encrypt_to_base64(plaintext: str) -> str:
    key = _get_key()
    nonce = os.urandom(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))
    return (nonce + tag + ciphertext).hex()


def decrypt_from_base64(token_hex: str) -> str:
    raw = bytes.fromhex(token_hex)
    nonce, tag, ciphertext = raw[:12], raw[12:28], raw[28:]
    key = _get_key()
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    return plaintext.decode("utf-8")


