"""
External ANPR server endpoint constants.
All paths are relative to EXTERNAL_SERVER_URL from config.
"""
from enum import Enum

from app.core.config import settings


class ExternalEndpoint(str, Enum):
    # Organization
    ORG_LOGIN = "/api/v1/organization/login"
    ORG_CREATE = "/api/v1/organization/create"
    ORG_LIST = "/api/v1/organization/list"
    ORG_FIND_ONE = "/api/v1/organization/find-one/{id}"
    ORG_UPDATE = "/api/v1/organization/update"
    ORG_DELETE = "/api/v1/organization/delete/{id}"

    # Device
    DEVICE_CREATE = "/api/v1/device/create"
    DEVICE_LIST = "/api/v1/device/list"
    DEVICE_FIND_ONE = "/api/v1/device/find-one/{id}"
    DEVICE_UPDATE = "/api/v1/device/update"
    DEVICE_DELETE = "/api/v1/device/delete/{id}"

    # Vehicle
    VEHICLE_CREATE = "/api/v1/vehicle/create"
    VEHICLE_LIST = "/api/v1/vehicle/list"
    VEHICLE_LIST_ALL = "/api/v1/vehicle/list/all"
    VEHICLE_FIND_ONE = "/api/v1/vehicle/find-one/{id}"
    VEHICLE_UPDATE = "/api/v1/vehicle/update"

    def external_url(self, **kwargs) -> str:
        """Build full URL, substituting path params if any.

        Usage:
            ExternalEndpoint.ORG_LOGIN.external_url()
            ExternalEndpoint.DEVICE_FIND_ONE.external_url(id="some-uuid")
        """
        path = self.value.format(**kwargs) if kwargs else self.value
        return f"{settings.EXTERNAL_SERVER_URL}{path}"
