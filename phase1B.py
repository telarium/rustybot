from timeit import default_timer as timer
from pydispatch import dispatcher
from webserver import WebServer
import subprocess
import time
import random
import math

Web_Server = WebServer() # Webserver running on BBB for an HTML interface

try:
    import Adafruit_BBIO.GPIO as GPIO
    import Adafruit_BBIO.PWM as PWM
except:
    print "Could not import GPIO library!"

# Hardware Pin defines
# ---------------------------------------
Solenoid1_Pin = "P9_23"
Solenoid2_Pin = "P9_24"

StepperPin0 = "P9_11"
StepperPin1 = "P9_13"
StepperPin2 = "P9_15"
StepperPin3 = "P9_27"
pin_list = [StepperPin0,StepperPin1,StepperPin2,StepperPin3]

# all leds are setup on pwm pins, although not necessary since not all need to fade
LED_Brain_Activity_Pin = "P9_14"
LED_Eye1_Pin = "P9_21"
LED_Eye2_Pin = "P8_13"
LED4_Pin = "P9_16"
LED5_Pin = "P9_12"
LED_Monitor_R_Pin = "P9_22"
LED_Monitor_G_Pin = "P9_42"
LED_Monitor_B_Pin = "P8_19"

Pause_Switch_Pin = "P8_14" # switch for starting and stopping the program
Hall_Limit_Pin = "P8_16"
PIR_Pin = "P8_18"
# ---------------------------------------


# State variables
# ---------------------------------------
'''
   Bot states summary:
   Bot_State = 200  --- Bot is homing after boot up
   Bot_State = 204/205 --- Bot hit a limit switch during homing and reverses direction
   Bot_State = 210 --- Bot hit second limit switch and travels to center
   Bot_State = 1000 --- Bot is in normal action state
   Bot_State = 2000 --- Bot begins varied second pattern
   Bot_State = 2100 --- Bot is in begining of second pattern
   Bot_State = 2200 --- Bot is in pause of second pattern
   Bot_State = 2300 --- Bot is in final fast typing stage of second pattern
   Bot_State = 2400 --- Bot is facing screen and typing quickly
   Bot_State = 5000 --- Bot hit a limit switch during normal routine and needs to home
'''

Bot_State = 200 # variable for current Bot State
Exit_State = False # flag for state transitions
State_Timer = 0 # timer for how long a state is active
# ---------------------------------------


# General program variables
# ---------------------------------------
Program_Paused_Button = False # Start Stop button for whole program. Acts like a global pause.
Program_Paused_Software = False # Start Stop from a software interface. Also acts as global pause.
PIR_Paused = False # paused if no motion is detected

PIR_Trigger = False # motion detection
Limit_Hit = False # Limit switch for head
Now_time = 0 # variable for current program time in milliseconds
PIR_Max_Time = 180 # seconds 
PIR_time = timer()
Homing_Needed = True # if a limit switch is hit then at the next resting state the bot will re-home
Debug_Print_Timer = 0 # seconds tracker for debug messages so as not to clog up program performance
Homing_Hit_Count = 0 # for debugging drift


# ---------------------------------------


# State duration variables, these can be changed to adjust how long a state lasts.
# ---------------------------------------
State1000_Duration = 5 # times in seconds (decimals are fine), State 1000 later gets random variation
State2000_Duration = 2
State2100_Duration = 3
State2200_Duration = 7
State2300_Duration = 4
State2400_Duration = 4

# min and max for random variation of state 1000 time
State1000_Min_Duration = 5 # seconds
State1000_Max_Duration = 10
# ---------------------------------------

# Variables for LED eye Blinking
# ---------------------------------------
Blink_Init_Delay = 1.75 # delay on state 2200 before blink
Blink_Duration = 0.150 # how long a blink ON/OFF lasts for
Blink_Millis = 0 # timer for Blinking pattern
Blinking = False # flag to start counting blinks
Blink_Count = 0
Num_Blinks = 6 # number of blinks by bot at monitor (divide by 2 since on and off)
# ---------------------------------------


# LED variables
# ---------------------------------------
# _Bright vars are 0 - 255 pwm intensity values
LED_Brain_Activity_Bright = 0
LED_Eye1_Bright = 0
LED_Eye2_Bright = 0
LED4_Bright = 0
LED_Monitor_Bright = 0

Fade_Rate = 5 # larger value creates a more rapid fade, could set specific rates for leds
LED_Millis = 0
LED_Millis2 = 0
LED_Update_Time = 0.050
Incoming_Message_Blink_Time = 0.300 #0.100# equals ~5Hz flashing

Full_ON = 255
Full_OFF = 0
Dim_Val = 5 # tune this to correct dim level for monitor LED
# ---------------------------------------


# Solenoid typing variables
# ---------------------------------------
Solenoid1_ON = False
Solenoid2_ON = False
Right_Hand_Turn = True # flag for switching between hands for typing

# typing timing variables
Typing_Timer = 0 # timer variable for the solenoid typing strokes, in milliseconds
Keystroke_Time_Init = 0.150 # time in ms that solenoids will stay on for
Keystroke_Time =  Keystroke_Time_Init
Min_Type_Pause = 0.100 # used to prevent the pause time from being less than a tenth of a second, this can be edited
Pause_Time = 2.0 # initial pause time, this will be updated with random variation

# variables for effecting random typing
Sigma_Init = 0.750 # standard deviation in milliseconds for pause time on solenoid actuatation, a large value will create a wider range of randomness
Mean_Init = 1.0 # average time between keystrokes, shorter will create faster typing
Sigma = Sigma_Init
Mean = Mean_Init

Switch_Hand_Val = 10 # initial value, this is used to decide whether to alternate hands
# ---------------------------------------


#Stepper motor variables
# ---------------------------------------
Steps = 0 # variable for commanding the number of Steps for the motor to turn
Look_Left = True # change this to reverse the direction the head stepper motor spins during looks
Look_Right = not Look_Left
Stepper_Direction = Look_Left
Steps_Per_Rev = 4096 # number of Steps per 1 full revolution, beware documentation on cheap stepper motors often don't match actual step number
Step_Count = 0
Move_Steps = 0
Steps_In_Head_Range = 0 # this gets set to be the total steps found in the intended head range of motion
Head_Pos_Tracker = 0 # this is a variable that is used only for tracking the head position in debugging
Center_Head_Step = 0 # step value for center of motion range
Left_Head_Step = 0
Right_Head_Step = 0

# range, 0 - ~ 500 
Steps_From_Hall_To_Monitor_Look = 100 # increase/decrease this value to get the head to look farther/less far during the turn to look at the monitor
Send_Step_Command = False
Do_Stepper_Move = False
Stepper_Command_Timer = 0
Last_Stepper_Time = 0
Rand_Stepper_Timer = 5.0 # random delay between small stepper movements
# ---------------------------------------


def gpioSetup(pin,dir):
    try:
        if dir == "out":
            dir = GPIO.OUT
        else:
            dir = GPIO.IN

        GPIO.setup(pin,dir)
    except:
        pass

def gpioOutput(pin,val):
    try:
        if val == 0:
            val = GPIO.LOW
        else:
            val = GPIO.HIGH

        GPIO.output(pin,val)
    except:
        print "GPIO output: " + str(pin) + ", " + str(val)
        #print Bot_State
        pass

def gpioInput(pin):
    try:
        return GPIO.input(pin)
    except:
        return 0

def gpioCleanup():
    try:
        GPIO.cleanup()
    except:
        pass

def pwmSetup(pin,val):
    try:
        PWM.start(pin,val)
    except:
        pass

def pwmSetDutyCycle(channel,duty):
    try:
        PWM.set_duty_cycle(channel,duty)
    except:
        #print "PWM duty cycle: " + str(channel) + ", " + str(duty)
        pass

def pwmCleanup():
    try:
        PWM.cleanup()
    except:
        pass


# Hardware Pin modes setup
# ---------------------------------------
gpioSetup(Solenoid1_Pin, "out")
gpioSetup(Solenoid2_Pin, "out")

gpioSetup(StepperPin0, "out")
gpioSetup(StepperPin1, "out")
gpioSetup(StepperPin2, "out")
gpioSetup(StepperPin3, "out")

gpioSetup(LED5_Pin, "out")

# start all of the LED PWM pins at 0 and update their duty cycle later
pwmSetup(LED_Brain_Activity_Pin, 0)
pwmSetup(LED_Eye1_Pin, 0)
pwmSetup(LED_Eye2_Pin, 0)
pwmSetup(LED4_Pin, 0)
pwmSetup(LED_Monitor_R_Pin, 0)
pwmSetup(LED_Monitor_G_Pin, 0)
pwmSetup(LED_Monitor_B_Pin, 0)

gpioSetup(Pause_Switch_Pin, "in") # BBB has internal pull down resistors
gpioSetup(Hall_Limit_Pin, "in")
gpioSetup(PIR_Pin, "in") 
# ---------------------------------------

State1000_Duration = random.uniform(State1000_Min_Duration, State1000_Max_Duration) # random time between min and max


def Software_PauseToggle():
    global Program_Paused_Software
    Program_Paused_Software = not Program_Paused_Software

def Play_WAV(filename):
    subprocess.Popen("aplay " + filename, shell=True)

def LED_SetAll(on=0):
    print "Set all LED's: " + str(on)
    LED_Brain_Activity_Bright = Full_OFF
    LED_Eye1_Bright = Full_OFF
    LED_Eye2_Bright = Full_OFF
    LED4_Bright = Full_OFF
    LED_Monitor_Bright = Full_OFF

    if int(on) == 1:
        LED_Brain_Activity_Bright = threshold_led(LED_Brain_Activity_Bright)
        LED_Eye1_Bright = threshold_led(LED_Eye1_Bright)
        LED_Eye2_Bright = threshold_led(LED_Eye2_Bright)
        LED4_Bright = threshold_led(LED4_Bright)
        LED_Monitor_Bright = threshold_led(LED_Monitor_Bright)

    pwmSetDutyCycle(LED_Brain_Activity_Pin, LED_Brain_Activity_Bright)
    pwmSetDutyCycle(LED_Eye1_Pin, LED_Eye1_Bright)
    pwmSetDutyCycle(LED_Eye2_Pin, LED_Eye2_Bright)
    pwmSetDutyCycle(LED4_Pin, LED4_Bright)
    pwmSetDutyCycle(LED_Monitor_R_Pin, LED_Monitor_Bright) 
    pwmSetDutyCycle(LED_Monitor_G_Pin, LED_Monitor_Bright)
    pwmSetDutyCycle(LED_Monitor_B_Pin, LED_Monitor_Bright)

def WebCallback(functionName=None,arg1=None,arg2=None):
    args = "()"
    if arg1 and not arg2:
        args = "('"+str(arg1)+"')"
    elif arg1 and arg2:
        args = "('"+str(arg1)+"','"+str(arg2)+"')"
    exec functionName+args

dispatcher.connect( WebCallback,  signal="call_function", sender=dispatcher.Any )

'''
   Stepper motor function, non-blocking
'''
def Stepper_Command(Steps, direction, pins):
    if Steps == 0:
        gpioOutput(StepperPin0, 0)
        gpioOutput(StepperPin1, 0)
        gpioOutput(StepperPin2, 0)
        gpioOutput(StepperPin3, 1)
    elif Steps == 1:
        gpioOutput(StepperPin0, 0)
        gpioOutput(StepperPin1, 0)
        gpioOutput(StepperPin2, 1)
        gpioOutput(StepperPin3, 1)
    elif Steps == 2:
        gpioOutput(StepperPin0, 0)
        gpioOutput(StepperPin1, 0)
        gpioOutput(StepperPin2, 1)
        gpioOutput(StepperPin3, 0)
    elif Steps == 3:
        gpioOutput(StepperPin0, 0)
        gpioOutput(StepperPin1, 1)
        gpioOutput(StepperPin2, 1)
        gpioOutput(StepperPin3, 0)
    elif Steps == 4:
        gpioOutput(StepperPin0, 0)
        gpioOutput(StepperPin1, 1)
        gpioOutput(StepperPin2, 0)
        gpioOutput(StepperPin3, 0)
    elif Steps == 5:
        gpioOutput(StepperPin0, 1)
        gpioOutput(StepperPin1, 1)
        gpioOutput(StepperPin2, 0)
        gpioOutput(StepperPin3, 0)
    elif Steps == 6:
        gpioOutput(StepperPin0, 1)
        gpioOutput(StepperPin1, 0)
        gpioOutput(StepperPin2, 0)
        gpioOutput(StepperPin3, 0)
    elif Steps == 7:
        gpioOutput(StepperPin0, 1)
        gpioOutput(StepperPin1, 0)
        gpioOutput(StepperPin2, 0)
        gpioOutput(StepperPin3, 1)
    else:
        gpioOutput(StepperPin0, 0)
        gpioOutput(StepperPin1, 0)
        gpioOutput(StepperPin2, 0)
        gpioOutput(StepperPin3, 0)

    if direction:
        Steps += 1
    else:
        Steps -= 1

    if Steps > 7: Steps = 0
    if Steps < 0: Steps = 7
    return Steps
'''
   End of, Stepper motor function, non-blocking
'''

'''
Threshold led function
'''
def threshold_led(in_val):
    if in_val > 100: in_val = 100
    elif in_val < 0: in_val = 0
##    in_val = in_val/255 * 100 # scales to 0-100 range
    return in_val
'''
End of Threshold led function
'''

'''
    Function for generating random gaussian numbers given a standard deviation and Mean
    using the Box-Muller method.
'''
def box_muller(Sigma, Mean):
    while True: 
        x1 = 2.0 * random.uniform(0, 99) / 100 - 1.0
        x2 = 2.0 * random.uniform(0, 99) / 100 - 1.0
        w = x1 * x1 + x2 * x2
        if w < 1.0: break

    w = math.sqrt( (-2.0 * math.log( w ) ) / w )
    y1 = x1 * w
    y2 = x2 * w
    return ( Mean + y1 * Sigma )
'''
    End of, Function for generating random gaussian numbers given a standard deviation and Mean
    using the Box-Muller method.
'''

try:
    while True:
        pause = False
        Now_time = timer() # update program time keeper

        # debug printing once/second
##        if Now_time - Debug_Print_Timer >= 1:
##            Debug_Print_Timer = Now_time
##            print("Head position: ",Head_Pos_Tracker)
        
        if Program_Paused_Software == True:
            pause = True
        else:
            Program_Paused_Button = gpioInput(Pause_Switch_Pin) # check state of program ON OFF switch
            pause = Program_Paused_Button

        PIR_Trigger = gpioInput(PIR_Pin)
        Limit_Hit = not gpioInput(Hall_Limit_Pin) # normally high switch
        if Bot_State > 500 and Bot_State < 5000 and Limit_Hit:
            Homing_Needed = True
            Bot_State = 5000
            Homing_Hit_Count += 1
                        
        elif Bot_State == 5000 and Limit_Hit: # this state backs the head off of whatever limit it hit
            Stepper_Direction = not Stepper_Direction
            if Send_Step_Command:
                Steps =  Stepper_Command(Steps, Stepper_Direction, pin_list)
                if not Stepper_Direction: Head_Pos_Tracker += 1
                else: Head_Pos_Tracker -= 1
                Send_Step_Command = False
        elif Bot_State == 5000 and not Limit_Hit:
            Bot_State = 200 # homing routine

        time.sleep(0.001)

        if not pause:
            
            if PIR_Trigger:
                PIR_time = Now_time
                PIR_Paused = False
            if Now_time - PIR_time > PIR_Max_Time:
                PIR_Paused = True
            elif Now_time - PIR_time > PIR_Max_Time*0.9:
                print(int(PIR_Max_Time - (Now_time - PIR_time))," secs till pause...")

            if not PIR_Paused:
                # State transitions
                # ---------------------------------------
                if Exit_State:
                    Exit_State = False
                    if Bot_State == 1000:
                        Bot_State = 2000
                        State1000_Duration = random.uniform(State1000_Min_Duration, State1000_Max_Duration) # generate new random state 1 duration

                    elif Bot_State == 2000: Bot_State = 2100
                    elif Bot_State == 2100: Bot_State = 2200
                    elif Bot_State == 2200: Bot_State = 2300
                    elif Bot_State == 2300: Bot_State = 2400
                    elif Bot_State == 2400: Bot_State = 1000
                    print("Entering state: ")
                    print(Bot_State)
                    Step_Count = 0
                
                # this chunk can be condensed
                if Bot_State == 1000 and Now_time - State_Timer > State1000_Duration and not Do_Stepper_Move:
                    State_Timer = Now_time
                    Exit_State = True

                elif Bot_State == 2000 and Now_time - State_Timer > State2000_Duration: 
                    State_Timer = Now_time
                    Exit_State = True

                elif Bot_State == 2100 and Now_time - State_Timer > State2100_Duration and not Do_Stepper_Move: 
                    State_Timer = Now_time
                    Exit_State = True

                elif Bot_State == 2200 and Now_time - State_Timer > State2200_Duration:
                    State_Timer = Now_time
                    Exit_State = True

                    Blinking = False # reset on state exit
                    Blink_Count = 0 # reset on state exit

                    if Head_Pos_Tracker < Center_Head_Step: Count_Up = True
                    elif Head_Pos_Tracker > Center_Head_Step: Count_Up = False
                    else: print("Unexpected head position.")

                elif Bot_State == 2300 and Now_time - State_Timer > State2300_Duration and not Do_Stepper_Move: 
                    State_Timer = Now_time
                    Exit_State = True

                elif Bot_State == 2400 and Now_time - State_Timer > State2400_Duration: 
                    State_Timer = Now_time
                    Exit_State = True

                if Bot_State == 1000 and Homing_Needed:
                    Bot_State = 200
                    State_Timer = Now_time
                    Exit_State = True

                # End of State Transitions
                # ---------------------------------------

                # Homing Sequence
                # ---------------------------------------
                # there is an uncovered case here that may need to be addressed, that is if the program boots
                # with the head not between the two limit switches or sitting on the right limit switch
                if Bot_State == 200 and Homing_Needed:
                    Homing_Needed = False
                    print("Homing routine in progress...")
                if Bot_State == 200 and not Limit_Hit: # Go left till hall triggers
                    Stepper_Direction = Look_Left
                    if Send_Step_Command:
                        Steps =  Stepper_Command(Steps, Stepper_Direction, pin_list)
                        if not Stepper_Direction: Head_Pos_Tracker += 1
                        else: Head_Pos_Tracker -= 1
                        Send_Step_Command = False
                elif Bot_State == 200 and Limit_Hit:
                    Head_Pos_Tracker = 0 # resetting the global position tracker meaning left is 0 position
                    Step_Count = 0 # this could solve the head angle drift issue
                    Bot_State = 205 # Move off limit magnet
                    print("Hit limit switch")
                elif Bot_State == 205 and Limit_Hit: # Move off limit magnet
                    Stepper_Direction = Look_Right
                    if Send_Step_Command:
                        Steps =  Stepper_Command(Steps, Stepper_Direction, pin_list)
                        if not Stepper_Direction: Head_Pos_Tracker += 1
                        else: Head_Pos_Tracker -= 1
                        Send_Step_Command = False
                        Step_Count += 1 
                elif Bot_State == 205 and not Limit_Hit: # cleared hall effect limit magnet
                    Bot_State = 206
                elif Bot_State == 206 and not Limit_Hit: # moving towards next hall limit switch
                    Stepper_Direction = Look_Right
                    if Send_Step_Command:
                        Steps =  Stepper_Command(Steps, Stepper_Direction, pin_list)
                        if not Stepper_Direction: Head_Pos_Tracker += 1
                        else: Head_Pos_Tracker -= 1
                        Send_Step_Command = False
                        Step_Count += 1
                elif Bot_State == 206 and Limit_Hit:
                    Bot_State = 210
                    Move_Steps = Step_Count/2
                    Center_Head_Step = Step_Count/2 # step value for center of motion range
                    Steps_In_Head_Range = Step_Count
                    print("Steps in head range: ", Steps_In_Head_Range) # should note if this changes 
                    Step_Count = 0
                    print("Hit limit switch 2")
                elif Bot_State == 210:
                    Stepper_Direction = Look_Left
                    if Send_Step_Command and Step_Count < Move_Steps:
                        Steps =  Stepper_Command(Steps, Stepper_Direction, pin_list)
                        if not Stepper_Direction: Head_Pos_Tracker += 1
                        else: Head_Pos_Tracker -= 1
                        Send_Step_Command = False
                        Step_Count += 1
                    elif Step_Count >= Move_Steps:
                        Bot_State = 1000
                        print("Bot successfully homed and centered")
                # End of Homing Sequence
                # ---------------------------------------

                # Solenoid timing ---- always running but solenoid outputs are disabled/enabled in the following program section
                # ---------------------------------------
                if not Solenoid1_ON and not Solenoid2_ON:
                    if Now_time - Typing_Timer >= Pause_Time: 
                        Typing_Timer = Now_time # reset typing timer
                        if Right_Hand_Turn:
                            Solenoid1_ON = True
                            Right_Hand_Turn = False

                        elif not Right_Hand_Turn: 
                            Solenoid2_ON = True
                            Right_Hand_Turn = True
                    
                
                elif Solenoid1_ON or Solenoid2_ON:

                    if Bot_State >= 2000 and Bot_State < 3000:  # fast typing state
                        Keystroke_Time =  Keystroke_Time_Init / 2
                        Sigma = Sigma_Init / 2
                        Mean = Mean_Init / 3
                    
                    else:
                        Keystroke_Time =  Keystroke_Time_Init
                        Sigma = Sigma_Init
                        Mean = Mean_Init
                        
                    if Now_time -  Typing_Timer > Keystroke_Time:
                        Typing_Timer = Now_time # reset typing timer
                        Solenoid1_ON = False
                        Solenoid2_ON = False

                        # at the end of each stroke calculate a new pause time
                        Pause_Time = box_muller(Sigma, Mean)
                        if Pause_Time <= Min_Type_Pause: Pause_Time = Min_Type_Pause# don't allow the pause time to be less than the min, this could be edited

                        # at the end of each stroke decide based on probability if the same hand should type again
                        Switch_Hand_Val = random.uniform(0, 10)
                        if  Switch_Hand_Val <= 2.5: Right_Hand_Turn = not Right_Hand_Turn
                  
                
                # End of Solenoid timing
                # ---------------------------------------


                # Solenoid outputs enable/disable based on state
                # ---------------------------------------
                if (Bot_State >= 2000 and Bot_State < 2300) or Bot_State < 500: 
                    Solenoid1_ON = False
                    Solenoid2_ON = False

    ##            print("RHT: ", Right_Hand_Turn," Sol1: ", Solenoid1_ON," Sol2: ",Solenoid2_ON)
                if Solenoid1_ON: gpioOutput(Solenoid1_Pin, 1)
                else: gpioOutput(Solenoid1_Pin, 0)
                
                if Solenoid2_ON: gpioOutput(Solenoid2_Pin, 1)
                else: gpioOutput(Solenoid2_Pin, 0)
                    
                
                # End of Solenoid outputs enable/disable based on state
                # ---------------------------------------


                # LED handling
                # ---------------------------------------

                # Brain Activity Monitor LED always fades in and out
                if Now_time - LED_Millis2 >= LED_Update_Time:
                    LED_Millis2 = Now_time
                    if LED_Brain_Activity_Bright >= 100 and Fade_Rate > 0: Fade_Rate = -Fade_Rate
                    elif LED_Brain_Activity_Bright <= 0 and Fade_Rate < 0: Fade_Rate = -Fade_Rate
                    LED_Brain_Activity_Bright += Fade_Rate
                
                if Bot_State == 1000: 
                    LED_Eye1_Bright = Full_ON
                    LED_Eye2_Bright = Full_ON
                    LED4_Bright = Full_ON
                    LED_Monitor_Bright = Full_OFF
                
                else:
                    LED4_Bright = Full_ON
                

                if Bot_State >= 2000 and Bot_State < 2200:  # LED monitor rapid Blinking for incoming message
                    if Now_time - LED_Millis >= Incoming_Message_Blink_Time: 
                        LED_Millis = Now_time
                        if LED_Monitor_Bright >= Full_ON: LED_Monitor_Bright = Full_OFF
                        elif LED_Monitor_Bright <= Full_OFF: LED_Monitor_Bright = Full_ON
                  
                
                elif Bot_State == 2200:  # LED monitor fading in and out
                    if Now_time - LED_Millis >=  LED_Update_Time: 
                        LED_Millis = Now_time
                        if LED_Monitor_Bright >= 100 and Fade_Rate > 0: Fade_Rate = -Fade_Rate
                        elif LED_Monitor_Bright <= Dim_Val and Fade_Rate < 0: Fade_Rate = -Fade_Rate
                        LED_Monitor_Bright += 2 * Fade_Rate
                  
                    if Now_time - Blink_Millis >= Blink_Init_Delay and not Blinking: 
                        Blink_Millis = Now_time
                        Blinking = True
                  
                    if Blinking and Blink_Count <= Num_Blinks and Now_time - Blink_Millis >= Blink_Duration: 
                        Blink_Millis = Now_time
                        if LED_Eye1_Bright == Full_ON: 
                            LED_Eye1_Bright = Full_OFF
                            LED_Eye2_Bright = Full_OFF
                        else: 
                            LED_Eye1_Bright = Full_ON
                            LED_Eye2_Bright = Full_ON

                        Blink_Count += 1
                  
                    elif Blink_Count > Num_Blinks:  # so eyes always end ON even if number of blinks is odd
                        LED_Eye1_Bright = Full_ON
                        LED_Eye2_Bright = Full_ON
                  
                
                elif Bot_State >= 2300 and Bot_State < 3000:  # LED monitor goes dim
                    if Now_time - LED_Millis >= LED_Update_Time:
                        LED_Millis = Now_time
                        if LED_Monitor_Bright > Dim_Val: LED_Monitor_Bright -= abs(Fade_Rate)
                  
                    LED_Eye1_Bright = Full_ON
                    LED_Eye2_Bright = Full_ON
                
                # End of LED handling
                # ---------------------------------------


                # Stepper handling
                # ---------------------------------------
                #LowRPM = 1
                #HighRPM = 15
                #Speed = 15 # tracks from 0 - 100 speed
                # can switch to micros to get a bit faster than the current 1 ms which is ~ 15 RPM
                if Now_time - Stepper_Command_Timer >= 0.005:
                    Stepper_Command_Timer = Now_time
                    Send_Step_Command = True
                

##                if Bot_State == 1000:
##                    if Now_time - Last_Stepper_Time > Rand_Stepper_Timer and not Do_Stepper_Move: 
##                        Last_Stepper_Time = Now_time
##                        Do_Stepper_Move = True
##                        if random.uniform(0, 10) > 5: Stepper_Direction = Look_Right
##                        else: Stepper_Direction = Look_Left
##                        Move_Steps = random.uniform(10, 150)
##                        Rand_Stepper_Timer = random.uniform(4, 10) # time in seconds 
##                  
##                    if Step_Count >= Move_Steps * 2 or Limit_Hit:
##                        Step_Count = 0
##                        Do_Stepper_Move = False # finished move
##
##                    elif Step_Count < Move_Steps * 2 and Send_Step_Command and Do_Stepper_Move: 
##                        if Step_Count == Move_Steps: Stepper_Direction = not Stepper_Direction
##                        Steps =  Stepper_Command(Steps, Stepper_Direction, pin_list)
##                        if not Stepper_Direction: Head_Pos_Tracker += 1
##                        else: Head_Pos_Tracker -= 1
##                        Send_Step_Command = False
##                        Step_Count += 1

                
                if Bot_State == 2100:
                    if not Do_Stepper_Move: # set it once when entering the state 
                        Move_Steps = Steps_In_Head_Range - Head_Pos_Tracker - Steps_From_Hall_To_Monitor_Look
                        print(Steps_In_Head_Range, Head_Pos_Tracker, Steps_From_Hall_To_Monitor_Look, Move_Steps) 
                    Do_Stepper_Move = True
                    Stepper_Direction = Look_Left

                    print("move steps:",Move_Steps," Step_Count:",Step_Count)
                    if Step_Count >= Move_Steps or Limit_Hit: 
                        Do_Stepper_Move = False
                        Exit_State = True # change state
                    elif Step_Count < Move_Steps and Send_Step_Command and Do_Stepper_Move: 
                        Steps =  Stepper_Command(Steps, Stepper_Direction, pin_list)
                        if not Stepper_Direction: Head_Pos_Tracker += 1
                        else: Head_Pos_Tracker -= 1
                        Send_Step_Command = False
                        Step_Count += 1
                  

                elif Bot_State == 2300: 
                    Do_Stepper_Move = True
                    Stepper_Direction = Look_Right
##                    print(Head_Pos_Tracker,Center_Head_Step, Step_Count,Move_Steps)
                    if Count_Up:
                        if Head_Pos_Tracker >= Center_Head_Step or Limit_Hit:
                            Do_Stepper_Move = False
                        elif Head_Pos_Tracker < Center_Head_Step and Send_Step_Command and Do_Stepper_Move: 
                            Steps =  Stepper_Command(Steps, Stepper_Direction, pin_list)
                            if not Stepper_Direction: Head_Pos_Tracker += 1
                            else: Head_Pos_Tracker -= 1
                            Send_Step_Command = False
                            Step_Count += 1
                    elif not Count_Up:
                        if Head_Pos_Tracker <= Center_Head_Step or Limit_Hit:
                            Do_Stepper_Move = False
                        elif Head_Pos_Tracker > Center_Head_Step and Send_Step_Command and Do_Stepper_Move: 
                            Steps =  Stepper_Command(Steps, Stepper_Direction, pin_list)
                            if not Stepper_Direction: Head_Pos_Tracker += 1
                            else: Head_Pos_Tracker -= 1
                            Send_Step_Command = False
                            Step_Count += 1
                    # old system. 
##                    if Step_Count >= Move_Steps or Limit_Hit: 
##                        Do_Stepper_Move = False
##                    elif Step_Count < Move_Steps and Send_Step_Command and Do_Stepper_Move: 
##                        Steps =  Stepper_Command(Steps, Stepper_Direction, pin_list)
##                        if not Stepper_Direction: Head_Pos_Tracker += 1
##                        else: Head_Pos_Tracker -= 1
##                        Send_Step_Command = False
##                        Step_Count += 1
                # End of Stepper handling
                # ---------------------------------------

      
        elif pause or PIR_Paused: # If program paused
            LED_Brain_Activity_Bright = Full_OFF
            LED_Eye1_Bright = Full_OFF
            LED_Eye2_Bright = Full_OFF
            LED4_Bright = Full_OFF
            LED_Monitor_Bright = Full_OFF

            print("program paused...")
      

        # thresholding LED vals for overshoot on 255 and 0
        # also adjusting to 0-100 scale for python IO library
        LED_Brain_Activity_Bright = threshold_led(LED_Brain_Activity_Bright)
        LED_Eye1_Bright = threshold_led(LED_Eye1_Bright)
        LED_Eye2_Bright = threshold_led(LED_Eye2_Bright)
        LED4_Bright = threshold_led(LED4_Bright)
        LED_Monitor_Bright = threshold_led(LED_Monitor_Bright)

        # writing LED outputs
        pwmSetDutyCycle(LED_Brain_Activity_Pin, LED_Brain_Activity_Bright)
        pwmSetDutyCycle(LED_Eye1_Pin, LED_Eye1_Bright)
        pwmSetDutyCycle(LED_Eye2_Pin, LED_Eye2_Bright)
        pwmSetDutyCycle(LED4_Pin, LED4_Bright)
        # using a single bright var for the monitor will default it to white
        # color variability should be added 
        pwmSetDutyCycle(LED_Monitor_R_Pin, LED_Monitor_Bright) 
        pwmSetDutyCycle(LED_Monitor_G_Pin, LED_Monitor_Bright)
        pwmSetDutyCycle(LED_Monitor_B_Pin, LED_Monitor_Bright)
except KeyboardInterrupt:
    print("interrupted by user keyboard")
    print("Limit switches hit: ",Homing_Hit_Count )
    gpioOutput(Solenoid1_Pin, 0)
    gpioOutput(Solenoid2_Pin, 0)


# turning off LEDs at program end
LED_Brain_Activity_Bright = Full_OFF
LED_Eye1_Bright = Full_OFF
LED_Eye2_Bright = Full_OFF
LED4_Bright = Full_OFF
LED_Monitor_Bright = Full_OFF
pwmSetDutyCycle(LED_Brain_Activity_Pin, LED_Brain_Activity_Bright)
pwmSetDutyCycle(LED_Eye1_Pin, LED_Eye1_Bright)
pwmSetDutyCycle(LED_Eye2_Pin, LED_Eye2_Bright)
pwmSetDutyCycle(LED4_Pin, LED4_Bright)
pwmSetDutyCycle(LED_Monitor_R_Pin, LED_Monitor_Bright) 
pwmSetDutyCycle(LED_Monitor_G_Pin, LED_Monitor_Bright)
pwmSetDutyCycle(LED_Monitor_B_Pin, LED_Monitor_Bright)
# GPIO cleanup on exit
pwmCleanup()
gpioCleanup()

Web_Server.shutdown()

