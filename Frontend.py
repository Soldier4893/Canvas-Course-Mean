import time
from threading import Thread
from tkinter import *
from tkinter.ttk import Progressbar
import BackendPlaceholder as backend


def login():
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
    # b1 = Button(button_frame, text='login', command=lambda: login_canvas(dvr, root, error_msg, entry_net_id.get(), entry_password.get()))
    b1 = Button(button_frame, text='login', command=lambda: backend.login(entry_net_id.get(), entry_password.get()))
    b1.grid(column=1)

    root.mainloop()


def run():
    login()