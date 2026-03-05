"""
External Sync Service - Forwards data to external ANPR server.
Single service file with classes for auth, organization, device, and vehicle.
"""
import threading
import time
from typing import Optional

import httpx

from app.core.config import settings
from app.core.external_endpoints import ExternalEndpoint
from app.core.logging import app_logger as logger
from app.core.exceptions import ExternalSyncException


class ExternalAuthManager:
    """Handles JWT login, token caching, and thread-safe refresh."""

    def __init__(self, client: httpx.Client):
        self._client = client
        self._token: Optional[str] = None
        self._token_acquired_at: float = 0
        self._token_ttl: float = 3500  # refresh before 1hr expiry
        self._lock = threading.Lock()

    def login(self) -> str:
        """Login to external server and return JWT token."""
        url = ExternalEndpoint.ORG_LOGIN.external_url()
        payload = {
            "name": settings.EXTERNAL_ADMIN_NAME,
            "password": settings.EXTERNAL_ADMIN_PASSWORD,
        }
        logger.info(f"External auth: logging in to {url}")
        response = self._client.post(url, json=payload)

        if response.status_code != 200:
            raise ExternalSyncException("ORG_LOGIN", response.status_code, response.text)

        data = response.json()
        self._token = data["token"]
        self._token_acquired_at = time.time()
        logger.info("External auth: login successful")
        return self._token

    def _is_token_expired(self) -> bool:
        if self._token is None:
            return True
        return (time.time() - self._token_acquired_at) > self._token_ttl

    def get_headers(self) -> dict:
        """Return auth headers, refreshing token if expired. Thread-safe."""
        if self._is_token_expired():
            with self._lock:
                if self._is_token_expired():
                    self.login()
        return {"Authorization": f"Bearer {self._token}"}


class ExternalOrgService:
    """Organization CRUD operations on external server."""

    def __init__(self, auth: ExternalAuthManager, client: httpx.Client):
        self._auth = auth
        self._client = client

    def create(self, name: str, password: str, role: str = "admin",
               organisation_status: str = "WORKING") -> str:
        """Create organization on external server. Returns external UUID."""
        url = ExternalEndpoint.ORG_CREATE.external_url()
        payload = {
            "name": name,
            "password": password,
            "role": role,
            "organisationStatus": organisation_status,
        }
        logger.info(f"External org create: {name}")
        response = self._client.post(url, json=payload, headers=self._auth.get_headers())

        if response.status_code not in (200, 201):
            raise ExternalSyncException("ORG_CREATE", response.status_code, response.text)

        data = response.json()
        ext_id = str(data["id"])
        logger.info(f"External org created: {ext_id}")
        return ext_id

    def update(self, external_org_id: str, name: Optional[str] = None,
               role: Optional[str] = None, organisation_status: Optional[str] = None,
               status: Optional[str] = None, is_deleted: Optional[bool] = None) -> dict:
        """Update organization on external server."""
        url = ExternalEndpoint.ORG_UPDATE.external_url()
        payload = {"id": external_org_id}
        if name is not None:
            payload["name"] = name
        if role is not None:
            payload["role"] = role
        if organisation_status is not None:
            payload["organisationStatus"] = organisation_status
        if status is not None:
            payload["status"] = status
        if is_deleted is not None:
            payload["isDeleted"] = is_deleted

        logger.info(f"External org update: {external_org_id}")
        response = self._client.put(url, json=payload, headers=self._auth.get_headers())

        if response.status_code != 200:
            raise ExternalSyncException("ORG_UPDATE", response.status_code, response.text)

        return response.json()

    def delete(self, external_org_id: str) -> bool:
        """Delete organization on external server."""
        url = ExternalEndpoint.ORG_DELETE.external_url(id=external_org_id)
        logger.info(f"External org delete: {external_org_id}")
        response = self._client.delete(url, headers=self._auth.get_headers())

        if response.status_code != 200:
            raise ExternalSyncException("ORG_DELETE", response.status_code, response.text)

        return True

    def find_one(self, external_org_id: str) -> dict:
        """Get organization by ID from external server."""
        url = ExternalEndpoint.ORG_FIND_ONE.external_url(id=external_org_id)
        response = self._client.get(url, headers=self._auth.get_headers())

        if response.status_code != 200:
            raise ExternalSyncException("ORG_FIND_ONE", response.status_code, response.text)

        return response.json()

    def list(self) -> list:
        """List all organizations from external server."""
        url = ExternalEndpoint.ORG_LIST.external_url()
        response = self._client.get(url, headers=self._auth.get_headers())

        if response.status_code != 200:
            raise ExternalSyncException("ORG_LIST", response.status_code, response.text)

        return response.json()


class ExternalDeviceService:
    """Device CRUD operations on external server."""

    def __init__(self, auth: ExternalAuthManager, client: httpx.Client):
        self._auth = auth
        self._client = client

    def create(self, name: str, source: Optional[str], frame_type: Optional[str],
               status: str, organization_id: str) -> str:
        """Create device on external server. Returns external UUID."""
        url = ExternalEndpoint.DEVICE_CREATE.external_url()
        payload = {
            "name": name,
            "source": source,
            "frameType": frame_type,
            "status": status,
            "organizationId": organization_id,
        }
        logger.info(f"External device create: {name}")
        response = self._client.post(url, json=payload, headers=self._auth.get_headers())

        if response.status_code not in (200, 201):
            raise ExternalSyncException("DEVICE_CREATE", response.status_code, response.text)

        data = response.json()
        ext_id = str(data["id"])
        logger.info(f"External device created: {ext_id}")
        return ext_id

    def update(self, external_device_id: str, name: Optional[str] = None,
               source: Optional[str] = None, frame_type: Optional[str] = None,
               status: Optional[str] = None) -> dict:
        """Update device on external server."""
        url = ExternalEndpoint.DEVICE_UPDATE.external_url()
        payload = {"id": external_device_id}
        if name is not None:
            payload["name"] = name
        if source is not None:
            payload["source"] = source
        if frame_type is not None:
            payload["frameType"] = frame_type
        if status is not None:
            payload["status"] = status

        logger.info(f"External device update: {external_device_id}")
        response = self._client.put(url, json=payload, headers=self._auth.get_headers())

        if response.status_code != 200:
            raise ExternalSyncException("DEVICE_UPDATE", response.status_code, response.text)

        return response.json()

    def delete(self, external_device_id: str) -> bool:
        """Delete device on external server."""
        url = ExternalEndpoint.DEVICE_DELETE.external_url(id=external_device_id)
        logger.info(f"External device delete: {external_device_id}")
        response = self._client.delete(url, headers=self._auth.get_headers())

        if response.status_code != 200:
            raise ExternalSyncException("DEVICE_DELETE", response.status_code, response.text)

        return True

    def find_one(self, external_device_id: str) -> dict:
        """Get device by ID from external server."""
        url = ExternalEndpoint.DEVICE_FIND_ONE.external_url(id=external_device_id)
        response = self._client.get(url, headers=self._auth.get_headers())

        if response.status_code != 200:
            raise ExternalSyncException("DEVICE_FIND_ONE", response.status_code, response.text)

        return response.json()

    def list(self) -> list:
        """List all devices from external server."""
        url = ExternalEndpoint.DEVICE_LIST.external_url()
        response = self._client.get(url, headers=self._auth.get_headers())

        if response.status_code != 200:
            raise ExternalSyncException("DEVICE_LIST", response.status_code, response.text)

        return response.json()


class ExternalVehicleService:
    """Vehicle (detection report) operations on external server."""

    def __init__(self, auth: ExternalAuthManager, client: httpx.Client):
        self._auth = auth
        self._client = client

    def create(self, number_plate: Optional[str] = None, vehicle_type: Optional[str] = None,
               device_name: Optional[str] = None, report_id: Optional[str] = None,
               number_plate_image: Optional[str] = None, vehicle_image: Optional[str] = None,
               device_id: str = "", organization_id: str = "",
               is_sent_back: str = "no", is_updated: bool = False) -> str:
        """Create vehicle report on external server. Returns external UUID."""
        url = ExternalEndpoint.VEHICLE_CREATE.external_url()
        payload = {
            "numberPlate": number_plate,
            "vehicleType": vehicle_type,
            "deviceName": device_name,
            "reportId": report_id,
            "numberPlateImage": number_plate_image,
            "vehicleImage": vehicle_image,
            "deviceId": device_id,
            "organizationId": organization_id,
            "isSentBack": is_sent_back,
            "isUpdated": is_updated,
        }
        logger.info(f"External vehicle create: plate={number_plate}")
        response = self._client.post(url, json=payload, headers=self._auth.get_headers())

        if response.status_code not in (200, 201):
            raise ExternalSyncException("VEHICLE_CREATE", response.status_code, response.text)

        data = response.json()
        ext_id = str(data["id"])
        logger.info(f"External vehicle created: {ext_id}")
        return ext_id

    def update(self, external_vehicle_id: str, number_plate: Optional[str] = None,
               vehicle_type: Optional[str] = None, device_name: Optional[str] = None,
               report_id: Optional[str] = None, number_plate_image: Optional[str] = None,
               vehicle_image: Optional[str] = None, is_sent_back: Optional[str] = None,
               is_updated: Optional[bool] = None) -> dict:
        """Update vehicle report on external server."""
        url = ExternalEndpoint.VEHICLE_UPDATE.external_url()
        payload = {"id": external_vehicle_id}
        if number_plate is not None:
            payload["numberPlate"] = number_plate
        if vehicle_type is not None:
            payload["vehicleType"] = vehicle_type
        if device_name is not None:
            payload["deviceName"] = device_name
        if report_id is not None:
            payload["reportId"] = report_id
        if number_plate_image is not None:
            payload["numberPlateImage"] = number_plate_image
        if vehicle_image is not None:
            payload["vehicleImage"] = vehicle_image
        if is_sent_back is not None:
            payload["isSentBack"] = is_sent_back
        if is_updated is not None:
            payload["isUpdated"] = is_updated

        logger.info(f"External vehicle update: {external_vehicle_id}")
        response = self._client.put(url, json=payload, headers=self._auth.get_headers())

        if response.status_code != 200:
            raise ExternalSyncException("VEHICLE_UPDATE", response.status_code, response.text)

        return response.json()

    def find_one(self, external_vehicle_id: str) -> dict:
        """Get vehicle report by ID from external server."""
        url = ExternalEndpoint.VEHICLE_FIND_ONE.external_url(id=external_vehicle_id)
        response = self._client.get(url, headers=self._auth.get_headers())

        if response.status_code != 200:
            raise ExternalSyncException("VEHICLE_FIND_ONE", response.status_code, response.text)

        return response.json()


class ExternalSyncService:
    """
    Main entry point for all external server communication.
    Composes auth, organization, device, and vehicle services
    with a shared httpx client and JWT auth manager.
    """

    def __init__(self):
        self._client = httpx.Client(timeout=30.0)
        self.auth = ExternalAuthManager(self._client)
        self.organization = ExternalOrgService(self.auth, self._client)
        self.device = ExternalDeviceService(self.auth, self._client)
        self.vehicle = ExternalVehicleService(self.auth, self._client)
        logger.info("ExternalSyncService initialized")

    @property
    def is_enabled(self) -> bool:
        return settings.EXTERNAL_SYNC_ENABLED and bool(settings.EXTERNAL_SERVER_URL)


# Singleton
_instance: Optional[ExternalSyncService] = None


def get_external_sync_service() -> ExternalSyncService:
    global _instance
    if _instance is None:
        _instance = ExternalSyncService()
    return _instance
