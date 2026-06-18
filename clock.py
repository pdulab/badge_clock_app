"""
Clock app

A simple clock that displays time
"""

import uasyncio as aio  # type: ignore

from apps.base_app import BaseApp
from net.net import register_receiver, send, BROADCAST_ADDRESS
from net.protocols import Protocol, NetworkFrame
from ui.page import Page
import ui.styles as styles
from ui import graphics

import lvgl
import fs_driver # From LVGL-micropython


from machine import RTC
import time



"""
Settings
"""

# Not implemented yet
DARK_MODE = False


""" Font """
# Default font
DEFAULT_FONT = lvgl.font_montserrat_42


# Custom font (leave empty if you want to use the default font)
#CUSTOM_FONT_FILENAME = ""
CUSTOM_FONT_FILENAME = "F:/ui/dejavu_mono_42.bin"





""" Message display """
# How long a message to the user should be displayed
MESSAGE_DISP_TIME = const(2000) # milliseconds





"""
Some checks regarding the font used for the time display :
- Whether the specified custom font file can be found (will default to the default font otherwise)
- Whether the font used (default or custom) is monospaced
"""
if CUSTOM_FONT_FILENAME:
    try:
        new_driver = lvgl.fs_drv_t()
        fs_driver.fs_register(new_driver, 'F')
        FONT = lvgl.binfont_create(CUSTOM_FONT_FILENAME)
    except:
        print('Warning : (Clock App) Custom font not found. Using default font instead')
        FONT = DEFAULT_FONT
else:
    FONT = DEFAULT_FONT
    print('(Clock App) Using default font')
    
# Determine if the font is monospaced or not (at least for the numbers and the colon)

# First, we get the width of each glyph
glyph_width_list = []

for c in range(48,59): # 48-58 is ASCII (decimal) for 0-9 and ':'
    glyph_width_list.append(FONT.get_glyph_width(c, 0))
    
# Then we test to see if they are all the same width
is_monospaced = True

for width in glyph_width_list:
    if width != glyph_width_list[0]:
        is_monospaced = False
        print('Warning : (Clock App) Font used for the time display is not monospaced. Numbers might move around. Consider using a monospaced font instead (see README for more info).')
        break



"""
Clock states
"""


# The clock uses a small state machine to handle different states
# (what we are currently doing) and which page to show : displaying
# the time, displaying a message and in the various settings menus.
# We are using states to remember where we're at between different
# calls to `run_foreground()`.

# We don't have enums, so some simple constants will do

ST_MESSAGE = const(1) #Showing a message, temporary state
ST_TIME_DISPLAY = const(2) # Displaying time
ST_SETTINGS_MENU = const(3) # In the settings menu
ST_SET_TIME_MAN = const(4) # Setting the time manually
ST_SET_DATE_MAN = const(5) # Setting the date manually
ST_SET_TIME_NTP = const(6) # Setting the time via NTP 



"""
Various strings
"""
weekday_names = ['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'] # Leave first element as '' for correct indexing
month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'] # Leave first element as '' for correct indexing





class Clock(BaseApp):
    """Clock App"""

    def __init__(self, name: str, badge):
        """ Define any attributes of the class in here, after super().__init__() is called.
            self.badge will be available in the rest of the class methods for accessing the badge hardware.
            If you don't have anything else to add, you can delete this method.
        """
        super().__init__(name, badge)
        # You can also set the sleep time when running in the foreground or background. Uncomment and update.
        # Remember to make background sleep longer so this app doesn't interrupt other processing.
        # self.foreground_sleep_ms = 10
        # self.background_sleep_ms = 1000


    def start(self):
        """ Register the app with the system.
            This is where to register any functions to be called when a message of that protocol is received.
            The app will start running in the background.
            If you don't have anything else to add, you can delete this method.
        """
        super().start()
        
        
        # Create the RTC object
        self.rtc = RTC()
        print(self.rtc.datetime())
        
        # Default state at startup
        self._state = ST_TIME_DISPLAY
        self._next_state = ST_TIME_DISPLAY
        
        
        # Display help at startup
        self._is_startup = True
        
        self._need_to_draw_state = True
        


        

    def run_foreground(self):
        """ Run one pass of the app's behavior when it is in the foreground (has keyboard input and control of the screen).
            You do not need to loop here, and the app will sleep for at least self.foreground_sleep_ms milliseconds between calls.
            Don't block in this function, for it will block reading the radio and keyboard.
            If the app only runs in the background, you can delete this method.
        """
        
        # Below is the state machine of the app with the different states
        
        
        # Displaying message for some amount of time
        if self._state == ST_MESSAGE:
            
            # Check to see if time's up and we need to change state
            if time.ticks_diff(self.message_end_time, time.ticks_ms())<0:
                self._state = self._next_state
                self._need_to_draw_state = True
            
            # If time's not up, do nothing
            # Note : we do not sleep in order to let the event scheduler do it's
            # thing with other apps
            else:
                pass
            
            
        
        
        # Displaying time
        if self._state == ST_TIME_DISPLAY:
            
            # # If we just arrived in this state, first we need to draw it
            if self._need_to_draw_state:
                self.draw_time_display()
                self._need_to_draw_state = False
            
            # Update the time
            self.update_time_display()
            
            # In case we want to switch to settings
            if self.badge.keyboard.f4():
                self._state = ST_SETTINGS_MENU
                self._need_to_draw_state = True
 


        # Currently in the settings menu
        if self._state == ST_SETTINGS_MENU:
            
            # If we just arrived in this state, first we need to draw it
            if self._need_to_draw_state:
                self.draw_settings_menu()
                self._need_to_draw_state = False
                
            # We want to set the time and date manually
            if self.badge.keyboard.f1():
                self._state = ST_SET_TIME_MAN
                self._need_to_draw_state = True
                
            # We want to set the time and date via ntp
            if self.badge.keyboard.f2():
                self._state = ST_SET_TIME_NTP
                self._need_to_draw_state = True
                
            # We want to go back to displaying time
            if self.badge.keyboard.f4():
                self._state = ST_TIME_DISPLAY
                self._need_to_draw_state = True
                
                
        # Settings time manually
        if self._state == ST_SET_TIME_MAN:
            
            # If we just arrived in this state, first we need to draw it 
            if self._need_to_draw_state:
                self.draw_settings_text_input(placeholder_text="Enter time as HH.MM.SS \n (Leave empty to skip)")
                self._need_to_draw_state = False
                
                
                
            # Some buttons are pressed
            key, text = self.settings_menu.text_box_type(self.badge.keyboard)
            
            # User pressed 'Enter'
            if self.badge.keyboard.f1():

                # Get the string input
                time_string = self.settings_menu.close_text_box()
                
                # Debugging
                print('Got:')
                print(time_string)
                
                # If the string is not empty, we need to parse/validate it, and then change the time
                if time_string:
                    valid_time, time_tuple = parse_time_string_input(time_string)
                    
                    if not valid_time:
                        self.show_message_and_change_state(message="Invalid time !", next_state=ST_SETTINGS_MENU, duration=MESSAGE_DISP_TIME)
                    else:
                        # Get the values from the input
                        hours,minutes,seconds = time_tuple
                        
                        # Get the time from the RTC and discard the parts that we want to change
                        (year, month, day, weekday, _, _, _, subseconds) = self.rtc.datetime()
                        # Set the new time
                        self.rtc.datetime((year, month, day, weekday, hours, minutes, seconds, subseconds))

                        # Message to tell the user it worked
 
                        self.show_message_and_change_state(message=f"Time set successfully to {hours:0>2}h{minutes:0>2}min{seconds:0>2}s " + lvgl.SYMBOL.OK, next_state=ST_SET_DATE_MAN, duration=MESSAGE_DISP_TIME)

                # If string is empty, the user wanted to skip this setting
                else:
                    # Message to tell the user we skipped setting the time
                    self.show_message_and_change_state(message="Skipped setting time " + lvgl.SYMBOL.OK, next_state=ST_SET_DATE_MAN, duration=MESSAGE_DISP_TIME)
            
            # Cancel 
            if self.badge.keyboard.f4():
                self.settings_menu = None # Delete the current graphics object
                self.show_message_and_change_state(message="Cancelled", next_state=ST_SETTINGS_MENU, duration=MESSAGE_DISP_TIME)
                

                    
        # Settings date manually
        if self._state == ST_SET_DATE_MAN:
            
            # If we just arrived in this state, first we need to draw it 
            if self._need_to_draw_state:
                self.draw_settings_text_input(placeholder_text="Enter date as yyyy/mm/dd \n(Leave empty to skip)")
                self._need_to_draw_state = False
                
                
                
            # Some buttons are pressed
            key, text = self.settings_menu.text_box_type(self.badge.keyboard)
            
            # User pressed 'Enter'
            if self.badge.keyboard.f1():
                
                # Get the string input
                date_string = self.settings_menu.close_text_box()
                
                # Debuging
                print('Got:')
                print(date_string)
                
                # If the string is not empty, we need to parse/validate it, and then change the date
                if date_string:
                    valid_date, date_tuple = parse_date_string_input(date_string)
                    
                    if not valid_date:
                        self.show_message_and_change_state(message="Invalid date !", next_state=ST_SETTINGS_MENU, duration=MESSAGE_DISP_TIME)
                    else:
                        # Get the values from the input
                        year,month,day,weekday = date_tuple
                        
                        # Get the time from the RTC and discard the parts that we want to change
                        (_, _, _, _, hours, minutes, seconds, subseconds) = self.rtc.datetime()
                        # Set the new time
                        self.rtc.datetime((year, month, day, weekday, hours, minutes, seconds, subseconds))
                        
                        weekday_str = weekday_names[weekday]

                        # Message to tell the user it worked
                        self.show_message_and_change_state(message=f"Date set successfully to {year}/{month:0>2}/{day:0>2}, {weekday_str} " + lvgl.SYMBOL.OK, next_state=ST_SETTINGS_MENU, duration=MESSAGE_DISP_TIME)
                
                # If the string is empty, the user wanted to skip this setting
                else:
                    # Message to tell the user we skipped setting the date
                    self.show_message_and_change_state(message="Skipped setting date " + lvgl.SYMBOL.OK, next_state=ST_SETTINGS_MENU, duration=MESSAGE_DISP_TIME)

                
                
            # Cancel 
            if self.badge.keyboard.f4():
                self.settings_menu = None # Delete the current graphics object
                self.show_message_and_change_state(message="Cancelled", next_state=ST_SETTINGS_MENU, duration=MESSAGE_DISP_TIME)
                
        
        # NOT IMPLEMENTED YET
        # Settings time and date via NTP
        if self._state == ST_SET_TIME_NTP:
            # Show a message to say that it's not implemented yet and go back to the menu
            self.show_message_and_change_state(message="NTP synch not implemented yet " + lvgl.SYMBOL.CLOSE, next_state=ST_SETTINGS_MENU, duration=MESSAGE_DISP_TIME)

 
        # Whether we're displaying time or in the settings, we want to be able to exit directly
        ## Co-op multitasking: all you have to do is get out
        if self.badge.keyboard.f5():
            self.badge.display.clear()
            self.switch_to_background()
        

    def run_background(self):
        """ App behavior when running in the background.
            You do not need to loop here, and the app will sleep for at least self.background_sleep_ms milliseconds between calls.
            Don't block in this function, for it will block reading the radio and keyboard.
            If the app only does things when running in the foreground, you can delete this method.
        """
        super().run_background()


    def switch_to_foreground(self):
        """ Set the app as the active foreground app.
            This will be called by the Menu when the app is selected.
            Any one-time logic to run when the app comes to the foreground (such as setting up the screen) should go here.
            If you don't have special transition logic, you can delete this method.
        """
        super().switch_to_foreground()


        # If it's the first time starting, we need do display the startup message/help
        if self._is_startup:
            self.show_message_and_change_state(message=" F4 = Settings \n F5 = Exit", next_state=ST_TIME_DISPLAY, duration=MESSAGE_DISP_TIME)
            self._is_startup = False
        
        # If not, we can just go to displaying time (we'll need to draw the display first, though)
        else:
            self._state = ST_TIME_DISPLAY
            self._need_to_draw_state = True



    def switch_to_background(self):
        """ Set the app as a background app.
            This will be called when the app is first started in the background and when it stops being in the foreground.
            If you don't have special transition logic, you can delete this method.
        """
        self.p = None
        self.time_display = None
        self.settings_menu = None
        self.message_display = None
        super().switch_to_background()
        
        
    def draw_time_display(self):
        self.badge.display.clear()
        
        # Some tests with background image
#         self.fullscreen = lvgl.obj(lvgl.screen_active()) 
#         self.fullscreen.add_style(styles.base_style, lvgl.STATE.DEFAULT)
#         self.fullscreen.set_width(lvgl.pct(100))
#         self.fullscreen.set_height(lvgl.pct(100))
#         graphics.create_image('rocket.png', self.fullscreen)

        self.time_display = lvgl.label(self.badge.display.screen)
        self.time_display.set_text('00:00:00')
        self.time_display.set_style_text_font(FONT, 0)
        self.time_display.set_align(lvgl.ALIGN.CENTER)
        self.time_display.set_style_text_align(lvgl.TEXT_ALIGN.CENTER, 0)
#         self.time_display.set_style_bg_opa(lvgl.OPA.COVER, 0)  # Some tests with background image
        print('Drawing time display')
        
        
    def update_time_display(self):

        # Get the time from the RTC and update the time display
        datetime = self.rtc.datetime()
        (year, month, day, weekday, hours, minutes, seconds, subseconds) = datetime
        
        self.time_display.set_text(f'{hours:0>2}:{minutes:0>2}:{seconds:0>2}')
        
        
    def draw_settings_menu(self):
        self.badge.display.clear()
        self.settings_menu = lvgl.label(self.badge.display.screen)
        self.settings_menu.set_text(' F1 = Set time and date manually \n F2 = Use NTP \n F4 = Exit settings')
        self.settings_menu.set_align(lvgl.ALIGN.CENTER)
        
        
    def draw_settings_text_input(self, placeholder_text=""):
        self.badge.display.clear()
        self.settings_menu = Page()
        self.settings_menu.create_content()
        self.settings_menu.create_menubar(["Enter", " ", " ", "Cancel", ""])
        self.settings_menu.create_text_box(default_text="", one_line=False)
        line_height = self.settings_menu.text_box.get_style_text_font(0).get_line_height()
        self.settings_menu.text_box.set_height(line_height*2+20)
        self.settings_menu.text_box.set_style_text_align(lvgl.TEXT_ALIGN.CENTER, 0)
        self.settings_menu.text_box.set_placeholder_text(placeholder_text)
        self.settings_menu.replace_screen()
        
        
        
    def show_message_and_change_state(self, message, next_state=ST_TIME_DISPLAY, duration=1000):
        """
        Show a message for some duration.
        
        This function sets up the duration, the next state and calls draw_message for the
        drawing part.
        """
        
        # Set the time at which we should stop showing the message
        curr_time = time.ticks_ms()
        self.message_end_time = time.ticks_add(curr_time, MESSAGE_DISP_TIME)
        
        # For debugging
        # print((curr_time, self.message_end_time))  

        # Draw the message screen
        self.draw_message(message)
        
        # Set the correct states
        self._state = ST_MESSAGE
        self._next_state = next_state
        
        
        
    def draw_message(self, message=""):
        self.badge.display.clear()
        self.message_display = lvgl.label(self.badge.display.screen)
        self.message_display.set_text(message)
        self.message_display.set_style_text_font(lvgl.font_montserrat_14, 0)
        self.message_display.set_align(lvgl.ALIGN.CENTER)
        self.message_display.set_style_text_align(lvgl.TEXT_ALIGN.CENTER, 0)
        





"""
Time and date related functions
"""
def parse_time_string_input(time_string):
    """
    Parse (and validate) a time inputed as "hh.mm.ss"
    """
    
    parts = time_string.split('.')
    
    valid_time = True
    
    # Check if we're missing (eg. only hours and minutes, no seconds)
    if len(parts)!=3:
        valid_time = False
        
    # Correct number of parts
    else:
        # Convert the strings to ints
        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
        
        # Cannot convert to int (for example, if there are letters instead of numbers)
        except:
            valid_time = False
            
        # If we haven't tripped on the casting to int, continue the validation
        if valid_time:
            if hours<0 or hours>24:
                valid_time = False
            if minutes<0 or minutes>60:
                valid_time = False
            if seconds<0 or seconds>60:
                valid_time = False
    
    if not valid_time:
        return((False, (0,0,0)))
    else:
        return((True, (hours, minutes, seconds)))
    
    
    
    
def parse_date_string_input(date_string):
    """
    Parse (and validate) a value of time inputed as "yyyy/mm/dd"
    """
    parts = date_string.split('/')
    
    valid_date = True
    
     # Check if we're missing some stuff (eg. only years and months, no days)
    if len(parts)!=3:
        valid_date = False
    
    # Correct number of parts
    else:
        # Convert the strings to ints
        try:
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])
            
        # Cannot convert to int (for example, if there are letters instead of numbers)
        # (Sorry, no dates in hexadecimal ! ;) )
        except:
            valid_date = False
            
        # If we haven't tripped on the casting to int, continue the validation
        if valid_date: 
            # No checks for years
            
            # Months
            if month<1 or month>12:
                valid_date = False
            
            # Days
            if day<1 or day>31:
                valid_date = False
            
            # And now, for specific cases
            
            # Month with only 30 days 
            if (month in [4,6,9,11]) and day==31:
                valid_date = False
            
            # Oh, February !
            if month==2:
                if day>29:
                    valid_date = False
                if not(is_leap_year(year)) and day==29:
                    valid_date = False
            
            # Before the start of the Gregorian calendar (Friday 15th 1582), we might have problems
            # Should not be the case anyway, so just say the date is not valid ...
            if year<=1582:
                if month<=10:
                    if day<15:
                        valid_date = False
                    
    if not valid_date:
        return((False, (0,0,0,0)))
    
    else:
        # Before returning, if the date is valid, we need to compute the day of the week
        # This works slightly differently before the start of the Georgian calendar, that's
        # why we avoid it. (And the change is weird too ...)
        weekday = compute_weekday_from_date(year, month, day)
        
        # Finally return the date
        return((True, (year, month, day, weekday)))
    
        
def is_leap_year(year):
    """
    Only works for the gregorian calendar
    """
    return(((year % 4 == 0) and (year % 100 != 0)) or (year % 400 == 0))



def compute_weekday_from_date(year, month, day):
    """
    Uses Gauss's algorithm (see Wikipedia article for "Determination of the day of the week")
    """
    leap_year = is_leap_year(year)
    
    if leap_year:
        month_offset = (0,3,4,0,2,5,0,3,6,1,4,6)[month-1] # month-1 because Python indices start at 0, but months at 1
    else:
        month_offset = (0,3,3,6,1,4,6,2,5,0,3,5)[month-1]

    gauss_weekday = (day + month_offset + 5*((year-1)%4) + 4*((year-1)%100) + 6*((year-1)%400)) % 7
    
    # Gauss's algorithm returns 0 for Sunday, but we want 7
    if gauss_weekday==0:
        weekday = 7
    else:
        weekday = gauss_weekday

    return(weekday)
    

        