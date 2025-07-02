from abc import ABC, abstractmethod  # noqa: F401
from typing import Any, Optional  # noqa: F401

from fastapi import Request  # noqa: F401

from ..base import AuthenticationResult, BaseAuthenticator  # noqa: F401
from ..exceptions import SecurityConfigurationException  # noqa: F401
