#!/usr/bin/env python3
"""
Chrome/ChromeDriver Diagnostic Script
Helps identify version mismatches and provides solutions
"""

import subprocess
import sys
import os
import requests
import json
from pathlib import Path

def run_command(cmd):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), 1

def get_chrome_version():
    """Get installed Chrome version"""
    commands = [
        "google-chrome --version",
        "chromium-browser --version",
        "chromium --version",
        "/usr/bin/google-chrome --version",
        "/usr/bin/chromium-browser --version"
    ]
    
    for cmd in commands:
        stdout, stderr, code = run_command(cmd)
        if code == 0 and stdout:
            return stdout
    
    return None

def get_chromedriver_version():
    """Get installed ChromeDriver version"""
    commands = [
        "chromedriver --version",
        "/usr/local/bin/chromedriver --version",
        "/usr/bin/chromedriver --version"
    ]
    
    for cmd in commands:
        stdout, stderr, code = run_command(cmd)
        if code == 0 and stdout:
            return stdout
    
    return None

def find_chromedriver_path():
    """Find ChromeDriver executable path"""
    stdout, _, code = run_command("which chromedriver")
    if code == 0 and stdout:
        return stdout
    return None

def get_compatible_chromedriver_version(chrome_version):
    """Get compatible ChromeDriver version for given Chrome version"""
    try:
        # Extract major version
        major_version = chrome_version.split('.')[0]
        
        # ChromeDriver compatibility mapping
        url = f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{major_version}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return response.text.strip()
        else:
            # Fallback for newer versions
            url = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for version_info in reversed(data['versions']):
                    if version_info['version'].startswith(major_version + '.'):
                        return version_info['version']
    except Exception as e:
        print(f"Error fetching compatible version: {e}")
    
    return None

def download_chromedriver(version, install_path="/usr/local/bin/chromedriver"):
    """Download and install compatible ChromeDriver"""
    try:
        # Determine architecture
        arch_map = {
            'x86_64': 'linux64',
            'aarch64': 'linux64',  # ARM64
            'armv7l': 'linux64'    # ARM
        }
        
        machine = os.uname().machine
        arch = arch_map.get(machine, 'linux64')
        
        # Try new format first (Chrome 115+)
        url = f"https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/{version}/linux64/chromedriver-linux64.zip"
        
        print(f"Downloading ChromeDriver {version} for {arch}...")
        print(f"URL: {url}")
        
        # Download using wget or curl
        download_cmd = f"wget -O /tmp/chromedriver.zip '{url}' || curl -L -o /tmp/chromedriver.zip '{url}'"
        stdout, stderr, code = run_command(download_cmd)
        
        if code != 0:
            # Try old format
            url = f"https://chromedriver.storage.googleapis.com/{version}/chromedriver_linux64.zip"
            download_cmd = f"wget -O /tmp/chromedriver.zip '{url}' || curl -L -o /tmp/chromedriver.zip '{url}'"
            stdout, stderr, code = run_command(download_cmd)
        
        if code == 0:
            # Extract and install
            extract_commands = [
                "cd /tmp && unzip -o chromedriver.zip",
                f"sudo cp /tmp/chromedriver {install_path} || sudo cp /tmp/chromedriver-linux64/chromedriver {install_path}",
                f"sudo chmod +x {install_path}",
                "rm -rf /tmp/chromedriver* /tmp/chromedriver.zip"
            ]
            
            for cmd in extract_commands:
                stdout, stderr, code = run_command(cmd)
                if code != 0:
                    print(f"Warning: Command failed: {cmd}")
                    print(f"Error: {stderr}")
            
            return True
        else:
            print(f"Download failed: {stderr}")
            return False
            
    except Exception as e:
        print(f"Error downloadi