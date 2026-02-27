---
name: http-client
description: Make HTTP requests (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS) to APIs and web services. Use when the user needs to call a REST API, fetch data from an endpoint, send form data, upload files, download files, or test HTTP services.
---

# HTTP Client

Use the `http_client` tool to make HTTP requests directly without needing curl or external binaries.

## Tool: `http_client`

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `method` | string | Yes | `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `HEAD`, or `OPTIONS` |
| `url` | string | Yes | Request URL |
| `headers` | object | No | HTTP headers as key-value pairs |
| `body` | string | No | Request body |
| `content_type` | string | No | Body content type: `json` (default), `form`, `text`, or `xml` |
| `auth` | string | No | Auth profile name for authenticated requests (configured in config) |
| `timeout` | integer | No | Timeout in seconds (default: 30) |
| `follow_redirects` | boolean | No | Follow redirects (default: true) |
| `download_path` | string | No | Save response body to this file path |
| `upload_file` | string | No | Path to file to upload as multipart form data |
| `upload_field` | string | No | Form field name for uploaded file (default: `file`) |

### Basic GET

```
http_client(method="GET", url="https://api.example.com/users")
```

### GET with query parameters

```
http_client(method="GET", url="https://api.example.com/users?page=2&limit=10")
```

### GET with custom headers

```
http_client(method="GET", url="https://api.example.com/users", headers={"Accept": "application/json", "X-Custom-Header": "value"})
```

### POST with JSON body

```
http_client(method="POST", url="https://api.example.com/users", body="{\"name\": \"Alice\", \"email\": \"alice@example.com\"}")
```

The `content_type` defaults to `json`, which sets `Content-Type: application/json` automatically.

### POST with form-encoded body

```
http_client(method="POST", url="https://api.example.com/login", content_type="form", body="username=alice&password=secret")
```

### POST with XML body

```
http_client(method="POST", url="https://api.example.com/soap", content_type="xml", body="<request><action>query</action></request>")
```

### PUT (full update)

```
http_client(method="PUT", url="https://api.example.com/users/42", body="{\"name\": \"Alice Updated\", \"email\": \"alice@example.com\"}")
```

### PATCH (partial update)

```
http_client(method="PATCH", url="https://api.example.com/users/42", body="{\"name\": \"Alice Updated\"}")
```

### DELETE

```
http_client(method="DELETE", url="https://api.example.com/users/42")
```

### HEAD (check resource existence)

```
http_client(method="HEAD", url="https://api.example.com/users/42")
```

### OPTIONS (check allowed methods)

```
http_client(method="OPTIONS", url="https://api.example.com/users")
```

## Authentication

### Auth profiles (recommended)

Use the `auth` parameter with a configured profile name. Auth profiles support OAuth 1.0a, Basic, and Bearer authentication automatically:

```
http_client(method="POST", url="https://api.twitter.com/2/tweets", auth="twitter", body="{\"text\": \"Hello!\"}")
http_client(method="GET", url="https://api.example.com/data", auth="my_api")
```

### Manual headers

You can also pass auth headers manually:

```
http_client(method="GET", url="https://api.example.com/me", headers={"Authorization": "Bearer eyJhbGciOi..."})
http_client(method="GET", url="https://api.example.com/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
http_client(method="GET", url="https://api.example.com/data", headers={"X-API-Key": "your-api-key"})
```

## Download

Save a response directly to a file using `download_path`. Use the absolute paths from your system prompt:

```
http_client(method="GET", url="https://example.com/report.pdf", download_path="/path/to/workspace/reports/report.pdf")
```

Download an image to the public media directory:

```
http_client(method="GET", url="https://example.com/photo.jpg", download_path="/path/to/public/media/photo.jpg")
```

Returns: `{"status": 200, "path": "/absolute/path/to/file", "size": 12345, "content_type": "application/pdf"}`

## Upload

Upload a file as multipart form data using `upload_file`:

```
http_client(method="POST", url="https://api.example.com/upload", upload_file="reports/data.csv")
```

Custom field name (default is "file"):

```
http_client(method="POST", url="https://api.example.com/upload", upload_file="images/logo.png", upload_field="image")
```

Upload with extra form fields (pass as JSON in body):

```
http_client(method="POST", url="https://api.example.com/upload", upload_file="doc.pdf", body="{\"description\": \"Monthly report\"}")
```

Upload with auth:

```
http_client(method="POST", url="https://api.example.com/upload", upload_file="data.csv", headers={"Authorization": "Bearer token123"})
```

## Advanced Options

### Custom timeout

```
http_client(method="GET", url="https://slow-api.example.com/data", timeout=120)
```

### Disable redirect following

```
http_client(method="GET", url="https://example.com/redirect", follow_redirects=false)
```

## Tips

- The response includes `status`, `headers`, `body`, and `truncated` fields.
- Response bodies larger than 50,000 characters are truncated.
- For APIs that return JSON, parse the response body as needed.
- The `content_type` parameter sets the `Content-Type` header automatically: `json` → `application/json`, `form` → `application/x-www-form-urlencoded`, `text` → `text/plain`, `xml` → `application/xml`.
- Use GET for reads, POST for creates, PUT for full replacements, PATCH for partial updates, DELETE for removals, HEAD for existence checks, OPTIONS for CORS/capability checks.
- Use `download_path` for binary files (images, PDFs, audio) — avoids encoding issues.
- Use `upload_file` for multipart uploads — auto-detects MIME type from file extension.
