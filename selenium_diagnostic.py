#!/usr/bin/env python3
"""
Selenium Version Diagnostic and Fix Script
"""

import subprocess
import sys
import pkg_resources

def run_command(cmd):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), 1

def get_installed_version(package):
    """Get installed version of a package"""
    try:
        return pkg_resources.get_distribution(package).version
    except pkg_resources.DistributionNotFound:
        return None

def check_selenium_compatibility():
    """Check Selenium and related packages"""
    print("🔍 Selenium Environment Diagnostic")
    print("=" * 50)
    
    # Check Python version
    python_version = sys.version.split()[0]
    print(f"🐍 Python version: {python_version}")
    
    # Check Selenium version
    selenium_version = get_installed_version("selenium")
    if selenium_version:
        print(f"🤖 Selenium version: {selenium_version}")
    else:
        print("❌ Selenium not installed")
        return False
    
    # Check related packages
    packages = ["beautifulsoup4", "requests", "urllib3", "certifi"]
    for package in packages:
        version = get_installed_version(package)
        if version:
            print(f"📦 {package}: {version}")
        else:
            print(f"❌ {package}: Not installed")
    
    # Check Chrome/ChromeDriver versions
    chrome_cmd = "google-chrome --version || chromium-browser --version || chromium --version"
    chrome_out, _, chrome_code = run_command(chrome_cmd)
    if chrome_code == 0:
        print(f"🌐 Chrome: {chrome_out}")
    else:
        print("❌ Chrome not found")
    
    chromedriver_out, _, chromedriver_code = run_command("chromedriver --version")
    if chromedriver_code == 0:
        print(f"🚗 ChromeDriver: {chromedriver_out}")
    else:
        print("❌ ChromeDriver not found")
    
    # Selenium version compatibility check
    print("\n🔧 Compatibility Analysis:")
    print("=" * 50)
    
    if selenium_version:
        major_version = int(selenium_version.split('.')[0])
        
        if major_version == 4:
            if selenium_version.startswith("4.0.") or selenium_version.startswith("4.1."):
                print("⚠️  Old Selenium 4.x version detected")
                print("   Known issues with error handling")
                print("   Recommended: 4.15.0 or newer")
                return "update_needed"
            elif selenium_version.startswith("4.2") or selenium_version.startswith("4.3"):
                print("⚠️  Selenium 4.2-4.3 has some compatibility issues")
                print("   Recommended: 4.15.0 or newer")
                return "update_recommended"
            else:
                print("✅ Selenium 4.x version looks good")
                return "check_chromedriver"
        elif major_version == 3:
            print("⚠️  Selenium 3.x is deprecated")
            print("   Recommended: Upgrade to 4.15.0+")
            return "major_update_needed"
        else:
            print(f"❓ Unknown Selenium version pattern: {selenium_version}")
            return "unknown"
    
    return False

def fix_selenium_issues():
    """Provide fixes for common Selenium issues"""
    status = check_selenium_compatibility()
    
    print("\n🛠️  Recommended Actions:")
    print("=" * 50)
    
    if status == "update_needed" or status == "update_recommended" or status == "major_update_needed":
        print("1. Update Selenium to latest stable version:")
        print("   pip3 install --upgrade selenium==4.15.2")
        print()
        
    if status == "check_chromedriver" or status == "update_needed":
        print("2. Update ChromeDriver (choose one method):")
        print()
        print("   Method A - Auto-install with webdriver-manager:")
        print("   pip3 install webdriver-manager")
        print()
        print("   Method B - Manual ChromeDriver update:")
        print("   # Remove old version")
        print("   sudo rm /usr/local/bin/chromedriver 2>/dev/null || true")
        print("   # Get Chrome version")
        print("   CHROME_VERSION=$(google-chrome --version | grep -oE '[0-9]+' | head -1)")
        print("   # Download compatible ChromeDriver")
        print("   wget -O /tmp/chromedriver.zip \"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}\"")
        print("   DRIVER_VERSION=$(cat /tmp/chromedriver.zip)")
        print("   wget -O /tmp/chromedriver.zip \"https://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip\"")
        print("   cd /tmp && unzip -o chromedriver.zip")
        print("   sudo cp chromedriver /usr/local/bin/")
        print("   sudo chmod +x /usr/local/bin/chromedriver")
        print("   rm -rf /tmp/chromedriver*")
        print()
    
    print("3. Clean reinstall (if above doesn't work):")
    print("   pip3 uninstall selenium -y")
    print("   pip3 install selenium==4.15.2")
    print()
    
    print("4. Test the fix:")
    print("   python3 -c \"from selenium import webdriver; print('Selenium import OK')\"")
    print()
    
    # Provide immediate fix commands
    answer = input("Do you want to run the automatic fix? (y/n): ")
    if answer.lower() == 'y':
        run_automatic_fix()

def run_automatic_fix():
    """Run automatic fix for Selenium issues"""
    print("\n🔄 Running automatic fix...")
    
    commands = [
        "pip3 install --upgrade selenium==4.15.2",
        "pip3 install webdriver-manager",  # This helps with driver management
    ]
    
    for cmd in commands:
        print(f"Running: {cmd}")
        stdout, stderr, code = run_command(cmd)
        if code == 0:
            print(f"✅ Success: {cmd}")
        else:
            print(f"❌ Failed: {cmd}")
            print(f"   Error: {stderr}")
    
    # Test the fix
    print("\n🧪 Testing the fix...")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        # Try using webdriver-manager
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            print("✅ WebDriver-Manager approach works!")
            
        except ImportError:
            # Fallback to system chromedriver
            driver = webdriver.Chrome(options=options)
            print("✅ System ChromeDriver approach works!")
        
        driver.get("https://www.google.com")
        title = driver.title
        driver.quit()
        
        print(f"✅ Full test passed! Page title: {title}")
        print("\n🎉 Fix completed successfully!")
        
    except Exception as e:
        print(f"❌ Test still failed: {e}")
        print("\nPlease try manual ChromeDriver update.")

if __name__ == "__main__":
    fix_selenium_issues()