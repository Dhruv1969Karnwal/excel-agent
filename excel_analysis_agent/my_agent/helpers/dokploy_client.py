import base64
import asyncio
import re
import traceback
import uuid
import zipfile
import io
import json
import httpx
import websockets
from typing import Dict, Any, List, Optional
from pathlib import Path
import uuid
# Dokploy Configuration
DOKPLOY_BASE_URL = "http://35.232.206.182:3000"
ENVIRONMENT_ID = "A71ogw4aDRXiXT7-f6DL2"  # From dokploy.txt
API_KEY = "codemateIgJZLeRwPQqKFyOvHXJifnUhwxAGsUucVXWxFqjxkaAHdzczpFACUWZDUHCGJhiK" # From dokploy.txt
SESSION_TOKEN = "y6Tp1ORUbv0BFbwMPbSXNZPbaCN9eNpt.r6H5aO6sv2pZ5IZ8LmOcQYkgqi%2FIzeASG94ruhBmF5A%3D"
PROJECT_ID = "lOOolgBk2tY-wpFRvySUk"

DOCKERFILE_CONTENT = """
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
"""

REQUIREMENTS_CONTENT = """
fastapi
uvicorn
numpy
matplotlib
pandas
openpyxl
seaborn
scipy
statsmodels
scikit-learn
tabulate
python-dateutil
"""

# Replace the MAIN_PY_TEMPLATE in your dokploy_client.py with this fixed version

MAIN_PY_TEMPLATE = """
import matplotlib
matplotlib.use("Agg")  # REQUIRED for containers

import sys
import io
import base64
import json
import matplotlib.pyplot as plt
from fastapi import FastAPI
import contextlib
import traceback

app = FastAPI()

# Cache for the execution result
_RESULT = None

@app.on_event("startup")
async def startup_event():
    global _RESULT
    # Execute the user code here when the container starts
    print("Starting user code execution...", flush=True)

    output_capture = io.StringIO()
    plots_data = []

    # Custom show to capture plots
    def custom_show():
        # CRITICAL FIX: Get the current figure explicitly
        fig = plt.gcf()  # Get current figure
        
        # Force a draw to ensure all elements are rendered
        fig.canvas.draw()
        
        # Use tight_layout to prevent cutoff
        try:
            fig.tight_layout()
        except:
            pass  # tight_layout might fail on some plots
        
        buf = io.BytesIO()
        # Save with explicit parameters
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plots_data.append(img_str)
        plt.close(fig)

    # Monkey patch plt.show
    plt.show = custom_show

    user_code = {user_code_repr}
    
    try:
        with contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(output_capture):
            exec(user_code, globals())
            
            # Check if there are any open figures that weren't shown
            if plt.get_fignums():
                # print("Capturing remaining plots...", flush=True)
                custom_show()
                
        output = output_capture.getvalue()
        success = True
        error = None
    except Exception as e:
        output = output_capture.getvalue()
        success = False
        error = f"{type(e).__name__}: {str(e)}\\n{traceback.format_exc()}"
    finally:
        # Ensure all figures are closed
        plt.close('all')

    # Print a special delimiter so we can parse the result from logs
    _RESULT = {
        "success": success,
        "output": output,
        "error": error,
        "plots": plots_data
    }

    # DIRECT STDOUT OUTPUT FOR WEBSOCKET
    sys.__stdout__.write("__DOKPLOY_RESULT_START__\\n")
    sys.__stdout__.write(json.dumps(_RESULT) + "\\n")
    sys.__stdout__.write("__DOKPLOY_RESULT_END__\\n")
    sys.__stdout__.flush()

@app.get("/")
def health():
    return {"status": "running"}

@app.get("/result")
def get_result():
    return _RESULT
"""

class DokployClient:
    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.code_history: List[str] = []

    def _get_headers(self) -> Dict[str, str]:
        """Returns the common headers for Dokploy API requests."""
        return {
            "Cookie": f"better-auth.session_token={SESSION_TOKEN}"
        }

    async def _create_application(self, app_name: str) -> Dict[str, Any]:
        """Creates a new application in Dokploy."""
        url = f"{DOKPLOY_BASE_URL}/api/application.create"
        print(f"📡 [Dokploy] POST {url} | Name: {app_name}")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                "name": app_name,
                "environmentId": ENVIRONMENT_ID
            }, headers=self._get_headers())
            print(f"📥 [Dokploy] Response {response.status_code}")
            response.raise_for_status()
            return response.json()

    def _create_zip_bundle(self, code: str, file_paths: List[str] = None) -> bytes:
        """Creates a ZIP archive containing main.py, requirements.txt, and any attached files."""
        # DEBUG: Force include file
        print(f"[_create_zip_bundle] Building zip. Attachments: {file_paths}")
        # file_paths = ["C:\\Users\\Dhruv\\Desktop\\CodeMate.AI\\crafting-ai-agents\\testData\\esd.xlsx"]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            # Add Dockerfile
            zf.writestr("Dockerfile", DOCKERFILE_CONTENT)

            # Add main.py
            main_py = MAIN_PY_TEMPLATE.replace("{user_code_repr}", repr(code))
            # FIX: Add encoding='utf-8' to handle emojis and special characters
            with open("main_zip_file.txt", "w", encoding='utf-8') as f:
                f.write(main_py)

            # FIX: Use writestr with bytes for proper UTF-8 encoding
            zf.writestr("main.py", main_py)
            
            # Add requirements.txt
            zf.writestr("requirements.txt", REQUIREMENTS_CONTENT)
            
            # Add any additional files (attachments)
            if file_paths:
                for path_str in file_paths:
                    p = Path(path_str)
                    if p.exists() and p.is_file():
                        print(f"📦 Adding attachment to bundle: {p.name}")
                        zf.write(p, p.name)
                    else:
                        print(f"⚠️ Attachment not found or not a file: {path_str}")
                        
        return buf.getvalue()

    async def _upload_code(self, application_id: str, zip_content: bytes):
        """Uploads the code zip to the application."""
        url = f"{DOKPLOY_BASE_URL}/api/trpc/application.dropDeployment"
        print(f"📡 [Dokploy] POST {url} | AppID: {application_id}")
        
        # Multipart form upload
        files = {'zip': ('app.zip', zip_content, 'application/zip')}
        data = {'applicationId': application_id}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data, files=files, headers=self._get_headers())
            print(f"📥 [Dokploy] Response {response.status_code}")
            # API returns JSON structure, check for errors if needed
            response.raise_for_status()
            return response.json()

    async def _save_build_type(self, application_id: str):
        """Configures the build type to Dockerfile."""
        url = f"{DOKPLOY_BASE_URL}/api/application.saveBuildType"
        print(f"📡 [Dokploy] POST {url} | AppID: {application_id}")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                "applicationId": application_id,
                "buildType": "dockerfile",
                "publishDirectory": None,
                "dockerfile": "Dockerfile",
                "dockerContextPath": "",
                "dockerBuildStage": "",
                "herokuVersion": None,
                "isStaticSpa": None,
                "railpackVersion": None
            }, headers=self._get_headers())
            print(f"📥 [Dokploy] Response {response.status_code}")
            response.raise_for_status()
            return response.json()

    async def _trigger_deploy(self, application_id: str):
        """Triggers the deployment."""
        url = f"{DOKPLOY_BASE_URL}/api/application.deploy"
        print(f"📡 [Dokploy] POST {url} | AppID: {application_id}")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={"applicationId": application_id}, headers=self._get_headers())
            print(f"📥 [Dokploy] Response {response.status_code}")
            response.raise_for_status()
            if response.text:
                return response.json()
            return {"success": True}

    async def _monitor_deployment(self, application_id: str):
        """Polls for deployment completion."""
        url = f"{DOKPLOY_BASE_URL}/api/deployment.all?applicationId={application_id}"
        print(f"📡 [Dokploy] GET {url}")
        
        for i in range(60): # Poll for up to 60 * 2 seconds = 2 minutes
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self._get_headers())
                deployments = response.json()
                
                if deployments and len(deployments) > 0:
                    latest_deployment = deployments[0]
                    status = latest_deployment.get("status")
                    if i % 5 == 0:
                        print(f"⏳ [Dokploy] Deployment Status: {status}")
                    
                    if status == "done":
                        return
                    elif status == "error":
                        raise Exception(f"Deployment failed: {latest_deployment.get('errorMessage')}")
                        
            await asyncio.sleep(2)
            
        raise Exception("Deployment timed out")

    async def _get_container_id(self, application_id: str, app_name: str) -> str:
        """Fetches the container ID for the given application."""
        input_data = {
            "0": {"json": None, "meta": {"values": ["undefined"]}},
            "1": {"json": None, "meta": {"values": ["undefined"]}},
            "2": {"json": {"applicationId": application_id}},
            "3": {"json": {"appName": app_name, "serverId": ""}},
            "4": {"json": {"projectId": PROJECT_ID}},
            "5": {"json": {"containerId": "select-a-container", "serverId": ""}}
        }
        
        import urllib.parse
        encoded_input = urllib.parse.quote(json.dumps(input_data))
        url = f"{DOKPLOY_BASE_URL}/api/trpc/organization.all,user.getInvitations,application.one,docker.getContainersByAppNameMatch,environment.byProjectId,docker.getConfig?batch=1&input={encoded_input}"
        
        headers = {
            "Cookie": f"better-auth.session_token={SESSION_TOKEN}"
        }
        
        print(f"📡 [Dokploy] GET {url} (tRPC Batch)")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                print(f"📥 [Dokploy] Response {response.status_code}")
                response.raise_for_status()
            except Exception as e:
                print(f"❌ [Dokploy] tRPC error: {str(e)}")
                raise
            
            results = response.json()
            
            # Index 3 corresponds to docker.getContainersByAppNameMatch
            container_info = results[3]["result"]["data"]["json"]
            if container_info and len(container_info) > 0:
                container_id = container_info[0]["containerId"]
                print(f"🔍 [Dokploy] Found Container ID: {container_id}")
                return container_id
            else:
                print(f"⚠️ [Dokploy] No containers found matching '{app_name}'. Full tRPC Response: {json.dumps(results[:4])}")
            
        raise Exception(f"Could not find container ID for {app_name}")

    async def _fetch_logs(self, container_id: str) -> str:
        """Fetches container logs via WebSocket."""
        # tail=10000 to ensure large plot logs aren't truncated
        ws_url = f"ws://35.232.206.182:3000/docker-container-logs?containerId={container_id}&tail=10000&since=all&search=&runType=native"
        print(f"🔌 [Dokploy] WebSocket Connect: {ws_url}")
        
        headers = [
            ("Cookie", f"better-auth.session_token={SESSION_TOKEN}")
        ]
        
        collected_logs = ""
        try:
            async with websockets.connect(ws_url, additional_headers=headers) as websocket:
                print(f"✅ [Dokploy] WebSocket Connected")
                try:
                    # Collect logs until we see BOTH markers or connection closes
                    async for message in websocket:
                        collected_logs += str(message)
                        if "__DOKPLOY_RESULT_START__" in collected_logs and "__DOKPLOY_RESULT_END__" in collected_logs:
                            break
                except websockets.exceptions.ConnectionClosed:
                    print(f"📡 [Dokploy] WebSocket Connection Closed")
                    pass
            
            if len(collected_logs) == 0:
                 print(f"⚠️ [Dokploy] Warning: No logs received via WebSocket. Retrying once...")
                 # Maybe wait a bit and try again? Or just return empty.
                 # Let's try one more seek if empty.
                 
            print(f"📦 [Dokploy] Raw logs received ({len(collected_logs)} chars)")
            if len(collected_logs) > 0:
                print(f"--- FULL LOGS START ---\n{collected_logs[:2000]}\n--- FULL LOGS END ---")
        except Exception as e:
            print(f"Error fetching logs: {e}")
        
        with open("collected_logs.txt", "w") as f:
            f.write(collected_logs)
        return collected_logs

    def _parse_logs(self, logs: str) -> Dict[str, Any]:
        """Extracts the result JSON from the logs, robustly stripping Dokploy timestamps from each line."""
        try:
            start_marker = "__DOKPLOY_RESULT_START__"
            end_marker = "__DOKPLOY_RESULT_END__"
            
            # 1. Split into lines
            lines = logs.splitlines()
            result_lines = []
            capturing = False
            
            # 2. Strict regex for Dokploy ISO timestamps
            # Matches strings like "2024-01-09T14:14:04.874924845Z "
            timestamp_regex = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z\s*')
            
            for line in lines:
                # Use "in" to find markers that might have timestamps prefixed
                if start_marker in line:
                    capturing = True
                    # If the marker line itself contains JSON start, handle it
                    content = line.split(start_marker)[-1]
                    content = timestamp_regex.sub('', content).strip()
                    if content:
                        result_lines.append(content)
                    continue
                
                if end_marker in line:
                    # If the end marker line has content before it, capture it
                    content = line.split(end_marker)[0]
                    content = timestamp_regex.sub('', content).strip()
                    if content:
                        result_lines.append(content)
                    capturing = False
                    break
                
                if capturing:
                    # Strip the timestamp prefix from this line
                    cleaned_line = timestamp_regex.sub('', line)
                    result_lines.append(cleaned_line)
            
            if result_lines:
                json_str = "".join(result_lines)
                
                # Final check: Ensure it starts with '{' (some junk might still be there)
                start_idx = json_str.find('{')
                if start_idx != -1:
                    json_str = json_str[start_idx:]
                
                # with open("logs_debug.json", "w") as f:
                #     f.write(json_str)
                    
                return json.loads(json_str)
                
        except Exception as e:
            print(f"Error parsing logs: {e}")
            traceback.print_exc()
            
        return {
            "success": False,
            "output": logs,
            "error": "Failed to parse execution result from logs",
            "plots": [],
            "tables": []
        }

    async def execute_code(self, code: str, file_paths: List[str] = None) -> Dict[str, Any]:
        """
        Executes code by creating/updating a Dokploy application and deploying a ZIP bundle.
        """
        # with open("code_execute.txt", "w") as f:
        #     f.write(code)
        print(f"[DokployClient] execute_code called. file_paths: {file_paths}")
        # 1. Update history and prepare combined code
        current_execution_code = "\n".join(self.code_history + [code])
        
        # 2. Application Name (Deterministic for reuse)
        # Use session_id if provided, otherwise a default
        uuid_new = uuid.uuid4()
        app_name = f"python-agent-{uuid_new}"
        
        print(f"🚀 [Dokploy] Starting execution for {app_name}")
        
        try:
            # 3. Check/Create Application
            app_id = None
            internal_app_name = None
            try:
                app_info = await self._create_application(app_name)
                app_id = app_info["applicationId"]
                internal_app_name = app_info.get("appName") # The internal Docker name
                print(f"🆕 [Dokploy] Created new application: {app_id} (Internal: {internal_app_name})")
                # Save Build Type only for new apps
                await self._save_build_type(app_id)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400 or "already exists" in e.response.text.lower():
                     print(f"🔄 [Dokploy] Application '{app_name}' already exists. Fetching details.")
                     # FETCH applications to find the ID and internal name
                     url = f"{DOKPLOY_BASE_URL}/api/application.all"
                     async with httpx.AsyncClient() as client:
                         resp = await client.get(url, headers=self._get_headers())
                         resp.raise_for_status()
                         apps = resp.json()
                         for a in apps:
                             if a["name"] == app_name:
                                 app_id = a["applicationId"]
                                 internal_app_name = a.get("appName")
                                 break
                else:
                    raise

            if not app_id:
                raise Exception(f"Could not resolve application ID for {app_name}")
            
            # 4. Upload Code (Drop Deployment)
            zip_content = self._create_zip_bundle(current_execution_code, file_paths)
            await self._upload_code(app_id, zip_content)
            
            # 5. Deploy
            await self._trigger_deploy(app_id)
            
            # 6. Monitor & Get Logs
            await self._monitor_deployment(app_id)
            
            # Wait for container to start (important for fresh containers)
            await asyncio.sleep(5)
            
            # Use internal_app_name for container lookup
            container_id = await self._get_container_id(app_id, internal_app_name)
            logs = await self._fetch_logs(container_id)
            
            # 7. Parse Results
            result = self._parse_logs(logs)

            with open("result.txt", "w") as f:
                f.write(str(result))
            
            if result["success"]:
                self.code_history.append(code)
                print(f"✅ [Dokploy] Execution successful. History size: {len(self.code_history)}")
            else:
                 print(f"❌ [Dokploy] Execution failed: {result.get('error')}")

            return result

        except Exception as e:
            import traceback
            error_msg = f"Dokploy execution error: {str(e)}\n{traceback.format_exc()}"
            print(f"❌ [Dokploy] {error_msg}")
            return {
                "success": False,
                "output": "",
                "error": error_msg,
                "plots": [],
                "tables": []
            }

