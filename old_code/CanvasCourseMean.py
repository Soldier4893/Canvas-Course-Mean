#!/usr/bin/env python

"""CanvasCourseMean.py: GUI App to help users determine their standing with respect to their class on Canvas"""

__author__ = "Leo Shen, Dhruba Paul"
__copyright__ = "Copyright 2022, Canvas Course Mean Project"

import time
from threading import Thread
from tkinter import ttk
from tkinter.ttk import Progressbar
import pandas as pd
from pandastable import Table
from tkinter import *
from selenium import webdriver
from selenium.common.exceptions import WebDriverException, NoSuchElementException
from selenium.webdriver import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.service import Service as ChromeService
from subprocess import CREATE_NO_WINDOW  # This flag will only be available in windows

# Global Variables
COURSE_DF = pd.DataFrame()  # Empty Dataframe


def clear_COURSE_DF():
    """
    Empties the Course dataframe

    :return: None
    """
    global COURSE_DF
    COURSE_DF = pd.DataFrame()  # Empty Dataframe


# Checking if the argument is a float value
def is_number(s):
    """
    Helper Method.
    Checks if the string argument is a number or not

    :param s: a string
    :return: True if it is a number, false otherwise
    """
    try:
        float(s)
        return True
    except ValueError:
        return False


# Finding the groups, total scores, and average scores of ALL ASSIGNMENTS ##########################################
def start_with_illegal_val(tr_ID):
    """
    Helper Method.
    checking if the tr_ID starts with one of the illegal expression

    :param tr_ID: the ID of the tr tag
    :return: True if the tr ID starts with an illegal expression, false otherwise
    """
    illegal_expressions = ['submission_group', "submission_final-grade", 'grade_info_final', 'grade_info_group']
    for f in illegal_expressions:
        if tr_ID.startswith(f):
            return True
    return False


# Calculating course mean and student grade with pandas dataframe
def calculate_grade(group_list, mean_list, total_list, dropped_list, student_score_list, group_weights):
    """
    Helper Method.
    Calculates course average grade, and student grade with a pandas dataframe

    :param group_list: list of all the assignment groups within a course
    :param mean_list: list of average scores for all assignments
    :param total_list: list of total scores for all assignments
    :param dropped_list: boolean list indicating whether an assignment has been dropped or not
    :param student_score_list: list of student scores achieved on all assignments
    :param group_weights: dictionary with assignment groups and their corresponding weights
    :return: A tuple (course avg. grade, student grade)
    """
    global COURSE_DF
    df = pd.DataFrame()
    df["groups"] = group_list
    df["mean_sum"] = mean_list
    df["student_score_sum"] = student_score_list
    df["total_sum"] = total_list
    df["dropped"] = dropped_list

    # Counting number of dropped courses per group
    dropped_count = df[["groups", "dropped"]]
    dropped_count = dropped_count.groupby("groups").sum()

    df = df[df["dropped"] == False]  # dropping rows with dropped assignments
    df = df.astype({'mean_sum': 'float', 'total_sum': 'float', 'student_score_sum': 'float'})  # type conversion
    df = df.groupby("groups").sum()  # getting mean_sum and total_sum
    df["dropped"] = dropped_count  # getting count for the number of assignments dropped

    df = df.reset_index()  # resetting index to use the groups values
    df["weights"] = df["groups"].apply(lambda x: group_weights[x])  # Fetching weights
    df = df.astype({'weights': 'float'})  # type conversion
    # weighted percentages (class average)
    df["weighted_percentage (course avg)"] = df["mean_sum"] / df["total_sum"] * df["weights"]
    # weighted percentages (student score)
    df["student_weighted_percentage (student grade)"] = df["student_score_sum"] / df["total_sum"] * df["weights"]
    print(df.to_string())
    COURSE_DF = df

    return df["weighted_percentage (course avg)"].sum(), df["student_weighted_percentage (student grade)"].sum()


def login_canvas(dvr, root, label_obj, net_id, password):
    """
    Logs into the students canvas account.

    Error is thrown with error messages in the tkinter window if any of the fields has missing input
    if the password provided is incorrect, if login is denied, or if the login times out.

    :param password: Password for the student to login
    :param net_id: The user_ID required for the login
    :param dvr: selenium webdriver object
    :param root: tkinter window object
    :param label_obj: a label object
    :return: True if login is successful, false otherwise
    """
    dvr.get("https://canvas.wisc.edu/")

    # Clearing message when new login attempt starts
    label_obj["text"] = ""
    root.update()

    # Checking if there are inputs for netID and password
    if net_id == "" or password == "":
        label_obj["text"] = "No input is provided for either netID or password"
        label_obj["fg"] = "red"
        return False

    # Logging in (polling)
    while True:
        try:
            dvr.find_element(by="tag name", value="input").send_keys(net_id)
            dvr.find_element(by="name", value="j_password").send_keys(password, Keys.RETURN)
            break
        except WebDriverException:
            time.sleep(0.2)

    # Notifying user to authenticate login (on DUO)
    label_obj["text"] = "Notification pushed to user's device. Waiting for user authentication..."
    label_obj["fg"] = "blue"
    root.update()

    while True:
        try:
            # Checking if password is incorrect
            try:
                dvr.find_element(by="tag name", value="strong")
                label_obj["text"] = "Login Failed. Username or password incorrect"
                label_obj["fg"] = "red"
                return False
            except NoSuchElementException:
                pass

            # Checking if Login has timed out or if login request is denied
            try:
                # switching to iframe
                iframe = dvr.find_element(by="id", value="duo_iframe")  # iframe
                dvr.switch_to.frame(iframe)  # switching to DOM under "#document"

                # Explicit polling until the iframe DOM fully loads (waiting to a maximum of 10 secs)
                elem = WebDriverWait(driver, 10).until(
                    ec.presence_of_element_located((By.CSS_SELECTOR, "#messages-view > div > div > div > span"))
                )

                if elem.text == "Login timed out.":
                    label_obj["text"] = "Login Timed Out. Try again!"
                    label_obj["fg"] = "red"
                    return False

                if elem.text == "Login request denied.":
                    label_obj["text"] = "Login request denied. User must accept login request!"
                    label_obj["fg"] = "red"
                    return False
            except NoSuchElementException:
                pass
            finally:
                dvr.switch_to.parent_frame()

            # Checking if the dashboard has loaded yet
            dvr.find_element(by="id", value="dashboard_header_container")
            root.destroy()  # Closing the login window when user is successfully logged in
            course_selection_gui(driver)  # prompts user for course url to compute course avg
            return True
        except WebDriverException:
            # time.sleep(10)
            time.sleep(0.2)


def scrape_and_calculate(html):
    """
    Scrapes the "grade" page of the course, and uses the information to computer the course avg and student grades.

    :param html: The html code that is to be scraped with BeautifulSoup
    :return: A Tuple --> (True if scraping is successful, false other), (a string with useful information for the user)
    """
    soup = BeautifulSoup(html, features="lxml")

    # Adding course name to return string
    course_name = soup.find(id='breadcrumbs').find_all("span")[2].text
    print(course_name)
    return_str = course_name + "\n"

    # Getting the weights
    try:
        # Creating a dictionary of groups corresponding to the weights
        unweighted_assignments = soup.find(id="assignments-not-weighted")
        unweighted_assignments_tbody = unweighted_assignments.find("tbody")
        groups = [tag.text for tag in unweighted_assignments_tbody.find_all("th")]
        weights = [tag.text[:-1] for tag in unweighted_assignments.find_all("td")]
        group_weights = dict(zip(groups, weights))
    except AttributeError:
        print("Class has no weights")
        return_str = return_str + "Class has no weights\n"
        return return_str

    # The "tr" tags represent assignment label (assignment group), grade info (has mean and total scores),
    # or grader comments (we don't need)
    grade_summary = soup.find(id="grades_summary").find("tbody")
    tr_lst = grade_summary.find_all("tr")
    mean_list = []
    student_score_list = []
    total_list = []
    group_list = []
    dropped_list = []

    # Looping over all the tr tags
    for tr in tr_lst:
        tr_id_val = tr.get("id", -1)
        tr_class_val = tr.get("class", "")

        # Skipping elements without ids
        if tr_id_val == -1:
            continue

        # Get student's own grade from Canvas
        if tr_id_val.startswith('submission_final-grade'):
            student_grade = tr.find_all("span")[2].text.strip()
            print("Your Grade on Canvas: " + student_grade)
            return_str = return_str + "Your Grade on Canvas: " + student_grade + "\n"

        # Skips if the tr ID start with an illegal expression
        if start_with_illegal_val(tr_id_val):
            continue

        # Adding groups and total scores and "dropped boolean" values to their respective lists
        if tr_id_val.startswith("submission"):
            total_list.append(tr.find_all("td")[-2].text.strip())  # total
            group_list.append(tr.find("div").text)  # group
            student_score_string = tr.find_all("td")[-3].text.split()[-5]
            student_score_list.append(student_score_string if is_number(student_score_string) else 0.0)  # student score

            # grade info has attribute if assignment is dropped
            grade_info = tr.find("td", {"class": "details"}).find("a").attrs.get("aria-expanded", -1)
            dropped_list.append("dropped" in tr_class_val or "excused" in tr_class_val or grade_info != -1)  # dropped
            continue

        # Adding mean to its respective lists
        if tr_id_val.startswith("grade_info"):
            try:
                # throws exception when assignment is ungraded
                mean_string = tr.find("tbody").find("td").text
                mean_list.append(mean_string.split(":")[-1].strip())  # Mean
            except AttributeError:
                mean_list.append(0)

    # Calculating course mean and student grade with pandas dataframe
    course_avg, student_grade = calculate_grade(group_list, mean_list, total_list,
                                                dropped_list, student_score_list, group_weights)

    print('Course Average: ' + str(course_avg))
    print('Student Grade: ' + str(student_grade))
    print()
    return_str = return_str + 'Course Average: ' + str(course_avg) + "\n" \
                            + 'Student Grade: ' + str(student_grade) + "\n"
    return return_str


def login_gui(dvr):
    """
    GUI. Allows the user to log into their canvas account.

    :param dvr: selenium webdriver
    :return: None
    """
    # root window
    root = Tk()
    root.title('Login')
    root.resizable(False, False)

    # Creating Frame
    main_frame = Frame(root)
    main_frame.pack(padx=(80, 80), pady=(80, 80))
    input_frame = Frame(main_frame)
    input_frame.pack()
    button_frame = Frame(main_frame)
    button_frame.pack()

    # Error Message
    error_msg = Label(main_frame)
    error_msg.pack()

    # NetID
    Label(input_frame, text="Net ID").grid(row=1, column=0)  # Label
    entry_net_id = Entry(input_frame, bd=3)  # Entry
    entry_net_id.grid(row=1, column=1)

    # Password
    Label(input_frame, text="Password").grid(row=2, column=0)  # Label
    entry_password = Entry(input_frame, show='*', bd=3)  # Entry
    entry_password.grid(row=2, column=1)

    # Button
    b1 = Button(button_frame, text='login',
                command=lambda: login_canvas(dvr, root, error_msg, entry_net_id.get(), entry_password.get()))
    b1.grid(column=1)

    root.mainloop()


def course_selection_gui(dvr):
    """
    Allows the user to pick courses for which they want to compute the course average and their own grade

    :param dvr: selenium webdriver
    :return: None
    """
    # root window
    root = Tk()
    root.resizable(False, False)
    root.title('Get Average(s)')

    # Creating Frame
    main_frame = Frame(root)
    main_frame.pack(padx=(60, 60), pady=(60, 60))
    input_frame = Frame(main_frame)
    input_frame.pack(padx=(20, 20), pady=(20, 20))
    button_frame = Frame(main_frame)
    button_frame.pack()
    feedback_frame = Frame(main_frame)
    feedback_frame.pack()

    # Labels
    Label(input_frame, text='Course URL (Home Page):').grid(row=0, column=0)

    # Entries
    entry_class_url = Entry(input_frame)
    entry_class_url.grid(row=0, column=1)

    # Button 1 (show for all active course)
    b1 = Button(button_frame, text='All Active Courses',
                command=lambda: Thread(target=get_all_active_courses, args=(dvr, root)).start())
    b1.grid(row=0, column=0, padx=(10, 10), pady=(10, 10))

    # Button 2 (show for the URL page)
    b2 = Button(button_frame, text='Compute from URL',
                command=lambda: Thread(target=get_from_url,
                                       args=(dvr, entry_class_url.get() + "/grades", root)).start())
    b2.grid(row=0, column=1, padx=(10, 10), pady=(10, 10))

    root.mainloop()


def get_all_active_courses(dvr, crs_select_root):
    """
    Scrapes the list of all active courses in the student's canvas account, and shows the course average as well as the
    student grade for each of those courses.

    :param crs_select_root: Window for the course selection (for providing progress feedback to user)
    :param dvr: Selenium Webdriver object
    :return: None
    """
    # Providing feedback to user
    feedback_frame = Frame(crs_select_root)
    feedback_frame.pack(padx=(20, 20), pady=(20, 20))
    progress_lvl = 0
    label = Label(feedback_frame, text=f"Computing {progress_lvl}%", fg="blue")
    label.pack(side=LEFT)
    progress = Progressbar(feedback_frame, orient=HORIZONTAL, length=100, mode='determinate')
    progress.pack(side=RIGHT)

    # Fetching all course links
    dvr.get("https://canvas.wisc.edu/")
    dvr.find_element(by="id", value="global_nav_courses_link").click()

    anchor_tags = []
    while len(anchor_tags) == 0:
        try:
            # Checking if the slider with the links for all active courses has loaded yet (polling)
            xpath = dvr.find_element(by=By.XPATH, value="/html/body/div[3]/span/span/div/div/div/div/div/ul[1]")
            anchor_tags = xpath.find_elements(by="tag name", value="a")
        except WebDriverException:
            time.sleep(0.2)

    course_links = {tag.get_attribute("textContent"): tag.get_attribute("href") for tag in anchor_tags}

    # Scrape and calculate (saving results)
    results_lst = []
    course_df_lst = []
    for course in course_links:
        # Loading Course
        dvr.get(course_links[course] + "/grades")

        # Scraping course, computing and saving result
        result = scrape_and_calculate(dvr.page_source)
        results_lst.append(result)
        course_df_lst.append(COURSE_DF)
        clear_COURSE_DF()  # Clearing result DF

        # Updating progress bar and Label
        progress_lvl += 100 / len(course_links)
        label["text"] = f"Computing {progress_lvl}%"
        progress["value"] = progress_lvl

    # Creating tkinter window (GUI)
    root = Toplevel()
    root.title('Course Results')
    root.resizable(True, True)

    # Create A Main Frame
    main_frame = Frame(root)
    main_frame.pack(fill=BOTH, expand=1)

    # Create A Canvas
    my_canvas = Canvas(main_frame)
    my_canvas.pack(side=LEFT, fill=BOTH, expand=1)

    # Add A Scrollbar To The Canvas
    my_scrollbar = ttk.Scrollbar(main_frame, orient=VERTICAL, command=my_canvas.yview)
    my_scrollbar.pack(side=RIGHT, fill=Y)

    # Configure The Canvas
    my_canvas.configure(yscrollcommand=my_scrollbar.set)
    my_canvas.bind('<Configure>', lambda e: my_canvas.configure(scrollregion=my_canvas.bbox("all")))

    # Create ANOTHER Frame INSIDE the Canvas
    second_frame = Frame(my_canvas)

    # Add that New frame To a Window In The Canvas
    my_canvas.create_window((0, 0), window=second_frame, anchor="nw")

    # Adding results for each course in GUI window
    for i in range(len(results_lst)):
        # Labels
        Label(second_frame, text="", justify=LEFT).pack()
        Label(second_frame, text=list(course_links.keys())[i], justify=LEFT, font='Helvetica 10 bold').pack()
        Label(second_frame, text=results_lst[i], justify=LEFT).pack()

        # Pandas Table
        third_frame = Frame(second_frame)
        third_frame.pack(fill="x", expand=True)
        pt = Table(third_frame, dataframe=course_df_lst[i], height=(len(course_df_lst[i]) + 1) * 20)
        pt.show()
        pt.redrawVisible()

    feedback_frame.destroy()
    root.state("zoomed")  # adjusting window size to display course dataframes


def get_from_url(dvr, url, crs_select_root):
    """
    Computes and displays the course average and student grade for the course corresponding to the url

    :param crs_select_root: Root tkinter window from the course_selection_gui
    :param dvr: selenium webdriver object
    :param url: url of the course
    :return: None
    """
    # Providing feedback to user
    feedback_frame = Frame(crs_select_root)
    feedback_frame.pack(padx=(20, 20), pady=(20, 20))
    label = Label(feedback_frame, text=f"Computing", fg="blue")
    label.pack(side=LEFT)
    progress = Progressbar(feedback_frame, orient=HORIZONTAL, length=100, mode='indeterminate')
    progress.pack(side=RIGHT)
    progress.start(2)

    # Loading url
    dvr.get(url)

    # Scraping course and computing result
    result = scrape_and_calculate(dvr.page_source)

    # Creating tkinter window
    root = Toplevel()
    root.resizable(True, True)
    root.title('Course Results')

    # Labels
    Label(root, text=result, justify=LEFT).pack()

    # Pandas Table
    frame = Frame(root)
    frame.pack(fill="x", expand=True)
    pt = Table(frame, dataframe=COURSE_DF, height=(len(COURSE_DF) + 1) * 20)
    pt.show()
    clear_COURSE_DF()  # Empties Dataframe

    progress.stop()
    feedback_frame.destroy()
    pt.redrawVisible()


if __name__ == "__main__":
    """
    Starts the webdriver in headless mode, starts the program if the user can successfully login,
    and closes the webdriver once the program is closed.
    """
    # Starting driver
    options = Options()
    options.headless = True
    # options.add_experimental_option('excludeSwitches', ['enable-logging'])  # Gets rid of Dev Tool Message
    chrome_service = ChromeService('chromedriver')  # To get rid of terminal window
    chrome_service.creationflags = CREATE_NO_WINDOW
    driver = webdriver.Chrome(options=options, service=chrome_service)
    driver.get("https://canvas.wisc.edu/")

    # Program starts if user successfully logs in
    login_gui(driver)

    # Closing driver
    driver.quit()
