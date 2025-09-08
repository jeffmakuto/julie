import os
import requests
import json


class RPAClient:
    def __init__(self):
        self.client_id = os.getenv("UIPATH_CLIENT_ID")
        self.refresh_token = os.getenv("UIPATH_REFRESH_TOKEN")
        self.cloud_url = os.getenv("UIPATH_CLOUD_URL")
        self.org = os.getenv("UIPATH_ORG")
        self.tenant = os.getenv("UIPATH_TENANT")
        self.folder_id = os.getenv("UIPATH_FOLDER_ID")
        self.queue_name = os.getenv("UIPATH_QUEUE_NAME")
        self._check_env()

    def _check_env(self):
        if not all([self.client_id, self.refresh_token, self.cloud_url,
                    self.org, self.tenant, self.folder_id, self.queue_name]):
            raise RuntimeError("Missing required UiPath env variables")

    def post_queue_item(self, payload: dict) -> dict:
        token_resp = requests.post(
            "https://account.uipath.com/oauth/token",
            json={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": self.refresh_token
            }
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        if "ClaimDetails" in payload and isinstance(payload["ClaimDetails"], list):
            payload["ClaimDetails"] = json.dumps(payload["ClaimDetails"])

        queue_url = f"{self.cloud_url}/{self.org}/{self.tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-UIPATH-OrganizationUnitId": self.folder_id
        }
        resp = requests.post(queue_url,
                             headers=headers,
                             json={
                                 "itemData": {
                                     "Name": self.queue_name,
                                     "Priority": "Normal",
                                     "SpecificContent": payload,
                                     "Reference": payload.get("MemberNumber")
                                 }
                             }
                            )
        resp.raise_for_status()
        return resp.json()

