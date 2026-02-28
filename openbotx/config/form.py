# Supported field types:
#   text, email, int, float, bool, secret, long-text,
#   select, credential, provider,
#   datetime, date, time, color

FORM_SCHEMAS: dict[str, list[dict]] = {
    "bot": [
        {"name": "name", "type": "text", "label": "Bot Name", "required": True},
        {"name": "description", "type": "text", "label": "Description"},
    ],
    "server": [
        {"name": "host", "type": "text", "label": "Host", "placeholder": "0.0.0.0"},
        {"name": "port", "type": "int", "label": "Port"},
        {
            "name": "public_url",
            "type": "text",
            "label": "Public URL",
            "placeholder": "Leave empty for http://localhost:PORT",
        },
        {"name": "credential", "type": "credential", "label": "JWT Secret (Credential)"},
    ],
    "web_client": [
        {"name": "credential", "type": "credential", "label": "Credential"},
    ],
    "storage": [
        {
            "name": "type",
            "type": "select",
            "label": "Storage Type",
            "options": [
                {"label": "Local", "value": "local"},
                {"label": "S3", "value": "s3"},
            ],
        },
        {
            "name": "local_path",
            "type": "text",
            "label": "Local Path",
            "visible_when": {"type": "local"},
        },
        {"name": "s3_bucket", "type": "text", "label": "S3 Bucket", "visible_when": {"type": "s3"}},
        {"name": "s3_region", "type": "text", "label": "S3 Region", "visible_when": {"type": "s3"}},
        {
            "name": "credential",
            "type": "credential",
            "label": "Credential",
            "visible_when": {"type": "s3"},
        },
    ],
    "tools_general": [
        {"name": "restrict_to_workspace", "type": "bool", "label": "Restrict to Workspace"},
    ],
    "tools_exec": [
        {"name": "timeout", "type": "int", "label": "Timeout (seconds)"},
    ],
    "tools_web_search": [
        {"name": "credential", "type": "credential", "label": "Credential"},
        {"name": "max_results", "type": "int", "label": "Max Results"},
    ],
    "channels_telegram": [
        {"name": "enabled", "type": "bool", "label": "Enabled"},
        {"name": "credential", "type": "credential", "label": "Credential"},
        {"name": "allowed_users", "type": "text", "label": "Allowed Users (comma-separated)"},
        {"name": "proxy", "type": "text", "label": "Proxy URL"},
        {"name": "reply_to_message", "type": "bool", "label": "Reply to Message"},
    ],
    "image": [
        {"name": "model", "type": "text", "label": "Model", "placeholder": "openai/dall-e-3"},
    ],
    "agent": [
        {"name": "workspace", "type": "text", "label": "Workspace"},
        {"name": "model", "type": "text", "label": "Model", "required": True},
        {"name": "description", "type": "text", "label": "Description"},
        {"name": "instructions", "type": "long-text", "label": "Instructions"},
    ],
    "provider": [
        {
            "name": "credential",
            "type": "credential",
            "label": "Credential",
            "required": True,
        },
        {
            "name": "base_url",
            "type": "text",
            "label": "Base URL",
            "placeholder": "Leave empty to use default endpoint",
        },
    ],
    "credential": [
        {
            "name": "type",
            "type": "select",
            "label": "Type",
            "required": True,
            "options": [
                {"label": "Simple (API Key / Token)", "value": "simple"},
                {"label": "OAuth 1.0", "value": "oauth1"},
                {"label": "Basic Auth", "value": "basic"},
                {"label": "Login", "value": "login"},
                {"label": "AWS", "value": "aws"},
                {"label": "Header", "value": "header"},
                {"label": "Bearer", "value": "bearer"},
            ],
        },
        # simple
        {"name": "key", "type": "secret", "label": "Key", "visible_when": {"type": "simple"}},
        # oauth1
        {
            "name": "consumer_key",
            "type": "secret",
            "label": "Consumer Key",
            "placeholder": "Leave empty to keep current",
            "visible_when": {"type": "oauth1"},
        },
        {
            "name": "consumer_secret",
            "type": "secret",
            "label": "Consumer Secret",
            "placeholder": "Leave empty to keep current",
            "visible_when": {"type": "oauth1"},
        },
        {
            "name": "access_token",
            "type": "secret",
            "label": "Access Token",
            "placeholder": "Leave empty to keep current",
            "visible_when": {"type": "oauth1"},
        },
        {
            "name": "access_token_secret",
            "type": "secret",
            "label": "Access Token Secret",
            "placeholder": "Leave empty to keep current",
            "visible_when": {"type": "oauth1"},
        },
        # basic / login
        {
            "name": "username",
            "type": "text",
            "label": "Username",
            "visible_when": {"type": ["basic", "login"]},
        },
        {
            "name": "password",
            "type": "secret",
            "label": "Password",
            "visible_when": {"type": ["basic", "login"]},
        },
        # aws
        {
            "name": "access_key",
            "type": "secret",
            "label": "Access Key",
            "visible_when": {"type": "aws"},
        },
        {
            "name": "secret_key",
            "type": "secret",
            "label": "Secret Key",
            "visible_when": {"type": "aws"},
        },
        # header
        {
            "name": "header_name",
            "type": "text",
            "label": "Header Name",
            "placeholder": "e.g. Authorization, X-API-Key",
            "visible_when": {"type": "header"},
        },
        {
            "name": "value",
            "type": "secret",
            "label": "Value",
            "placeholder": "Leave empty to keep current",
            "visible_when": {"type": "header"},
        },
        # bearer
        {
            "name": "token",
            "type": "secret",
            "label": "Token",
            "placeholder": "Leave empty to keep current",
            "visible_when": {"type": "bearer"},
        },
    ],
    "login": [
        {"name": "username", "type": "text", "label": "Username", "required": True},
        {"name": "password", "type": "secret", "label": "Password", "required": True},
    ],
    "scheduler_job": [
        {"name": "name", "type": "text", "label": "Name", "required": True},
        {"name": "message", "type": "text", "label": "Message", "required": True},
        {
            "name": "type",
            "type": "select",
            "label": "Schedule Type",
            "options": [
                {"label": "Interval", "value": "every"},
                {"label": "Cron Expression", "value": "cron"},
                {"label": "One-time", "value": "at"},
            ],
        },
        {
            "name": "every_seconds",
            "type": "int",
            "label": "Interval (seconds)",
            "visible_when": {"type": "every"},
        },
        {
            "name": "cron_expr",
            "type": "text",
            "label": "Cron Expression",
            "placeholder": "0 9 * * *",
            "visible_when": {"type": "cron"},
        },
        {"name": "at", "type": "datetime", "label": "Date/Time", "visible_when": {"type": "at"}},
    ],
    "create_file": [
        {"name": "name", "type": "text", "label": "File Name", "required": True},
    ],
    "create_folder": [
        {"name": "name", "type": "text", "label": "Folder Name", "required": True},
    ],
}
