"""
JWT Authentication Backend for django-ninja API endpoints.

Validates JWT tokens issued by the ID service using RS256 asymmetric keys.
The ID service signs tokens with its private key; this backend validates them
using the public key, which can be safely shared.

This is a resource server pattern:
- ID service is the authorization server (issues tokens)
- App backend is the resource server (validates tokens for protected resources)
"""

from typing import Optional

import jwt
from django.contrib.auth import get_user_model
from django.conf import settings
from ninja.security import HttpBearer

User = get_user_model()


class JWTAuthenticationBackend(HttpBearer):
    """
    Django-Ninja HTTP Bearer authentication using JWT tokens from ID service.

    On valid token:
    - Returns the authenticated User object
    - Auto-creates user from JWT claims if not found

    On invalid token:
    - Returns None (authentication failure)
    """

    def authenticate(self, request, token: str) -> Optional[User]:
        """
        Validate JWT token and return authenticated user.

        Args:
            request: Django request object
            token: Bearer token string (without "Bearer " prefix)

        Returns:
            User object if token is valid, None otherwise
        """
        try:
            # Validate and decode the JWT using ID service's public key
            if not settings.JWT_PUBLIC_KEY:
                return None

            payload = jwt.decode(
                token,
                settings.JWT_PUBLIC_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                issuer=settings.JWT_ISSUER,
                audience=settings.JWT_AUDIENCE,
                options={"verify_exp": True, "verify_signature": True},
            )

            # Extract user identity from JWT claims
            # django-allauth JWT strategy uses 'sub' for the user identifier
            user_email = payload.get("email")
            user_uuid = payload.get("uuid") or payload.get("sub")

            if not user_email:
                return None

            # Get or create user based on email
            # Email is the unique identifier across the platform
            user, created = User.objects.get_or_create(
                email=user_email,
                defaults={
                    "username": str(user_uuid) if user_uuid else user_email,
                    "is_active": True,
                },
            )

            # If user was just created, set the UUID as username for consistency
            if created and user_uuid:
                user.username = str(user_uuid)
                user.save(update_fields=["username"])

            return user

        except jwt.ExpiredSignatureError:
            # Token has expired
            return None
        except jwt.InvalidSignatureError:
            # Token was signed with wrong key or tampered with
            return None
        except jwt.InvalidAlgorithmError:
            # Token was signed with unsupported algorithm
            return None
        except (jwt.DecodeError, ValueError):
            # Token is malformed or invalid
            return None
        except Exception:
            # Catch any other errors during validation
            return None
