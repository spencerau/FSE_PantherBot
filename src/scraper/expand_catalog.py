#!/usr/bin/env python3
import sys
import time
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

def parse_args():
    parser = argparse.ArgumentParser(
        description="Expand all course entries on a catalog page"
    )
    parser.add_argument("url", help="URL of the catalog page")
    parser.add_argument(
        "--selector",
        default="li.acalog-course.acalog-course span.event a",
        help="CSS selector for expand-toggle elements",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Delay (seconds) between clicks",
    )
    parser.add_argument(
        "--pdf",
        help="Output PDF filename; if set, saves screenshot after expanding"
    )
    parser.add_argument(
        "--chromedriver",
        default=None,
        help="Path to chromedriver executable"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    chrome_opts = Options()
    chrome_opts.add_argument('--disable-gpu')
    chrome_opts.add_argument('--window-size=1920,1080')
    service = Service(args.chromedriver) if args.chromedriver else Service()
    driver = webdriver.Chrome(service=service, options=chrome_opts)

    try:
        driver.get(args.url)
        driver.implicitly_wait(10)
        buttons = driver.find_elements(By.CSS_SELECTOR, args.selector)
        print(f"Found {len(buttons)} expand-controls using selector '{args.selector}'")

        for btn in buttons:
            try:
                driver.execute_script("arguments[0].scrollIntoView();", btn)
                driver.execute_script("arguments[0].setAttribute('aria-expanded', 'true');", btn)
                if btn.get_attribute('onclick'):
                    driver.execute_script(btn.get_attribute('onclick'), btn)
                else:
                    btn.click()
                time.sleep(args.delay)
            except Exception as e:
                print("Warning: could not click one item:", e)

        if args.pdf:
            print("Saving screenshot after expansion...")
            driver.save_screenshot(args.pdf if args.pdf.endswith('.png') else args.pdf + '.png')
            print("Output saved:", args.pdf)

        print("Expansion complete. You may now print or save the page manually.")
        print("Close the browser window when finished.")
    except Exception as e:
        print("Error during expansion:", e)
        driver.quit()

if __name__ == "__main__":
    main()