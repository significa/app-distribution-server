import secrets
import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from app_distribution_server.build_info import (
    BuildInfo,
    Platform,
    get_build_info,
)
from app_distribution_server.config import (
    UPLOADS_SECRET_AUTH_TOKEN,
    get_absolute_url,
)
from app_distribution_server.errors import (
    InvalidFileTypeError,
    NotFoundError,
    UnauthorizedError,
)
from app_distribution_server.logger import logger
from app_distribution_server.storage import (
    delete_upload,
    get_latest_upload_id_by_bundle_id,
    get_upload_asserted_platform,
    load_build_info,
    save_upload,
    list_all_uploaded_files,
    add_tag,
    get_all_tags,
    tag_exists,
    update_tag as storage_update_tag,
    save_upload_tags,
    load_upload_tags,
)

x_auth_token_dependency = APIKeyHeader(name="X-Auth-Token")


def x_auth_token_validator(
    x_auth_token: str = Depends(x_auth_token_dependency),
):
    if not secrets.compare_digest(x_auth_token, UPLOADS_SECRET_AUTH_TOKEN):
        raise UnauthorizedError()


router = APIRouter(
    tags=["API"],
)


def _upload_app(
    app_file: UploadFile,
    tags: list[str] = None
) -> BuildInfo:
    platform: Platform

    if app_file.filename is None:
        raise InvalidFileTypeError()

    if app_file.filename.endswith(".ipa"):
        platform = Platform.ios
    elif app_file.filename.endswith(".apk"):
        platform = Platform.android
    else:
        raise InvalidFileTypeError()

    app_file_content = app_file.file.read()
    build_info = get_build_info(platform, app_file_content)
    upload_id = build_info.upload_id

    logger.debug(f"Starting upload of {upload_id!r}")

    # Ensure tags are set on build_info before saving
    build_info.tags = tags or []

    save_upload(build_info, app_file_content, build_info.tags)
    logger.info(f"Successfully uploaded {build_info.bundle_id!r} ({upload_id!r})")

    return build_info


_upload_route_kwargs = {
    "responses": {
        InvalidFileTypeError.STATUS_CODE: {
            "description": InvalidFileTypeError.ERROR_MESSAGE,
        },
        UnauthorizedError.STATUS_CODE: {
            "description": UnauthorizedError.ERROR_MESSAGE,
        },
    },
    "summary": "Upload an iOS/Android app Build",
    "description": "On swagger UI authenticate in the upper right corner ('Authorize' button).",
}


@router.post("/upload", **_upload_route_kwargs)
def _plaintext_post_upload(
    app_file: UploadFile = File(description="An `.ipa` or `.apk` build"),
    tags: list[str] = Form(default=None, description="Optional list of tags to associate with this upload"),
) -> PlainTextResponse:
    valid_tags = []
    if tags:
        valid_tags = [t.strip() for t in tags if t.strip()]
        all_tags = set(get_all_tags())
        invalid_tags = [t for t in valid_tags if t not in all_tags]
        if invalid_tags:
            raise HTTPException(status_code=400, detail=f"Invalid tags: {invalid_tags}")
    build_info = _upload_app(app_file, valid_tags)
    return PlainTextResponse(
        content=get_absolute_url(f"/get/{build_info.upload_id}"),
    )


@router.post("/api/upload", **_upload_route_kwargs)
def _json_api_post_upload(
    app_file: UploadFile = File(description="An `.ipa` or `.apk` build"),
    tags: list[str] = Form(default=None, description="Optional list of tags to associate with this upload"),
) -> BuildInfo:
    valid_tags = []
    if tags:
        valid_tags = [t.strip() for t in tags if t.strip()]
        all_tags = set(get_all_tags())
        invalid_tags = [t for t in valid_tags if t not in all_tags]
        if invalid_tags:
            raise HTTPException(status_code=400, detail=f"Invalid tags: {invalid_tags}")
    return _upload_app(app_file, valid_tags)


async def _api_delete_app_upload(
    upload_id: str = Path(),
) -> PlainTextResponse:
    get_upload_asserted_platform(upload_id)

    delete_upload(upload_id)
    logger.info(f"Upload {upload_id!r} deleted successfully")

    return PlainTextResponse(status_code=200, content="Upload deleted successfully")


router.delete(
    "/api/delete/{upload_id}",
    summary="Delete an uploaded app build",
    response_class=PlainTextResponse,
)(_api_delete_app_upload)

router.delete(
    "/delete/{upload_id}",
    deprecated=True,
    summary="Delete an uploaded app build. Deprecated, use /api/delete/UPLOAD_ID instead",
    response_class=PlainTextResponse,
)(_api_delete_app_upload)


@router.get(
    "/api/bundle/{bundle_id}/latest_upload",
    summary="Retrieve the latest upload from a bundle ID",
)
def api_get_latest_upload_by_bundle_id(
    bundle_id: str = Path(
        pattern=r"^[a-zA-Z0-9\.\-\_]{1,256}$",
    ),
) -> BuildInfo:
    upload_id = get_latest_upload_id_by_bundle_id(bundle_id)

    if not upload_id:
        raise NotFoundError()

    get_upload_asserted_platform(upload_id)
    return load_build_info(upload_id)

def serialize(obj):
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize(v) for v in obj]
    elif isinstance(obj, datetime.datetime):
        return obj.isoformat()
    else:
        return obj

@router.get(
    "/api/uploads",
    summary="List all uploaded files with their URLs, optionally filtered by platform and tags",
    dependencies=[Depends(x_auth_token_validator)]
)
def api_list_all_uploaded_files(
    platform: str = Query(default=None, description="Filter by platform: 'android' or 'ios'"),
    tags: list[str] = Query(default=None, description="Filter by tags (multi-select)")
):
    uploads = list_all_uploaded_files()
    result = []
    platform = platform.lower() if platform else None
    tags_filter = set([t.strip() for t in tags if t.strip()]) if tags else None

    for upload_id, files in uploads.items():
        build_info = None
        try:
            build_info = load_build_info(upload_id)
            build_info_dict = build_info.model_dump() if hasattr(build_info, "model_dump") else build_info.__dict__
            build_info_dict = serialize(build_info_dict)
            # Platform filter
            if platform and (not hasattr(build_info, "platform") or build_info.platform.value.lower() != platform):
                continue
            # Tag filter (from build_info.tags)
            app_tags = set(getattr(build_info, "tags", []))
            if tags_filter and not tags_filter.issubset(app_tags):
                continue
        except Exception:
            continue  # skip this upload if build_info cannot be loaded

        for file_name in files:
            if file_name.startswith(".") or file_name.endswith(".json"):
                continue
            url = get_absolute_url(f"/get/{upload_id}")
            result.append({
                "upload_id": upload_id,
                "file_name": file_name,
                "url": url,
                "build_info": build_info_dict,
                "tags": list(getattr(build_info, "tags", []))
            })
    # Sort by created_at (descending). Be resilient if created_at is missing or unparsable.
    def _parse_created_at(value):
        if isinstance(value, datetime.datetime):
            return value
        if not value:
            return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        try:
            return datetime.datetime.fromisoformat(value)
        except Exception:
            return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)

    try:
        result.sort(
            key=lambda r: _parse_created_at(r.get("build_info", {}).get("created_at")),
            reverse=True,
        )
    except Exception:
        # In case of any unexpected data shape, fall back to unsorted result
        pass
    return JSONResponse(result)

class TagCreateRequest(BaseModel):
    tag: str

@router.post(
    "/api/tags",
    summary="Create a new tag (unique string)",
)
def create_tag(request: TagCreateRequest):
    tag = request.tag.strip()
    if not tag:
        raise HTTPException(status_code=400, detail="Tag cannot be empty")
    if not add_tag(tag):
        raise HTTPException(status_code=409, detail="Tag already exists")
    return {"tag": tag}

@router.get(
    "/api/tags",
    summary="Get all tags",
)
def get_tags():
    return {"tags": get_all_tags()}

@router.get(
    "/api/tags/{tag}",
    summary="Get a single tag",
)
def get_tag(tag: str = Path()):
    if not tag_exists(tag):
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"tag": tag}

@router.put(
    "/api/tags/{old_tag}",
    summary="Update a tag (rename)",
)
def update_tag(old_tag: str = Path(), new_tag: str = None):
    if new_tag is None or not new_tag.strip():
        raise HTTPException(status_code=400, detail="New tag cannot be empty")
    new_tag = new_tag.strip()
    if not tag_exists(old_tag):
        raise HTTPException(status_code=404, detail="Old tag not found")
    if tag_exists(new_tag):
        raise HTTPException(status_code=409, detail="New tag already exists")
    if not storage_update_tag(old_tag, new_tag):
        raise HTTPException(status_code=400, detail="Failed to update tag")
    return {"old_tag": old_tag, "new_tag": new_tag}

@router.get(
    "/api/uploads/{upload_id}/tags",
    summary="Get tags associated with an upload",
)
def get_upload_tags(upload_id: str = Path()):
    tags = load_upload_tags(upload_id)
    return {"upload_id": upload_id, "tags": tags}

@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login - App Distribution Server</title>
        <style>
            body {
                font-family: 'Segoe UI', Arial, sans-serif;
                background: #f4f6fb;
                margin: 0;
                padding: 0;
            }
            .login-box {
                max-width: 400px;
                margin: 6em auto;
                padding: 2.5em 2em 2em 2em;
                background: #fff;
                border-radius: 12px;
                box-shadow: 0 2px 16px rgba(44, 62, 80, 0.12);
                border: 1px solid #e0e6ed;
            }
            h2 {
                text-align: center;
                color: #2a4d8f;
                margin-bottom: 1.5em;
                font-size: 2em;
                font-weight: 700;
            }
            label {
                font-weight: 500;
                color: #2a4d8f;
                margin-bottom: 0.5em;
                display: block;
            }
            input[type="text"] {
                width: 100%;
                padding: 0.7em;
                border-radius: 6px;
                border: 1px solid #bfc9da;
                font-size: 1.1em;
                margin-bottom: 1.2em;
                transition: border 0.2s;
            }
            input[type="text"]:focus {
                border: 1.5px solid #2a4d8f;
                outline: none;
            }
            button {
                width: 100%;
                padding: 0.7em;
                background: #2a4d8f;
                color: #fff;
                border: none;
                border-radius: 6px;
                font-size: 1.1em;
                font-weight: 600;
                cursor: pointer;
                transition: background 0.2s;
                margin-bottom: 0.5em;
            }
            button:hover {
                background: #16325c;
            }
            #msg {
                text-align: center;
                margin-top: 1em;
                font-size: 1em;
                color: #27ae60;
            }
            .footer {
                text-align: center;
                margin-top: 2em;
                color: #888;
                font-size: 0.95em;
            }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>App Distribution Login</h2>
            <form id="loginForm" onsubmit="saveToken(event)">
                <label for="token">X-Auth-Token</label>
                <input type="text" id="token" name="token" required autocomplete="off" placeholder="Enter your token" />
                <button type="submit">Login</button>
            </form>
            <div id="msg"></div>
            <div class="footer">
                &copy; 2025 App Distribution Server
            </div>
        </div>
        <script>
            function saveToken(e) {
                e.preventDefault();
                const token = document.getElementById('token').value.trim();
                const msgDiv = document.getElementById('msg');
                if (!token) {
                    msgDiv.textContent = "Token is required.";
                    msgDiv.style.color = "#e74c3c";
                    return;
                }
                localStorage.setItem('X-Auth-Token', token);
                msgDiv.textContent = "Token saved! Redirecting...";
                msgDiv.style.color = "#27ae60";
                setTimeout(() => { window.location.href = "/"; }, 700);
            }
            window.onload = function() {
                const token = localStorage.getItem('X-Auth-Token');
                if (token) document.getElementById('token').value = token;
            };
        </script>
    </body>
    </html>
    """


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>App Distribution Server - Home</title>
        <style>
            body {
                font-family: 'Segoe UI', Arial, sans-serif;
                margin: 0;
                padding: 0;
                background: #f4f6fb;
                color: #222;
            }
            .container {
                max-width: 1200px;
                margin: 2em auto;
                background: #fff;
                border-radius: 10px;
                box-shadow: 0 2px 12px rgba(0,0,0,0.07);
                padding: 2em 3em;
            }
            .header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 2em;
            }
            .header h1 {
                margin: 0;
                color: #2a4d8f;
                font-size: 2.2em;
            }
            .logout {
                background: #e74c3c;
                color: #fff;
                border: none;
                border-radius: 5px;
                padding: 0.5em 1.2em;
                font-size: 1em;
                cursor: pointer;
                transition: background 0.2s;
            }
            .logout:hover {
                background: #c0392b;
            }
            .drawer-btn {
                background: #2a4d8f;
                color: #fff;
                border: none;
                border-radius: 5px;
                padding: 0.5em 1.2em;
                font-size: 1em;
                cursor: pointer;
                margin-bottom: 1em;
                transition: background 0.2s;
            }
            .drawer-btn:hover {
                background: #16325c;
            }
            .drawer {
                position: fixed;
                top: 0;
                right: 0;
                width: 400px;
                height: 100%;
                background: #fff;
                box-shadow: -2px 0 12px rgba(0,0,0,0.12);
                z-index: 1000;
                padding: 2em 1.5em;
                overflow-y: auto;
                transition: transform 0.3s, visibility 0.3s;
                transform: translateX(100%);
                visibility: hidden;
                display: none;
            }
            .drawer.open {
                transform: translateX(0);
                visibility: visible;
                display: block;
            }
            .drawer-close {
                background: #e74c3c;
                color: #fff;
                border: none;
                border-radius: 5px;
                padding: 0.3em 1em;
                font-size: 1em;
                cursor: pointer;
                float: right;
                margin-bottom: 1em;
            }
            .drawer-close:hover {
                background: #c0392b;
            }
            .section-title {
                color: #2a4d8f;
                font-size: 1.3em;
                margin-bottom: 1em;
                font-weight: 600;
            }
            .filter-row {
                display: flex;
                gap: 2em;
                align-items: center;
                margin-bottom: 1em;
            }
            .filter-row label {
                font-weight: 500;
                color: #2a4d8f;
            }
            .filter-row select, .filter-row button {
                margin-left: 0.5em;
                padding: 0.3em 0.7em;
                border-radius: 4px;
                border: 1px solid #bfc9da;
                font-size: 1em;
            }
            .filter-row button {
                background: #2a4d8f;
                color: #fff;
                border: none;
                cursor: pointer;
                transition: background 0.2s;
            }
            .filter-row button:hover {
                background: #16325c;
            }
            .app-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 1em;
            }
            .app-table th, .app-table td {
                border: 1px solid #e0e6ed;
                padding: 0.7em 0.5em;
                text-align: left;
            }
            .app-table th {
                background: #2a4d8f;
                color: #fff;
                font-weight: 600;
            }
            .app-table tr:nth-child(even) {
                background: #f7f9fc;
            }
            .tag {
                background: #2a4d8f;
                color: #fff;
                border-radius: 3px;
                padding: 2px 8px;
                margin-right: 6px;
                font-size: 0.92em;
                display: inline-block;
                margin-top: 2px;
            }
            .no-data {
                text-align: center;
                color: #888;
                margin: 2em 0;
                font-size: 1.1em;
            }
            .upload-form, .tag-form, .tag-update-form {
                display: flex;
                gap: 1em;
                align-items: center;
                margin-bottom: 1em;
                flex-wrap: wrap;
            }
            .upload-form input[type="file"], .upload-form select, .upload-form button,
            .tag-form input, .tag-form button, .tag-update-form input, .tag-update-form button {
                padding: 0.4em 0.7em;
                border-radius: 4px;
                border: 1px solid #bfc9da;
                font-size: 1em;
            }
            .upload-form button, .tag-form button, .tag-update-form button {
                background: #27ae60;
                color: #fff;
                border: none;
                cursor: pointer;
                transition: background 0.2s;
            }
            .upload-form button:hover, .tag-form button:hover, .tag-update-form button:hover {
                background: #219150;
            }
            .tag-list {
                margin-top: 1em;
            }
            .tag-list span {
                margin-right: 8px;
            }
            .success-msg {
                color: #27ae60;
                margin-left: 1em;
            }
            .error-msg {
                color: #e74c3c;
                margin-left: 1em;
            }
            .clear-btn {
                background: #bfc9da;
                color: #2a4d8f;
                border: none;
                border-radius: 4px;
                padding: 0.3em 1em;
                margin-left: 1em;
                cursor: pointer;
                font-size: 1em;
                transition: background 0.2s;
            }
            .clear-btn:hover {
                background: #e74c3c;
                color: #fff;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>App Distribution Server</h1>
                <button class="logout" onclick="logout()">Logout</button>
            </div>
            <button class="drawer-btn" onclick="toggleDrawer()">Upload / Tag Management</button>
            <div class="section">
                <div class="section-title">Uploaded Apps</div>
                <div class="filter-row">
                    <label>
                        Platform:
                        <select id="platform">
                            <option value="">All</option>
                            <option value="android">Android</option>
                            <option value="ios">iOS</option>
                        </select>
                    </label>
                    <label>
                        Tags:
                        <select id="tags" multiple size="3"></select>
                    </label>
                    <button onclick="fetchApps()">Filter</button>
                    <button class="clear-btn" onclick="clearTagFilter()">Clear Tags</button>
                </div>
                <div id="appTableContainer"></div>
            </div>
        </div>
        <div class="drawer" id="drawer">
            <button class="drawer-close" onclick="closeDrawer()">Close</button>
            <div class="section-title">Upload App</div>
            <form class="upload-form" id="uploadForm" enctype="multipart/form-data" onsubmit="uploadApp(event)">
                <input type="file" id="appFile" name="appFile" accept=".apk,.ipa" required />
                <label for="uploadTags">Tags:</label>
                <select id="uploadTags" name="tags" multiple size="3"></select>
                <button type="submit">Upload</button>
                <span id="uploadMsg"></span>
            </form>
            <hr>
            <div class="section-title">Manage Tags</div>
            <form class="tag-form" id="tagForm" onsubmit="createTag(event)">
                <input type="text" id="newTag" placeholder="New tag name" required />
                <button type="submit">Create Tag</button>
                <span id="tagMsg"></span>
            </form>
            <form class="tag-update-form" id="tagUpdateForm" onsubmit="updateTag(event)">
                <select id="oldTagSelect" required></select>
                <input type="text" id="updatedTag" placeholder="New tag name" required />
                <button type="submit">Update Tag</button>
                <span id="tagUpdateMsg"></span>
            </form>
            <div class="tag-list" id="tagList"></div>
        </div>
        <script>
            function toggleDrawer() {
                const drawer = document.getElementById('drawer');
                if (drawer.classList.contains('open')) {
                    closeDrawer();
                } else {
                    openDrawer();
                }
            }
            function openDrawer() {
                const drawer = document.getElementById('drawer');
                drawer.style.display = 'block';
                setTimeout(() => {
                    drawer.classList.add('open');
                }, 10);
            }
            function closeDrawer() {
                const drawer = document.getElementById('drawer');
                drawer.classList.remove('open');
                setTimeout(() => {
                    drawer.style.display = 'none';
                }, 300);
            }
            // Ensure drawer is hidden on page load
            window.onload = async function() {
                document.getElementById('drawer').classList.remove('open');
                document.getElementById('drawer').style.display = 'none';
                checkToken();
                await fetchTagsForAll();
                await fetchApps();
            };
            function getToken() {
                return localStorage.getItem('X-Auth-Token');
            }
            function logout() {
                localStorage.removeItem('X-Auth-Token');
                window.location.href = "/login";
            }
            function checkToken() {
                if (!getToken()) {
                    window.location.href = "/login";
                }
            }
            async function fetchTagsForAll() {
                checkToken();
                try {
                    const res = await fetch('/api/tags', {
                        headers: { 'X-Auth-Token': getToken() }
                    });
                    const data = await res.json();
                    const tags = (data.tags || []);
                    // For filter
                    const tagsSelect = document.getElementById('tags');
                    tagsSelect.innerHTML = '';
                    if (tags.length === 0) {
                        const opt = document.createElement('option');
                        opt.disabled = true;
                        opt.textContent = "No tags available";
                        tagsSelect.appendChild(opt);
                    } else {
                        tags.forEach(tag => {
                            const opt = document.createElement('option');
                            opt.value = tag;
                            opt.textContent = tag;
                            tagsSelect.appendChild(opt);
                        });
                    }
                    // For upload
                    const uploadTagsSelect = document.getElementById('uploadTags');
                    uploadTagsSelect.innerHTML = '';
                    if (tags.length === 0) {
                        const opt = document.createElement('option');
                        opt.disabled = true;
                        opt.textContent = "No tags available";
                        uploadTagsSelect.appendChild(opt);
                    } else {
                        tags.forEach(tag => {
                            const opt = document.createElement('option');
                            opt.value = tag;
                            opt.textContent = tag;
                            uploadTagsSelect.appendChild(opt);
                        });
                    }
                    // For tag update
                    const oldTagSelect = document.getElementById('oldTagSelect');
                    oldTagSelect.innerHTML = '';
                    if (tags.length === 0) {
                        const opt = document.createElement('option');
                        opt.disabled = true;
                        opt.textContent = "No tags available";
                        oldTagSelect.appendChild(opt);
                    } else {
                        tags.forEach(tag => {
                            const opt = document.createElement('option');
                            opt.value = tag;
                            opt.textContent = tag;
                            oldTagSelect.appendChild(opt);
                        });
                    }
                    // Tag list
                    const tagList = document.getElementById('tagList');
                    tagList.innerHTML = '';
                    if (tags.length === 0) {
                        tagList.innerHTML = '<span style="color:#888;">No tags available.</span>';
                    } else {
                        tagList.innerHTML = tags.map(t => `<span class="tag">${t}</span>`).join('');
                    }
                } catch (e) {
                    document.getElementById('tagList').innerHTML = '<span style="color:#e74c3c;">Error loading tags.</span>';
                }
            }
            async function fetchApps() {
                checkToken();
                const platform = document.getElementById('platform').value;
                const tagsSelect = document.getElementById('tags');
                const selectedTags = Array.from(tagsSelect.selectedOptions).map(opt => opt.value);
                let url = '/api/uploads?';
                if (platform) url += 'platform=' + encodeURIComponent(platform) + '&';
                selectedTags.forEach(tag => { url += 'tags=' + encodeURIComponent(tag) + '&'; });
                const appTableContainer = document.getElementById('appTableContainer');
                appTableContainer.innerHTML = '';
                try {
                    const res = await fetch(url, {
                        headers: { 'X-Auth-Token': getToken() }
                    });
                    const data = await res.json();
                    if (!Array.isArray(data) || data.length === 0) {
                        appTableContainer.innerHTML = '<div class="no-data">No apps found.</div>';
                        return;
                    }
                    let table = `<table class="app-table">
                        <thead>
                            <tr>
                                <th>File Name</th>
                                <th>Platform</th>
                                <th>Bundle ID</th>
                                <th>Version</th>
                                <th>Created At</th>
                                <th>Tags</th>
                                <th>Download</th>
                            </tr>
                        </thead>
                        <tbody>`;
                    data.forEach(app => {
                        let createdAt = app.build_info?.created_at || '';
                        if (createdAt) {
                            try {
                                createdAt = new Date(createdAt).toLocaleString();
                            } catch (e) {}
                        }
                        table += `<tr>
                            <td>${app.file_name}</td>
                            <td>${app.build_info?.platform || 'unknown'}</td>
                            <td>${app.build_info?.bundle_id || ''}</td>
                            <td>${app.build_info?.bundle_version || ''}</td>
                            <td>${createdAt}</td>
                            <td>${
                                (app.tags && app.tags.length > 0)
                                ? app.tags.map(t => `<span class="tag">${t}</span>`).join(' ')
                                : '<span style="color:#888;">No tags</span>'
                            }</td>
                            <td><a class="download-link" href="${app.url}" target="_blank">Download</a></td>
                        </tr>`;
                    });
                    table += '</tbody></table>';
                    appTableContainer.innerHTML = table;
                } catch (e) {
                    appTableContainer.innerHTML = '<div class="no-data">Error loading apps.</div>';
                }
            }
            async function uploadApp(e) {
                e.preventDefault();
                checkToken();
                const fileInput = document.getElementById('appFile');
                const tagsSelect = document.getElementById('uploadTags');
                const selectedTags = Array.from(tagsSelect.selectedOptions).map(opt => opt.value);
                const uploadMsg = document.getElementById('uploadMsg');
                uploadMsg.textContent = '';
                if (!fileInput.files.length) {
                    uploadMsg.textContent = 'Please select a file.';
                    uploadMsg.className = 'error-msg';
                    return;
                }
                const formData = new FormData();
                formData.append('app_file', fileInput.files[0]);
                selectedTags.forEach(tag => formData.append('tags', tag));
                try {
                    const res = await fetch('/upload', {
                        method: 'POST',
                        headers: { 'X-Auth-Token': getToken() },
                        body: formData
                    });
                    if (res.ok) {
                        uploadMsg.textContent = 'Upload successful!';
                        uploadMsg.className = 'success-msg';
                        fileInput.value = '';
                        await fetchApps();
                    } else {
                        const data = await res.json();
                        uploadMsg.textContent = data.detail || 'Upload failed.';
                        uploadMsg.className = 'error-msg';
                    }
                } catch (err) {
                    uploadMsg.textContent = 'Upload failed.';
                    uploadMsg.className = 'error-msg';
                }
            }
            async function createTag(e) {
                e.preventDefault();
                checkToken();
                const newTagInput = document.getElementById('newTag');
                const tagMsg = document.getElementById('tagMsg');
                tagMsg.textContent = '';
                const tag = newTagInput.value.trim();
                if (!tag) {
                    tagMsg.textContent = 'Tag name required.';
                    tagMsg.className = 'error-msg';
                    return;
                }
                try {
                    const res = await fetch('/api/tags', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Auth-Token': getToken()
                        },
                        body: JSON.stringify({ tag })
                    });
                    if (res.ok) {
                        tagMsg.textContent = 'Tag created!';
                        tagMsg.className = 'success-msg';
                        newTagInput.value = '';
                        await fetchTagsForAll();
                    } else {
                        const data = await res.json();
                        tagMsg.textContent = data.detail || 'Failed to create tag.';
                        tagMsg.className = 'error-msg';
                    }
                } catch (err) {
                    tagMsg.textContent = 'Failed to create tag.';
                    tagMsg.className = 'error-msg';
                }
            }
            async function updateTag(e) {
                e.preventDefault();
                checkToken();
                const oldTagSelect = document.getElementById('oldTagSelect');
                const updatedTagInput = document.getElementById('updatedTag');
                const tagUpdateMsg = document.getElementById('tagUpdateMsg');
                tagUpdateMsg.textContent = '';
                const oldTag = oldTagSelect.value;
                const newTag = updatedTagInput.value.trim();
                if (!oldTag || !newTag) {
                    tagUpdateMsg.textContent = 'Both fields required.';
                    tagUpdateMsg.className = 'error-msg';
                    return;
                }
                try {
                    const res = await fetch(`/api/tags/${encodeURIComponent(oldTag)}?new_tag=${encodeURIComponent(newTag)}`, {
                        method: 'PUT',
                        headers: { 'X-Auth-Token': getToken() }
                    });
                    if (res.ok) {
                        tagUpdateMsg.textContent = 'Tag updated!';
                        tagUpdateMsg.className = 'success-msg';
                        updatedTagInput.value = '';
                        await fetchTagsForAll();
                    } else {
                        const data = await res.json();
                        tagUpdateMsg.textContent = data.detail || 'Failed to update tag.';
                        tagUpdateMsg.className = 'error-msg';
                    }
                } catch (err) {
                    tagUpdateMsg.textContent = 'Failed to update tag.';
                    tagUpdateMsg.className = 'error-msg';
                }
            }
            function clearTagFilter() {
                const tagsSelect = document.getElementById('tags');
                Array.from(tagsSelect.options).forEach(opt => opt.selected = false);
                fetchApps();
            }
            window.onload = async function() {
                checkToken();
                await fetchTagsForAll();
                await fetchApps();
            };
        </script>
    </body>
    </html>
    """



