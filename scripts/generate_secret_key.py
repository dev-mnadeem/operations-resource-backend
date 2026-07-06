#!/usr/bin/env python3
"""
Generate a cryptographically secure secret key for use in Django or other configs.
Usage: python scripts/generate_secret_key.py
"""

import secrets

# 50 chars, URL-safe base64 (Django-style length)
SECRET_KEY = secrets.token_urlsafe(50)

if __name__ == "__main__":
    print(SECRET_KEY)
