from Tkinter import *
import RPi.GPIO as GPIO
import time
import os
import datetime
import subprocess
from random import random

Nunits = 2

offangle = 100
onangle = 120

#pinouts
flash = [12,15]
camera = [13,16]
servo = [18,22]

GPIO.setwarnings(False) 
GPIO.setmode(GPIO.BOARD)
pwm = [0,0]

for unit in range(Nunits):
    GPIO.setup(flash[unit], GPIO.OUT) #GPIO 1 relay1
    GPIO.setup(camera[unit], GPIO.OUT) #GPIO 2 relay2
    GPIO.setup(servo[unit], GPIO.OUT) #GPIO 5 servo #1
    pwm[unit] = GPIO.PWM(servo[unit], 100)
    pwm[unit].start(5)
    
def setservo(unit,angle):
    duty = float(angle) / 10.0 + 2.5
    pwm[unit].ChangeDutyCycle(duty)
    
#to control the events on the system we don't use blocking delays any more
state = ['prep','prep'] #we start with wanting to wake up the camera
next_event_time = [0.0,0.0]

#before we start, make folder etc.
folder = "beeimages/" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
print "Making folder %s" % folder
if not os.path.exists(folder):
    os.makedirs(folder)
for unit in range(Nunits):
    unit_folder = folder+'/unit%d' % unit
    if not os.path.exists(unit_folder):
        os.makedirs(unit_folder)
        
def set_next_event(unit,new_state,delay):
    next_event_time[unit] = time.time() + delay
    state[unit] = new_state
   
for unit in range(Nunits):
    setservo(unit,offangle)
 
def upload_files(unit): #this just seems to grab the first camera (so we just need to make sure no more than one is plugged in at once)
    subfolder = "%s/unit%d/%05d" % (folder, unit, batch)
    print "Making subfolder %s" % subfolder
    if not os.path.exists(subfolder):
        os.makedirs(subfolder)
    oldpath = os.getcwd()
    os.chdir(subfolder)
    print "Getting files"
    res = subprocess.check_output('gphoto2 --get-all-files',shell=True)
    print res
    print "Deleting files"
    res = subprocess.check_output('gphoto2 --delete-all-files -R',shell=True)
    print res
  #  os.system('gphoto2 --get-all-files')
  #  os.system('gphoto2 --delete-all-files -R')
    os.chdir(oldpath)
    
#TODO Should have written this as seperate objects, rather than carrying around indices everywhere.
def run_events():
    #decide what to do next
    s = state[unit]
    #print "In %0.2fs: %s" % (next_event_time[unit] - time.time(), state[unit])
    print s
    if (s=='prep'):
        GPIO.output(flash[unit],True) 
        GPIO.output(camera[unit],True) 
        set_next_event(unit,'prep_servo_on',2.5)
        return
    if (s=='take_noflash'): #start no flash photo
        GPIO.output(flash[unit],True) #disconnect flash
        set_next_event(unit,'take_servo_on',0.5) 
        return
    if (s=='take_flash'): #start flash photo
        GPIO.output(flash[unit],False) #connect flash
        set_next_event(unit,'take_servo_on',0.5) 
        return
        
    if (s=='prep_servo_on'):
        setservo(unit,onangle)
        set_next_event(unit,'servo_off',2.5) 
        return
    if (s=='take_servo_on'):
        setservo(unit,onangle)
        set_next_event(unit,'servo_off',2.5) 
        return
        
    if (s=='servo_off'):
        setservo(unit,offangle)
        set_next_event(unit,'wait',3.0) #set to waiting
        return
    
    if (s=='wait_upload'):
        set_next_event(unit,'upload',5.0+random()*5)
        return
        
    if (s=='upload'):
        #check no other unit is in 'upload' state TODO RACE CONDITION
        if (state.count('upload')>1) or (state.count('do_transfer')>0):
            set_next_event(unit,'wait_upload',0) #we'll wait 5-10 seconds until they've finished.
        else:
            set_next_event(unit,'do_transfer',3.0)
            GPIO.output(camera[unit],False) #connect camera
        return
        
    if (s=='do_transfer'):
        upload_files(unit) #blocks!
        set_next_event(unit,'end_upload',1.0)
        return
        
    if (s=='end_upload'):
        GPIO.output(camera[unit],True) #disconnect camera
        set_next_event(unit,'done',2.5)
        return
        
    if (s=='wait'):
        setservo(unit,offangle)
        set_next_event(unit,'ready',0) #set to ready
        return
                
flash_photos_taken = [0,0]
no_flash_photos_taken = [0,0]
ready_for_upload = [False,False]
set_next_event(0,'prep',0)
set_next_event(1,'prep',1000)
batch=0
while (True):
    for unit in range(Nunits):
        if time.time()>next_event_time[unit]:
            run_events()

        if state[unit]=='ready':
            if no_flash_photos_taken[unit]<1:
                set_next_event(unit,'take_noflash',0)
                no_flash_photos_taken[unit]+=1
            else:
                if flash_photos_taken[unit]<4:
                    set_next_event(unit,'take_flash',0) 
                    flash_photos_taken[unit]+=1
                else:
                    set_next_event(unit,'upload',0)
        if state[unit]=='done':
            batch+=1
            set_next_event(unit,'prep',0)
            flash_photos_taken[unit] = 0
            no_flash_photos_taken[unit] = 0
    time.sleep(0.1)
   
