from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import time
import random


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

        # # Inject JavaScript to log manual clicks
        # print("Injecting JavaScript to log manual clicks on 'Manage Classes' page...")
        # page.evaluate("""
        #     document.addEventListener('click', function(event) {
        #         console.log('Clicked element:', event.target);
        #         console.log('Element ID:', event.target.id || 'No ID');
        #         console.log('Element Classes:', event.target.className || 'No Class');
        #         console.log('Element Outer HTML:', event.target.outerHTML || 'No Outer HTML');
        #     });
        # """)
        # print("JavaScript injected. Click on any element to log its details in the browser console.")

        # input("Press Enter to continue the automated script after manual interaction...")

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
            print("Selecting the row for 'Spring 2025'...")
            spring_2025_row = page.locator("text='Spring 2025'")
            spring_2025_row.wait_for(state="visible", timeout=60000)
            spring_2025_row.scroll_into_view_if_needed()
            spring_2025_row.click()
            print("Row for 'Spring 2025' selected successfully.")
        except Exception as e:
            print(f"Error selecting the row for 'Spring 2025': {e}")

        random_delay(2.0, 3.0)

        # Step 8: Enter "CPSC" in the search field and execute the search using Enter key
        try:
            print("Entering 'CPSC' in the search field...")
            search_field = page.locator("input[placeholder='Enter keyword e.g. course, subject, class, topic']")
            search_field.wait_for(state="visible", timeout=60000)
            search_field.fill("CPSC")
            random_delay(0.8, 1.5)

            print("Pressing 'Enter' to execute the search...")
            page.keyboard.press("Enter")

            print("Search executed successfully.")
        except Exception as e:
            print(f"Error during search: {e}")

        random_delay(2.0, 3.5)

        #TODO: Step 9: Scrape course data and fix selectors
        print("Scraping course data...")
        courses = page.query_selector_all(".ps_box-group.ps_layout")
        for course in courses:
            course_code = course.query_selector("span.course-code").text_content()
            course_title = course.query_selector("span.course-title").text_content()
            print(f"Code: {course_code}, Title: {course_title}")
            random_delay(0.5, 1.0)

        # Close the browser
        browser.close()


scrape_courses()