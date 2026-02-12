"""
Manual Cookie Saver - Run this while browser is still open and you're logged in
"""
from playwright.sync_api import sync_playwright
import json
from pathlib import Path

print("=" * 60)
print("Manual Cookie Saver for Facebook")
print("=" * 60)
print()
print("INSTRUKSI:")
print("1. Pastikan browser Facebook masih terbuka dan Anda sudah login")
print("2. Script ini akan connect ke browser dan save cookies")
print()

# Create cookies directory if not exists
cookies_dir = Path("data/cookies")
cookies_dir.mkdir(parents=True, exist_ok=True)

try:
    with sync_playwright() as p:
        # Try to connect to existing browser
        print("Mencoba connect ke browser...")
        
        # Launch a new browser in non-headless mode
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print()
        print("Browser baru dibuka. Silakan:")
        print("1. Login ke Facebook di browser ini")
        print("2. Tunggu sampai masuk homepage")
        print("3. Jangan close browser!")
        print()
        input("Press ENTER setelah Anda login dan di homepage...")
        
        # Get cookies
        cookies = context.cookies()
        
        if cookies:
            # Save cookies
            cookies_path = cookies_dir / "cookies_default.json"
            with open(cookies_path, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2)
            
            print()
            print("=" * 60)
            print(f"✓ SUCCESS! {len(cookies)} cookies tersimpan!")
            print(f"✓ Location: {cookies_path}")
            print("=" * 60)
            print()
            print("Sekarang Anda bisa close browser dan run crawler seperti biasa.")
        else:
            print()
            print("✗ ERROR: Tidak ada cookies!")
            print("Pastikan Anda sudah login ke Facebook.")
        
        browser.close()
        
except Exception as e:
    print()
    print(f"✗ ERROR: {e}")
    print()

input("Press ENTER to exit...")
