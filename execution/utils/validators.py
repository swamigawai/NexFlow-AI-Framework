import re
import os
import json
from urllib.parse import urlparse
from typing import Optional, Dict, Any, List
from datetime import datetime

class ValidationError(Exception):
    pass

def validate_url(url: str) -> str:
    """Validates URL format."""
    if not url or not isinstance(url, str):
        raise ValidationError("URL must be a non-empty string")
    parsed = urlparse(url)
    if not all([parsed.scheme, parsed.netloc]):
        raise ValidationError(f"Invalid URL format: {url}")
    if parsed.scheme not in ["http", "https"]:
        raise ValidationError(f"Invalid scheme: {parsed.scheme}. Only http and https are allowed.")
    return url

def validate_email(email: str) -> str:
    """Validates email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not isinstance(email, str) or not re.match(pattern, email):
        raise ValidationError(f"Invalid email: {email}")
    return email

def validate_file_exists(filepath: str) -> str:
    """Validates if file exists."""
    if not isinstance(filepath, str) or not os.path.isfile(filepath):
        raise ValidationError(f"File not found: {filepath}")
    return filepath

def validate_directory_exists(dirpath: str) -> str:
    """Validates if directory exists."""
    if not isinstance(dirpath, str) or not os.path.isdir(dirpath):
        raise ValidationError(f"Directory not found: {dirpath}")
    return dirpath

def sanitize_filename(filename: str) -> str:
    """Sanitizes filename to prevent path traversal."""
    if not filename or not isinstance(filename, str):
        raise ValidationError("Filename must be a non-empty string")
    cleaned = re.sub(r'[^\w\.-]', '_', os.path.basename(filename))
    if not cleaned:
        raise ValidationError("Filename is empty after sanitization")
    return cleaned

def validate_api_key(api_key: Optional[str], env_var_name: str) -> str:
    """Validates API key existence."""
    if not api_key:
        raise ValidationError(f"API key missing. Please set {env_var_name} environment variable.")
    if len(api_key) < 8:
        raise ValidationError(f"API key too short for {env_var_name}.")
    return api_key

def validate_selectors(selectors: dict) -> dict:
    """Validates CSS selectors dictionary."""
    if not selectors:
        raise ValidationError("Selectors dictionary cannot be empty.")
    if not isinstance(selectors, dict):
        raise ValidationError("Selectors must be a dictionary.")
    for key, selector in selectors.items():
        if not isinstance(key, str) or not isinstance(selector, str):
            raise ValidationError("Selectors and keys must be strings.")
    return selectors

def validate_ip_address(ip: str) -> str:
    """Validates an IPv4 or IPv6 address."""
    pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    if not isinstance(ip, str) or not re.match(pattern, ip):
        # Extremely simplified IPv6 check for basic validation
        if ':' not in ip:
            raise ValidationError(f"Invalid IP address: {ip}")
    return ip

def validate_json_string(data: str) -> Any:
    """Validates if a string is valid JSON."""
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValidationError(f"Invalid JSON data: {e}")

def validate_date_string(date_str: str, format: str = "%Y-%m-%d") -> datetime:
    """Validates if a date string matches a format."""
    try:
        return datetime.strptime(date_str, format)
    except ValueError as e:
        raise ValidationError(f"Invalid date format: {e}")

def validate_domain(domain: str) -> str:
    """Validates domain name format."""
    pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    if not isinstance(domain, str) or not re.match(pattern, domain):
        raise ValidationError(f"Invalid domain: {domain}")
    return domain

def validate_port(port: int) -> int:
    """Validates network port."""
    try:
        port_num = int(port)
        if not (1 <= port_num <= 65535):
            raise ValueError()
        return port_num
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid port number: {port}. Must be 1-65535.")
