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
        print(f"Error downloading ChromeDriver: {e}")
        return False

def main():
    print("🔍 Chrome/ChromeDriver Diagnostic Tool")
    print("=" * 50)
    
    # Check Chrome version
    chrome_version = get_chrome_version()
    if chrome_version:
        print(f"✅ Chrome found: {chrome_version}")
        # Extract version number
        chrome_num = chrome_version.split()[-1] if chrome_version else "unknown"
    else:
        print("❌ Chrome not found!")
        print("Install Chrome: sudo apt update && sudo apt install google-chrome-stable")
        return
    
    # Check ChromeDriver version
    chromedriver_version = get_chromedriver_version()
    chromedriver_path = find_chromedriver_path()
    
    if chromedriver_version:
        print(f"✅ ChromeDriver found: {chromedriver_version}")
        print(f"📍 Path: {chromedriver_path}")
    else:
        print("❌ ChromeDriver not found!")
    
    # Check compatibility
    if chrome_version and chromedriver_version:
        chrome_major = chrome_num.split('.')[0]
        driver_major = chromedriver_version.split()[1].split('.')[0] if 'ChromeDriver' in chromedriver_version else chromedriver_version.split('.')[0]
        
        if chrome_major == driver_major:
            print("✅ Versions are compatible!")
        else:
            print(f"❌ Version mismatch detected!")
            print(f"   Chrome major version: {chrome_major}")
            print(f"   ChromeDriver major version: {driver_major}")
            
            # Get compatible version
            compatible_version = get_compatible_chromedriver_version(chrome_major)
            if compatible_version:
                print(f"💡 Compatible ChromeDriver version: {compatible_version}")
                
                answer = input("\nDo you want to download and install the compatible version? (y/n): ")
                if answer.lower() == 'y':
                    if download_chromedriver(compatible_version):
                        print("✅ ChromeDriver updated successfully!")
                    else:
                        print("❌ Failed to update ChromeDriver")
            else:
                print("❌ Could not determine compatible version")
    
    print("\n🛠️  Manual Installation Commands:")
    print("=" * 50)
    
    if chrome_version:
        chrome_major = chrome_num.split('.')[0]
        print(f"# For Chrome {chrome_major}.x:")
        print(f"wget -O /tmp/chromedriver.zip 'https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{chrome_major}'")
        print("cd /tmp")
        print("unzip chromedriver.zip")
        print("sudo cp chromedriver /usr/local/bin/")
        print("sudo chmod +x /usr/local/bin/chromedriver")
        print("rm -rf chromedriver*")
    
    print("\n# Alternative: Use system package manager:")
    print("sudo apt update")
    print("sudo apt remove chromium-chromedriver")  # Remove old version
    print("sudo apt install chromium-chromedriver")
    
    print("\n# Test the installation:")
    print("chromedriver --version")
    print("google-chrome --version")

if __name__ == "__main__":
    main()