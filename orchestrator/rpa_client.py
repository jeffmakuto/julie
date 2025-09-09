import os
import requests
import json
from typing import Optional, List, Dict, Any


class RPAClient:
    def __init__(self):
        self.client_id = os.getenv("UIPATH_CLIENT_ID")
        self.refresh_token = os.getenv("UIPATH_REFRESH_TOKEN")
        self.cloud_url = os.getenv("UIPATH_CLOUD_URL")
        self.org = os.getenv("UIPATH_ORG")
        self.tenant = os.getenv("UIPATH_TENANT")
        self.folder_id = os.getenv("UIPATH_FOLDER_ID")
        self.queue_name = os.getenv("UIPATH_QUEUE_NAME")
        self.access_token: Optional[str] = None
        self._check_env()

    def _check_env(self):
        if not all([
            self.client_id,
            self.refresh_token,
            self.cloud_url,
            self.org,
            self.tenant,
            self.folder_id,
            self.queue_name
        ]):
            raise RuntimeError("Missing required UiPath environment variables")

    def get_access_token(self) -> str:
        """Return a cached token or fetch a new one."""
        if self.access_token:
            return self.access_token
        resp = requests.post(
            "https://account.uipath.com/oauth/token",
            json={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": self.refresh_token
            }
        )
        resp.raise_for_status()
        self.access_token = resp.json()["access_token"]
        if not self.access_token:
            raise RuntimeError("Failed to retrieve access token")
        return self.access_token

    def headers(self) -> Dict[str, str]:
        """Return public headers for API requests."""
        return {
            "Authorization": f"Bearer {self.get_access_token()}",
            "Content-Type": "application/json",
            "X-UIPATH-OrganizationUnitId": str(self.folder_id)
        }

    def post_queue_item(self, payload: dict, queue_name: Optional[str] = None) -> dict:
        if "ClaimDetails" in payload and isinstance(payload["ClaimDetails"], list):
            payload["ClaimDetails"] = json.dumps(payload["ClaimDetails"])
        target_queue = queue_name or self.queue_name
        queue_url = f"{self.cloud_url}/{self.org}/{self.tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem"
        resp = requests.post(
            queue_url,
            headers=self.headers(),
            json={
                "itemData": {
                    "Name": target_queue,
                    "Priority": "Normal",
                    "SpecificContent": payload,
                    "Reference": payload.get("MemberNumber")
                }
            }
        )
        resp.raise_for_status()
        return resp.json()

    def get_queue_items(self, queue_name: Optional[str] = None, status: str = "New") -> List[Dict[str, Any]]:
        target_queue = queue_name or self.queue_name
        # 1. Get Queue ID
        queues_url = f"{self.cloud_url}/{self.org}/{self.tenant}/orchestrator_/odata/Queues?$filter=Name eq '{target_queue}'"
        queues_resp = requests.get(queues_url, headers=self.headers())
        queues_resp.raise_for_status()
        queues_data = queues_resp.json().get("value", [])
        if not queues_data:
            raise RuntimeError(f"Queue '{target_queue}' not found")
        queue_id = queues_data[0]["Id"]

        # 2. Get Queue Items
        items_url = f"{self.cloud_url}/{self.org}/{self.tenant}/orchestrator_/odata/QueueItems?$filter=QueueDefinitionId eq {queue_id} and Status eq '{status}'"
        items_resp = requests.get(items_url, headers=self.headers())
        items_resp.raise_for_status()
        return items_resp.json().get("value", [])
