from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import time
import random
import re
import argparse
import csv
from datetime import datetime


load_dotenv()
USERNAME = os.getenv("CHAPMAN_USERNAME")
PASSWORD = os.getenv("CHAPMAN_PASSWORD")


def random_delay(min_time, max_time):
    """Add a random delay between actions to simulate natural behavior."""
    time.sleep(random.uniform(min_time, max_time))


def scrape_courses():
    with sync_playwright() as p:
        # Launch the browser in non-headless mode for visual debugging
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # Step 1: Navigate to the Student Center login page
        print("Navigating to Student Center...")
        page.goto("https://studentcenter.chapman.edu/")
        random_delay(1.5, 3.0)

        # Step 2: Enter the username/email
        print("Filling in username...")
        page.wait_for_selector("#i0116") 
        page.fill("#i0116", USERNAME)
        random_delay(0.8, 1.5)
        page.keyboard.press("Enter") 
        random_delay(1.5, 3.0)

        # Step 3: Handle password prompt or 2FA bypass
        print("Checking for 'Use your password instead' option or password prompt...")
        if page.is_visible("#idA_PWD_SwitchToPassword"):
            print("Skipping initial password prompt. Clicking 'Use your password instead'...")
            page.click("#idA_PWD_SwitchToPassword")
            random_delay(1.0, 2.0)

        if page.is_visible("#i0118"): 
            print("Entering password...")
            page.fill("#i0118", PASSWORD)
            random_delay(0.8, 1.5)
            page.keyboard.press("Enter")
            random_delay(1.5, 3.0)

        # Step 4: Handle "Stay Signed In" prompt
        print("Handling 'Stay Signed In' prompt...")
        if page.is_visible("input#idSIButton9"): 
            if page.is_visible("input#KmsiCheckboxField"):
                page.check("input#KmsiCheckboxField") 
                random_delay(0.5, 1.0)
            page.click("input#idSIButton9")
            random_delay(1.5, 2.5)

        # wait a few seconds for the page to load
        random_delay(2.0, 3.0)  

        # Step 5: Navigate directly to "Manage Classes"
        print("Navigating to 'Manage Classes'...")
        manage_classes_url = "https://cs92prod.chapman.edu/psc/CS92PROD_35/EMPLOYEE/SA/c/SSR_STUDENT_FL.SSR_START_PAGE_FL.GBL?GMenu=SSR_STUDENT_FL&GComp=SSR_START_PAGE_FL&GPage=SSR_START_PAGE_FL&scname=CS_SSR_MANAGE_CLASSES_NAV"
        page.goto(manage_classes_url)
        print("Navigated to 'Manage Classes'.")

        random_delay(2.0, 3.0)

        # Step 6: Select "Class Search and Enroll"
        try:
            print("Selecting 'Class Search and Enroll'...")
            class_search_button = page.locator("text='Class Search and Enroll'")
            class_search_button.wait_for(state="visible", timeout=60000)
            class_search_button.scroll_into_view_if_needed()
            class_search_button.click()
            print("'Class Search and Enroll' selected successfully.")
        except Exception as e:
            print(f"Error selecting 'Class Search and Enroll': {e}")

        random_delay(2.0, 3.0)

        # Step 7: Select the appropriate term (e.g., "Spring 2025")
        try:
            select_term(page, TERM)
        except Exception as e:
            print(f"Error selecting the term '{TERM}': {e}")

        random_delay(2.0, 3.0)

        # Step 8: Enter "SUBJECT" in the search field and execute the search using Enter key
        try:
            print(f"Entering {SUBJECT} in the search field...")
            search_field = page.locator("input[placeholder='Enter keyword e.g. course, subject, class, topic']")
            search_field.wait_for(state="visible", timeout=60000)
            # since regular SE has too many results 
            if (SUBJECT == "SE"):
                search_field.fill("Software Engineering")
            else:
                search_field.fill(SUBJECT)
            random_delay(0.8, 1.5)

            print("Pressing 'Enter' to execute the search...")
            page.keyboard.press("Enter")

            print("Search executed successfully.")
        except Exception as e:
            print(f"Error during search: {e}")

        random_delay(2.0, 3.5)

        #Step 9: Scrape course data and fix selectors
        print("Scraping course data...")
        scrape_all_classes_dynamic(page)

        browser.close()


def determine_current_term():
    now = datetime.now()
    month = now.month
    year = now.year

    if month == 1:
        current_term = f"Interterm {year}"
    elif 2 <= month <= 5:
        current_term = f"Spring {year}"
    elif 6 <= month <= 8:
        current_term = f"Summer {year}"
    elif 9 <= month <= 12:
        current_term = f"Fall {year}"
    else:
        raise ValueError("Invalid month for term determination.")
    
    return current_term


def get_term_order(term):
    term_order = {
        "Interterm": 0,
        "Spring": 1,
        "Summer": 2,
        "Fall": 3
    }

    term_name, term_year = term.split()
    return int(term_year) * 4 + term_order[term_name]


def select_term(page, target_term):
    try:
        current_term = determine_current_term()
        print(f"Current term based on date: {current_term}")
        
        # Check if the target term is prior to the current term
        if get_term_order(target_term) < get_term_order(current_term):
            print(f"Selecting Terms prior to {current_term}...")
            prior_terms_button = page.locator(f"text='Terms prior to {current_term}'")
            prior_terms_button.wait_for(state="visible", timeout=60000)
            prior_terms_button.click()
            page.wait_for_timeout(2000)

        print(f"Selecting the row for '{target_term}'...")
        term_row = page.locator(f"text='{target_term}'")
        term_row.wait_for(state="visible", timeout=60000)
        term_row.scroll_into_view_if_needed()
        term_row.click()
            
        print(f"Row for '{target_term}' selected successfully.")
    except Exception as e:
        print(f"Error selecting the row for '{target_term}': {e}")


def scrape_section(page, row, class_text, title):
    try:
        # Check if the course requires special handling for topic (298, 370, 470)
        special_courses = ["298", "370", "398"]
        if any(course in class_text for course in special_courses):
        #if "298" in class_text or "370" in class_text or "470" in class_text:
            status = row.locator("td:nth-child(2)").inner_text(timeout=5000).strip()
            days_and_times_raw = row.locator("td:nth-child(7)").inner_text(timeout=5000).strip()
            seats = row.locator("td:nth-child(10)").inner_text(timeout=5000).strip()
            topic = row.locator("td:nth-child(5)").inner_text(timeout=5000).strip()
            title = f"{title} - {topic}"
            
        else: # not a 298/370/470 course
            status = row.locator("td:nth-child(2)").inner_text(timeout=5000).strip()
            days_and_times_raw = row.locator("td:nth-child(6)").inner_text(timeout=5000).strip()
            seats = row.locator("td:nth-child(9)").inner_text(timeout=5000).strip()
            topic = ""

        # Split days and times into separate columns
        days, times = "", ""
        if "\n" in days_and_times_raw:
            parts = days_and_times_raw.split("\n")
            days = parts[0].strip()
            times = parts[1].strip() if len(parts) > 1 else ""

        section_details = [status, days, times, seats, title]
        return section_details
    except Exception as e:
        print(f"Error scraping section details: {e}")
        return None


def scrape_course_details(page, class_text):
    with open(f"data/course_listings/{TERM}.csv", mode="a", newline="") as file:
        writer = csv.writer(file)
        try:
            course_info_button = page.locator("a:has-text('Course Information')")
            course_info_button.click()
            page.wait_for_timeout(2000)

            title = page.locator("span#SSR_CRSE_INFO_V_COURSE_TITLE_LONG").inner_text(timeout=5000).strip()
            print(f"Title: {title}")

            description = page.locator("span#SSR_CRSE_INFO_V_DESCRLONG").inner_text(timeout=5000).strip()
            print(f"Description: {description}")

            credits = page.locator("span#SSR_CLSRCH_F_WK_UNITS_RANGE").inner_text(timeout=5000).strip()
            print(f"Credits: {credits}")

            grading_option = page.locator("span#SSR_CLSRCH_F_WK_SSR_GRAD_BASIS_LNG").inner_text(timeout=5000).strip()
            print(f"Grading Option: {grading_option}")

            rows = page.locator(".ps_grid-body tr")
            row_count = rows.count()

            if file.tell() == 0:
                writer.writerow(["Term", "Class", "Title", "Description", "Status", "Days", "Time", "Seats"])

            for i in range(row_count):
                row = rows.nth(i)
                try:
                    section_details = scrape_section(page, row, class_text, title)
                    if section_details:
                        status, days, times, seats, updated_title = section_details
                        writer.writerow([TERM, class_text, updated_title, description, status, days, times, seats])
                        print(f"Section Details: {section_details}")
                        print("-" * 50)
                except Exception as e:
                    print(f"Error processing row {i + 1}: {e}")
        except Exception as e:
            print(f"Error in scrape_course_details: {e}")


def scrape_all_classes_dynamic(page):
    try:
        class_elements = page.locator("a[class*='ps-link']")
        class_count = class_elements.count()
        print(f"Found {class_count} classes.")

        for i in range(class_count):
            class_link = class_elements.nth(i)
            class_text = class_link.inner_text(timeout=5000).strip()
            if re.match(rf"^{SUBJECT} \d{{3}}$", class_text):
                print(f"\nClicking on class: {class_text}\n")
                class_link.click()
                random_delay(2.0, 3.0)

                scrape_course_details(page, class_text)

                page.go_back(timeout=60000)
                random_delay(2.0, 3.0)
                page.wait_for_selector(".ps_box-group", timeout=60000)
    except Exception as e:
        print(f"Error while scraping classes: {e}")


def parser():
    parser = argparse.ArgumentParser(description="Scrape course data from Chapman University's Student Center.")
    parser.add_argument("--term", type=str, required=True, help="The season + year of the term to scrape (e.g., 'Spring 2025')")
    parser.add_argument("--subject", type=str, required=True, help="The subject code to search for (e.g., 'CPSC')")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parser()

    TERM = args.term
    SUBJECT = args.subject

    scrape_courses()