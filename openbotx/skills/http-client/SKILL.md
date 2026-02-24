---
name: http-client
description: Make HTTP requests (GET, POST, PUT, PATCH, DELETE) to APIs and web services. Use when the user needs to call a REST API, fetch data from an endpoint, send form data, upload files, or test HTTP services.
---

# HTTP Client

Use the `http_client` tool to make HTTP requests directly without needing curl or external binaries.

## Tool: `http_client`

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
http_client(method="POST", url="https://api.example.com/users", headers={"Content-Type": "application/json"}, body="{\"name\": \"Alice\", \"email\": \"alice@example.com\"}")
```

### PUT (full update)

```
http_client(method="PUT", url="https://api.example.com/users/42", headers={"Content-Type": "application/json"}, body="{\"name\": \"Alice Updated\", \"email\": \"alice@example.com\"}")
```

### PATCH (partial update)

```
http_client(method="PATCH", url="https://api.example.com/users/42", headers={"Content-Type": "application/json"}, body="{\"name\": \"Alice Updated\"}")
```

### DELETE

```
http_client(method="DELETE", url="https://api.example.com/users/42")
```

## Authentication

### Bearer token

```
http_client(method="GET", url="https://api.example.com/me", headers={"Authorization": "Bearer eyJhbGciOi..."})
```

### Basic auth

```
http_client(method="GET", url="https://api.example.com/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
```

### API key in header

```
http_client(method="GET", url="https://api.example.com/data", headers={"X-API-Key": "your-api-key"})
```

## Body Types

### JSON

```
http_client(method="POST", url="https://api.example.com/data", headers={"Content-Type": "application/json"}, body="{\"key\": \"value\"}")
```

### Form-encoded

```
http_client(method="POST", url="https://api.example.com/login", headers={"Content-Type": "application/x-www-form-urlencoded"}, body="username=alice&password=secret")
```

### Plain text

```
http_client(method="POST", url="https://api.example.com/text", headers={"Content-Type": "text/plain"}, body="Hello, world!")
```

## Tips

- The response includes status code, headers, and body.
- For APIs that return JSON, parse the response body as needed.
- Set `Content-Type` header explicitly when sending a body.
- Use GET for reads, POST for creates, PUT for full replacements, PATCH for partial updates, DELETE for removals.
- For file downloads, prefer using the `exec` tool with `curl -o` instead.
