"""
title: SAIT AI
author: sait_ai
description: SAIT AI - Chat with your documents
requirements: httpx, python-multipart
"""

from typing import Optional, Callable, Union, Generator, Iterator, List
from pydantic import BaseModel, Field
import httpx
import os


class Pipe:
    class Valves(BaseModel):
        BACKEND_URL: str = Field(
            default="http://fastapi:8001",
            description="URL of SAIT AI backend",
        )

    def __init__(self):
        self.type = "manifold"
        self.valves = self.Valves()

    def pipes(self) -> List[dict]:
        return [
            {
                "id": "sait-ai",
                "name": "SAIT AI",
            },
        ]

    def _extract_user_message(self, body: dict) -> str:
        messages = body.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "user":
                raw = msg.get("content", "")
                if isinstance(raw, str):
                    return raw
                elif isinstance(raw, list):
                    parts = []
                    for p in raw:
                        if isinstance(p, dict) and p.get("type") == "text":
                            parts.append(str(p.get("text", "")))
                    return " ".join(parts)
                elif isinstance(raw, dict):
                    return str(raw.get("text", ""))
                else:
                    return str(raw) if raw else ""
        if messages:
            raw = messages[-1].get("content", "")
            return str(raw) if raw else ""
        return ""

    def _upload_file_to_backend(self, files: list):
        for f in files:
            file_data = f.get("file", {})
            fid = file_data.get("id", "")
            fname = file_data.get("filename", "")
            upload_path = f"/app/backend/data/uploads/{fid}_{fname}"
            if os.path.exists(upload_path):
                try:
                    with open(upload_path, "rb") as fp:
                        file_bytes = fp.read()
                    httpx.post(
                        f"{self.valves.BACKEND_URL}/upload",
                        files={"file": (fname, file_bytes, "application/pdf")},
                        timeout=60.0,
                    )
                except Exception:
                    pass

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __files__: Optional[list] = None,
        __metadata__: Optional[dict] = None,
        __event_emitter__: Optional[Callable] = None,
        **kwargs,
    ) -> Union[str, Generator, Iterator]:

        user_message = self._extract_user_message(body)

        if __files__:
            self._upload_file_to_backend(__files__)

        async with httpx.AsyncClient(timeout=600.0) as client:
            try:
                resp = await client.post(
                    f"{self.valves.BACKEND_URL}/chat",
                    json={
                        "question": str(user_message),
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                answer = str(data.get("answer", ""))
                sources = data.get("sources", [])
                source_names = []
                for s in sources:
                    name = s.get("file_name", s.get("name", ""))
                    if name and name not in source_names:
                        source_names.append(name)
                if source_names:
                    answer += "\n\n**Sources:** " + ", ".join(source_names)
                return answer
            except httpx.ConnectError:
                return "Error: Cannot connect to SAIT AI backend. Please ensure the backend service is running."
            except httpx.TimeoutException:
                return "Error: Request timed out. The document may be too large or the server is busy."
            except Exception as e:
                return f"Error: {str(e)}"